"""单元分析管线：Context → 理解/设计（可注入）→ 校验 → 发布资产。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AnalysisJobModel,
    KnowledgeUnitModel,
    UnitLearningAssetModel,
)
from app.modules.learning_assets.assessment_validator import validate_assessment_payload
from app.modules.learning_assets.context_builder import build_analysis_context
from app.modules.learning_assets.dual_write import dual_write_unit_columns
from app.modules.learning_assets.evidence_validator import (
    find_quote_offsets,
    validate_evidence_ref,
)
from app.modules.learning_assets.models_domain import (
    Ability,
    AssessmentCriterion,
    AssessmentItem,
    AssetStatus,
    EvidenceRef,
    FreshnessStatus,
    Importance,
    LearningObjective,
    ReadinessStatus,
    SourceClaim,
    UnitLearningAssetPayload,
)
from app.modules.learning_assets.readiness import evaluate_payload_readiness
from app.modules.learning_assets.understanding import to_legacy_view

logger = logging.getLogger(__name__)

StageFn = Callable[[dict[str, Any]], Awaitable[dict[str, Any]] | dict[str, Any]]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _job_key(unit_id: str, source_hash: str, prompt_version: str = "p1") -> str:
    return f"unit_analyze:{unit_id}:{source_hash}:{prompt_version}:unit-asset-v1"


async def _maybe_await(result):
    if hasattr(result, "__await__"):
        return await result
    return result


def default_rule_stage1(ctx: dict[str, Any]) -> dict[str, Any]:
    """无 LLM 时的规则化理解：用单元全文作唯一 required claim。"""
    text = ctx.get("unit_text") or ""
    block = (ctx.get("blocks") or [{}])[0]
    block_id = block.get("id") or "blk_unknown"
    quote = text[: min(40, len(text))] if text else ""
    start, end = 0, len(quote)
    if quote and block.get("text"):
        offs = find_quote_offsets(block["text"], quote)
        if offs:
            start, end = offs
        else:
            # quote 取 block 前缀
            quote = block["text"][: min(40, len(block["text"]))]
            start, end = 0, len(quote)
    er_id = "er_auto_1"
    return {
        "unit_type": "concept",
        "central_question": "本单元的核心内容是什么？",
        "claims": [
            {
                "id": "c_auto_1",
                "claim_type": "definition",
                "importance": "required",
                "text": quote or text[:80] or "单元内容",
                "evidence": [
                    {
                        "id": er_id,
                        "block_id": block_id,
                        "start_offset": start,
                        "end_offset": end,
                        "quote": quote or text[:80],
                    }
                ],
            }
        ],
        "objectives": [
            {
                "id": "o_auto_1",
                "description": "能复述本单元的核心结论",
                "ability": "recall",
                "importance": "required",
                "source_claim_ids": ["c_auto_1"],
            }
        ],
    }


def default_rule_stage2(understanding: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """教学资产设计（规则路径）。

    v2：每个 non-tangential claim 的 mastery_check → 至少一道检验题；
    tangential 不出题。v1/legacy：保持旧行为。
    """
    version = understanding.get("understanding_version") or "v1"
    claims = understanding.get("claims") or []
    objectives = understanding.get("objectives") or []

    if version == "v2" and claims:
        return _stage2_from_v2(understanding, ctx)

    obj = (objectives or [{}])[0]
    oid = obj.get("id") or "o_auto_1"
    return {
        "summary": understanding.get("central_question") or "",
        "explanation": (ctx.get("unit_text") or "")[:500],
        "criteria": [
            {
                "id": "cr_auto_1",
                "objective_id": oid,
                "observable_behavior": "正确复述核心结论",
                "pass_threshold": 0.8,
            }
        ],
        "items": [
            {
                "id": "it_auto_1",
                "objective_ids": [oid],
                "criterion_ids": ["cr_auto_1"],
                "item_type": "short_answer",
                "stem": "请用一句话概括本单元核心内容。",
                "expected_answer": (claims or [{}])[0].get("text") or "",
                "ability": "recall",
                "phase_usage": ["assessment", "diagnose"],
                "equivalence_group_id": "eq_auto_1",
            },
            {
                "id": "it_auto_2",
                "objective_ids": [oid],
                "criterion_ids": ["cr_auto_1"],
                "item_type": "short_answer",
                "stem": "换一种说法，本单元在讲什么？",
                "expected_answer": (claims or [{}])[0].get("text") or "",
                "ability": "recall",
                "phase_usage": ["reassessment"],
                "equivalence_group_id": "eq_auto_1",
            },
        ],
        "teaching_strategy": {"skeleton": "definition_examples"},
        "repair_strategy_map": {
            "memory": "reencode",
            "confusion": "contrast",
            "missing_prereq": "spawn_prereq",
        },
    }


_COG_TO_ABILITY_STAGE2 = {
    "remember": "recall",
    "understand": "explain",
    "apply": "apply",
    "analyze": "differentiate",
}


def _stage2_from_v2(understanding: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    claims = understanding.get("claims") or []
    objectives = understanding.get("objectives") or []
    # map claim id → objective ids
    claim_to_objs: dict[str, list[str]] = {}
    for o in objectives:
        oid = o.get("id") or ""
        for cid in o.get("source_claim_ids") or []:
            claim_to_objs.setdefault(cid, []).append(oid)
        # covers_claims indices
        for idx in o.get("covers_claims") or []:
            try:
                ii = int(idx)
            except (TypeError, ValueError):
                continue
            if 0 <= ii < len(claims):
                cid = claims[ii].get("id")
                if cid:
                    claim_to_objs.setdefault(cid, []).append(oid)

    criteria = []
    items = []
    for i, c in enumerate(claims):
        role = (c.get("role_in_book") or "").lower()
        if role == "tangential":
            continue
        cid = c.get("id") or f"c_{i+1}"
        mastery = c.get("mastery_check") or f"能正确说明：{c.get('text') or ''}"
        text = c.get("text") or ""
        oids = claim_to_objs.get(cid) or (
            [objectives[0]["id"]] if objectives and objectives[0].get("id") else [f"o_for_{cid}"]
        )
        # ensure objective exists for orphan
        if not claim_to_objs.get(cid) and not objectives:
            objectives.append(
                {
                    "id": oids[0],
                    "description": mastery,
                    "ability": "explain",
                    "importance": "required",
                    "source_claim_ids": [cid],
                }
            )
        cog = "understand"
        for o in objectives:
            if o.get("id") in oids and o.get("cognitive_level"):
                cog = o["cognitive_level"]
                break
        ability = _COG_TO_ABILITY_STAGE2.get(cog, "explain")
        cr_id = f"cr_{cid}"
        it_id = f"it_{cid}"
        criteria.append(
            {
                "id": cr_id,
                "objective_id": oids[0],
                "observable_behavior": mastery,
                "pass_threshold": 0.8,
            }
        )
        # primary assessment item
        items.append(
            {
                "id": it_id,
                "objective_ids": oids[:1],
                "criterion_ids": [cr_id],
                "item_type": "short_answer",
                "stem": mastery if mastery.endswith("？") or mastery.endswith("?") else f"{mastery}？",
                "expected_answer": text,
                "ability": ability,
                "phase_usage": ["assessment", "diagnose", "check"],
                "equivalence_group_id": f"eq_{cid}",
                "claim_id": cid,
                "scoring_rubric": {
                    "mastery_check": mastery,
                    "claim_id": cid,
                    "claim_text": text,
                    "cognitive_level": cog,
                },
            }
        )
        # reassessment variant
        items.append(
            {
                "id": f"{it_id}_re",
                "objective_ids": oids[:1],
                "criterion_ids": [cr_id],
                "item_type": "short_answer",
                "stem": f"换一种场景或表述：{mastery}",
                "expected_answer": text,
                "ability": ability,
                "phase_usage": ["reassessment"],
                "equivalence_group_id": f"eq_{cid}",
                "claim_id": cid,
                "scoring_rubric": {
                    "mastery_check": mastery,
                    "claim_id": cid,
                    "claim_text": text,
                    "cognitive_level": cog,
                },
            }
        )

    # fallback if all tangential
    if not items:
        return default_rule_stage2({**understanding, "understanding_version": "v1"}, ctx)

    return {
        "summary": understanding.get("unit_gist") or understanding.get("central_question") or "",
        "explanation": (ctx.get("unit_text") or "")[:500],
        "criteria": criteria,
        "items": items,
        "teaching_strategy": {
            "skeleton": "role_budgeted",
            "understanding_version": "v2",
            "unit_gist": understanding.get("unit_gist") or "",
        },
        "repair_strategy_map": {
            "memory": "reencode",
            "confusion": "contrast",
            "missing_prereq": "spawn_prereq",
        },
    }


async def analyze_unit(
    session: AsyncSession,
    unit_id: str,
    *,
    stage1: Optional[StageFn] = None,
    stage2: Optional[StageFn] = None,
    prompt_version: str = "rule-v1",
    model_name: str = "rule",
) -> UnitLearningAssetModel:
    unit = (
        await session.execute(
            select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
        )
    ).scalar_one_or_none()
    if unit is None:
        raise ValueError(f"unit not found: {unit_id}")

    analysis_ctx = await build_analysis_context(session, unit_id)
    rev_id = analysis_ctx.document_revision_id
    block_dicts = analysis_ctx.unit_blocks
    source_hash = (block_dicts[0].get("id") if block_dicts else "empty") or "empty"
    # prefer content hash stability: use first block text length + unit id
    if block_dicts:
        import hashlib
        source_hash = "sha256:" + hashlib.sha256(
            (block_dicts[0].get("text") or "").encode("utf-8")
        ).hexdigest()
    idem = _job_key(unit_id, source_hash, prompt_version)

    existing_job = (
        await session.execute(
            select(AnalysisJobModel).where(AnalysisJobModel.idempotency_key == idem)
        )
    ).scalar_one_or_none()
    if existing_job and existing_job.status in ("succeeded", "degraded"):
        asset = (
            await session.execute(
                select(UnitLearningAssetModel).where(
                    UnitLearningAssetModel.unit_id == unit_id,
                    UnitLearningAssetModel.status == AssetStatus.ACTIVE.value,
                )
            )
        ).scalar_one_or_none()
        if asset:
            return asset

    job = existing_job or AnalysisJobModel(
        id=str(uuid4()),
        scope_type="unit",
        scope_id=unit_id,
        status="running",
        priority=5,
        idempotency_key=idem,
        attempt_count=0,
    )
    if existing_job is None:
        session.add(job)
    job.status = "running"
    job.attempt_count = (job.attempt_count or 0) + 1
    await session.flush()

    ctx = analysis_ctx.to_pipeline_ctx()

    s1 = stage1 or default_rule_stage1
    s2 = stage2 or default_rule_stage2
    understanding = await _maybe_await(s1(ctx))
    # Step3：v2 完整字段进 stage2；否则走 legacy 适配
    if (understanding or {}).get("understanding_version") == "v2":
        design_input = understanding
    else:
        design_input = to_legacy_view(understanding)
    design = await _maybe_await(s2(design_input, ctx))

    # Build evidence refs + claims（保留 understanding 中的 v2 字段）
    evidence_refs: list[EvidenceRef] = []
    claims: list[SourceClaim] = []
    block_by_id = {b["id"]: b for b in block_dicts}

    for raw_c in understanding.get("claims") or []:
        er_ids = []
        for raw_e in raw_c.get("evidence") or []:
            bid = raw_e.get("block_id")
            btxt = (block_by_id.get(bid) or {}).get("text") or ""
            start = int(raw_e.get("start_offset") or 0)
            end = int(raw_e.get("end_offset") or 0)
            quote = raw_e.get("quote") or ""
            er_id = raw_e.get("id") or str(uuid4())
            if btxt:
                vr = validate_evidence_ref(
                    block_text=btxt,
                    start_offset=start,
                    end_offset=end,
                    quote=quote,
                )
                vstatus = "valid" if vr.valid else vr.code
            else:
                vstatus = "missing_block"
            evidence_refs.append(
                EvidenceRef(
                    id=er_id,
                    document_revision_id=rev_id,
                    block_id=bid or "",
                    start_offset=start,
                    end_offset=end,
                    quote=quote,
                    validation_status=vstatus,
                )
            )
            er_ids.append(er_id)
        support = "supported" if er_ids and all(
            next((e for e in evidence_refs if e.id == i), None)
            and next(e for e in evidence_refs if e.id == i).validation_status
            in ("valid", "ok_whitespace_normalized", "unchecked")
            for i in er_ids
        ) else "unsupported"
        # tighten: only valid counts
        if er_ids:
            ok_all = True
            for i in er_ids:
                e = next((x for x in evidence_refs if x.id == i), None)
                if e is None or e.validation_status not in ("valid", "ok_whitespace_normalized"):
                    ok_all = False
                    break
            support = "supported" if ok_all else "unsupported"
        claims.append(
            SourceClaim(
                id=raw_c.get("id") or str(uuid4()),
                claim_type=raw_c.get("claim_type") or "fact",
                importance=Importance(raw_c.get("importance") or "required"),
                text=raw_c.get("text") or "",
                evidence_ref_ids=er_ids,
                support_status=support,
                role_in_book=raw_c.get("role_in_book"),
                mastery_check=raw_c.get("mastery_check"),
                related_concepts=list(raw_c.get("related_concepts") or []),
            )
        )

    objectives = [
        LearningObjective(
            id=o.get("id") or str(uuid4()),
            description=o.get("description") or "",
            ability=Ability(o.get("ability") or "recall"),
            importance=Importance(o.get("importance") or "required"),
            source_claim_ids=list(o.get("source_claim_ids") or []),
            cognitive_level=o.get("cognitive_level"),
        )
        for o in understanding.get("objectives") or []
    ]
    criteria = [
        AssessmentCriterion(
            id=c.get("id") or str(uuid4()),
            objective_id=c.get("objective_id") or (objectives[0].id if objectives else ""),
            observable_behavior=c.get("observable_behavior") or "",
            pass_threshold=float(c.get("pass_threshold") or 0.8),
        )
        for c in design.get("criteria") or []
    ]
    items = [
        AssessmentItem(
            id=it.get("id") or str(uuid4()),
            objective_ids=list(it.get("objective_ids") or []),
            criterion_ids=list(it.get("criterion_ids") or []),
            item_type=it.get("item_type") or "short_answer",
            stem=it.get("stem") or "",
            expected_answer=it.get("expected_answer") or "",
            ability=Ability(it.get("ability") or "recall"),
            phase_usage=list(it.get("phase_usage") or ["assessment"]),
            equivalence_group_id=it.get("equivalence_group_id"),
            scoring_rubric=dict(it.get("scoring_rubric") or {}),
            # claim_id 进 rubric 扩展，兼容无该字段的旧模型
        )
        for it in design.get("items") or []
    ]
    # 把 claim_id 写入 scoring_rubric（若 stage2 提供）
    for it_raw, it_model in zip(design.get("items") or [], items):
        cid = it_raw.get("claim_id")
        if cid:
            rub = dict(it_model.scoring_rubric or {})
            rub.setdefault("claim_id", cid)
            if it_raw.get("scoring_rubric", {}).get("mastery_check"):
                rub.setdefault("mastery_check", it_raw["scoring_rubric"]["mastery_check"])
            it_model.scoring_rubric = rub

    payload = UnitLearningAssetPayload(
        unit_type=understanding.get("unit_type") or "concept",
        central_question=understanding.get("central_question") or understanding.get("unit_gist") or "",
        claims=claims,
        learning_objectives=objectives,
        assessment_criteria=criteria,
        assessment_items=items,
        evidence_refs=evidence_refs,
        teaching_strategy=design.get("teaching_strategy") or {},
        repair_strategy_map=design.get("repair_strategy_map") or {},
        summary=design.get("summary") or "",
        explanation=design.get("explanation") or "",
        understanding_version=understanding.get("understanding_version") or "v1",
        unit_gist=understanding.get("unit_gist") or "",
        content_hash=understanding.get("content_hash") or "",
        overview_injected=bool(understanding.get("overview_injected")),
    )

    decision = evaluate_payload_readiness(payload)
    readiness = decision.readiness
    assess_val = validate_assessment_payload(payload)
    if not assess_val.ok and readiness != ReadinessStatus.INVALID:
        # 题目 hard 失败 → 最多降为 degraded（事实证据仍在）
        readiness = ReadinessStatus.DEGRADED_TEACHABLE

    # version
    last = (
        await session.execute(
            select(UnitLearningAssetModel)
            .where(UnitLearningAssetModel.unit_id == unit_id)
            .order_by(UnitLearningAssetModel.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    version = (last.version + 1) if last else 1

    # supersede previous active
    prev_actives = (
        await session.execute(
            select(UnitLearningAssetModel).where(
                UnitLearningAssetModel.unit_id == unit_id,
                UnitLearningAssetModel.status == AssetStatus.ACTIVE.value,
            )
        )
    ).scalars().all()
    for a in prev_actives:
        a.status = AssetStatus.SUPERSEDED.value

    status = AssetStatus.ACTIVE.value
    if readiness == ReadinessStatus.INVALID:
        status = AssetStatus.INVALID.value

    asset = UnitLearningAssetModel(
        id=str(uuid4()),
        unit_id=unit_id,
        version=version,
        status=status,
        readiness_status=readiness.value,
        freshness_status=FreshnessStatus.CURRENT.value,
        quality_score=decision.quality_score,
        quality_profile="generic_structured_nonfiction_v1",
        quality_algorithm_version="quality-v1",
        document_revision_id=rev_id,
        payload_json=payload.model_dump_json(),
        schema_version="unit-asset-v1",
        prompt_version=prompt_version,
        model_name=model_name,
        analysis_job_id=job.id,
        published_at=_utc_now() if status == AssetStatus.ACTIVE.value else None,
    )
    session.add(asset)

    job.status = (
        "succeeded"
        if readiness == ReadinessStatus.TEACHABLE
        else ("degraded" if readiness == ReadinessStatus.DEGRADED_TEACHABLE else "failed")
    )
    job.quality_result_json = json.dumps(
        {
            "readiness": readiness.value,
            "quality_score": decision.quality_score,
            "checks": [c.__dict__ for c in decision.checks],
            "assessment_checks": [c.__dict__ for c in assess_val.checks],
            "sent_block_ids": analysis_ctx.sent_block_ids,
        },
        ensure_ascii=False,
    )
    await session.flush()

    if status == AssetStatus.ACTIVE.value:
        await dual_write_unit_columns(session, unit_id, payload)

    logger.info(
        "analyze_unit done unit=%s asset=%s readiness=%s job=%s",
        unit_id,
        asset.id,
        readiness.value,
        job.status,
    )
    return asset
