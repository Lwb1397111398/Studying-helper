"""Teaching Session v2：绑定 asset、状态机推进、Attempt/Evidence。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    LearningAttemptModel,
    LearningEvidenceModel,
    MasteryRecordModel,
    TeachingSessionModel,
    UnitLearningAssetModel,
)
from app.modules.learning_assets.models_domain import UnitLearningAssetPayload
from app.modules.teaching import state_machine_v2 as sm

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionV2Error(Exception):
    def __init__(self, message: str, code: str = "session_error"):
        super().__init__(message)
        self.code = code
        self.message = message


async def start_session_v2(
    session: AsyncSession,
    *,
    user_id: str,
    book_id: str,
    unit_id: str,
    asset_id: Optional[str] = None,
) -> TeachingSessionModel:
    q = select(UnitLearningAssetModel).where(UnitLearningAssetModel.unit_id == unit_id)
    if asset_id:
        q = q.where(UnitLearningAssetModel.id == asset_id)
    else:
        q = q.where(UnitLearningAssetModel.status == "active")
    asset = (await session.execute(q)).scalar_one_or_none()
    if asset is None:
        raise SessionV2Error("no active asset", "ASSET_PENDING")
    if asset.readiness_status not in ("teachable", "degraded_teachable"):
        raise SessionV2Error(
            f"asset readiness={asset.readiness_status}",
            "ASSET_INVALID" if asset.readiness_status == "invalid" else "ASSET_PENDING",
        )
    if asset.freshness_status and asset.freshness_status != "current":
        raise SessionV2Error("asset stale", "ASSET_STALE")

    payload = UnitLearningAssetPayload.model_validate_json(asset.payload_json or "{}")
    plan_snapshot = {
        "schema_version": "plan-snapshot-v1",
        "objective_ids": [o.id for o in payload.learning_objectives],
        "assessment_item_ids": [i.id for i in payload.assessment_items],
        "asset_id": asset.id,
        "created_at": _utc_now().isoformat(),
    }

    tr = sm.transition("?", sm.SESSION_STARTED)
    ts = TeachingSessionModel(
        id=str(uuid4()),
        user_id=user_id,
        plan_session_id="",
        book_id=book_id,
        unit_ids=json.dumps([unit_id], ensure_ascii=False),
        primary_unit_id=unit_id,
        current_unit_index=0,
        current_phase="activate",
        strategy_json="{}",
        status="active",
        asset_id=asset.id,
        state_v2=tr.next_state,
        completion_status=tr.completion_status or "in_progress",
        plan_snapshot_json=json.dumps(plan_snapshot, ensure_ascii=False),
    )
    session.add(ts)
    await session.flush()

    # prepare → diagnose if asset ready
    tr2 = sm.transition(
        ts.state_v2,
        sm.ASSET_READY,
        {"asset_readiness": asset.readiness_status},
    )
    ts.state_v2 = tr2.next_state
    if tr2.completion_status:
        ts.completion_status = tr2.completion_status
    await session.flush()
    return ts


async def apply_event(
    session: AsyncSession,
    session_id: str,
    event: str,
    guards: Optional[dict[str, Any]] = None,
) -> TeachingSessionModel:
    ts = (
        await session.execute(
            select(TeachingSessionModel).where(TeachingSessionModel.id == session_id)
        )
    ).scalar_one_or_none()
    if ts is None:
        raise SessionV2Error("session not found", "NOT_FOUND")
    state = ts.state_v2 or sm.PREPARE
    g = dict(guards or {})
    # auto load required_objectives_passed from evidences if not provided
    if "required_objectives_passed" not in g and ts.asset_id:
        g["required_objectives_passed"] = await _required_passed(session, ts)

    tr = sm.transition(state, event, g)
    if not tr.accepted and tr.next_state == state and event not in (sm.USER_ASKED,):
        if event != sm.USER_ASKED:
            raise SessionV2Error(tr.message or "invalid transition", "INVALID_TRANSITION")

    ts.state_v2 = tr.next_state
    if tr.completion_status:
        ts.completion_status = tr.completion_status
    if tr.pause_reason:
        ts.pause_reason = tr.pause_reason
    if tr.next_state == sm.PAUSED:
        ts.status = "paused"

    skip_mastery = (
        "do_not_mark_mastered" in tr.side_effects
        or (ts.completion_status or "") in ("visited_only", "skipped")
        or event in (sm.ASSESSMENT_SKIPPED, sm.UNIT_SKIPPED)
    )
    frozen_completion = ts.completion_status if skip_mastery else None

    if tr.next_state == sm.COMPLETED:
        ts.status = "completed"
        ts.ended_at = _utc_now()
        if "project_mastery" in tr.side_effects and not skip_mastery:
            await _project_mastery(session, ts)

    # reflect/schedule auto-chain once
    if ts.state_v2 == sm.REFLECT:
        tr3 = sm.transition(sm.REFLECT, sm.EXPLANATION_ACKNOWLEDGED, g)
        ts.state_v2 = tr3.next_state
    if ts.state_v2 == sm.SCHEDULE_REVIEW:
        g2 = dict(g)
        g2.setdefault(
            "required_objectives_passed",
            await _required_passed(session, ts),
        )
        tr4 = sm.transition(sm.SCHEDULE_REVIEW, sm.EXPLANATION_ACKNOWLEDGED, g2)
        ts.state_v2 = tr4.next_state
        if frozen_completion:
            ts.completion_status = frozen_completion
        elif tr4.completion_status:
            ts.completion_status = tr4.completion_status
        if tr4.next_state == sm.COMPLETED:
            ts.status = "completed"
            ts.ended_at = _utc_now()
            if not skip_mastery and not frozen_completion:
                await _project_mastery(session, ts)
            elif frozen_completion:
                # keep visited_only/skipped — never project mastery
                ts.completion_status = frozen_completion
    await session.flush()
    return ts


async def submit_attempt(
    session: AsyncSession,
    *,
    session_id: str,
    user_id: str,
    assessment_item_id: str,
    response: dict[str, Any],
    idempotency_key: str,
    source_type: str = "assessment",
    device_id: Optional[str] = None,
) -> dict[str, Any]:
    ts = (
        await session.execute(
            select(TeachingSessionModel).where(TeachingSessionModel.id == session_id)
        )
    ).scalar_one_or_none()
    if ts is None:
        raise SessionV2Error("session not found", "NOT_FOUND")

    existing = (
        await session.execute(
            select(LearningAttemptModel).where(
                LearningAttemptModel.user_id == user_id,
                LearningAttemptModel.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        ev = (
            await session.execute(
                select(LearningEvidenceModel).where(
                    LearningEvidenceModel.attempt_id == existing.id,
                    LearningEvidenceModel.status == "active",
                )
            )
        ).scalars().all()
        return {
            "attempt_id": existing.id,
            "idempotent": True,
            "evidences": [_ev_dict(e) for e in ev],
        }

    asset = (
        await session.execute(
            select(UnitLearningAssetModel).where(
                UnitLearningAssetModel.id == ts.asset_id
            )
        )
    ).scalar_one_or_none()
    if asset is None:
        raise SessionV2Error("asset missing on session", "ASSET_PENDING")
    payload = UnitLearningAssetPayload.model_validate_json(asset.payload_json or "{}")
    item = next((i for i in payload.assessment_items if i.id == assessment_item_id), None)
    if item is None:
        raise SessionV2Error("assessment item not in asset", "INVALID_ITEM")

    attempt = LearningAttemptModel(
        id=str(uuid4()),
        user_id=user_id,
        session_id=session_id,
        assessment_item_id=assessment_item_id,
        response_json=json.dumps(response, ensure_ascii=False),
        idempotency_key=idempotency_key,
        device_id=device_id,
        status="evaluated",
    )
    session.add(attempt)
    await session.flush()

    answer = str(response.get("answer", "")).strip()
    expected = (item.expected_answer or "").strip()
    # simple rule score
    if item.item_type in ("multiple_choice", "true_false"):
        correct = answer == expected
        score = 1.0 if correct else 0.0
    else:
        # short answer: containment heuristic
        if not expected:
            score = 0.5
            correct = False
        else:
            correct = expected in answer or answer in expected
            score = 1.0 if correct else (0.5 if answer and expected[:4] in answer else 0.0)

    result = "correct" if score >= 0.8 else ("partial" if score >= 0.5 else "incorrect")
    objective_id = (item.objective_ids or ["unknown"])[0]
    criterion_id = (item.criterion_ids or [None])[0]

    # supersede previous active for same attempt/objective — first write only
    evidence = LearningEvidenceModel(
        id=str(uuid4()),
        attempt_id=attempt.id,
        user_id=user_id,
        book_id=ts.book_id,
        unit_id=ts.primary_unit_id or json.loads(ts.unit_ids or "[]")[0],
        objective_id=objective_id,
        criterion_id=criterion_id,
        session_id=session_id,
        source_type=source_type,
        question_id=assessment_item_id,
        claim_id=(item.scoring_rubric or {}).get("claim_id") if getattr(item, "scoring_rubric", None) else None,
        ability=item.ability.value if hasattr(item.ability, "value") else str(item.ability),
        result=result,
        score=score,
        error_type=None if correct else "memory",
        evaluator_type="rule",
        evaluator_version="rule-v1",
        evaluation_revision=1,
        status="active",
    )
    session.add(evidence)
    await session.flush()
    return {
        "attempt_id": attempt.id,
        "idempotent": False,
        "evidences": [_ev_dict(evidence)],
        "score": score,
        "result": result,
    }


async def _required_passed(session: AsyncSession, ts: TeachingSessionModel) -> bool:
    if not ts.asset_id:
        return False
    asset = (
        await session.execute(
            select(UnitLearningAssetModel).where(UnitLearningAssetModel.id == ts.asset_id)
        )
    ).scalar_one_or_none()
    if asset is None:
        return False
    payload = UnitLearningAssetPayload.model_validate_json(asset.payload_json or "{}")
    required = [o for o in payload.learning_objectives if o.importance.value == "required" or o.importance == "required"]
    if not required:
        return False
    for o in required:
        evs = (
            await session.execute(
                select(LearningEvidenceModel).where(
                    LearningEvidenceModel.session_id == ts.id,
                    LearningEvidenceModel.objective_id == o.id,
                    LearningEvidenceModel.status == "active",
                    LearningEvidenceModel.source_type.in_(["assessment", "reassessment"]),
                )
            )
        ).scalars().all()
        best = max((e.score for e in evs), default=0.0)
        if best < (o.required_score or 0.8):
            return False
    return True


async def _project_mastery(session: AsyncSession, ts: TeachingSessionModel) -> None:
    unit_id = ts.primary_unit_id
    if not unit_id:
        ids = json.loads(ts.unit_ids or "[]")
        unit_id = ids[0] if ids else None
    if not unit_id:
        return
    passed = await _required_passed(session, ts)
    score = 0.9 if passed else 0.4
    level = "mastered" if passed else "learning"
    if ts.completion_status in ("visited_only", "skipped"):
        return
    rec = (
        await session.execute(
            select(MasteryRecordModel).where(
                MasteryRecordModel.user_id == ts.user_id,
                MasteryRecordModel.knowledge_unit_id == unit_id,
            )
        )
    ).scalar_one_or_none()
    now = _utc_now()
    if rec is None:
        session.add(
            MasteryRecordModel(
                id=str(uuid4()),
                user_id=ts.user_id,
                knowledge_unit_id=unit_id,
                book_id=ts.book_id,
                mastery_score=score,
                mastery_level=level,
                next_review_at=now,
                last_reviewed_at=now,
            )
        )
    else:
        rec.mastery_score = max(rec.mastery_score or 0, score)
        rec.mastery_level = level
        rec.last_reviewed_at = now
    await session.flush()


def _ev_dict(e: LearningEvidenceModel) -> dict[str, Any]:
    return {
        "id": e.id,
        "attempt_id": e.attempt_id,
        "objective_id": e.objective_id,
        "claim_id": getattr(e, "claim_id", None),
        "score": e.score,
        "result": e.result,
        "source_type": e.source_type,
        "status": e.status,
    }
