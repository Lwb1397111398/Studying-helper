from app.modules.learning_assets.models_domain import (
    Ability,
    AssessmentCriterion,
    AssessmentItem,
    EvidenceRef,
    Importance,
    LearningObjective,
    ReadinessStatus,
    SourceClaim,
    UnitLearningAssetPayload,
)
from app.modules.learning_assets.readiness import evaluate_payload_readiness


def _base_payload(**kwargs) -> UnitLearningAssetPayload:
    ref = EvidenceRef(
        id="er1",
        document_revision_id="rev1",
        block_id="blk1",
        start_offset=0,
        end_offset=4,
        quote="光合",
        validation_status="valid",
    )
    claim = SourceClaim(
        id="c1",
        text="光合作用定义",
        importance=Importance.REQUIRED,
        evidence_ref_ids=["er1"],
        support_status="supported",
    )
    obj = LearningObjective(
        id="o1",
        description="能用自己的话说明光合作用的定义",
        ability=Ability.EXPLAIN,
        importance=Importance.REQUIRED,
        source_claim_ids=["c1"],
    )
    crit = AssessmentCriterion(
        id="cr1",
        objective_id="o1",
        observable_behavior="口头或书面给出正确定义",
        pass_threshold=0.8,
    )
    item = AssessmentItem(
        id="it1",
        objective_ids=["o1"],
        criterion_ids=["cr1"],
        stem="什么是光合作用？",
        expected_answer="植物利用光能转化有机物",
        ability=Ability.EXPLAIN,
        phase_usage=["assessment"],
    )
    item_apply = AssessmentItem(
        id="it2",
        objective_ids=["o1"],
        criterion_ids=["cr1"],
        stem="给出一个光合作用应用场景",
        expected_answer="大棚补光增产",
        ability=Ability.APPLY,
        phase_usage=["assessment"],
    )
    data = dict(
        claims=[claim],
        learning_objectives=[obj],
        assessment_criteria=[crit],
        assessment_items=[item, item_apply],
        evidence_refs=[ref],
        central_question="什么是光合作用？",
    )
    data.update(kwargs)
    return UnitLearningAssetPayload(**data)


def test_teachable_when_required_supported():
    d = evaluate_payload_readiness(_base_payload())
    assert d.readiness == ReadinessStatus.TEACHABLE


def test_invalid_when_required_claim_unsupported():
    p = _base_payload()
    p.claims[0].support_status = "unsupported"
    d = evaluate_payload_readiness(p)
    assert d.readiness == ReadinessStatus.INVALID


def test_degraded_when_missing_high_order_only():
    # base already may lack apply/transfer — ensure degraded path with supporting fail
    p = _base_payload()
    p.claims.append(
        SourceClaim(
            id="c2",
            text="次要观点",
            importance=Importance.SUPPORTING,
            evidence_ref_ids=[],
            support_status="unsupported",
        )
    )
    # add another supporting unsupported to drop ratio
    p.claims.append(
        SourceClaim(
            id="c3",
            text="再次要",
            importance=Importance.SUPPORTING,
            evidence_ref_ids=[],
            support_status="unsupported",
        )
    )
    d = evaluate_payload_readiness(p)
    assert d.readiness in (ReadinessStatus.DEGRADED_TEACHABLE, ReadinessStatus.TEACHABLE)
    # two supporting unsupported → ratio 0 → degraded
    assert d.readiness == ReadinessStatus.DEGRADED_TEACHABLE
