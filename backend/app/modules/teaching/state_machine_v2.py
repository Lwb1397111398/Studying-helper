"""教学状态机 v2：状态 + 事件 + 守卫（纯函数，服务端掌权）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# States
PREPARE = "prepare"
DIAGNOSE = "diagnose"
ACTIVATE = "activate"
EXPLAIN = "explain"
GUIDED_PRACTICE = "guided_practice"
ASSESS = "assess"
REPAIR = "repair"
REASSESS = "reassess"
PREREQUISITE_INTERVENTION = "prerequisite_intervention"
REFLECT = "reflect"
SCHEDULE_REVIEW = "schedule_review"
COMPLETED = "completed"
PAUSED = "paused"

# Events
SESSION_STARTED = "SESSION_STARTED"
ASSET_READY = "ASSET_READY"
DIAGNOSIS_SUBMITTED = "DIAGNOSIS_SUBMITTED"
EXPLANATION_ACKNOWLEDGED = "EXPLANATION_ACKNOWLEDGED"
PRACTICE_SUBMITTED = "PRACTICE_SUBMITTED"
ASSESSMENT_SUBMITTED = "ASSESSMENT_SUBMITTED"
REPAIR_COMPLETED = "REPAIR_COMPLETED"
REASSESSMENT_SUBMITTED = "REASSESSMENT_SUBMITTED"
PREREQ_CHILD_COMPLETED = "PREREQ_CHILD_COMPLETED"
PREREQ_CHILD_FAILED = "PREREQ_CHILD_FAILED"
USER_ASKED = "USER_ASKED"
USER_PAUSED = "USER_PAUSED"
USER_RESUMED = "USER_RESUMED"
ASSESSMENT_SKIPPED = "ASSESSMENT_SKIPPED"
UNIT_SKIPPED = "UNIT_SKIPPED"
SESSION_TIMEOUT = "SESSION_TIMEOUT"


@dataclass
class TransitionResult:
    next_state: str
    completion_status: Optional[str] = None
    pause_reason: Optional[str] = None
    side_effects: List[str] = field(default_factory=list)
    accepted: bool = True
    message: str = ""


def transition(state: str, event: str, guards: Optional[Dict[str, Any]] = None) -> TransitionResult:
    """根据当前状态、事件与守卫决定下一状态。

    guards 常用键：
    - asset_readiness: teachable|degraded_teachable|invalid|pending|...
    - diagnosis_summary: strong|mixed|weak|already_mastered|missing_prereq
    - required_objectives_passed: bool
    - missing_prereq: bool
    - repairable_gaps: bool
    - repair_rounds: int
    - max_repair_rounds: int (default 3，配合三级提示阶梯)
    - interrupted_state: str (for resume)
    - child_outcome: mastered|completed_with_gaps|skipped|failed
    """
    g = guards or {}
    max_repair = int(g.get("max_repair_rounds", 3))
    repair_rounds = int(g.get("repair_rounds", 0))

    if event == USER_PAUSED:
        return TransitionResult(
            next_state=PAUSED,
            completion_status="in_progress",
            pause_reason="user_exit",
            side_effects=["save_interrupted_state"],
        )
    if event == SESSION_TIMEOUT:
        return TransitionResult(
            next_state=PAUSED,
            completion_status="in_progress",
            pause_reason="timeout",
        )
    if event == USER_RESUMED and state == PAUSED:
        return TransitionResult(
            next_state=g.get("interrupted_state") or PREPARE,
            completion_status="in_progress",
        )
    if event == USER_ASKED:
        return TransitionResult(
            next_state=state,
            side_effects=["handle_question_interrupt"],
            message="interrupt only; state unchanged",
        )

    if event == SESSION_STARTED:
        return TransitionResult(next_state=PREPARE, completion_status="in_progress")

    if state == PREPARE and event == ASSET_READY:
        readiness = g.get("asset_readiness", "pending")
        if readiness in ("teachable", "degraded_teachable"):
            return TransitionResult(next_state=DIAGNOSE)
        if readiness in ("pending", "stale", "understanding_ready"):
            return TransitionResult(
                next_state=PREPARE,
                accepted=True,
                side_effects=["enqueue_or_wait_analysis"],
                message="asset not ready",
            )
        return TransitionResult(
            next_state=PAUSED,
            completion_status="needs_support",
            pause_reason="asset_invalid",
            accepted=False,
            message="asset invalid",
        )

    if state == DIAGNOSE and event == DIAGNOSIS_SUBMITTED:
        summary = g.get("diagnosis_summary", "mixed")
        if summary == "missing_prereq" or g.get("missing_prereq"):
            return TransitionResult(
                next_state=PREREQUISITE_INTERVENTION,
                side_effects=["spawn_prereq_child"],
            )
        if summary == "already_mastered":
            return TransitionResult(
                next_state=ASSESS,
                side_effects=["challenge_assessment_optional"],
            )
        if summary == "strong":
            return TransitionResult(next_state=EXPLAIN, side_effects=["shorten_activate"])
        return TransitionResult(next_state=ACTIVATE)

    if state == ACTIVATE and event == EXPLANATION_ACKNOWLEDGED:
        return TransitionResult(next_state=EXPLAIN)

    if state == EXPLAIN and event == EXPLANATION_ACKNOWLEDGED:
        return TransitionResult(next_state=GUIDED_PRACTICE)

    if state == GUIDED_PRACTICE and event == PRACTICE_SUBMITTED:
        return TransitionResult(next_state=ASSESS)

    if state in (ASSESS, REASSESS) and event in (ASSESSMENT_SUBMITTED, REASSESSMENT_SUBMITTED):
        if g.get("required_objectives_passed"):
            return TransitionResult(next_state=REFLECT, side_effects=["mark_objectives_passed"])
        if g.get("missing_prereq"):
            return TransitionResult(
                next_state=PREREQUISITE_INTERVENTION,
                side_effects=["spawn_prereq_child"],
            )
        if g.get("repairable_gaps", True) and repair_rounds < max_repair:
            return TransitionResult(
                next_state=REPAIR,
                side_effects=["increment_repair_rounds"],
            )
        return TransitionResult(
            next_state=PAUSED,
            completion_status="needs_support",
            pause_reason="repeated_assessment_failure",
        )

    if state == REPAIR and event == REPAIR_COMPLETED:
        return TransitionResult(next_state=REASSESS)

    if state == PREREQUISITE_INTERVENTION and event == PREREQ_CHILD_COMPLETED:
        outcome = g.get("child_outcome", "mastered")
        if outcome == "mastered":
            return TransitionResult(next_state=REASSESS)
        if outcome == "completed_with_gaps":
            return TransitionResult(next_state=REPAIR)
        return TransitionResult(
            next_state=PAUSED,
            completion_status="needs_support",
            pause_reason="prereq_unresolved",
        )

    if state == PREREQUISITE_INTERVENTION and event == PREREQ_CHILD_FAILED:
        return TransitionResult(
            next_state=PAUSED,
            completion_status="needs_support",
            pause_reason="prereq_failed",
        )

    if state == REFLECT and event in (EXPLANATION_ACKNOWLEDGED, "REFLECT_DONE"):
        return TransitionResult(next_state=SCHEDULE_REVIEW)

    if state == SCHEDULE_REVIEW and event in (EXPLANATION_ACKNOWLEDGED, "SCHEDULE_DONE"):
        return TransitionResult(
            next_state=COMPLETED,
            completion_status="completed_mastered"
            if g.get("required_objectives_passed")
            else "completed_with_gaps",
            side_effects=["write_review_items", "project_mastery"],
        )

    # Auto-advance helpers for internal completion of reflect/schedule
    if state == REFLECT:
        return TransitionResult(next_state=SCHEDULE_REVIEW, side_effects=["generate_summary"])
    if state == SCHEDULE_REVIEW:
        return TransitionResult(
            next_state=COMPLETED,
            completion_status="completed_mastered"
            if g.get("required_objectives_passed", True)
            else "completed_with_gaps",
            side_effects=["write_review_items", "project_mastery"],
        )

    if event == ASSESSMENT_SKIPPED:
        return TransitionResult(
            next_state=REFLECT,
            completion_status="visited_only",
            side_effects=["do_not_mark_mastered"],
        )

    if event == UNIT_SKIPPED:
        return TransitionResult(
            next_state=COMPLETED,
            completion_status="skipped",
            side_effects=["do_not_mark_mastered"],
        )

    return TransitionResult(
        next_state=state,
        accepted=False,
        message=f"no transition for state={state} event={event}",
    )
