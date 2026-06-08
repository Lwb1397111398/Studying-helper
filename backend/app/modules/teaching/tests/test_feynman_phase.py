"""费曼学习法阶段测试"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.common.llm_client import LLMResponse
from app.modules.ai_learning.schemas import LearnedUnit, Concept, KeyPoint, SelfAssessment, TestQuestion
from app.modules.teaching.schemas import (
    TeachingPhase, TeachingStrategy, FeynmanAssessment,
)
from app.modules.teaching.service import TeachingService
from app.modules.teaching.strategies import select_phases


def _make_mock_db_session():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()
    return mock_db


def _make_unit(difficulty: int) -> LearnedUnit:
    """创建指定难度的知识单元"""
    return LearnedUnit(
        unit_id="u1", book_id="b1", summary="测试内容",
        key_points=[KeyPoint(title="要点1")], concepts=[],
        difficulty_level=difficulty, importance_score=0.5, prerequisites=[],
        self_assessment=SelfAssessment(
            score=float(difficulty * 15), test_questions=[], self_answers=[],
            weak_points=[], needs_deepening=False,
        ),
    )


class TestFeynmanPhaseInStrategy:
    """测试费曼阶段在策略中的位置"""

    def test_simple_phases_include_feynman_after_core(self):
        """简单单元：CORE 后面是 FEYNMAN"""
        unit = _make_unit(difficulty=1)
        phases = select_phases(unit, mastery=0.8)
        core_idx = phases.index(TeachingPhase.CORE)
        assert phases[core_idx + 1] == TeachingPhase.FEYNMAN

    def test_medium_phases_include_feynman_after_core(self):
        """中等单元：CORE 后面是 FEYNMAN"""
        unit = _make_unit(difficulty=3)
        phases = select_phases(unit, mastery=0.5)
        core_idx = phases.index(TeachingPhase.CORE)
        assert phases[core_idx + 1] == TeachingPhase.FEYNMAN

    def test_complex_phases_include_feynman_after_core(self):
        """复杂单元：CORE 后面是 FEYNMAN"""
        unit = _make_unit(difficulty=5)
        phases = select_phases(unit, mastery=0.3)
        core_idx = phases.index(TeachingPhase.CORE)
        assert phases[core_idx + 1] == TeachingPhase.FEYNMAN

    def test_feynman_before_retrieval(self):
        """FEYNMAN 在 RETRIEVAL 之前"""
        unit = _make_unit(difficulty=3)
        phases = select_phases(unit, mastery=0.5)
        feynman_idx = phases.index(TeachingPhase.FEYNMAN)
        retrieval_idx = phases.index(TeachingPhase.RETRIEVAL)
        assert feynman_idx < retrieval_idx


class TestFeynmanAssessment:
    """测试费曼评估模型"""

    def test_default_values(self):
        assessment = FeynmanAssessment()
        assert assessment.completeness == 0.5
        assert assessment.accuracy == 0.5
        assert assessment.depth == 0.5
        assert assessment.overall_score == 50
        assert assessment.should_advance is True

    def test_full_assessment(self):
        assessment = FeynmanAssessment(
            completeness=0.9,
            accuracy=0.85,
            depth=0.7,
            overall_score=82,
            covered_points=["要点1", "要点2"],
            missed_points=["要点3"],
            feedback="覆盖全面",
            should_advance=True,
        )
        assert assessment.overall_score == 82
        assert len(assessment.covered_points) == 2
        assert assessment.should_advance is True


class TestFeynmanServiceMethods:
    """测试费曼相关的服务方法"""

    @pytest.mark.asyncio
    async def test_generate_feynman_prompt(self, mock_llm, sample_unit):
        """生成费曼引导内容"""
        mock_llm.chat = AsyncMock(return_value=LLMResponse(
            content="请用自己的话解释一下数组这个概念，可以举例子帮助说明。",
            model="mock", usage={},
        ))
        service = TeachingService(llm_client=mock_llm, db=_make_mock_db_session())
        result = await service._generate_feynman(sample_unit)
        assert len(result) > 0
        assert "数组" in result or "解释" in result

    @pytest.mark.asyncio
    async def test_assess_feynman_explanation(self, mock_llm, sample_unit):
        """评估费曼解释"""
        mock_llm.chat_json = AsyncMock(return_value={
            "completeness": 0.8,
            "accuracy": 0.9,
            "depth": 0.7,
            "overall_score": 80,
            "covered_points": ["连续存储", "相同类型"],
            "missed_points": [],
            "inaccurate_points": [],
            "feedback": "解释清晰",
            "suggestion": "可以再深入一点",
            "should_advance": True,
        })
        service = TeachingService(llm_client=mock_llm, db=_make_mock_db_session())
        assessment = await service._assess_feynman_explanation(
            sample_unit, "数组就是连续存储的数据结构，所有元素类型相同"
        )
        assert assessment["overall_score"] == 80
        assert assessment["should_advance"] is True

    @pytest.mark.asyncio
    async def test_assess_feynman_fallback_on_error(self, mock_llm, sample_unit):
        """LLM 失败时返回默认评估（允许继续）"""
        mock_llm.chat_json = AsyncMock(side_effect=Exception("LLM error"))
        service = TeachingService(llm_client=mock_llm, db=_make_mock_db_session())
        assessment = await service._assess_feynman_explanation(
            sample_unit, "一些解释"
        )
        assert assessment["overall_score"] == 50
        assert assessment["should_advance"] is True  # 降级时默认允许继续
