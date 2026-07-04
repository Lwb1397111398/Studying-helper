"""AID API 路由 - /api/v1/aid"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ServiceError, ErrorCode, ERROR_STATUS_MAP
from app.db.database import get_db
from app.deps import get_aid_llm_client
from app.modules.adaptive_design.service import AIDService
from app.modules.adaptive_design.schemas import (
    LearnerIntentProfileSchema,
    ProfileUpdateRequest,
    MacroDesignSchema,
    MicroPlanSchema,
    TeachingDesignSchema,
)

router = APIRouter(prefix="/api/v1/aid", tags=["adaptive_design"])

DEFAULT_USER_ID = "anonymous"


def _get_service(
    db: AsyncSession = Depends(get_db),
    llm_client=Depends(get_aid_llm_client),
) -> AIDService:
    return AIDService(llm_client=llm_client, db=db)


# ── 画像 ──


@router.get("/{book_id}/profile", response_model=LearnerIntentProfileSchema)
async def get_or_create_profile(
    book_id: str,
    svc: AIDService = Depends(_get_service),
):
    """获取或创建画像（不存在则规则化推断）"""
    try:
        return await svc.get_or_create_profile(book_id, DEFAULT_USER_ID)
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.put("/{book_id}/profile", response_model=LearnerIntentProfileSchema)
async def update_profile(
    book_id: str,
    update: ProfileUpdateRequest,
    svc: AIDService = Depends(_get_service),
):
    """用户调整画像"""
    try:
        return await svc.update_profile(book_id, update, DEFAULT_USER_ID)
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/{book_id}/profile/confirm", response_model=LearnerIntentProfileSchema)
async def confirm_profile(
    book_id: str,
    svc: AIDService = Depends(_get_service),
):
    """确认画像（生成 macro 的前置门禁）"""
    try:
        return await svc.confirm_profile(book_id, DEFAULT_USER_ID)
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


# ── 宏观设计 ──


@router.post("/{book_id}/macro", response_model=MacroDesignSchema)
async def generate_macro(
    book_id: str,
    svc: AIDService = Depends(_get_service),
):
    """生成宏观教学设计（跨章节模块化）"""
    try:
        return await svc.generate_macro_design(book_id, DEFAULT_USER_ID)
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/{book_id}/design", response_model=Optional[TeachingDesignSchema])
async def get_design(
    book_id: str,
    svc: AIDService = Depends(_get_service),
):
    """获取当前教学设计（含 macro、进度、调整审计）"""
    try:
        return await svc.get_design(book_id, DEFAULT_USER_ID)
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


# ── 微观编排 ──


@router.post("/{book_id}/micro/{module_index}", response_model=MicroPlanSchema)
async def generate_micro(
    book_id: str,
    module_index: int,
    svc: AIDService = Depends(_get_service),
):
    """生成指定模块的微观编排（幂等）"""
    try:
        design = await svc.get_design(book_id, DEFAULT_USER_ID)
        if not design:
            raise ServiceError(ErrorCode.NOT_FOUND, "教学设计不存在，请先生成宏观设计")
        return await svc.generate_micro_plan(design.id, module_index, DEFAULT_USER_ID)
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/{book_id}/micro/{module_index}", response_model=Optional[MicroPlanSchema])
async def get_micro(
    book_id: str,
    module_index: int,
    svc: AIDService = Depends(_get_service),
):
    """获取指定模块的微观编排"""
    try:
        design = await svc.get_design(book_id, DEFAULT_USER_ID)
        if not design:
            return None
        return await svc.get_micro_plan(design.id, module_index)
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


# ── 模块推进 ──


@router.post("/{book_id}/advance")
async def advance_module(
    book_id: str,
    svc: AIDService = Depends(_get_service),
):
    """完成当前模块，推进到下一模块（触发 replan 的入口，M3 实现）"""
    try:
        next_idx = await svc.advance_to_next_module(book_id, DEFAULT_USER_ID)
        return {"next_module_index": next_idx, "completed": next_idx is None}
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/{book_id}/activate")
async def activate_module(
    book_id: str,
    svc: AIDService = Depends(_get_service),
):
    """激活当前模块（pending→active），表示开始学习"""
    try:
        idx = await svc.activate_module(book_id, DEFAULT_USER_ID)
        return {"current_module_index": idx}
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


class ReplanRequest(BaseModel):
    """模块结束反馈"""
    weak_points: list[str] = []
    user_feedback: Optional[str] = None
    time_spent_minutes: Optional[int] = None


@router.post("/{book_id}/replan")
async def replan_next(
    book_id: str,
    request: ReplanRequest,
    svc: AIDService = Depends(_get_service),
):
    """模块结束后查漏补缺，调整下一模块（保守：跳过 mastery>=0.85，revisit<=2）"""
    try:
        from app.modules.adaptive_design.schemas import StageFeedback
        feedback = StageFeedback(
            module_index=0,  # 由 service 内部按 current 推断
            weak_points=request.weak_points,
            user_feedback=request.user_feedback,
            time_spent_minutes=request.time_spent_minutes,
        )
        result = await svc.replan_next_module(book_id, feedback, DEFAULT_USER_ID)
        return result.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


class AdjustmentRequest(BaseModel):
    """用户调整审计"""
    field: str
    old_value: str = ""
    new_value: str = ""
    module_index: Optional[int] = None
    reason: Optional[str] = None


@router.post("/{book_id}/adjustment")
async def record_adjustment(
    book_id: str,
    request: AdjustmentRequest,
    svc: AIDService = Depends(_get_service),
):
    """记录用户对设计/画像的调整（append-only 审计，喂给 LLM 防反复拉锯）"""
    try:
        design = await svc.apply_user_adjustments(
            book_id, request.field, request.old_value, request.new_value,
            request.module_index, request.reason, DEFAULT_USER_ID,
        )
        return design.model_dump() if design else None
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/{book_id}/active-units")
async def get_active_units(
    book_id: str,
    svc: AIDService = Depends(_get_service),
):
    """获取当前模块的重排 unit_ids（teaching 集成用，前端也可调）"""
    try:
        unit_ids = await svc.get_active_module_ordered_unit_ids(book_id, DEFAULT_USER_ID)
        return {"book_id": book_id, "unit_ids": unit_ids}
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)
