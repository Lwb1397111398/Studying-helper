"""Teaching v2 HTTP endpoints — parallel to legacy teaching router."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import TeachingSessionModel
from app.modules.teaching.session_v2_service import (
    SessionV2Error,
    apply_event,
    start_session_v2,
    submit_attempt,
)

router = APIRouter(prefix="/api/v1/teaching/v2", tags=["teaching-v2"])


class StartBody(BaseModel):
    user_id: str = "anonymous"
    book_id: str
    unit_id: str
    asset_id: Optional[str] = None


class EventBody(BaseModel):
    event: str
    guards: dict[str, Any] = Field(default_factory=dict)


class AttemptBody(BaseModel):
    user_id: str = "anonymous"
    assessment_item_id: str
    response: dict[str, Any]
    idempotency_key: str
    source_type: str = "assessment"
    device_id: Optional[str] = None


@router.post("/sessions/start")
async def api_start(body: StartBody, db: AsyncSession = Depends(get_db)):
    try:
        ts = await start_session_v2(
            db,
            user_id=body.user_id,
            book_id=body.book_id,
            unit_id=body.unit_id,
            asset_id=body.asset_id,
        )
    except SessionV2Error as e:
        raise HTTPException(status_code=400, detail={"code": e.code, "message": e.message}) from e
    return _session_dict(ts)


@router.post("/sessions/{session_id}/event")
async def api_event(session_id: str, body: EventBody, db: AsyncSession = Depends(get_db)):
    try:
        ts = await apply_event(db, session_id, body.event, body.guards)
    except SessionV2Error as e:
        status = 404 if e.code == "NOT_FOUND" else 400
        raise HTTPException(status_code=status, detail={"code": e.code, "message": e.message}) from e
    return _session_dict(ts)


@router.post("/sessions/{session_id}/attempts")
async def api_attempt(session_id: str, body: AttemptBody, db: AsyncSession = Depends(get_db)):
    try:
        result = await submit_attempt(
            db,
            session_id=session_id,
            user_id=body.user_id,
            assessment_item_id=body.assessment_item_id,
            response=body.response,
            idempotency_key=body.idempotency_key,
            source_type=body.source_type,
            device_id=body.device_id,
        )
    except SessionV2Error as e:
        status = 404 if e.code == "NOT_FOUND" else 400
        raise HTTPException(status_code=status, detail={"code": e.code, "message": e.message}) from e
    return result


@router.get("/sessions/{session_id}")
async def api_get(session_id: str, db: AsyncSession = Depends(get_db)):
    ts = (
        await db.execute(
            select(TeachingSessionModel).where(TeachingSessionModel.id == session_id)
        )
    ).scalar_one_or_none()
    if ts is None:
        raise HTTPException(status_code=404, detail="session not found")
    return _session_dict(ts)


def _session_dict(ts: TeachingSessionModel) -> dict[str, Any]:
    return {
        "id": ts.id,
        "user_id": ts.user_id,
        "book_id": ts.book_id,
        "unit_ids": ts.unit_ids,
        "primary_unit_id": ts.primary_unit_id,
        "asset_id": ts.asset_id,
        "state_v2": ts.state_v2,
        "completion_status": ts.completion_status,
        "pause_reason": ts.pause_reason,
        "status": ts.status,
        "parent_session_id": ts.parent_session_id,
    }
