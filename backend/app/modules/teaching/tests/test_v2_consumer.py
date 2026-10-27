"""Step3：教学侧 v2 消费测试。"""

from __future__ import annotations

import json

import pytest

from app.modules.learning_assets.models_domain import (
    Importance,
    SourceClaim,
    UnitLearningAssetPayload,
    LearningObjective,
    Ability,
    AssessmentItem,
    AssessmentCriterion,
)
from app.modules.learning_assets.pipeline import default_rule_stage2, _stage2_from_v2
from app.modules.learning_assets.assessment_validator import validate_assessment_payload
from app.modules.learning_assets.understanding import to_legacy_view
from app.modules.teaching.v2_consumer import (
    V2TeachingContext,
    build_explain_budget_block,
    build_check_claims_block,
    build_reflect_connect_block,
    pick_feynman_mastery_checks,
    COG_QUESTION_HINT,
)
from app.modules.teaching.prompts import (
    EXPLAIN_PROMPT_V2,
    CHECK_PROMPT_V2,
    GRADE_PROMPT_V2,
    REFLECT_PROMPT_V2,
    FEYNMAN_EXPLAIN_PROMPT_V2,
)


def _v2_understanding():
    return {
        "understanding_version": "v2",
        "unit_gist": "本单元阐明反向传播如何支撑全书可训练性论点",
        "central_question": "本单元阐明反向传播如何支撑全书可训练性论点",
        "claims": [
            {
                "id": "c1",
                "claim_type": "principle",
                "importance": "required",
                "text": "反向传播用链式法则算梯度",
                "role_in_book": "key_mechanism",
                "mastery_check": "能用自己的话解释反向传播如何借助链式法则计算梯度",
                "related_concepts": ["反向传播", "链式法则"],
            },
            {
                "id": "c2",
                "claim_type": "fact",
                "importance": "required",
                "text": "深层网络可能梯度消失",
                "role_in_book": "core_thesis_support",
                "mastery_check": "能说明层数增加为何加剧梯度消失",
                "related_concepts": ["梯度消失"],
            },
            {
                "id": "c3",
                "claim_type": "fact",
                "importance": "supporting",
                "text": "插图仅为示意",
                "role_in_book": "tangential",
                "mastery_check": "能指出插图不是证明",
                "related_concepts": [],
            },
        ],
        "objectives": [
            {
                "id": "o1",
                "description": "解释反向传播",
                "ability": "explain",
                "importance": "required",
                "source_claim_ids": ["c1", "c2"],
                "cognitive_level": "understand",
                "covers_claims": [0, 1],
            }
        ],
    }


def test_stage2_v2_covers_required_not_tangential():
    design = default_rule_stage2(_v2_understanding(), {"unit_text": "正文" * 20})
    claim_ids = {
        (it.get("scoring_rubric") or {}).get("claim_id")
        for it in design["items"]
        if (it.get("scoring_rubric") or {}).get("claim_id")
    }
    assert "c1" in claim_ids
    assert "c2" in claim_ids
    assert "c3" not in claim_ids  # tangential 不出题
    # 每 claim 至少 assessment + reassess
    assert len([i for i in design["items"] if (i.get("scoring_rubric") or {}).get("claim_id") == "c1"]) >= 2


def test_stage2_v1_unchanged_shape():
    legacy = to_legacy_view(_v2_understanding())
    design = default_rule_stage2(legacy, {"unit_text": "x"})
    assert design["items"][0]["id"] == "it_auto_1"
    assert "claim_id" not in (design["items"][0].get("scoring_rubric") or {})


def test_assessment_validator_a11_mastery_coverage():
    understanding = _v2_understanding()
    design = default_rule_stage2(understanding, {"unit_text": "x"})
    claims = [
        SourceClaim(
            id=c["id"],
            claim_type=c["claim_type"],
            importance=Importance(c["importance"]),
            text=c["text"],
            role_in_book=c["role_in_book"],
            mastery_check=c["mastery_check"],
            related_concepts=c.get("related_concepts") or [],
            support_status="supported",
        )
        for c in understanding["claims"]
    ]
    objectives = [
        LearningObjective(
            id="o1",
            description="解释",
            ability=Ability.EXPLAIN,
            importance=Importance.REQUIRED,
            source_claim_ids=["c1", "c2"],
            cognitive_level="understand",
        )
    ]
    items = [
        AssessmentItem(
            id=it["id"],
            objective_ids=it["objective_ids"],
            criterion_ids=it["criterion_ids"],
            item_type=it["item_type"],
            stem=it["stem"],
            expected_answer=it["expected_answer"],
            ability=Ability(it["ability"]),
            phase_usage=it["phase_usage"],
            equivalence_group_id=it.get("equivalence_group_id"),
            scoring_rubric=it.get("scoring_rubric") or {},
        )
        for it in design["items"]
    ]
    criteria = [
        AssessmentCriterion(
            id=c["id"],
            objective_id=c["objective_id"],
            observable_behavior=c["observable_behavior"],
            pass_threshold=c.get("pass_threshold", 0.8),
        )
        for c in design["criteria"]
    ]
    payload = UnitLearningAssetPayload(
        understanding_version="v2",
        claims=claims,
        learning_objectives=objectives,
        assessment_items=items,
        assessment_criteria=criteria,
        unit_gist=understanding["unit_gist"],
    )
    result = validate_assessment_payload(payload)
    a11 = [c for c in result.checks if c.code.startswith("A11_")]
    assert a11, "should have A11 checks"
    assert all(c.passed for c in a11 if "c3" not in c.code)
    # c3 tangential 不应要求覆盖
    assert not any(c.code.endswith(":c3") for c in a11)


def test_assessment_validator_a11_fails_when_missing_item():
    claims = [
        SourceClaim(
            id="c1",
            text="命题",
            importance=Importance.REQUIRED,
            role_in_book="key_mechanism",
            mastery_check="能解释命题",
            support_status="supported",
        )
    ]
    payload = UnitLearningAssetPayload(
        understanding_version="v2",
        claims=claims,
        learning_objectives=[
            LearningObjective(
                id="o1",
                description="x",
                ability=Ability.EXPLAIN,
                importance=Importance.REQUIRED,
                source_claim_ids=["c1"],
            )
        ],
        assessment_items=[
            AssessmentItem(
                id="it1",
                objective_ids=["o1"],
                criterion_ids=["cr1"],
                stem="无关题",
                expected_answer="a",
                ability=Ability.RECALL,
                scoring_rubric={},  # 无 claim_id
            )
        ],
        assessment_criteria=[
            AssessmentCriterion(id="cr1", objective_id="o1", observable_behavior="x")
        ],
    )
    result = validate_assessment_payload(payload)
    a11 = [c for c in result.checks if c.code.startswith("A11_") and not c.passed]
    assert a11


def test_explain_budget_skips_tangential_instruction():
    ctx = V2TeachingContext(
        available=True,
        understanding_version="v2",
        unit_gist="角色",
        core_thesis="全书论点",
        claims=[
            SourceClaim(id="c1", text="核心机制", role_in_book="key_mechanism", mastery_check="能解释机制", importance=Importance.REQUIRED),
            SourceClaim(id="c2", text="插图", role_in_book="tangential", mastery_check="能指出示意", importance=Importance.SUPPORTING),
        ],
        required_claims=[
            SourceClaim(id="c1", text="核心机制", role_in_book="key_mechanism", mastery_check="能解释机制", importance=Importance.REQUIRED),
        ],
    )
    block = build_explain_budget_block(ctx)
    assert "key_mechanism" in block
    assert "跳过" in block or "一句带过" in block
    assert "全书论点" in block
    # prompt 可 format
    prompt = EXPLAIN_PROMPT_V2.format(
        title="t", summary="s", concepts="无",
        explanation_style="balanced",
        teaching_style="explain_then_probe",
        scaffold_level="partial",
        budget_block=block,
    )
    assert "讲解预算" in prompt


def test_check_block_maps_cognitive_levels():
    ctx = V2TeachingContext(
        available=True,
        understanding_version="v2",
        claims=[
            SourceClaim(id="c1", text="A", role_in_book="key_mechanism", mastery_check="能解释A", importance=Importance.REQUIRED),
        ],
        required_claims=[
            SourceClaim(id="c1", text="A", role_in_book="key_mechanism", mastery_check="能解释A", importance=Importance.REQUIRED),
        ],
        payload=UnitLearningAssetPayload(
            understanding_version="v2",
            learning_objectives=[
                LearningObjective(
                    id="o1", description="d", ability=Ability.EXPLAIN,
                    source_claim_ids=["c1"], cognitive_level="apply",
                )
            ],
        ),
    )
    block = build_check_claims_block(ctx)
    assert "mastery_check" in block
    assert "apply" in block
    assert COG_QUESTION_HINT["apply"].split("：")[0] in block or "举例" in block


def test_reflect_connect_only_known_concepts():
    ctx = V2TeachingContext(
        available=True,
        understanding_version="v2",
        claims=[
            SourceClaim(
                id="c1", text="x", role_in_book="key_mechanism",
                mastery_check="能解释", related_concepts=["链式法则", "不存在的概念"],
            )
        ],
        required_claims=[],
        overview_key_concepts=[
            {"name": "链式法则", "definition": "复合函数求导法则", "first_chapter_id": "ch1"},
        ],
    )
    block = build_reflect_connect_block(ctx)
    assert "链式法则" in block
    assert "不存在的概念" not in block
    assert "ch1" in block


def test_feynman_picks_explain_style_checks():
    ctx = V2TeachingContext(
        available=True,
        understanding_version="v2",
        required_claims=[
            SourceClaim(id="c1", text="a", mastery_check="能用自己的话解释反向传播", role_in_book="key_mechanism"),
            SourceClaim(id="c2", text="b", mastery_check="能举出一个例子", role_in_book="supporting_detail"),
        ],
        claims=[],
    )
    picks = pick_feynman_mastery_checks(ctx)
    assert any("自己的话" in p for p in picks)


def test_grade_prompt_v2_injects_rubric():
    p = GRADE_PROMPT_V2.format(
        question="请解释反向传播",
        mastery_check="能用自己的话解释反向传播如何借助链式法则计算梯度",
        claim_text="反向传播用链式法则算梯度",
        student_answer="就是一层层往回算导数",
        claim_id="c1",
    )
    assert "mastery_check" in p
    assert "c1" in p
    assert "链式法则" in p


def test_check_prompt_v2_format():
    p = CHECK_PROMPT_V2.format(summary="摘要", claims_block="## 待检验\n1. claim_id=c1")
    assert "mastery_check" in p
    assert "claim_id" in p


def test_version_fallback_ctx_not_v2():
    ctx = V2TeachingContext(available=False)
    assert ctx.is_v2 is False
    ctx2 = V2TeachingContext(available=True, understanding_version="v1", claims=[
        SourceClaim(id="c", text="t", importance=Importance.REQUIRED)
    ], required_claims=[SourceClaim(id="c", text="t")])
    assert ctx2.is_v2 is False  # version not v2
