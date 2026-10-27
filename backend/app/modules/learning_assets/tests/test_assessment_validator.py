from app.modules.learning_assets.assessment_validator import validate_assessment_payload
from app.modules.learning_assets.models_domain import (
    Ability,
    AssessmentCriterion,
    AssessmentItem,
    Importance,
    LearningObjective,
    UnitLearningAssetPayload,
)


def test_assessment_requires_item_per_required_objective():
    payload = UnitLearningAssetPayload(
        learning_objectives=[
            LearningObjective(
                id="o1",
                description="能复述定义",
                ability=Ability.RECALL,
                importance=Importance.REQUIRED,
            )
        ],
        assessment_criteria=[],
        assessment_items=[],
    )
    result = validate_assessment_payload(payload)
    assert result.ok is False
    assert any(not c.passed and c.code.startswith("A1_") for c in result.checks)


def test_assessment_ok_with_item_and_criterion():
    payload = UnitLearningAssetPayload(
        learning_objectives=[
            LearningObjective(
                id="o1",
                description="能复述定义",
                ability=Ability.RECALL,
                importance=Importance.REQUIRED,
            )
        ],
        assessment_criteria=[
            AssessmentCriterion(
                id="cr1",
                objective_id="o1",
                observable_behavior="写出定义",
            )
        ],
        assessment_items=[
            AssessmentItem(
                id="it1",
                objective_ids=["o1"],
                criterion_ids=["cr1"],
                stem="什么是 X？",
                expected_answer="Y",
                item_type="short_answer",
                equivalence_group_id="eq1",
            ),
            AssessmentItem(
                id="it2",
                objective_ids=["o1"],
                criterion_ids=["cr1"],
                stem="再用一句话解释 X",
                expected_answer="Y",
                item_type="short_answer",
                phase_usage=["reassessment"],
                equivalence_group_id="eq1",
            ),
        ],
    )
    result = validate_assessment_payload(payload)
    assert result.ok is True
