"""AI学习路由"""

import json
import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from uuid import uuid4

from app.common.time_utils import utc_now
from app.db.database import get_db
from app.deps import get_ai_analysis_llm_client as get_ai_analysis_llm, get_llm_client
from app.common.llm_client import LLMClient
from app.db.models import (
    KnowledgeUnitModel, ChapterModel, LearningRecordModel,
    MasteryRecordModel, BookModel, DailyStatsModel, AnnotationModel,
)

router = APIRouter(prefix="/api/v1/learning", tags=["learning"])

DEFAULT_USER_ID = "anonymous"

# 进度存储（内存中，TTL 清理防止泄漏）
_learning_progress: dict[str, dict] = {}
_PROGRESS_TTL = timedelta(hours=2)


def _cleanup_progress():
    """清理已完成超过 TTL 的进度条目"""
    now = utc_now()
    expired = [
        bid for bid, prog in _learning_progress.items()
        if prog.get("status") in ("completed", "error")
        and prog.get("updated_at")
        and now - datetime.fromisoformat(prog["updated_at"]) > _PROGRESS_TTL
    ]
    for bid in expired:
        del _learning_progress[bid]


class LearnRequest(BaseModel):
    unit_ids: Optional[List[str]] = None
    on_progress_url: Optional[str] = None
    force_relearn: bool = False  # 是否强制重新学习已学习的单元


class LearnSelectedRequest(BaseModel):
    chapter_ids: List[str]
    on_progress_url: Optional[str] = None


class StartSessionRequest(BaseModel):
    unit_id: str


class EndSessionRequest(BaseModel):
    performance_score: Optional[float] = None


class NoteRequest(BaseModel):
    content: str


class MarkRequest(BaseModel):
    mark: str


class EnrichRequest(BaseModel):
    """增量更新请求"""
    focus: Optional[str] = None  # 补充方向，如 "examples" / "explanations" / "connections"
    instruction: Optional[str] = None  # 自由文本补充指令


class RestoreRequest(BaseModel):
    """恢复请求（撤销增量更新用）"""
    summary: str
    explanation: str = ""
    key_points: List[dict]  # [{title, explanation, examples}]
    concepts: List[dict]
    difficulty_level: int = 3
    importance_score: float = 0.5
    prerequisites: List[str] = []


@router.get("/units/{unit_id}")
async def get_knowledge_unit(unit_id: str, db: AsyncSession = Depends(get_db)):
    """获取知识单元详情"""
    result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
    )
    unit = result.scalar_one_or_none()
    if unit is None:
        raise HTTPException(status_code=404, detail="知识单元不存在")
    return {
        "id": unit.id,
        "book_id": unit.book_id,
        "chapter_id": unit.chapter_id,
        "section_id": unit.section_id,
        "title": unit.title,
        "content": unit.content,
        "summary": unit.summary,
        "explanation": unit.explanation or "",
        "difficulty_level": unit.difficulty_level,
        "importance_score": unit.importance_score or 0.5,
        "concepts": json.loads(unit.concepts) if unit.concepts else [],
        "key_points": json.loads(unit.key_points) if unit.key_points else [],
    }


@router.post("/sessions")
async def start_learning_session(body: StartSessionRequest, db: AsyncSession = Depends(get_db)):
    """开始学习会话"""
    now = utc_now()
    record_id = str(uuid4())
    record = LearningRecordModel(
        id=record_id,
        user_id=DEFAULT_USER_ID,
        book_id="",
        session_id=record_id,  # session_id 与 id 保持一致
        started_at=now,
    )
    # 获取单元的 book_id
    result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == body.unit_id)
    )
    unit = result.scalar_one_or_none()
    if unit:
        record.book_id = unit.book_id

    db.add(record)
    await db.flush()
    return {
        "id": record.id,
        "user_id": record.user_id,
        "book_id": record.book_id,
        "session_id": record.session_id,
        "started_at": record.started_at,
        "ended_at": None,
        "duration_minutes": None,
        "units_covered": None,
        "questions_asked": 0,
        "test_score": None,
        "annotations_created": 0,
    }


@router.put("/sessions/{session_id}")
async def end_learning_session(session_id: str, body: EndSessionRequest, db: AsyncSession = Depends(get_db)):
    """结束学习会话"""
    result = await db.execute(
        select(LearningRecordModel).where(LearningRecordModel.id == session_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="学习记录不存在")

    now = utc_now()
    record.ended_at = now
    if record.started_at:
        try:
            record.duration_minutes = int((now - record.started_at).total_seconds() / 60)
        except Exception:
            pass

    if body.performance_score is not None:
        record.test_score = body.performance_score

    await db.flush()
    return {
        "id": record.id,
        "user_id": record.user_id,
        "book_id": record.book_id,
        "session_id": record.session_id,
        "started_at": record.started_at,
        "ended_at": record.ended_at,
        "duration_minutes": record.duration_minutes,
        "units_covered": record.units_covered,
        "questions_asked": record.questions_asked,
        "test_score": record.test_score,
        "annotations_created": record.annotations_created,
    }


@router.post("/units/{unit_id}/notes")
async def save_note(
    unit_id: str,
    body: NoteRequest,
    db: AsyncSession = Depends(get_db),
):
    """保存学习笔记"""
    unit_result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
    )
    unit = unit_result.scalar_one_or_none()
    if unit is None:
        raise HTTPException(status_code=404, detail="知识单元不存在")

    note_result = await db.execute(
        select(AnnotationModel).where(
            AnnotationModel.user_id == DEFAULT_USER_ID,
            AnnotationModel.knowledge_unit_id == unit_id,
            AnnotationModel.annotation_type == "note",
        )
    )
    note = note_result.scalar_one_or_none()
    if note:
        note.content = body.content
    else:
        db.add(AnnotationModel(
            user_id=DEFAULT_USER_ID,
            knowledge_unit_id=unit_id,
            annotation_type="note",
            content=body.content,
        ))

    await db.flush()
    return {"success": True, "message": "笔记已保存"}


@router.get("/units/{unit_id}/notes")
async def get_note(unit_id: str, db: AsyncSession = Depends(get_db)):
    """获取学习笔记"""
    note_result = await db.execute(
        select(AnnotationModel).where(
            AnnotationModel.user_id == DEFAULT_USER_ID,
            AnnotationModel.knowledge_unit_id == unit_id,
            AnnotationModel.annotation_type == "note",
        )
    )
    note = note_result.scalar_one_or_none()
    return {"unit_id": unit_id, "content": note.content if note else ""}


@router.post("/units/{unit_id}/mark")
async def mark_unit(
    unit_id: str,
    body: MarkRequest,
    db: AsyncSession = Depends(get_db),
):
    """标记知识单元（写入掌握度记录）"""
    # 验证单元存在
    result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
    )
    unit = result.scalar_one_or_none()
    if unit is None:
        raise HTTPException(status_code=404, detail="知识单元不存在")

    # 映射标记到掌握度分数和等级
    mark_mapping = {
        "mastered": (1.0, "mastered"),
        "proficient": (0.8, "proficient"),
        "familiar": (0.6, "familiar"),
        "beginner": (0.3, "beginner"),
        "needs_review": (0.2, "beginner"),
    }
    score, level = mark_mapping.get(body.mark, (0.5, "familiar"))

    # 查询是否已有掌握度记录
    mastery_result = await db.execute(
        select(MasteryRecordModel).where(
            MasteryRecordModel.user_id == DEFAULT_USER_ID,
            MasteryRecordModel.knowledge_unit_id == unit_id,
        )
    )
    mastery = mastery_result.scalar_one_or_none()

    if mastery:
        mastery.mastery_score = score
        mastery.mastery_level = level
        mastery.last_reviewed_at = utc_now()
    else:
        mastery = MasteryRecordModel(
            id=str(uuid4()),
            user_id=DEFAULT_USER_ID,
            knowledge_unit_id=unit_id,
            book_id=unit.book_id,
            mastery_score=score,
            mastery_level=level,
            last_reviewed_at=utc_now(),
            next_review_at=utc_now(),
        )
        db.add(mastery)

    await db.flush()
    return {"success": True, "mark": body.mark, "mastery_score": score}


@router.get("/stats")
async def get_learning_stats(db: AsyncSession = Depends(get_db)):
    """获取学习统计"""
    # 总学习天数
    days_result = await db.execute(
        select(func.count(func.distinct(DailyStatsModel.date)))
        .where(DailyStatsModel.user_id == DEFAULT_USER_ID)
    )
    total_days = days_result.scalar() or 0

    # 已完成单元数
    units_result = await db.execute(
        select(func.coalesce(func.sum(BookModel.learned_units), 0))
        .where(BookModel.user_id == DEFAULT_USER_ID)
    )
    completed_units = units_result.scalar() or 0

    # 今日学习时长
    today = utc_now().strftime("%Y-%m-%d")
    today_result = await db.execute(
        select(DailyStatsModel.total_minutes)
        .where(DailyStatsModel.user_id == DEFAULT_USER_ID, DailyStatsModel.date == today)
    )
    today_minutes = today_result.scalar() or 0

    # 连续学习天数
    from app.modules.user_storage.services.streak_service import StreakService
    streak_svc = StreakService(db)
    streak = await streak_svc.calculate_streak(DEFAULT_USER_ID)

    return {
        "total_days": total_days,
        "completed_units": completed_units,
        "mastery_distribution": {},
        "today_minutes": today_minutes,
        "streak_days": streak,
    }


@router.get("/report")
async def get_learning_report(period: str = "week", db: AsyncSession = Depends(get_db)):
    """获取学习报告"""
    from datetime import date as date_type, timedelta

    today = utc_now().date()

    # 根据周期计算起始日期
    if period == "week":
        start_date = today - timedelta(days=today.weekday())
    elif period == "month":
        start_date = today.replace(day=1)
    elif period == "year":
        start_date = today.replace(month=1, day=1)
    else:
        start_date = today - timedelta(days=7)

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = today.strftime("%Y-%m-%d")

    # 获取周期内的学习时长
    stats_result = await db.execute(
        select(
            func.coalesce(func.sum(DailyStatsModel.total_minutes), 0),
            func.coalesce(func.sum(DailyStatsModel.units_learned), 0),
        )
        .where(
            DailyStatsModel.user_id == DEFAULT_USER_ID,
            DailyStatsModel.date >= start_str,
            DailyStatsModel.date <= end_str,
        )
    )
    stats_row = stats_result.one()
    total_minutes = stats_row[0] or 0
    units_completed = stats_row[1] or 0

    # 获取掌握度分布
    mastery_result = await db.execute(
        select(MasteryRecordModel.mastery_level, func.count(MasteryRecordModel.id))
        .where(MasteryRecordModel.user_id == DEFAULT_USER_ID)
        .group_by(MasteryRecordModel.mastery_level)
    )
    mastery_distribution = {}
    for level, count in mastery_result.all():
        if level:
            level_label = {
                "mastered": "优秀",
                "proficient": "良好",
                "familiar": "一般",
                "beginner": "需加强",
            }.get(level, level)
            mastery_distribution[level_label] = count

    # 获取薄弱知识点（掌握度低的单元）
    weak_result = await db.execute(
        select(KnowledgeUnitModel.title)
        .join(MasteryRecordModel, MasteryRecordModel.knowledge_unit_id == KnowledgeUnitModel.id)
        .where(
            MasteryRecordModel.user_id == DEFAULT_USER_ID,
            MasteryRecordModel.mastery_score < 0.5,
        )
        .order_by(MasteryRecordModel.mastery_score.asc())
        .limit(5)
    )
    weak_points = [row[0] for row in weak_result.all()]

    # 生成学习建议
    suggestions = []
    if total_minutes == 0:
        suggestions.append("开始学习，即可生成个性化学习报告")
    else:
        if total_minutes < 60:
            suggestions.append("每天保持至少30分钟的学习时间")
        if weak_points:
            suggestions.append(f"重点复习薄弱知识点：{', '.join(weak_points[:3])}")
        if units_completed > 0:
            suggestions.append("继续保持学习节奏，定期复习巩固")

    # 集成教学统计
    from app.modules.teaching.service import TeachingService
    days = 7 if period == "week" else (30 if period == "month" else 365)
    try:
        teaching_llm = await get_llm_client("teaching")
        teaching_svc = TeachingService(llm_client=teaching_llm, db=db)
        teaching_stats = await teaching_svc.get_teaching_stats(days=days)
    except Exception:
        teaching_stats = {
            'total_sessions': 0,
            'total_minutes': 0,
            'questions_asked': 0,
            'avg_test_score': 0,
            'units_covered': 0,
        }

    return {
        "period": period,
        "total_minutes": total_minutes,
        "units_completed": units_completed,
        "mastery_distribution": mastery_distribution,
        "weak_points": weak_points,
        "suggestions": suggestions,
        "teaching_sessions": teaching_stats['total_sessions'],
        "teaching_minutes": teaching_stats['total_minutes'],
        "questions_asked": teaching_stats['questions_asked'],
        "avg_test_score": teaching_stats['avg_test_score'],
    }


@router.get("/{book_id}/learn-progress")
async def get_learning_progress_status(book_id: str):
    """获取 AI 学习进度"""
    progress = _learning_progress.get(book_id)
    if not progress:
        return {"status": "not_started", "current": 0, "total": 0, "message": ""}
    return progress


async def _run_learning_job(
    book_id: str,
    unit_ids: Optional[List[str]],
    force_relearn: bool,
    llm_client: LLMClient,
):
    """执行 AI 学习后台任务。"""
    from app.db.database import async_session_factory
    from app.modules.ai_learning.service import AILearningService
    from app.modules.knowledge_splitter.schemas import KnowledgeUnit, Chapter
    from sqlalchemy import update as sql_update
    import logging

    if async_session_factory is None:
        raise RuntimeError("数据库未初始化，请先调用 init_engine()")

    async with async_session_factory() as db:
        units_result = await db.execute(
            select(KnowledgeUnitModel)
            .where(KnowledgeUnitModel.book_id == book_id)
            .order_by(KnowledgeUnitModel.order_index)
        )
        db_units = units_result.scalars().all()
        chapters_result = await db.execute(
            select(ChapterModel).where(ChapterModel.book_id == book_id)
        )
        db_chapters = chapters_result.scalars().all()

        units = [
            KnowledgeUnit(
                id=u.id, book_id=u.book_id, chapter_id=u.chapter_id,
                title=u.title, content=u.content,
                order_index=u.order_index or 0,
                char_offset_start=u.char_offset_start or 0,
                char_offset_end=u.char_offset_end or 0,
                summary=u.summary,
                key_points=json.loads(u.key_points) if u.key_points else [],
            )
            for u in db_units
        ]
        chapters = [
            Chapter(
                id=c.id, book_id=c.book_id, title=c.title,
                chapter_number=c.chapter_number or 0,
                order_index=c.order_index or 0,
            )
            for c in db_chapters
        ]

        if unit_ids:
            units = [u for u in units if u.id in unit_ids]
            chapter_ids = {u.chapter_id for u in units}
            chapters = [c for c in chapters if c.id in chapter_ids]

        def on_progress(current: int, total: int, message: str):
            if current >= 0:
                _learning_progress[book_id] = {
                    "status": "in_progress",
                    "current": current,
                    "total": total,
                    "message": message,
                    "updated_at": utc_now().isoformat(),
                }
            else:
                _learning_progress[book_id]["message"] = message
                _learning_progress[book_id]["updated_at"] = utc_now().isoformat()

        try:
            service = AILearningService(llm_client=llm_client, db_session=db)
            result = await service.learn_book(
                book_id, units, chapters,
                on_progress=on_progress,
                force_relearn=force_relearn,
            )

            learned_count_result = await db.execute(
                select(func.count(KnowledgeUnitModel.id)).where(
                    KnowledgeUnitModel.book_id == book_id,
                    KnowledgeUnitModel.summary.isnot(None),
                    KnowledgeUnitModel.summary != "",
                )
            )
            actual_learned = learned_count_result.scalar() or 0
            await db.execute(
                sql_update(BookModel)
                .where(BookModel.id == book_id)
                .values(learned_units=actual_learned)
            )
            await db.commit()

            _learning_progress[book_id] = {
                "status": "completed",
                "current": result.total_units,
                "total": result.total_units,
                "message": f"学习完成！成功 {result.learned_count} 个，失败 {result.failed_count} 个",
                "updated_at": utc_now().isoformat(),
            }
        except Exception as e:
            await db.rollback()
            logging.getLogger(__name__).error(f"AI学习失败: {e}", exc_info=True)
            current = _learning_progress.get(book_id, {}).get("current", 0)
            _learning_progress[book_id] = {
                "status": "error",
                "current": current,
                "total": len(units),
                "message": "学习失败，请稍后重试",
                "updated_at": utc_now().isoformat(),
            }


@router.post("/{book_id}/learn", status_code=202)
async def start_learning(
    book_id: str,
    request: LearnRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    llm_client: LLMClient = Depends(get_ai_analysis_llm),
):
    """开始AI学习（整本书或指定单元）"""
    units_result = await db.execute(
        select(KnowledgeUnitModel.id)
        .where(KnowledgeUnitModel.book_id == book_id)
        .order_by(KnowledgeUnitModel.order_index)
    )
    unit_ids = [row[0] for row in units_result.all()]
    if not unit_ids:
        raise HTTPException(status_code=404, detail="书籍没有知识单元，请先上传并解析书籍")

    selected_unit_ids = request.unit_ids
    if selected_unit_ids:
        existing_ids = set(unit_ids)
        selected_unit_ids = [uid for uid in selected_unit_ids if uid in existing_ids]
        if not selected_unit_ids:
            raise HTTPException(status_code=404, detail="指定的知识单元不存在")

    total_units = len(selected_unit_ids) if selected_unit_ids else len(unit_ids)
    _cleanup_progress()
    _learning_progress[book_id] = {
        "status": "in_progress",
        "current": 0,
        "total": total_units,
        "message": "AI 学习任务已开始",
        "updated_at": utc_now().isoformat(),
    }

    background_tasks.add_task(
        _run_learning_job,
        book_id=book_id,
        unit_ids=selected_unit_ids,
        force_relearn=request.force_relearn,
        llm_client=llm_client,
    )

    return {
        "book_id": book_id,
        "status": "in_progress",
        "total_units": total_units,
        "message": "AI 学习任务已开始",
    }


@router.post("/{book_id}/learn-selected")
async def start_selected_learning(
    book_id: str,
    request: LearnSelectedRequest,
    db: AsyncSession = Depends(get_db),
    llm_client: LLMClient = Depends(get_ai_analysis_llm),
):
    """选择性学习"""
    from app.modules.ai_learning.service import SelectiveLearningService
    from app.modules.knowledge_splitter.schemas import KnowledgeUnit, Chapter

    units_result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id == book_id)
    )
    db_units = units_result.scalars().all()
    chapters_result = await db.execute(
        select(ChapterModel).where(ChapterModel.book_id == book_id)
    )
    db_chapters = chapters_result.scalars().all()

    units = [
        KnowledgeUnit(
            id=u.id, book_id=u.book_id, chapter_id=u.chapter_id,
            title=u.title, content=u.content,
            order_index=u.order_index or 0,
            char_offset_start=u.char_offset_start or 0,
            char_offset_end=u.char_offset_end or 0,
        )
        for u in db_units
    ]
    chapters = [
        Chapter(
            id=c.id, book_id=c.book_id, title=c.title,
            chapter_number=c.chapter_number or 0,
            order_index=c.order_index or 0,
        )
        for c in db_chapters
    ]

    service = SelectiveLearningService(llm_client=llm_client, db_session=db)
    result = await service.learn_selected(
        book_id, request.chapter_ids, units, chapters
    )

    # 更新书籍的 learned_units 统计
    from sqlalchemy import update as sql_update
    learned_count_result = await db.execute(
        select(func.count(KnowledgeUnitModel.id)).where(
            KnowledgeUnitModel.book_id == book_id,
            KnowledgeUnitModel.summary.isnot(None),
            KnowledgeUnitModel.summary != "",
        )
    )
    actual_learned = learned_count_result.scalar() or 0
    await db.execute(
        sql_update(BookModel)
        .where(BookModel.id == book_id)
        .values(learned_units=actual_learned)
    )
    await db.flush()

    return {
        "book_id": result.book_id,
        "total_units": result.total_units,
        "learned_count": result.learned_count,
        "failed_count": result.failed_count,
        "skipped_count": result.skipped_count,
        "total_token_cost": result.total_token_cost,
        "duration_seconds": round(result.duration_seconds, 2),
    }


@router.get("/{book_id}/progress")
async def get_progress(book_id: str, db: AsyncSession = Depends(get_db)):
    """获取学习进度"""
    # 总单元数
    total_result = await db.execute(
        select(func.count(KnowledgeUnitModel.id))
        .where(KnowledgeUnitModel.book_id == book_id)
    )
    total_units = total_result.scalar() or 0

    # 已学完的单元数（有 summary 且有 key_points 的，表示经过AI学习）
    learned_result = await db.execute(
        select(func.count(KnowledgeUnitModel.id))
        .where(
            KnowledgeUnitModel.book_id == book_id,
            KnowledgeUnitModel.summary.isnot(None),
            KnowledgeUnitModel.summary != "",
            KnowledgeUnitModel.key_points.isnot(None),
            KnowledgeUnitModel.key_points != "[]",
        )
    )
    learned_units = learned_result.scalar() or 0

    return {
        "book_id": book_id,
        "status": (
            "completed" if learned_units == total_units and total_units > 0
            else "in_progress" if learned_units > 0
            else "not_started"
        ),
        "total_units": total_units,
        "learned_units": learned_units,
        "progress_percent": round(learned_units / total_units * 100, 1) if total_units > 0 else 0,
    }


@router.get("/{book_id}/overview")
async def get_overview(book_id: str, db: AsyncSession = Depends(get_db)):
    """获取书籍概览"""
    from app.modules.knowledge_splitter.schemas import KnowledgeUnit, Chapter

    chapters_result = await db.execute(
        select(ChapterModel).where(ChapterModel.book_id == book_id)
    )
    db_chapters = chapters_result.scalars().all()
    units_result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id == book_id)
    )
    db_units = units_result.scalars().all()

    chapters = [
        Chapter(
            id=c.id, book_id=c.book_id, title=c.title,
            chapter_number=c.chapter_number or 0,
            order_index=c.order_index or 0,
        )
        for c in db_chapters
    ]
    units = [
        KnowledgeUnit(
            id=u.id, book_id=u.book_id, chapter_id=u.chapter_id,
            title=u.title, content=u.content,
            order_index=u.order_index or 0,
            char_offset_start=u.char_offset_start or 0,
            char_offset_end=u.char_offset_end or 0,
        )
        for u in db_units
    ]

    # 直接构造概览，无需 LLM client
    from app.modules.ai_learning.schemas import BookOverview, ChapterOverview

    chapter_overviews = []
    for chapter in chapters:
        chapter_units = [u for u in units if u.chapter_id == chapter.id]
        avg_difficulty = sum(
            u.difficulty_level or 3 for u in chapter_units
        ) / max(len(chapter_units), 1)
        chapter_overviews.append(
            ChapterOverview(
                chapter_id=chapter.id,
                title=chapter.title,
                key_concepts_preview=[],
                estimated_minutes=len(chapter_units) * 12,
                difficulty_level=round(avg_difficulty),
                unit_count=len(chapter_units),
            )
        )
    overview = BookOverview(
        book_id=book_id,
        title="",
        total_chapters=len(chapters),
        chapters=chapter_overviews,
    )

    return {
        "book_id": overview.book_id,
        "title": overview.title,
        "total_chapters": overview.total_chapters,
        "chapters": [
            {
                "chapter_id": ch.chapter_id,
                "title": ch.title,
                "unit_count": ch.unit_count,
                "estimated_minutes": ch.estimated_minutes,
                "difficulty_level": ch.difficulty_level,
            }
            for ch in overview.chapters
        ],
    }


@router.post("/units/{unit_id}/relearn")
async def relearn_unit(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
    llm_client: LLMClient = Depends(get_ai_analysis_llm),
):
    """重新生成指定知识单元的 AI 分析（覆盖旧结果）"""
    from app.modules.ai_learning.service import AILearningService
    from app.modules.knowledge_splitter.schemas import KnowledgeUnit

    result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
    )
    db_unit = result.scalar_one_or_none()
    if db_unit is None:
        raise HTTPException(status_code=404, detail="知识单元不存在")

    unit = KnowledgeUnit(
        id=db_unit.id, book_id=db_unit.book_id, chapter_id=db_unit.chapter_id,
        title=db_unit.title, content=db_unit.content,
        order_index=db_unit.order_index or 0,
        char_offset_start=db_unit.char_offset_start or 0,
        char_offset_end=db_unit.char_offset_end or 0,
    )

    service = AILearningService(llm_client=llm_client, db_session=db)
    learned = await service.relearn_unit(unit)

    return {
        "unit_id": learned.unit_id,
        "summary": learned.summary,
        "key_points": learned.key_points,
        "concepts": [{"name": c.name, "definition": c.definition} for c in learned.concepts],
        "difficulty_level": learned.difficulty_level,
        "token_cost": learned.token_cost,
    }


@router.put("/units/{unit_id}/enrich")
async def enrich_unit(
    unit_id: str,
    body: EnrichRequest,
    db: AsyncSession = Depends(get_db),
    llm_client: LLMClient = Depends(get_ai_analysis_llm),
):
    """增量更新指定知识单元（在原有基础上补充细节，不覆盖）"""
    from app.modules.ai_learning.service import AILearningService

    result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
    )
    db_unit = result.scalar_one_or_none()
    if db_unit is None:
        raise HTTPException(status_code=404, detail="知识单元不存在")

    service = AILearningService(llm_client=llm_client, db_session=db)
    learned = await service.enrich_unit(
        unit_id=unit_id,
        book_id=db_unit.book_id,
        chapter_id=db_unit.chapter_id,
        title=db_unit.title,
        content=db_unit.content,
        existing_summary=db_unit.summary or "",
        existing_key_points=json.loads(db_unit.key_points) if db_unit.key_points else [],
        existing_concepts=json.loads(db_unit.concepts) if db_unit.concepts else [],
        existing_explanation=db_unit.explanation or "",
        existing_difficulty_level=db_unit.difficulty_level or 3,
        existing_importance_score=db_unit.importance_score or 0.5,
        existing_prerequisites=json.loads(db_unit.prerequisites) if db_unit.prerequisites else [],
        focus=body.focus,
        instruction=body.instruction,
    )

    return {
        "unit_id": learned.unit_id,
        "summary": learned.summary,
        "explanation": learned.explanation,
        "key_points": learned.key_points,
        "concepts": [{"name": c.name, "definition": c.definition, "examples": c.examples} for c in learned.concepts],
        "difficulty_level": learned.difficulty_level,
        "token_cost": learned.token_cost,
    }


@router.post("/units/{unit_id}/restore")
async def restore_unit(
    unit_id: str,
    body: RestoreRequest,
    db: AsyncSession = Depends(get_db),
):
    """恢复知识单元到指定状态（撤销增量更新）"""
    result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
    )
    db_unit = result.scalar_one_or_none()
    if db_unit is None:
        raise HTTPException(status_code=404, detail="知识单元不存在")

    db_unit.summary = body.summary
    db_unit.explanation = body.explanation
    db_unit.key_points = json.dumps(body.key_points, ensure_ascii=False)
    db_unit.concepts = json.dumps(body.concepts, ensure_ascii=False)
    db_unit.difficulty_level = body.difficulty_level
    db_unit.importance_score = body.importance_score
    db_unit.prerequisites = json.dumps(body.prerequisites, ensure_ascii=False)

    await db.flush()
    return {"success": True, "unit_id": unit_id}
