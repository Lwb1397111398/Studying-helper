"""Learning assets API：文档块、分析、资产查询。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import AnalysisJobModel, UnitLearningAssetModel
from app.modules.learning_assets.block_builder import ensure_document_blocks_for_book
from app.modules.learning_assets.pipeline import analyze_unit

router = APIRouter(prefix="/api/v1/learning-assets", tags=["learning-assets"])


class EnsureBlocksResponse(BaseModel):
    book_id: str
    document_revision_id: str


class AnalyzeResponse(BaseModel):
    asset_id: str
    unit_id: str
    version: int
    status: str
    readiness_status: str
    quality_score: float | None = None
    analysis_job_id: str | None = None


class AssetResponse(BaseModel):
    id: str
    unit_id: str
    version: int
    status: str
    readiness_status: str
    freshness_status: str
    quality_score: float | None
    document_revision_id: str | None
    payload: dict[str, Any]
    schema_version: str


@router.post("/books/{book_id}/document-blocks/ensure", response_model=EnsureBlocksResponse)
async def api_ensure_blocks(book_id: str, db: AsyncSession = Depends(get_db)):
    try:
        rev_id = await ensure_document_blocks_for_book(db, book_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return EnsureBlocksResponse(book_id=book_id, document_revision_id=rev_id)


@router.post("/units/{unit_id}/analyze", response_model=AnalyzeResponse)
async def api_analyze_unit(unit_id: str, db: AsyncSession = Depends(get_db)):
    try:
        asset = await analyze_unit(db, unit_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return AnalyzeResponse(
        asset_id=asset.id,
        unit_id=asset.unit_id,
        version=asset.version,
        status=asset.status,
        readiness_status=asset.readiness_status,
        quality_score=asset.quality_score,
        analysis_job_id=asset.analysis_job_id,
    )


@router.get("/units/{unit_id}/asset", response_model=AssetResponse)
async def api_get_active_asset(unit_id: str, db: AsyncSession = Depends(get_db)):
    asset = (
        await db.execute(
            select(UnitLearningAssetModel).where(
                UnitLearningAssetModel.unit_id == unit_id,
                UnitLearningAssetModel.status == "active",
            )
        )
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="no active asset")
    return _to_asset_response(asset)


@router.get("/assets/{asset_id}", response_model=AssetResponse)
async def api_get_asset(asset_id: str, db: AsyncSession = Depends(get_db)):
    asset = (
        await db.execute(
            select(UnitLearningAssetModel).where(UnitLearningAssetModel.id == asset_id)
        )
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="asset not found")
    return _to_asset_response(asset)


@router.get("/jobs/{job_id}")
async def api_get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = (
        await db.execute(select(AnalysisJobModel).where(AnalysisJobModel.id == job_id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "id": job.id,
        "scope_type": job.scope_type,
        "scope_id": job.scope_id,
        "status": job.status,
        "wait_reason": job.wait_reason,
        "attempt_count": job.attempt_count,
        "idempotency_key": job.idempotency_key,
        "quality_result": json.loads(job.quality_result_json or "{}"),
        "error": json.loads(job.error_json) if job.error_json else None,
    }


def _to_asset_response(asset: UnitLearningAssetModel) -> AssetResponse:
    try:
        payload = json.loads(asset.payload_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    return AssetResponse(
        id=asset.id,
        unit_id=asset.unit_id,
        version=asset.version,
        status=asset.status,
        readiness_status=asset.readiness_status,
        freshness_status=asset.freshness_status,
        quality_score=asset.quality_score,
        document_revision_id=asset.document_revision_id,
        payload=payload,
        schema_version=asset.schema_version,
    )
