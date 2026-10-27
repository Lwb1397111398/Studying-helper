"""根据校验结果决定 readiness_status。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.modules.learning_assets.models_domain import (
    Importance,
    ReadinessStatus,
    UnitLearningAssetPayload,
)


@dataclass
class CheckResult:
    code: str
    passed: bool
    level: str  # blocking|degradable|quality
    message: str = ""


@dataclass
class ReadinessDecision:
    readiness: ReadinessStatus
    checks: List[CheckResult] = field(default_factory=list)
    quality_score: float = 0.0


def evaluate_payload_readiness(payload: UnitLearningAssetPayload) -> ReadinessDecision:
    checks: List[CheckResult] = []
    refs = {r.id: r for r in payload.evidence_refs}
    claims = payload.claims
    objectives = payload.learning_objectives
    items = payload.assessment_items

    required_claims = [c for c in claims if c.importance == Importance.REQUIRED]
    supporting_claims = [c for c in claims if c.importance == Importance.SUPPORTING]
    required_objectives = [o for o in objectives if o.importance == Importance.REQUIRED]

    # Blocking: required claims supported + valid refs
    for c in required_claims:
        # Prefer explicit support_status after validator pass
        ok = c.support_status == "supported" and bool(c.evidence_ref_ids)
        if c.evidence_ref_ids:
            for rid in c.evidence_ref_ids:
                ref = refs.get(rid)
                if ref is None:
                    ok = False
                    break
                if ref.validation_status in ("offset_mismatch", "missing_block", "invalid_offsets", "offset_out_of_range"):
                    ok = False
                    break
        checks.append(
            CheckResult(
                code=f"required_claim:{c.id}",
                passed=ok,
                level="blocking",
                message=c.text[:80],
            )
        )

    if not required_claims:
        checks.append(
            CheckResult(
                code="required_claims_present",
                passed=False,
                level="blocking",
                message="no required claims",
            )
        )

    if not required_objectives:
        checks.append(
            CheckResult(
                code="required_objectives_present",
                passed=False,
                level="blocking",
                message="no required objectives",
            )
        )
    else:
        for o in required_objectives:
            vague = o.description.strip() in ("", "理解本章", "掌握知识", "学会本单元")
            checks.append(
                CheckResult(
                    code=f"objective_concrete:{o.id}",
                    passed=not vague and len(o.description.strip()) >= 4,
                    level="blocking",
                    message=o.description[:80],
                )
            )
            has_item = any(o.id in it.objective_ids and it.status == "active" for it in items)
            checks.append(
                CheckResult(
                    code=f"objective_has_item:{o.id}",
                    passed=has_item,
                    level="blocking",
                    message="missing assessment item",
                )
            )
            has_crit = any(cr.objective_id == o.id for cr in payload.assessment_criteria)
            checks.append(
                CheckResult(
                    code=f"objective_has_criterion:{o.id}",
                    passed=has_crit,
                    level="degradable",
                    message="missing criterion",
                )
            )

    # Supporting coverage
    if supporting_claims:
        sup_ok = sum(1 for c in supporting_claims if c.support_status == "supported")
        ratio = sup_ok / len(supporting_claims)
        checks.append(
            CheckResult(
                code="supporting_coverage",
                passed=ratio >= 0.6,
                level="degradable" if ratio >= 0.6 else "degradable",
                message=f"ratio={ratio:.2f}",
            )
        )
        if ratio < 0.6:
            checks[-1].passed = False

    # High-order items optional
    high = [it for it in items if it.ability.value in ("apply", "transfer", "differentiate")]
    if not high:
        checks.append(
            CheckResult(
                code="high_order_items",
                passed=False,
                level="degradable",
                message="no high-order items",
            )
        )
    else:
        checks.append(
            CheckResult(
                code="high_order_items",
                passed=True,
                level="quality",
            )
        )

    blocking_fail = [c for c in checks if c.level == "blocking" and not c.passed]
    degradable_fail = [c for c in checks if c.level == "degradable" and not c.passed]

    if blocking_fail:
        readiness = ReadinessStatus.INVALID
    elif degradable_fail:
        readiness = ReadinessStatus.DEGRADED_TEACHABLE
    else:
        readiness = ReadinessStatus.TEACHABLE

    # quality score auxiliary
    total = len(checks) or 1
    passed_n = sum(1 for c in checks if c.passed)
    quality = passed_n / total

    return ReadinessDecision(readiness=readiness, checks=checks, quality_score=quality)
