"""教学API路由"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ServiceError, ErrorCode, ERROR_STATUS_MAP
from app.db.database import get_db
from app.db.models import KnowledgeUnitModel, TeachingSessionModel
from app.deps import get_llm_client
from app.modules.ai_learning.schemas import LearnedUnit
from app.modules.teaching.service import TeachingService
from app.modules.teaching.schemas import TeachingMessage, UserQuestion, Annotation, SessionTest

router = APIRouter(prefix="/api/v1/teaching", tags=["teaching"])

DEFAULT_USER_ID = "anonymous"


class StartSessionRequest(BaseModel):
    plan_session_id: str = ""
    book_id: str
    unit_ids: List[str]
    user_id: str = DEFAULT_USER_ID


class AskQuestionRequest(BaseModel):
    question: str


class AnnotationRequest(BaseModel):
    unit_id: str
    annotation_type: str
    content: Optional[str] = None
    user_id: str = DEFAULT_USER_ID


class SubmitTestRequest(BaseModel):
    answers: List[str]


async def _load_learned_units(db: AsyncSession, unit_ids: List[str]) -> List[LearnedUnit]:
    """从DB加载已学习单元"""
    if not unit_ids:
        return []
    result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.id.in_(unit_ids))
    )
    db_units = result.scalars().all()
    return [
        LearnedUnit(
            unit_id=u.id,
            summary=u.summary or "",
            key_points=u.key_points.split(",") if u.key_points else [],
            concepts=[],
            difficulty_level=u.difficulty_level or 1,
            importance_score=u.importance_score or 0.5,
            prerequisites=[],
        )
        for u in db_units
    ]


async def _get_units_for_session(db: AsyncSession, session_id: str) -> List[LearnedUnit]:
    """通过会话ID加载关联的知识单元"""
    result = await db.execute(
        select(TeachingSessionModel).where(TeachingSessionModel.id == session_id)
    )
    db_session = result.scalar_one_or_none()
    if not db_session:
        raise HTTPException(status_code=404, detail="会话不存在")

    unit_ids = json.loads(db_session.unit_ids)
    return await _load_learned_units(db, unit_ids)


def _get_service(
    db: AsyncSession = Depends(get_db),
    llm_client=Depends(lambda: get_llm_client("teaching")),
) -> TeachingService:
    return TeachingService(llm_client=llm_client, db=db)


@router.post("/sessions/start")
async def start_session(
    request: StartSessionRequest,
    svc: TeachingService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
):
    """开始教学会话"""
    try:
        units = await _load_learned_units(db, request.unit_ids)
        session = await svc.start_session(
            user_id=request.user_id,
            plan_session_id=request.plan_session_id,
            book_id=request.book_id,
            unit_ids=request.unit_ids,
            units=units,
        )
        return session.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/sessions/{session_id}/next-message")
async def get_next_message(
    session_id: str,
    svc: TeachingService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
):
    """获取下一条教学消息"""
    try:
        units = await _get_units_for_session(db, session_id)
        message = await svc.get_next_message(session_id, units)
        return message.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/sessions/{session_id}/ask")
async def ask_question(
    session_id: str,
    request: AskQuestionRequest,
    svc: TeachingService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
):
    """提问"""
    try:
        units = await _get_units_for_session(db, session_id)
        answer = await svc.answer_question(session_id, request.question, units)
        return answer.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    svc: TeachingService = Depends(_get_service),
):
    """获取会话所有消息"""
    try:
        messages = await svc.get_session_messages(session_id)
        return [m.model_dump() for m in messages]
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/annotations")
async def add_annotation(
    request: AnnotationRequest,
    svc: TeachingService = Depends(_get_service),
):
    """添加笔记/标记"""
    try:
        annotation = await svc.add_annotation(
            user_id=request.user_id,
            unit_id=request.unit_id,
            annotation_type=request.annotation_type,
            content=request.content,
        )
        return annotation.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/sessions/{session_id}/test")
async def run_test(
    session_id: str,
    svc: TeachingService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
):
    """运行测试"""
    try:
        units = await _get_units_for_session(db, session_id)
        test = await svc.run_session_test(session_id, units)
        return test.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/tests/{test_id}/submit")
async def submit_test(
    test_id: str,
    request: SubmitTestRequest,
    svc: TeachingService = Depends(_get_service),
):
    """提交测试答案"""
    try:
        test = await svc.submit_test_answers(test_id, request.answers)
        return test.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    svc: TeachingService = Depends(_get_service),
):
    """完成会话"""
    try:
        summary = await svc.complete_session(session_id)
        return summary.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)
