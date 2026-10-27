"""Step5：教学偏好消费 + 三级提示阶梯 + 风格指令。"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.teaching.hint_ladder import (
    build_repair_instruction,
    classify_error_type,
    fail_count_from_assessments,
    format_repair_assessment,
    hint_level_from_repair_rounds,
    next_hint_level,
    rule_based_repair_text,
    should_mark_review,
)
from app.modules.teaching.schemas import (
    DEFAULT_TEACHING_PREFS,
    TeachingStrategy,
    UserTeachingProfile,
)
from app.modules.teaching.strategies import (
    calibrate_session_minutes,
    select_teaching_strategy,
)
from app.modules.teaching.state_machine_v2 import (
    ASSESS,
    ASSESSMENT_SUBMITTED,
    PAUSED,
    REPAIR,
    transition,
)
from app.modules.adaptive_design.profile_builder import (
    _default_teaching_extra_json,
    teaching_prefs_from_profile,
)
from app.modules.teaching.prompts import EXPLAIN_PROMPT_V2, REPAIR_PROMPT_V2


def _unit(summary="测试", key_points=None, concepts=None, difficulty=3):
    from app.modules.ai_learning.schemas import (
        LearnedUnit, Concept as LConcept, KeyPoint, SelfAssessment, TestQuestion,
    )
    kps = key_points or ["要点"]
    kp_objects = [KeyPoint(title=k) if isinstance(k, str) else k for k in kps]
    return LearnedUnit(
        unit_id="u1", book_id="b1", summary=summary,
        key_points=kp_objects, concepts=concepts or [],
        difficulty_level=difficulty, importance_score=0.5,
        prerequisites=[],
        self_assessment=SelfAssessment(
            score=50,
            test_questions=[TestQuestion(
                question="q", question_type="short_answer",
                correct_answer="a", explanation="e",
            )],
            self_answers=[], weak_points=[], needs_deepening=False,
        ),
    )


class TestPreferenceConsumption:
    def test_default_prefs_constants(self):
        assert DEFAULT_TEACHING_PREFS["teaching_style"] == "explain_then_probe"
        assert DEFAULT_TEACHING_PREFS["hint_policy"] == "ladder"
        assert DEFAULT_TEACHING_PREFS["preferred_session_minutes"] == 25
        assert DEFAULT_TEACHING_PREFS["example_style"] == "example_first"

    def test_profile_defaults_flow_into_strategy(self):
        unit = _unit(difficulty=3)
        profile = UserTeachingProfile(avg_mastery_score=0.5)
        s = select_teaching_strategy(unit, profile)
        assert s.teaching_style == "explain_then_probe"
        assert s.hint_policy == "ladder"
        assert s.preferred_session_minutes == 25
        assert s.explanation_style == "example_first"  # example_style 默认
        assert s.interaction_frequency == "high"  # explain_then_probe

    def test_preferred_style_beats_example_style(self):
        from app.modules.ai_learning.schemas import Concept as LConcept
        unit = _unit(
            summary="什么是类",
            key_points=["类是模板"],
            concepts=[LConcept(name="类", definition="对象模板")],
            difficulty=2,
        )
        profile = UserTeachingProfile(
            avg_mastery_score=0.8,
            preferred_style="problem_based",
            example_style="example_first",
        )
        s = select_teaching_strategy(unit, profile)
        assert s.explanation_style == "problem_based"

    def test_no_profile_keeps_type_based_style(self):
        from app.modules.ai_learning.schemas import Concept as LConcept
        unit = _unit(
            summary="什么是多态",
            key_points=["多态的定义"],
            concepts=[LConcept(name="多态", definition="同一接口多种形式")],
            difficulty=3,
        )
        s = select_teaching_strategy(unit, None)
        assert s.explanation_style == "analogy"
        # 系统仍带推荐 hint_policy 默认写入 strategy（REPAIR 可用）
        assert s.hint_policy == "ladder"

    def test_calibrate_session_minutes(self):
        assert calibrate_session_minutes(None, 25) == 25
        assert calibrate_session_minutes(25, 25) == 25
        assert calibrate_session_minutes(50, 25) == 50
        assert calibrate_session_minutes(25, 50) == 50  # 翻倍偏好

    def test_new_profile_extra_json_defaults(self):
        raw = _default_teaching_extra_json()
        data = json.loads(raw)
        assert data["hint_policy"] == "ladder"
        assert data["preferred_session_minutes"] == 25
        prefs = teaching_prefs_from_profile({"extra_json": raw, "time_budget_minutes": 25})
        assert prefs["example_style"] == "example_first"


class TestHintLadder:
    def test_fail_count_consecutive(self):
        hist = [
            {"score": 30, "should_advance": False},
            {"score": 40, "should_advance": False},
        ]
        assert fail_count_from_assessments(hist) == 2
        hist.append({"score": 80, "should_advance": True})
        assert fail_count_from_assessments(hist) == 0
        hist.append({"score": 20, "should_advance": False})
        assert fail_count_from_assessments(hist) == 1

    def test_levels_1_2_3(self):
        assert next_hint_level(0) == 1
        assert next_hint_level(1) == 2
        assert next_hint_level(2) == 3
        assert next_hint_level(5) == 3
        assert should_mark_review(3) is True
        assert should_mark_review(2) is False

    def test_error_type_memory_vs_confusion(self):
        assert classify_error_type("不知道") == "memory"
        assert classify_error_type("我觉得是 X", feedback="你把 A 和 B 混淆了") == "confusion"
        assert classify_error_type("没学过前置", feedback="") == "missing_prereq"

    def test_rule_based_texts_differ_by_level_and_type(self):
        t1 = rule_based_repair_text(1, mastery_check="能解释反向传播", error_type="memory")
        t2 = rule_based_repair_text(2, mastery_check="能解释反向传播", error_type="confusion")
        t3 = rule_based_repair_text(3, mastery_check="能解释反向传播", claim_text="链式求导", error_type="memory")
        assert "1/3" in t1
        assert "2/3" in t2
        assert "3/3" in t3 and "复习" in t3
        assert t1 != t2 != t3
        # 错误类型影响文案
        tm = rule_based_repair_text(1, error_type="memory")
        tc = rule_based_repair_text(1, error_type="confusion")
        assert tm != tc

    def test_format_assessment_level3_advances_flag(self):
        a = format_repair_assessment(
            hint_level=3, error_type="memory", repair_text="完整", score=20, mark_review=True,
        )
        assert a["mark_review"] is True
        assert a["hint_level"] == 3
        assert a["should_advance"] is True  # 给完答案后允许用户继续

    def test_repair_instruction_contains_level(self):
        ins = build_repair_instruction(1, error_type="memory", mastery_check="能复述")
        assert "hint_level=1" in ins
        assert "禁止" in ins or "引导" in ins
        ins3 = build_repair_instruction(3, error_type="confusion", claim_text="命题")
        assert "hint_level=3" in ins3

    def test_state_machine_default_allows_three_repairs(self):
        # default max_repair_rounds=3：rounds=2 仍可进 REPAIR
        r = transition(
            ASSESS,
            ASSESSMENT_SUBMITTED,
            {"required_objectives_passed": False, "repairable_gaps": True, "repair_rounds": 2},
        )
        assert r.next_state == REPAIR
        r2 = transition(
            ASSESS,
            ASSESSMENT_SUBMITTED,
            {"required_objectives_passed": False, "repairable_gaps": True, "repair_rounds": 3},
        )
        assert r2.next_state == PAUSED
        assert r2.completion_status == "needs_support"
        assert hint_level_from_repair_rounds(0) == 1
        assert hint_level_from_repair_rounds(2) == 3


class TestPromptStyleInjection:
    def test_explain_v2_has_example_first_and_probe(self):
        assert "example_first" in EXPLAIN_PROMPT_V2
        assert "想一想" in EXPLAIN_PROMPT_V2
        assert "teaching_style" in EXPLAIN_PROMPT_V2
        assert "{teaching_style}" in EXPLAIN_PROMPT_V2

    def test_repair_prompt_exists(self):
        assert "{repair_instruction}" in REPAIR_PROMPT_V2
        assert "三级提示阶梯" in REPAIR_PROMPT_V2


@pytest.mark.asyncio
async def test_submit_answer_ladder_three_fails(mock_llm):
    """模拟连续答错 3 次 → hint 1/2/3，第 3 次 mark_review。"""
    from app.modules.teaching.service import TeachingService
    from app.modules.teaching.schemas import TeachingPhase

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    session_model = MagicMock()
    session_model.id = "s1"
    session_model.user_id = "anonymous"
    session_model.plan_session_id = "p1"
    session_model.book_id = "b1"
    session_model.unit_ids = json.dumps(["u1"])
    session_model.current_unit_index = 0
    session_model.current_phase = TeachingPhase.CHECK.value
    session_model.strategy_json = json.dumps(TeachingStrategy(
        hint_policy="ladder", teaching_style="explain_then_probe",
    ).model_dump())
    session_model.status = "active"
    session_model.started_at = datetime(2026, 1, 1)
    session_model.ended_at = None

    # 历史 assessment 累积
    history: list[MagicMock] = []

    async def smart_execute(query, *args, **kwargs):
        q = str(query)
        res = MagicMock()
        if "teaching_sessions" in q:
            res.scalar_one_or_none = MagicMock(return_value=session_model)
            res.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None), all=MagicMock(return_value=[])))
            return res
        if "teaching_messages" in q or "TeachingMessage" in q:
            # 问题消息 + 历史带 assessment 的
            q_msg = MagicMock()
            q_msg.content = "请解释反向传播 <!--claim_id=c1||mastery_check=能说明链式法则-->"
            q_msg.assessment_json = None
            msgs = [q_msg] + history

            def scalars():
                m = MagicMock()
                m.first = MagicMock(return_value=q_msg)
                m.all = MagicMock(return_value=msgs)
                return m

            res.scalars = scalars
            res.scalar_one_or_none = MagicMock(return_value=q_msg)
            return res
        if "mastery" in q.lower():
            res.scalar_one_or_none = MagicMock(return_value=None)
            res.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            return res
        res.scalar_one_or_none = MagicMock(return_value=None)
        res.scalars = MagicMock(return_value=MagicMock(first=MagicMock(return_value=None), all=MagicMock(return_value=[])))
        return res

    mock_db.execute = AsyncMock(side_effect=smart_execute)

    # 评分始终低分
    mock_llm.chat_json = AsyncMock(return_value={
        "score": 25, "is_correct": False, "feedback": "未达到掌握标准", "claim_id": "c1",
    })
    mock_llm.chat = AsyncMock(return_value=MagicMock(content="阶梯提示正文"))

    service = TeachingService(llm_client=mock_llm, db=mock_db)
    unit = _unit(summary="反向传播", key_points=["链式法则"])

    levels = []
    for i in range(3):
        msg = await service.submit_answer("s1", f"错误答案{i}", [unit])
        assert msg.assessment is not None
        levels.append(msg.assessment.get("hint_level"))
        # 把刚写入的 assessment 记入 history（模拟 DB）
        am = MagicMock()
        am.content = msg.content
        am.assessment_json = json.dumps(msg.assessment)
        history.append(am)

    assert levels == [1, 2, 3]
    assert msg.assessment.get("mark_review") is True
