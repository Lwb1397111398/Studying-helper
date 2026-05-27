"""AI学习路由"""

import json

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from uuid import uuid4

from app.db.database import get_db
from app.deps import get_llm_client
from app.common.llm_client import LLMClient
from app.db.models import (
    KnowledgeUnitModel, ChapterModel, LearningRecordModel,
    MasteryRecordModel, BookModel, DailyStatsModel,
)

router = APIRouter(prefix="/api/v1/learning", tags=["learning"])

DEFAULT_USER_ID = "anonymous"


class LearnRequest(BaseModel):
    unit_ids: Optional[List[str]] = None
    on_progress_url: Optional[str] = None


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        "difficulty_level": unit.difficulty_level,
        "concepts": json.loads(unit.concepts) if unit.concepts else [],
    }


@router.post("/sessions")
async def start_learning_session(body: StartSessionRequest, db: AsyncSession = Depends(get_db)):
    """开始学习会话"""
    now = _now_iso()
    record = LearningRecordModel(
        id=str(uuid4()),
        user_id=DEFAULT_USER_ID,
        book_id="",
        session_id=str(uuid4()),
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

    now = _now_iso()
    record.ended_at = now
    if record.started_at:
        try:
            start = datetime.fromisoformat(record.started_at)
            end = datetime.fromisoformat(now)
            record.duration_minutes = int((end - start).total_seconds() / 60)
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
async def save_note(unit_id: str, body: NoteRequest):
    """保存学习笔记（暂存内存，后续可持久化）"""
    return {"success": True}


@router.post("/units/{unit_id}/mark")
async def mark_unit(unit_id: str, body: MarkRequest):
    """标记知识单元（暂存内存）"""
    return {"success": True}


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
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_result = await db.execute(
        select(DailyStatsModel.total_minutes)
        .where(DailyStatsModel.user_id == DEFAULT_USER_ID, DailyStatsModel.date == today)
    )
    today_minutes = today_result.scalar() or 0

    # 连续学习天数
    from datetime import date as date_type, timedelta
    streak = 0
    check_date = datetime.now(timezone.utc).date()
    while True:
        date_str = check_date.strftime("%Y-%m-%d")
        r = await db.execute(
            select(DailyStatsModel)
            .where(DailyStatsModel.user_id == DEFAULT_USER_ID, DailyStatsModel.date == date_str)
        )
        stats = r.scalar_one_or_none()
        if stats is None or stats.total_minutes == 0:
            break
        streak += 1
        check_date = check_date - timedelta(days=1)

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
    return {
        "period": period,
        "total_minutes": 0,
        "units_completed": 0,
        "mastery_distribution": {},
        "weak_points": [],
        "suggestions": ["上传书籍并开始学习，即可生成个性化学习报告"],
    }


@router.post("/{book_id}/learn")
async def start_learning(
    book_id: str,
    request: LearnRequest,
    db: AsyncSession = Depends(get_db),
    llm_client: LLMClient = Depends(lambda: get_llm_client("ai_analysis")),
):
    """开始AI学习（整本书或指定单元）"""
    from app.modules.ai_learning.service import AILearningService
    from app.modules.knowledge_splitter.schemas import KnowledgeUnit, Chapter

    # 从 DB 加载知识单元和章节
    units_result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id == book_id)
    )
    db_units = units_result.scalars().all()
    if not db_units:
        raise HTTPException(status_code=404, detail="书籍没有知识单元，请先上传并解析书籍")

    chapters_result = await db.execute(
        select(ChapterModel).where(ChapterModel.book_id == book_id)
    )
    db_chapters = chapters_result.scalars().all()

    # 转为 schema 对象
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

    # 如果指定了 unit_ids，只学指定单元
    if request.unit_ids:
        units = [u for u in units if u.id in request.unit_ids]
        if not units:
            raise HTTPException(status_code=404, detail="指定的知识单元不存在")
        # 只保留涉及到的章节
        chapter_ids = {u.chapter_id for u in units}
        chapters = [c for c in chapters if c.id in chapter_ids]

    service = AILearningService(llm_client=llm_client, db_session=db)
    result = await service.learn_book(book_id, units, chapters)

    return {
        "book_id": result.book_id,
        "total_units": result.total_units,
        "learned_count": result.learned_count,
        "failed_count": result.failed_count,
        "skipped_count": result.skipped_count,
        "total_token_cost": result.total_token_cost,
        "duration_seconds": round(result.duration_seconds, 2),
    }


@router.post("/{book_id}/learn-selected")
async def start_selected_learning(
    book_id: str,
    request: LearnSelectedRequest,
    db: AsyncSession = Depends(get_db),
    llm_client: LLMClient = Depends(lambda: get_llm_client("ai_analysis")),
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

    # 已学完的单元数（有 summary 的）
    learned_result = await db.execute(
        select(func.count(KnowledgeUnitModel.id))
        .where(
            KnowledgeUnitModel.book_id == book_id,
            KnowledgeUnitModel.summary.isnot(None),
            KnowledgeUnitModel.summary != "",
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
    from app.modules.ai_learning.service import SelectiveLearningService
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

    # 不需要 LLM client 来生成概览
    service = SelectiveLearningService(llm_client=None, db_session=db)
    overview = service.get_book_overview(book_id, chapters, units)

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
    llm_client: LLMClient = Depends(lambda: get_llm_client("ai_analysis")),
):
    """重新生成指定知识单元的 AI 分析（覆盖旧结果）"""
    from app.modules.ai_learning.service import AILearningService
    from app.modules.knowledge_splitter.schemas import KnowledgeUnit, LearningContext

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
    llm_client: LLMClient = Depends(lambda: get_llm_client("ai_analysis")),
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
        focus=body.focus,
        instruction=body.instruction,
    )

    return {
        "unit_id": learned.unit_id,
        "summary": learned.summary,
        "key_points": learned.key_points,
        "concepts": [{"name": c.name, "definition": c.definition, "examples": c.examples} for c in learned.concepts],
        "difficulty_level": learned.difficulty_level,
        "token_cost": learned.token_cost,
    }
