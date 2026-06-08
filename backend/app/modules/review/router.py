"""复习引擎API路由"""

import json
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ServiceError, ErrorCode, ERROR_STATUS_MAP
from app.db.database import get_db
from app.db.models import KnowledgeUnitModel, MasteryRecordModel, ReviewSessionModel, KGEdgeModel
from app.modules.review.schemas import (
    ExamConfig, ExportFormat, MasteryRecord,
)
from app.modules.review.service import ReviewService
from app.modules.knowledge_splitter.schemas import KnowledgeUnit

router = APIRouter(prefix="/api/v1/review", tags=["review"])

DEFAULT_USER_ID = "anonymous"


def _get_service(db: AsyncSession) -> ReviewService:
    return ReviewService(db)


# ===== 请求模型 =====

class StartReviewRequest(BaseModel):
    book_id: str
    unit_ids: List[str] = []
    review_type: str = 'spaced'


class SubmitAnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str
    response_time: float = 0.0
    confidence_level: int = 0  # 信心等级 1-3（0=未提供）


class StartExamRequest(BaseModel):
    book_id: str
    chapter_ids: List[str]
    config: Optional[ExamConfig] = None


class SubmitExamRequest(BaseModel):
    session_id: str
    answers: Dict[str, str]


class ExportRequest(BaseModel):
    book_title: str
    format: ExportFormat
    chapters: List[Dict]
    knowledge_units: List[Dict]
    mastery_records: Dict[str, Dict]
    wrong_questions: Optional[List[Dict]] = None


# ===== 辅助：从 DB 加载知识单元 =====

async def _load_related_unit_ids(db: AsyncSession, book_id: str, unit_ids: List[str]) -> List[str]:
    """从知识图谱加载与指定单元关联的单元 ID（similar_to / contrasts_with）"""
    if not unit_ids:
        return []
    result = await db.execute(
        select(KGEdgeModel).where(
            KGEdgeModel.book_id == book_id,
            KGEdgeModel.relation_type.in_(["similar_to", "contrasts_with"]),
            (KGEdgeModel.source_id.in_(unit_ids)) | (KGEdgeModel.target_id.in_(unit_ids)),
        )
    )
    edges = result.scalars().all()
    related = set()
    for edge in edges:
        if edge.source_id in unit_ids:
            related.add(edge.target_id)
        if edge.target_id in unit_ids:
            related.add(edge.source_id)
    # 排除已在请求列表中的
    return list(related - set(unit_ids))

def _extract_strings(items: list) -> list:
    """从混合列表中提取字符串（兼容 key_points/concepts 的两种存储格式）"""
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append(item.get("title", item.get("name", str(item))))
        else:
            result.append(str(item))
    return result

async def _load_units(db: AsyncSession, book_id: str, unit_ids: List[str] = None) -> List[KnowledgeUnit]:
    if unit_ids:
        result = await db.execute(
            select(KnowledgeUnitModel)
            .where(KnowledgeUnitModel.id.in_(unit_ids))
        )
    else:
        result = await db.execute(
            select(KnowledgeUnitModel)
            .where(KnowledgeUnitModel.book_id == book_id)
            .limit(20)
        )
    db_units = list(result.scalars().all())
    return [
        KnowledgeUnit(
            id=u.id, book_id=u.book_id, chapter_id=u.chapter_id,
            section_id=u.section_id,
            title=u.title, content=u.content, order_index=u.order_index,
            char_offset_start=u.char_offset_start, char_offset_end=u.char_offset_end,
            summary=u.summary,
            key_points=_extract_strings(json.loads(u.key_points)) if u.key_points else None,
            concepts=_extract_strings(json.loads(u.concepts)) if u.concepts else None,
            difficulty_level=u.difficulty_level,
            importance_score=u.importance_score,
        )
        for u in db_units
    ]


async def _load_mastery_records(db: AsyncSession, user_id: str) -> List[MasteryRecord]:
    result = await db.execute(
        select(MasteryRecordModel).where(MasteryRecordModel.user_id == user_id)
    )
    rows = result.scalars().all()
    return [
        MasteryRecord(
            id=r.id, user_id=r.user_id, knowledge_unit_id=r.knowledge_unit_id,
            book_id=r.book_id or "",
            mastery_score=r.mastery_score, mastery_level=r.mastery_level,
            last_reviewed_at=r.last_reviewed_at, next_review_at=r.next_review_at,
            review_count=r.review_count, ease_factor=r.ease_factor,
            interval_days=r.interval_days,
        )
        for r in rows
    ]


# ===== 辅助：从 DB 加载答题历史 =====

async def _load_review_history(db: AsyncSession, user_id: str, unit_id: str) -> List[Dict]:
    """加载某用户某知识单元的答题历史"""
    result = await db.execute(
        select(ReviewSessionModel)
        .where(ReviewSessionModel.user_id == user_id)
        .order_by(ReviewSessionModel.started_at.desc())
        .limit(10)
    )
    sessions = result.scalars().all()
    history = []
    for sess in sessions:
        if not sess.questions_json:
            continue
        questions = json.loads(sess.questions_json)
        for q in questions:
            if q.get('unit_id') == unit_id and q.get('is_correct') is not None:
                history.append({
                    'is_correct': q['is_correct'],
                    'response_time': 30.0,
                    'score': 1.0 if q['is_correct'] else 0.0,
                })
    return history


# ===== API 端点 =====

@router.get("/due")
async def get_due_reviews(
    book_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = _get_service(db)
        records = await _load_mastery_records(db, DEFAULT_USER_ID)
        due = svc.get_due_reviews(DEFAULT_USER_ID, book_id, records)
        return [r.model_dump() for r in due]
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/start")
async def start_review(
    request: StartReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = _get_service(db)
        knowledge_units = await _load_units(db, request.book_id, request.unit_ids or [])
        unit_ids = [u.id for u in knowledge_units]

        # 加载关联单元（similar_to / contrasts_with）用于生成干扰项
        related_ids = await _load_related_unit_ids(db, request.book_id, unit_ids)
        if related_ids:
            related_units = await _load_units(db, request.book_id, related_ids)
            knowledge_units.extend(related_units)

        session = await svc.start_review(
            user_id=DEFAULT_USER_ID,
            book_id=request.book_id,
            unit_ids=unit_ids,
            knowledge_units=knowledge_units,
            review_type=request.review_type,
        )
        return session.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/answer")
async def submit_answer(
    request: SubmitAnswerRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = _get_service(db)
        feedback = await svc.submit_review_answer(
            session_id=request.session_id,
            question_id=request.question_id,
            answer=request.answer,
            response_time=request.response_time,
            user_id=DEFAULT_USER_ID,
            confidence_level=request.confidence_level,
        )
        return feedback.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


# ===== 自由回忆（Free Recall） =====

class StartFreeRecallRequest(BaseModel):
    book_id: str
    unit_ids: List[str]


class SubmitFreeRecallRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str


@router.post("/free-recall/start")
async def start_free_recall(
    request: StartFreeRecallRequest,
    db: AsyncSession = Depends(get_db),
):
    """开始自由回忆复习"""
    try:
        svc = _get_service(db)
        knowledge_units = await _load_units(db, request.book_id, request.unit_ids)
        unit_ids = [u.id for u in knowledge_units]
        session = await svc.start_free_recall(
            user_id=DEFAULT_USER_ID, book_id=request.book_id,
            unit_ids=unit_ids, knowledge_units=knowledge_units,
        )
        return session.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/free-recall/answer")
async def submit_free_recall_answer(
    request: SubmitFreeRecallRequest,
    db: AsyncSession = Depends(get_db),
):
    """提交自由回忆答案"""
    try:
        from app.deps import get_llm_client
        llm_client = await get_llm_client("ai_analysis")
        svc = ReviewService(db, llm_client=llm_client)
        result = await svc.submit_free_recall_answer(
            session_id=request.session_id,
            question_id=request.question_id,
            answer=request.answer,
            user_id=DEFAULT_USER_ID,
        )
        return result.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/mastery/{unit_id}")
async def assess_mastery(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = _get_service(db)
        history = await _load_review_history(db, DEFAULT_USER_ID, unit_id)
        assessment = svc.assess_mastery(user_id=DEFAULT_USER_ID, unit_id=unit_id, review_history=history)
        return assessment.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/exam/start")
async def start_exam(
    request: StartExamRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = _get_service(db)
        config = request.config or ExamConfig()
        knowledge_units = await _load_units(db, request.book_id)
        mastery_records = await _load_mastery_records(db, DEFAULT_USER_ID)
        session = await svc.start_exam(
            user_id=DEFAULT_USER_ID,
            book_id=request.book_id,
            chapter_ids=request.chapter_ids,
            config=config,
            knowledge_units=knowledge_units,
            mastery_records=mastery_records,
        )
        return session.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/exam/submit")
async def submit_exam(
    request: SubmitExamRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = _get_service(db)
        result = await svc.submit_exam(session_id=request.session_id, answers=request.answers, user_id=DEFAULT_USER_ID)
        return result.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/export/{book_id}")
async def export_book(
    book_id: str,
    book_title: str,
    format: ExportFormat = ExportFormat.MARKDOWN,
    db: AsyncSession = Depends(get_db),
):
    try:
        svc = _get_service(db)

        # 加载章节
        from app.db.models import ChapterModel, KnowledgeUnitModel
        chapters_result = await db.execute(
            select(ChapterModel).where(ChapterModel.book_id == book_id)
        )
        db_chapters = chapters_result.scalars().all()
        chapters = [{"id": c.id, "title": c.title} for c in db_chapters]

        # 加载知识单元
        units_result = await db.execute(
            select(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id == book_id)
        )
        db_units = units_result.scalars().all()
        knowledge_units = [
            {"id": u.id, "title": u.title, "summary": u.summary, "key_points": json.loads(u.key_points) if u.key_points else []}
            for u in db_units
        ]

        # 加载掌握度记录
        mastery_result = await db.execute(
            select(MasteryRecordModel).where(
                MasteryRecordModel.user_id == DEFAULT_USER_ID,
                MasteryRecordModel.book_id == book_id,
            )
        )
        db_mastery = mastery_result.scalars().all()
        mastery_records = {
            r.knowledge_unit_id: {"mastery_score": r.mastery_score, "mastery_level": r.mastery_level}
            for r in db_mastery
        }

        result = svc.export(
            book_title=book_title,
            export_format=format,
            chapters=chapters,
            knowledge_units=knowledge_units,
            mastery_records=mastery_records,
        )
        return result.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)
