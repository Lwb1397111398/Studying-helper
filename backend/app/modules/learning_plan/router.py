"""学习方案API路由"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.deps import get_current_user
from app.common.errors import ServiceError, ErrorCode, ERROR_STATUS_MAP
from app.modules.learning_plan.service import LearningPlanService
from app.modules.learning_plan.style_analyzer import LearningStyleAnalyzer
from app.modules.learning_plan.schemas import SessionPerformance

router = APIRouter(prefix="/api/v1/plans", tags=["plans"])


class GeneratePlanRequest(BaseModel):
    daily_goal_minutes: int = 30


class CompleteSessionRequest(BaseModel):
    correct_rate: float
    avg_response_time: float
    questions_asked: int
    duration_minutes: int
    feedback_rating: Optional[int] = None


def _get_service(db: AsyncSession) -> LearningPlanService:
    style_analyzer = LearningStyleAnalyzer(db_session=db)
    return LearningPlanService(style_analyzer=style_analyzer, db_session=db)


@router.post("/{book_id}/generate")
async def generate_plan(book_id: str, request: GeneratePlanRequest,
                        db: AsyncSession = Depends(get_db),
                        current_user: str = Depends(get_current_user)):
    """生成学习方案"""
    try:
        svc = _get_service(db)
        units = await svc.load_units_from_db(db, book_id)
        if not units:
            raise ServiceError(
                ErrorCode.INSUFFICIENT_DATA,
                f"书籍 {book_id} 没有可用的知识单元，请先完成知识拆分"
            )
        plan = await svc.generate_plan(
            user_id=current_user,
            book_id=book_id,
            units=units,
            daily_goal_minutes=request.daily_goal_minutes,
        )
        return plan.model_dump()
    except ServiceError as e:
        raise HTTPException(
            status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message
        )


@router.get("/{book_id}/current-session")
async def get_current_session(book_id: str,
                              completed_sessions: int = 0,
                              db: AsyncSession = Depends(get_db),
                              current_user: str = Depends(get_current_user)):
    """获取当前会话"""
    try:
        svc = _get_service(db)
        units = await svc.load_units_from_db(db, book_id)
        if not units:
            raise ServiceError(
                ErrorCode.INSUFFICIENT_DATA,
                f"书籍 {book_id} 没有可用的知识单元"
            )
        plan = await svc.generate_plan(
            user_id=current_user,
            book_id=book_id,
            units=units,
        )
        session = svc.get_current_session(plan, completed_sessions)
        if session is None:
            raise ServiceError(
                ErrorCode.NOT_FOUND,
                "所有会话已完成，恭喜！"
            )
        return {
            "session": session.model_dump(),
            "total_sessions": len(plan.sessions),
            "completed_sessions": completed_sessions,
            "progress_percent": round(
                completed_sessions / len(plan.sessions) * 100, 1
            ),
        }
    except ServiceError as e:
        raise HTTPException(
            status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message
        )


@router.post("/{book_id}/sessions/{session_id}/complete")
async def complete_session(book_id: str, session_id: str,
                           request: CompleteSessionRequest,
                           db: AsyncSession = Depends(get_db),
                           current_user: str = Depends(get_current_user)):
    """完成会话"""
    try:
        svc = _get_service(db)
        units = await svc.load_units_from_db(db, book_id)
        plan = await svc.generate_plan(
            user_id=current_user,
            book_id=book_id,
            units=units,
        )
        performance = SessionPerformance(
            correct_rate=request.correct_rate,
            avg_response_time=request.avg_response_time,
            questions_asked=request.questions_asked,
            duration_minutes=request.duration_minutes,
            feedback_rating=request.feedback_rating,
        )
        update = await svc.complete_session(plan, session_id, performance)
        return update.model_dump()
    except ServiceError as e:
        raise HTTPException(
            status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message
        )
