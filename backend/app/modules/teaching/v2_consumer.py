"""教学侧 v2 资产消费辅助。

- 加载 unit 的 active UnitLearningAsset
- 版本分支：understanding_version==v2 才启用
- 生成 EXPLAIN/CHECK/REFLECT/FEYNMAN 注入块
- 题型映射 cognitive_level → 题型说明
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BookModel, UnitLearningAssetModel
from app.modules.learning_assets.models_domain import (
    Importance,
    SourceClaim,
    UnitLearningAssetPayload,
)

logger = logging.getLogger(__name__)

COG_QUESTION_HINT = {
    "remember": "回忆/填空：直接考查关键事实或定义的准确回忆",
    "understand": "用自己的话解释：要求学生说明含义或因果，禁止只背原文",
    "apply": "举例/应用：要求学生给出新情境下的例子或用法",
    "analyze": "对比/分析：要求学生比较、辨析边界或指出关系",
}

ROLE_BUDGET = {
    "core_thesis_support": "详细讲（必须含例子 + 类比，约 100–150 字）",
    "key_mechanism": "详细讲（必须含例子 + 类比，约 100–150 字）",
    "supporting_detail": "正常讲（约 60–100 字）",
    "example": "作为例证素材融入其他 claim，不必单独成段",
    "tangential": "跳过或最多一句带过，不要花篇幅",
}


@dataclass
class V2TeachingContext:
    available: bool = False
    understanding_version: str = "v1"
    unit_gist: str = ""
    core_thesis: str = ""
    claims: List[SourceClaim] = field(default_factory=list)
    required_claims: List[SourceClaim] = field(default_factory=list)
    payload: Optional[UnitLearningAssetPayload] = None
    overview_key_concepts: List[dict[str, Any]] = field(default_factory=list)
    understanding_partial: bool = False

    @property
    def is_v2(self) -> bool:
        return self.available and self.understanding_version == "v2" and bool(self.required_claims or self.claims)


async def load_v2_teaching_context(
    session: AsyncSession,
    unit_id: str,
    book_id: Optional[str] = None,
) -> V2TeachingContext:
    """加载单元 active 资产；非 v2 或缺失 → available=False（教学走旧路径）。"""
    asset = (
        await session.execute(
            select(UnitLearningAssetModel)
            .where(
                UnitLearningAssetModel.unit_id == unit_id,
                UnitLearningAssetModel.status == "active",
            )
            .order_by(UnitLearningAssetModel.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if asset is None:
        return V2TeachingContext()

    try:
        payload = UnitLearningAssetPayload.model_validate_json(asset.payload_json or "{}")
    except Exception as exc:
        logger.warning("parse asset payload fail unit=%s: %s", unit_id, exc)
        return V2TeachingContext()

    version = getattr(payload, "understanding_version", None) or "v1"
    if version != "v2":
        return V2TeachingContext(available=False, understanding_version=version, payload=payload)

    claims = list(payload.claims or [])
    required = [
        c
        for c in claims
        if (c.role_in_book or "") != "tangential"
        and (
            c.importance == Importance.REQUIRED
            or c.importance == "required"
            or (c.role_in_book or "") in ("core_thesis_support", "key_mechanism", "supporting_detail", "example")
        )
    ]
    # 若 importance 全是 required 但 role 区分：required = non-tangential with mastery_check
    if not required:
        required = [c for c in claims if (c.role_in_book or "") != "tangential"]

    core_thesis = ""
    overview_concepts: list[dict[str, Any]] = []
    bid = book_id
    if not bid and claims:
        # try from unit via asset only — book from KnowledgeUnit if needed
        pass
    if bid:
        book = (
            await session.execute(select(BookModel).where(BookModel.id == bid))
        ).scalar_one_or_none()
        if book and book.overview_json:
            try:
                from app.modules.ai_learning.schemas import BookDeepOverview

                ov = BookDeepOverview.model_validate_json(book.overview_json)
                if not ov.degraded:
                    core_thesis = ov.core_thesis or ""
                    overview_concepts = [
                        {
                            "name": c.name,
                            "definition": c.definition,
                            "first_chapter_id": c.first_chapter_id,
                        }
                        for c in (ov.key_concepts or [])
                    ]
            except Exception:
                pass
    else:
        # resolve book_id from unit
        from app.db.models import KnowledgeUnitModel

        unit = (
            await session.execute(
                select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
            )
        ).scalar_one_or_none()
        if unit:
            book = (
                await session.execute(select(BookModel).where(BookModel.id == unit.book_id))
            ).scalar_one_or_none()
            if book and book.overview_json:
                try:
                    from app.modules.ai_learning.schemas import BookDeepOverview

                    ov = BookDeepOverview.model_validate_json(book.overview_json)
                    if not ov.degraded:
                        core_thesis = ov.core_thesis or ""
                        overview_concepts = [
                            {
                                "name": c.name,
                                "definition": c.definition,
                                "first_chapter_id": c.first_chapter_id,
                            }
                            for c in (ov.key_concepts or [])
                        ]
                except Exception:
                    pass

    partial = bool(getattr(payload, "content_hash", None) and len(payload.claims or []) < 3)

    return V2TeachingContext(
        available=True,
        understanding_version="v2",
        unit_gist=payload.unit_gist or payload.central_question or "",
        core_thesis=core_thesis,
        claims=claims,
        required_claims=required,
        payload=payload,
        overview_key_concepts=overview_concepts,
        understanding_partial=partial,
    )


def build_explain_budget_block(ctx: V2TeachingContext) -> str:
    lines = [
        "## 本单元在全书中的位置",
        f"单元角色：{ctx.unit_gist or '（未标注）'}",
    ]
    if ctx.core_thesis:
        lines.append(f"全书核心论点：{ctx.core_thesis}")
    lines.append("")
    lines.append("## 讲解预算（按 role_in_book，必须遵守）")
    for i, c in enumerate(ctx.claims, 1):
        role = c.role_in_book or "supporting_detail"
        budget = ROLE_BUDGET.get(role, ROLE_BUDGET["supporting_detail"])
        lines.append(f"{i}. [{role}] {c.text}")
        lines.append(f"   预算：{budget}")
        if c.mastery_check:
            lines.append(f"   掌握标准：{c.mastery_check}")
        if c.related_concepts:
            lines.append(f"   相关概念：{'、'.join(c.related_concepts)}")
    if ctx.understanding_partial:
        lines.append("\n（注意：本单元 understanding_partial=true，材料可能不完整，讲解时勿过度扩展）")
    return "\n".join(lines)


def build_check_claims_block(ctx: V2TeachingContext) -> str:
    """required claims → 出题清单（tangential 排除）。"""
    lines = ["## 待检验命题（一 claim 一题，禁止合并）"]
    targets = ctx.required_claims or [
        c for c in ctx.claims if (c.role_in_book or "") != "tangential"
    ]
    for i, c in enumerate(targets, 1):
        # cognitive from linked objective if any
        cog = "understand"
        if ctx.payload:
            for o in ctx.payload.learning_objectives or []:
                if c.id in (o.source_claim_ids or []):
                    cog = o.cognitive_level or (
                        o.ability.value if hasattr(o.ability, "value") else str(o.ability or "understand")
                    )
                    # map ability-ish to cog
                    if cog in ("recall", "recognize", "remember"):
                        cog = "remember"
                    elif cog in ("explain", "understand"):
                        cog = "understand"
                    elif cog in ("apply",):
                        cog = "apply"
                    elif cog in ("analyze", "differentiate", "transfer"):
                        cog = "analyze"
                    else:
                        cog = cog if cog in COG_QUESTION_HINT else "understand"
                    break
        hint = COG_QUESTION_HINT.get(cog, COG_QUESTION_HINT["understand"])
        lines.append(f"{i}. claim_id={c.id}")
        lines.append(f"   命题：{c.text}")
        lines.append(f"   mastery_check（通过标准）：{c.mastery_check or '能正确说明该命题'}")
        lines.append(f"   cognitive_level：{cog} → 题型要求：{hint}")
    return "\n".join(lines)


def build_reflect_connect_block(ctx: V2TeachingContext) -> str:
    """related_concepts × overview key_concepts → 联结素材。"""
    related: list[str] = []
    for c in ctx.claims:
        related.extend(c.related_concepts or [])
    # unique preserve order
    seen = set()
    uniq = []
    for n in related:
        if n and n not in seen:
            seen.add(n)
            uniq.append(n)

    concept_map = {c["name"]: c for c in ctx.overview_key_concepts if c.get("name")}
    lines = ["## 可跨章联结的概念（仅使用下列有定义的；查不到的跳过）"]
    found = 0
    for name in uniq:
        meta = concept_map.get(name)
        if not meta:
            continue
        found += 1
        lines.append(
            f"- {name}：{meta.get('definition') or '（无定义）'}；首次出现章节 id={meta.get('first_chapter_id') or '未知'}"
        )
    if found == 0:
        lines.append("（本单元 related_concepts 在全书概念清单中未命中，请只做单元内反思，不要硬编跨章关系）")
    return "\n".join(lines)


def pick_feynman_mastery_checks(ctx: V2TeachingContext) -> List[str]:
    """选取「能用自己的话解释…」类 mastery_check 作为费曼提示。"""
    out = []
    for c in ctx.required_claims or ctx.claims:
        mc = (c.mastery_check or "").strip()
        if not mc:
            continue
        if any(k in mc for k in ("自己的话", "解释", "说明", "阐述")):
            out.append(mc)
    if not out:
        out = [c.mastery_check for c in (ctx.required_claims or [])[:2] if c.mastery_check]
    return out[:3]


def claim_id_for_question_index(ctx: V2TeachingContext, index: int) -> Optional[str]:
    targets = ctx.required_claims or [
        c for c in ctx.claims if (c.role_in_book or "") != "tangential"
    ]
    if 0 <= index < len(targets):
        return targets[index].id
    return None


def mastery_check_for_claim(ctx: V2TeachingContext, claim_id: Optional[str]) -> Optional[str]:
    if not claim_id:
        return None
    for c in ctx.claims:
        if c.id == claim_id:
            return c.mastery_check
    return None
