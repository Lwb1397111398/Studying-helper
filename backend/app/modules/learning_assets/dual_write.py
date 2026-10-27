"""将 UnitLearningAsset 投影到 knowledge_units 旧列，兼容旧 UI。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeUnitModel
from app.modules.learning_assets.models_domain import UnitLearningAssetPayload


async def dual_write_unit_columns(
    session: AsyncSession,
    unit_id: str,
    payload: UnitLearningAssetPayload,
) -> None:
    unit = (
        await session.execute(
            select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
        )
    ).scalar_one_or_none()
    if unit is None:
        return

    if payload.summary:
        unit.summary = payload.summary
    elif payload.central_question:
        unit.summary = payload.central_question

    if payload.explanation:
        unit.explanation = payload.explanation
    elif payload.claims:
        unit.explanation = "\n".join(c.text for c in payload.claims[:5])

    key_points: list[Any] = []
    for c in payload.claims:
        key_points.append({"title": c.claim_type, "explanation": c.text, "examples": []})
    if key_points:
        unit.key_points = json.dumps(key_points, ensure_ascii=False)

    concepts = []
    for o in payload.learning_objectives:
        concepts.append({"name": o.id, "definition": o.description, "examples": [], "related_concepts": []})
    if concepts:
        unit.concepts = json.dumps(concepts, ensure_ascii=False)

    prereq_labels = []
    for p in payload.prerequisites:
        if p.resolved_unit_id:
            prereq_labels.append(p.resolved_unit_id)
        elif p.label:
            prereq_labels.append(p.label)
    if prereq_labels:
        unit.prerequisites = json.dumps(prereq_labels, ensure_ascii=False)

    await session.flush()
