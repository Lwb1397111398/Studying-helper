"""AnalysisJob 编排门面：对外稳定 API，内部委托 pipeline / understanding。"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AnalysisJobModel, UnitLearningAssetModel
from app.modules.learning_assets.block_builder import ensure_document_blocks_for_book
from app.modules.learning_assets.pipeline import analyze_unit as pipeline_analyze_unit
from app.modules.learning_assets.understanding import (
    precompute_book_understanding,
    run_understanding,
    to_legacy_view,
)


async def ensure_blocks(session: AsyncSession, book_id: str) -> str:
    return await ensure_document_blocks_for_book(session, book_id)


async def analyze_unit_job(
    session: AsyncSession,
    unit_id: str,
    *,
    stage1=None,
    stage2=None,
    prompt_version: str = "rule-v1",
    model_name: str = "rule",
) -> UnitLearningAssetModel:
    """创建/复用 AnalysisJob 并发布 UnitLearningAsset。"""
    return await pipeline_analyze_unit(
        session,
        unit_id,
        stage1=stage1,
        stage2=stage2,
        prompt_version=prompt_version,
        model_name=model_name,
    )


async def run_unit_understanding(
    session: AsyncSession,
    unit_id: str,
    *,
    llm_client=None,
    force: bool = False,
):
    """仅理解阶段（Step2 独立入口）。"""
    return await run_understanding(
        session, unit_id, llm_client=llm_client, force=force
    )


async def precompute_understanding_for_book(
    session: AsyncSession,
    book_id: str,
    *,
    llm_client=None,
    force: bool = False,
) -> dict[str, Any]:
    return await precompute_book_understanding(
        session, book_id, llm_client=llm_client, force=force
    )


async def get_active_asset(
    session: AsyncSession, unit_id: str
) -> Optional[UnitLearningAssetModel]:
    return (
        await session.execute(
            select(UnitLearningAssetModel).where(
                UnitLearningAssetModel.unit_id == unit_id,
                UnitLearningAssetModel.status == "active",
            )
        )
    ).scalar_one_or_none()


async def get_job(session: AsyncSession, job_id: str) -> Optional[AnalysisJobModel]:
    return (
        await session.execute(
            select(AnalysisJobModel).where(AnalysisJobModel.id == job_id)
        )
    ).scalar_one_or_none()


async def list_jobs_for_unit(
    session: AsyncSession, unit_id: str, limit: int = 20
) -> list[AnalysisJobModel]:
    rows = (
        await session.execute(
            select(AnalysisJobModel)
            .where(
                AnalysisJobModel.scope_type == "unit",
                AnalysisJobModel.scope_id == unit_id,
            )
            .order_by(AnalysisJobModel.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)
