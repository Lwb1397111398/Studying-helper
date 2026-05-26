"""教学服务测试"""
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.common.llm_client import LLMMessage, LLMResponse
from app.modules.teaching.schemas import (
    TeachingPhase, TeachingStrategy, UserTeachingProfile, KnowledgeType,
)
from app.modules.teaching.strategies import select_teaching_strategy
from app.modules.teaching.service import TeachingService


def _make_mock_db_session():
    """创建一个模拟的 DB session，支持 execute/flush/add"""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.delete = AsyncMock()
    return mock_db


def _make_db_session_model(session_id, unit_ids, current_phase="activate", current_unit_index=0):
    """创建模拟的 TeachingSessionModel 返回值"""
    mock_model = MagicMock()
    mock_model.id = session_id
    mock_model.user_id = "user-1"
    mock_model.plan_session_id = "plan-session-1"
    mock_model.book_id = "book-1"
    mock_model.unit_ids = json.dumps(unit_ids)
    mock_model.current_unit_index = current_unit_index
    mock_model.current_phase = current_phase
    mock_model.strategy_json = json.dumps(TeachingStrategy().model_dump())
    mock_model.status = "active"
    mock_model.started_at = datetime(2026, 1, 1, 10, 0, 0)
    mock_model.ended_at = None
    return mock_model


def _setup_mock_db_for_session(mock_db, session_model):
    """配置 mock_db.execute 返回 session_model"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=session_model)
    mock_db.execute = AsyncMock(return_value=mock_result)


# ---- 策略选择测试 ----

class TestStrategySelection:

    def _make_unit(self, summary, key_points, concepts, difficulty, importance=0.5, prerequisites=None):
        from app.modules.ai_learning.schemas import LearnedUnit, Concept as LConcept, SelfAssessment, TestQuestion
        return LearnedUnit(
            unit_id="u1", book_id="b1", summary=summary,
            key_points=key_points, concepts=concepts,
            difficulty_level=difficulty, importance_score=importance,
            prerequisites=prerequisites or [],
            self_assessment=SelfAssessment(
                score=float(difficulty * 15),
                test_questions=[TestQuestion(
                    question="测试问题", question_type="short_answer",
                    correct_answer="参考答案", explanation="解释",
                )],
                self_answers=["自测答案"],
                weak_points=[],
                needs_deepening=False,
            ),
        )

    def test_easy_unit_gets_low_visual(self):
        unit = self._make_unit("简单概念", ["定义"], [], 1)
        strategy = select_teaching_strategy(unit)
        assert strategy.visual_level == "low"

    def test_hard_unit_gets_high_visual(self):
        unit = self._make_unit("复杂原理", ["深层机制"], [], 5, 0.9)
        strategy = select_teaching_strategy(unit)
        assert strategy.visual_level == "high"

    def test_procedure_unit_gets_example_first(self):
        unit = self._make_unit(
            "如何操作数据库",
            ["步骤：连接数据库", "步骤：执行查询", "步骤：关闭连接"],
            [], 3, 0.8,
        )
        strategy = select_teaching_strategy(unit)
        assert strategy.explanation_style == "example_first"
        assert strategy.knowledge_type == KnowledgeType.PROCEDURE.value

    def test_concept_unit_gets_analogy(self):
        from app.modules.ai_learning.schemas import Concept as LConcept
        unit = self._make_unit(
            "什么是多态",
            ["多态的定义：同一接口多种表现形式"],
            [LConcept(name="多态", definition="同一接口多种表现形式",
                      examples=["动物叫声"], related_concepts=["继承"])],
            3, 0.8,
        )
        strategy = select_teaching_strategy(unit)
        assert strategy.explanation_style == "analogy"
        assert strategy.knowledge_type == KnowledgeType.CONCEPT.value

    def test_principle_unit_gets_theory_first(self):
        from app.modules.ai_learning.schemas import Concept as LConcept
        unit = self._make_unit(
            "B+树的原理",
            ["多路平衡机制", "为什么叶子链表能加速范围查询"],
            [LConcept(name="B+树原理", definition="多路平衡查找树",
                      examples=["数据库索引"], related_concepts=["B树"])],
            4, 0.9,
        )
        strategy = select_teaching_strategy(unit)
        assert strategy.explanation_style == "theory_first"
        assert strategy.knowledge_type == KnowledgeType.PRINCIPLE.value

    def test_user_profile_advanced_gets_minimal_scaffold(self):
        unit = self._make_unit("测试", ["测试点"], [], 2)
        profile = UserTeachingProfile(avg_mastery_score=0.9, total_sessions=20)
        strategy = select_teaching_strategy(unit, profile)
        assert strategy.scaffold_level == "minimal"
        assert strategy.pace == "fast"
        assert strategy.feedback_style == "delayed"

    def test_user_profile_beginner_gets_full_scaffold(self):
        unit = self._make_unit("测试", ["测试点"], [], 3)
        profile = UserTeachingProfile(avg_mastery_score=0.15, total_sessions=1)
        strategy = select_teaching_strategy(unit, profile)
        assert strategy.scaffold_level == "full"
        assert strategy.feedback_style == "immediate"
        assert strategy.interaction_frequency == "high"

    def test_user_preferred_style_overrides_default(self):
        from app.modules.ai_learning.schemas import Concept as LConcept
        unit = self._make_unit(
            "什么是类", ["类是面向对象的基础"],
            [LConcept(name="类", definition="对象的模板")],
            2, 0.7,
        )
        profile = UserTeachingProfile(avg_mastery_score=0.8, preferred_style="problem_based")
        strategy = select_teaching_strategy(unit, profile)
        assert strategy.explanation_style == "problem_based"

    def test_default_strategy_without_profile(self):
        unit = self._make_unit("测试", ["测试点"], [], 3)
        strategy = select_teaching_strategy(unit)
        assert strategy.scaffold_level == "partial"

    def test_hard_unit_gets_slow_pace(self):
        unit = self._make_unit("极难概念", ["抽象理论"], [], 5)
        strategy = select_teaching_strategy(unit)
        assert strategy.pace == "slow"

    def test_easy_unit_with_advanced_user_gets_fast_pace(self):
        unit = self._make_unit("简单回顾", ["已知概念"], [], 1)
        profile = UserTeachingProfile(avg_mastery_score=0.9)
        strategy = select_teaching_strategy(unit, profile)
        assert strategy.pace == "fast"


# ---- 教学服务测试 ----

class TestTeachingService:

    @pytest.mark.asyncio
    async def test_start_session(self, mock_llm, sample_units_basic):
        """开始会话"""
        mock_db = _make_mock_db_session()
        service = TeachingService(llm_client=mock_llm, db=mock_db)
        session = await service.start_session(
            user_id="user-1",
            plan_session_id="plan-session-1",
            book_id="book-1",
            unit_ids=["unit-1"],
            units=sample_units_basic,
        )
        assert session.status == "active"
        assert session.user_id == "user-1"
        assert len(session.unit_ids) == 1
        assert session.current_phase == TeachingPhase.ACTIVATE

    @pytest.mark.asyncio
    async def test_start_session_with_user_profile(self, mock_llm, sample_units_basic, mock_user_profile):
        """带用户画像开始会话"""
        mock_db = _make_mock_db_session()
        service = TeachingService(llm_client=mock_llm, db=mock_db)
        session = await service.start_session(
            user_id="user-1",
            plan_session_id="plan-session-1",
            book_id="book-1",
            unit_ids=["unit-1"],
            units=sample_units_basic,
            user_profile=mock_user_profile,
        )
        assert session.strategy.scaffold_level == "partial"

    @pytest.mark.asyncio
    async def test_teaching_phases_sequence(self, mock_llm, sample_units_basic):
        """六阶段顺序：ACTIVATE → INTRO → CORE → CHECK → REFLECT → CONNECT"""
        mock_db = _make_mock_db_session()
        session_model = _make_db_session_model("session-1", ["unit-1"])
        _setup_mock_db_for_session(mock_db, session_model)

        # 让 mock_llm.chat 返回不同阶段的响应
        call_count = 0
        async def mock_chat(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return LLMResponse(content=f"第{call_count}阶段内容", model="mock", usage={})

        mock_llm.chat = mock_chat
        mock_llm.chat_json = AsyncMock(return_value={"key": "value"})

        service = TeachingService(llm_client=mock_llm, db=mock_db)
        session = await service.start_session(
            user_id="user-1",
            plan_session_id="plan-session-1",
            book_id="book-1",
            unit_ids=["unit-1"],
            units=sample_units_basic,
        )
        session_model.id = session.id

        phases = []
        for _ in range(6):
            msg = await service.get_next_message(session.id, sample_units_basic)
            phases.append(msg.phase)

        assert phases == [
            TeachingPhase.ACTIVATE,
            TeachingPhase.INTRO,
            TeachingPhase.CORE,
            TeachingPhase.CHECK,
            TeachingPhase.REFLECT,
            TeachingPhase.CONNECT,
        ]

    @pytest.mark.asyncio
    async def test_activate_phase_content(self, mock_llm, sample_units_basic):
        """ACTIVATE 阶段生成内容非空"""
        mock_db = _make_mock_db_session()
        session_model = _make_db_session_model("session-1", ["unit-1"])
        _setup_mock_db_for_session(mock_db, session_model)

        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content="1. 你知道什么是变量吗？\n2. 数据类型有哪些？", model="mock", usage={}
        ))

        service = TeachingService(llm_client=mock_llm, db=mock_db)
        session = await service.start_session(
            user_id="user-1",
            plan_session_id="plan-session-1",
            book_id="book-1",
            unit_ids=["unit-1"],
            units=sample_units_basic,
        )
        session_model.id = session.id

        msg = await service.get_next_message(session.id, sample_units_basic)
        assert msg.phase == TeachingPhase.ACTIVATE
        assert len(msg.content) > 0

    @pytest.mark.asyncio
    async def test_reflect_phase_content(self, mock_llm, sample_units_basic):
        """REFLECT 阶段生成内容非空"""
        mock_db = _make_mock_db_session()
        session_model = _make_db_session_model("session-1", ["unit-1"])
        _setup_mock_db_for_session(mock_db, session_model)

        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content="1. 你能用自己的话解释这个概念吗？\n2. 这和你之前学的有什么联系？",
            model="mock", usage={}
        ))
        mock_llm.chat_json = AsyncMock(return_value={"key": "value"})

        service = TeachingService(llm_client=mock_llm, db=mock_db)
        session = await service.start_session(
            user_id="user-1",
            plan_session_id="plan-session-1",
            book_id="book-1",
            unit_ids=["unit-1"],
            units=sample_units_basic,
        )
        session_model.id = session.id

        # 推进到 REFLECT 阶段（跳过 ACTIVATE, INTRO, CORE, CHECK）
        for _ in range(4):
            await service.get_next_message(session.id, sample_units_basic)

        msg = await service.get_next_message(session.id, sample_units_basic)
        assert msg.phase == TeachingPhase.REFLECT
        assert len(msg.content) > 0

    @pytest.mark.asyncio
    async def test_answer_question(self, mock_llm, sample_units_basic):
        """回答问题"""
        mock_db = _make_mock_db_session()
        session_model = _make_db_session_model("session-1", ["unit-1"])
        _setup_mock_db_for_session(mock_db, session_model)

        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content="concept", model="mock", usage={}
        ))
        mock_llm.chat_json = AsyncMock(return_value={
            "answer": "数组是线性表数据结构",
            "follow_up_questions": ["数组和链表有什么区别？"],
        })

        service = TeachingService(llm_client=mock_llm, db=mock_db)
        session = await service.start_session(
            user_id="user-1",
            plan_session_id="plan-session-1",
            book_id="book-1",
            unit_ids=["unit-1"],
            units=sample_units_basic,
        )
        session_model.id = session.id

        result = await service.answer_question(
            session.id, "什么是数组？", sample_units_basic
        )
        assert result.answer != ""
        assert len(result.follow_up_questions) >= 1

    @pytest.mark.asyncio
    async def test_add_annotation(self, mock_llm):
        """添加笔记"""
        mock_db = _make_mock_db_session()
        service = TeachingService(llm_client=mock_llm, db=mock_db)
        annotation = await service.add_annotation(
            user_id="user-1",
            unit_id="unit-1",
            annotation_type="confusing",
            content="不理解这个概念",
        )
        assert annotation.annotation_type == "confusing"
        assert annotation.user_id == "user-1"

    @pytest.mark.asyncio
    async def test_run_session_test(self, mock_llm, sample_units_basic):
        """运行测试"""
        mock_db = _make_mock_db_session()
        session_model = _make_db_session_model("session-1", ["unit-1"])
        _setup_mock_db_for_session(mock_db, session_model)

        service = TeachingService(llm_client=mock_llm, db=mock_db)
        session = await service.start_session(
            user_id="user-1",
            plan_session_id="plan-session-1",
            book_id="book-1",
            unit_ids=["unit-1"],
            units=sample_units_basic,
        )
        session_model.id = session.id

        test = await service.run_session_test(session.id, sample_units_basic)
        assert len(test.questions) >= 1

    @pytest.mark.asyncio
    async def test_submit_test_answers(self, mock_llm):
        """提交测试答案（LLM 判分）"""
        mock_db = _make_mock_db_session()

        mock_test_model = MagicMock()
        mock_test_model.id = "test-1"
        mock_test_model.session_id = "session-1"
        mock_test_model.questions_json = json.dumps([{
            "question": "什么是数组？",
            "question_type": "short_answer",
            "correct_answer": "用连续存储空间存储相同类型元素的数据结构",
            "explanation": "数组定义",
        }])
        mock_test_model.user_answers_json = "[]"
        mock_test_model.score = None
        mock_test_model.weak_points_json = "[]"
        mock_test_model.completed_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_test_model)
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_llm.chat_json = AsyncMock(return_value={
            "score": 85, "is_correct": True, "feedback": "回答正确",
        })

        service = TeachingService(llm_client=mock_llm, db=mock_db)
        completed = await service.submit_test_answers(
            "test-1",
            ["用连续存储空间存储相同类型元素的数据结构"],
        )
        assert completed.score is not None
        assert 0 <= completed.score <= 100


# ---- LLM 判分测试 ----

class TestLLMGrading:

    @pytest.mark.asyncio
    async def test_semantic_correct_answer_gets_high_score(self):
        from app.modules.ai_learning.schemas import TestQuestion

        mock_llm = AsyncMock()
        mock_llm.chat_json = AsyncMock(return_value={
            "score": 95, "is_correct": True, "feedback": "回答准确完整",
        })

        service = TeachingService(llm_client=mock_llm, db=_make_mock_db_session())
        question = TestQuestion(
            question="什么是数组？", question_type="short_answer",
            correct_answer="用连续存储空间存储相同类型元素的数据结构",
            explanation="数组定义",
        )
        score = await service._grade_answer(question, "数组就是把相同类型的数据连续存放在内存里的结构")
        assert score >= 80

    @pytest.mark.asyncio
    async def test_wrong_answer_gets_low_score(self):
        from app.modules.ai_learning.schemas import TestQuestion

        mock_llm = AsyncMock()
        mock_llm.chat_json = AsyncMock(return_value={
            "score": 20, "is_correct": False, "feedback": "回答与问题无关",
        })

        service = TeachingService(llm_client=mock_llm, db=_make_mock_db_session())
        question = TestQuestion(
            question="什么是数组？", question_type="short_answer",
            correct_answer="用连续存储空间存储相同类型元素的数据结构",
            explanation="数组定义",
        )
        score = await service._grade_answer(question, "猫是一种可爱的动物")
        assert score < 40

    @pytest.mark.asyncio
    async def test_partial_answer_gets_medium_score(self):
        from app.modules.ai_learning.schemas import TestQuestion

        mock_llm = AsyncMock()
        mock_llm.chat_json = AsyncMock(return_value={
            "score": 65, "is_correct": False, "feedback": "核心概念正确，但缺少关键细节",
        })

        service = TeachingService(llm_client=mock_llm, db=_make_mock_db_session())
        question = TestQuestion(
            question="什么是数组？", question_type="short_answer",
            correct_answer="用连续存储空间存储相同类型元素的数据结构",
            explanation="数组定义",
        )
        score = await service._grade_answer(question, "数组是存储数据的结构")
        assert 40 <= score < 80

    @pytest.mark.asyncio
    async def test_grading_fallback_on_llm_failure(self):
        from app.modules.ai_learning.schemas import TestQuestion

        mock_llm = AsyncMock()
        mock_llm.chat_json = AsyncMock(side_effect=Exception("LLM error"))

        service = TeachingService(llm_client=mock_llm, db=_make_mock_db_session())
        question = TestQuestion(
            question="什么是数组？", question_type="short_answer",
            correct_answer="用连续存储空间存储相同类型元素的数据结构",
            explanation="数组定义",
        )
        score = await service._grade_answer(question, "用连续存储空间存储相同类型元素的数据结构")
        assert score == 100.0
        score = await service._grade_answer(question, "完全错误的答案")
        assert score == 0.0


# ---- 测试题型生成测试 ----

class TestQuestionGeneration:

    @pytest.mark.asyncio
    async def test_concept_generates_choice_question(self, mock_llm, sample_units_basic):
        service = TeachingService(llm_client=mock_llm, db=_make_mock_db_session())
        strategy = TeachingStrategy(knowledge_type=KnowledgeType.CONCEPT.value)
        question = await service._generate_test_question(sample_units_basic[0], strategy)
        assert question.question_type == "choice"
        assert question.options is not None
        assert len(question.options) >= 2

    @pytest.mark.asyncio
    async def test_procedure_generates_short_answer(self, mock_llm, sample_unit_procedure):
        service = TeachingService(llm_client=mock_llm, db=_make_mock_db_session())
        strategy = TeachingStrategy(knowledge_type=KnowledgeType.PROCEDURE.value)
        question = await service._generate_test_question(sample_unit_procedure, strategy)
        assert question.question_type == "short_answer"
        assert "步骤" in question.question or "操作" in question.question

    @pytest.mark.asyncio
    async def test_principle_generates_explanation(self, mock_llm):
        from app.modules.ai_learning.schemas import LearnedUnit, Concept as LConcept, SelfAssessment

        unit = LearnedUnit(
            unit_id="u1", book_id="b1", summary="B+树的原理",
            key_points=["多路平衡机制", "为什么叶子链表能加速范围查询"],
            concepts=[LConcept(name="B+树原理", definition="多路平衡查找树")],
            difficulty_level=4, importance_score=0.9, prerequisites=[],
            self_assessment=SelfAssessment(
                score=60, test_questions=[], self_answers=[],
                weak_points=[], needs_deepening=False,
            ),
        )
        service = TeachingService(llm_client=mock_llm, db=_make_mock_db_session())
        strategy = TeachingStrategy(knowledge_type=KnowledgeType.PRINCIPLE.value)
        question = await service._generate_test_question(unit, strategy)
        assert question.question_type == "short_answer"
        assert "为什么" in question.question or "原理" in question.question

    @pytest.mark.asyncio
    async def test_fact_generates_fill_blank(self, mock_llm):
        from app.modules.ai_learning.schemas import LearnedUnit, Concept as LConcept, SelfAssessment

        unit = LearnedUnit(
            unit_id="u1", book_id="b1", summary="Python 之父是 Guido van Rossum",
            key_points=["Guido van Rossum 于1991年发布 Python"],
            concepts=[LConcept(name="Python", definition="一种编程语言")],
            difficulty_level=1, importance_score=0.3, prerequisites=[],
            self_assessment=SelfAssessment(
                score=95, test_questions=[], self_answers=[],
                weak_points=[], needs_deepening=False,
            ),
        )
        service = TeachingService(llm_client=mock_llm, db=_make_mock_db_session())
        strategy = TeachingStrategy(knowledge_type=KnowledgeType.FACT.value)
        question = await service._generate_test_question(unit, strategy)
        assert question.question_type == "fill_blank"
        assert "______" in question.question
