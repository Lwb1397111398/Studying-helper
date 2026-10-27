"""AssessmentItem / LearningObjective 程序校验（阶段 2.5）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.modules.learning_assets.models_domain import (
    Ability,
    Importance,
    UnitLearningAssetPayload,
)


@dataclass
class AssessmentCheck:
    code: str
    passed: bool
    level: str  # hard|soft
    message: str = ""


@dataclass
class AssessmentValidationResult:
    ok: bool
    checks: List[AssessmentCheck] = field(default_factory=list)

    @property
    def hard_failures(self) -> List[AssessmentCheck]:
        return [c for c in self.checks if c.level == "hard" and not c.passed]


def validate_assessment_payload(payload: UnitLearningAssetPayload) -> AssessmentValidationResult:
    checks: List[AssessmentCheck] = []
    objectives = payload.learning_objectives
    items = [i for i in payload.assessment_items if i.status == "active"]
    criteria = payload.assessment_criteria

    required_objs = [
        o for o in objectives
        if (o.importance == Importance.REQUIRED or o.importance == "required")
    ]

    for o in required_objs:
        has_item = any(o.id in (it.objective_ids or []) for it in items)
        checks.append(
            AssessmentCheck(
                code=f"A1_objective_has_item:{o.id}",
                passed=has_item,
                level="hard",
                message="each required objective needs >=1 active item",
            )
        )
        has_crit = any(c.objective_id == o.id for c in criteria)
        checks.append(
            AssessmentCheck(
                code=f"A10_objective_has_criterion:{o.id}",
                passed=has_crit,
                level="hard",
                message="required objective needs criterion",
            )
        )

    for it in items:
        if not it.objective_ids:
            checks.append(
                AssessmentCheck(
                    code=f"A2_item_objective:{it.id}",
                    passed=False,
                    level="hard",
                    message="item missing objective_ids",
                )
            )
        else:
            known = {o.id for o in objectives}
            ok = all(oid in known for oid in it.objective_ids)
            checks.append(
                AssessmentCheck(
                    code=f"A2_item_objective:{it.id}",
                    passed=ok,
                    level="hard",
                    message="objective_id must exist",
                )
            )

        if it.item_type in ("multiple_choice", "choice", "true_false"):
            # unique determinable answer
            if it.options and it.expected_answer:
                matches = [o for o in it.options if o == it.expected_answer]
                checks.append(
                    AssessmentCheck(
                        code=f"A3_unique_answer:{it.id}",
                        passed=len(matches) == 1 or it.expected_answer in it.options,
                        level="hard",
                        message="choice answer must be determinable",
                    )
                )
            elif not it.expected_answer:
                checks.append(
                    AssessmentCheck(
                        code=f"A3_unique_answer:{it.id}",
                        passed=False,
                        level="hard",
                        message="choice missing expected_answer",
                    )
                )

        if it.item_type in ("short_answer",):
            has_rubric = bool(it.scoring_rubric) or bool(it.expected_answer)
            checks.append(
                AssessmentCheck(
                    code=f"A5_short_rubric:{it.id}",
                    passed=has_rubric,
                    level="hard",
                    message="short_answer needs rubric or expected_answer",
                )
            )

        # stem should not equal answer literally for choice
        if it.expected_answer and it.stem and it.expected_answer.strip() and it.expected_answer in it.stem:
            checks.append(
                AssessmentCheck(
                    code=f"A6_leak:{it.id}",
                    passed=False,
                    level="hard",
                    message="stem leaks expected_answer",
                )
            )
        else:
            checks.append(
                AssessmentCheck(
                    code=f"A6_leak:{it.id}",
                    passed=True,
                    level="hard",
                )
            )

        ability = it.ability.value if hasattr(it.ability, "value") else str(it.ability)
        if ability in (Ability.APPLY.value, Ability.TRANSFER.value) and it.item_type in (
            "fill_blank",
            "true_false",
        ):
            checks.append(
                AssessmentCheck(
                    code=f"A9_high_order_type:{it.id}",
                    passed=False,
                    level="soft",
                    message="high-order ability with low-fidelity item type",
                )
            )

    # equivalence group for reassess soft
    groups: dict[str, int] = {}
    for it in items:
        if it.equivalence_group_id:
            groups[it.equivalence_group_id] = groups.get(it.equivalence_group_id, 0) + 1
    for gid, n in groups.items():
        checks.append(
            AssessmentCheck(
                code=f"A8_equivalence:{gid}",
                passed=n >= 2,
                level="soft",
                message="reassess group should have >=2 items",
            )
        )

    # Step3：v2 required claims 的 mastery_check 必须被题目覆盖
    if getattr(payload, "understanding_version", "v1") == "v2":
        required_claims = [
            c
            for c in (payload.claims or [])
            if (getattr(c, "role_in_book", None) or "") != "tangential"
        ]
        for c in required_claims:
            cid = c.id
            covered = False
            for it in items:
                rub = it.scoring_rubric or {}
                if rub.get("claim_id") == cid:
                    covered = True
                    break
                if c.mastery_check and c.mastery_check in (it.stem or ""):
                    covered = True
                    break
            checks.append(
                AssessmentCheck(
                    code=f"A11_mastery_check_covered:{cid}",
                    passed=covered,
                    level="hard",
                    message="each required claim mastery_check needs >=1 assessment item",
                )
            )

    hard_fail = any(c.level == "hard" and not c.passed for c in checks)
    return AssessmentValidationResult(ok=not hard_fail, checks=checks)
