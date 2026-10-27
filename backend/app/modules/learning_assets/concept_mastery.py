"""claim / concept 掌握度聚合（Step4）

只读、实时计算、不物化。不改现有掌握度更新逻辑。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    LearningEvidenceModel,
    UnitLearningAssetModel,
    BookConceptModel,
)
from app.modules.learning_assets.models_domain import UnitLearningAssetPayload

logger = logging.getLogger(__name__)

# 弱 claim 阈值（可配常量）
WEAK_MASTERY_THRESHOLD = 0.7
RECENT_EVIDENCE_LIMIT = 3

ROLE_PRIORITY = {
    "core_thesis_support": 0,
    "key_mechanism": 1,
    "supporting_detail": 2,
    "example": 3,
    "tangential": 9,
}


async def _load_v2_payloads(
    session: AsyncSession,
    book_id: str,
    unit_ids: Optional[list[str]] = None,
) -> list[tuple[str, UnitLearningAssetPayload]]:
    """返回 [(unit_id, payload)] 仅 understanding_version=v2 的 active 资产。"""
    from app.db.models import KnowledgeUnitModel

    q = select(KnowledgeUnitModel.id).where(KnowledgeUnitModel.book_id == book_id)
    if unit_ids:
        q = q.where(KnowledgeUnitModel.id.in_(unit_ids))
    uids = [r[0] for r in (await session.execute(q)).all()]
    if not uids:
        return []

    assets = (
        await session.execute(
            select(UnitLearningAssetModel).where(
                UnitLearningAssetModel.unit_id.in_(uids),
                UnitLearningAssetModel.status == "active",
            )
        )
    ).scalars().all()

    # 每 unit 取最高 version
    best: dict[str, UnitLearningAssetModel] = {}
    for a in assets:
        prev = best.get(a.unit_id)
        if prev is None or (a.version or 0) > (prev.version or 0):
            best[a.unit_id] = a

    out = []
    for uid, a in best.items():
        try:
            payload = UnitLearningAssetPayload.model_validate_json(a.payload_json or "{}")
        except Exception:
            continue
        if getattr(payload, "understanding_version", "v1") != "v2":
            continue
        out.append((uid, payload))
    return out


async def claim_mastery(
    session: AsyncSession,
    book_id: str,
    *,
    user_id: str = "anonymous",
    unit_ids: Optional[list[str]] = None,
) -> dict[str, Optional[float]]:
    """按 claim_id 聚合 LearningEvidence → 最近 N 次评分均值（0–1），无证据 = None。"""
    q = select(LearningEvidenceModel).where(
        LearningEvidenceModel.book_id == book_id,
        LearningEvidenceModel.user_id == user_id,
        LearningEvidenceModel.status == "active",
        LearningEvidenceModel.claim_id.isnot(None),
    )
    if unit_ids:
        q = q.where(LearningEvidenceModel.unit_id.in_(unit_ids))
    q = q.order_by(LearningEvidenceModel.created_at.desc())
    rows = list((await session.execute(q)).scalars().all())

    by_claim: dict[str, list[float]] = {}
    for e in rows:
        cid = e.claim_id
        if not cid:
            continue
        bucket = by_claim.setdefault(cid, [])
        if len(bucket) >= RECENT_EVIDENCE_LIMIT:
            continue
        # score 可能是 0-1 或 0-100
        s = float(e.score or 0.0)
        if s > 1.0:
            s = s / 100.0
        bucket.append(max(0.0, min(1.0, s)))

    return {
        cid: (sum(vals) / len(vals) if vals else None)
        for cid, vals in by_claim.items()
    }


async def concept_mastery(
    session: AsyncSession,
    book_id: str,
    *,
    user_id: str = "anonymous",
    unit_ids: Optional[list[str]] = None,
) -> dict[str, Optional[float]]:
    """概念掌握度 = 关联 required claims 的 mastery 均值（忽略 null）。"""
    cm = await claim_mastery(session, book_id, user_id=user_id, unit_ids=unit_ids)
    payloads = await _load_v2_payloads(session, book_id, unit_ids)

    # concept name → claim ids (required / non-tangential)
    concept_claims: dict[str, list[str]] = {}
    for _uid, payload in payloads:
        for c in payload.claims or []:
            role = (c.role_in_book or "")
            if role == "tangential":
                continue
            for name in c.related_concepts or []:
                n = (name or "").strip()
                if not n:
                    continue
                concept_claims.setdefault(n, []).append(c.id)

    # also map book_concepts names
    rows = (
        await session.execute(
            select(BookConceptModel).where(BookConceptModel.book_id == book_id)
        )
    ).scalars().all()
    known = {r.name for r in rows}

    result: dict[str, Optional[float]] = {}
    for name, cids in concept_claims.items():
        scores = [cm[c] for c in cids if c in cm and cm[c] is not None]
        result[name] = (sum(scores) / len(scores)) if scores else None
    # ensure known concepts appear
    for n in known:
        result.setdefault(n, None)
    return result


async def weak_required_claims(
    session: AsyncSession,
    book_id: str,
    *,
    user_id: str = "anonymous",
    unit_ids: Optional[list[str]] = None,
    threshold: float = WEAK_MASTERY_THRESHOLD,
) -> list[dict[str, Any]]:
    """required 且（mastery < threshold 或无证据）的 claims，按 role 优先级排序。"""
    cm = await claim_mastery(session, book_id, user_id=user_id, unit_ids=unit_ids)
    payloads = await _load_v2_payloads(session, book_id, unit_ids)

    weak: list[dict[str, Any]] = []
    for uid, payload in payloads:
        for c in payload.claims or []:
            role = (c.role_in_book or "supporting_detail")
            if role == "tangential":
                continue
            mastery = cm.get(c.id)
            if mastery is not None and mastery >= threshold:
                continue
            weak.append(
                {
                    "claim_id": c.id,
                    "unit_id": uid,
                    "text": c.text,
                    "role_in_book": role,
                    "mastery_check": c.mastery_check,
                    "mastery": mastery,
                    "related_concepts": list(c.related_concepts or []),
                }
            )

    weak.sort(
        key=lambda x: (
            ROLE_PRIORITY.get(x["role_in_book"], 5),
            0 if x["mastery"] is None else 1,
            x["mastery"] if x["mastery"] is not None else -1,
        )
    )
    return weak


def format_weak_claims_for_prompt(weak: list[dict[str, Any]], limit: int = 8) -> str:
    if not weak:
        return "（无 claim 级薄弱证据，按常规规划）"
    lines = []
    for w in weak[:limit]:
        m = "无证据" if w["mastery"] is None else f"{w['mastery']:.2f}"
        lines.append(
            f"- [{w['role_in_book']}] unit={w['unit_id']} claim={w['claim_id']} "
            f"mastery={m}\n  命题：{w['text']}\n  掌握标准：{w.get('mastery_check') or '无'}"
        )
    return "\n".join(lines)
