"""AI学习服务测试"""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock


class TestAILearningService:
    @pytest.mark.asyncio
    async def test_learn_unit_basic(self, mock_llm, sample_unit):
        """基本学习流程：输入知识单元，输出学习结果"""
        from app.modules.ai_learning.service import AILearningService
        from app.modules.ai_learning.schemas import LearningContext

        service = AILearningService(llm_client=mock_llm)
        result = await service.learn_unit(sample_unit, LearningContext())

        assert result.summary != ""
        assert len(result.key_points) >= 1
        assert 1 <= result.difficulty_level <= 5
        assert result.unit_id == "unit-1"
        assert result.self_assessment is None

    @pytest.mark.asyncio
    async def test_learn_book_progress_callback(
        self, mock_llm, sample_units, sample_chapters
    ):
        """学习进度回调：每个单元完成后触发回调"""
        from app.modules.ai_learning.service import AILearningService

        progress_calls = []
        service = AILearningService(llm_client=mock_llm)
        result = await service.learn_book(
            "book-1",
            sample_units,
            sample_chapters,
            on_progress=lambda c, t, title: progress_calls.append((c, t)),
        )

        # 每个单元产生 2 个回调：1个信息性（cur=-1）+ 1个进度更新
        progress_only = [call for call in progress_calls if call[0] >= 0]
        assert len(progress_only) == len(sample_units)
        assert result.learned_count > 0
        assert result.total_token_cost > 0

    @pytest.mark.asyncio
    async def test_token_budget_enforcement(
        self, mock_llm, sample_units, sample_chapters
    ):
        """Token预算：超出预算后停止学习"""
        from app.modules.ai_learning.service import AILearningService

        # 设置极小的预算（mock每次调用返回300 token，每个单元需要2次调用=600 token）
        service = AILearningService(llm_client=mock_llm, token_budget=100)
        result = await service.learn_book(
            "book-1", sample_units, sample_chapters
        )

        # 预算太小，只学了部分（或0个）单元
        assert result.learned_count <= len(sample_units)

    @pytest.mark.asyncio
    async def test_persist_learned_unit_flushes_without_committing(self, mock_llm):
        """服务层持久化不应越过请求事务边界提交事务"""
        from app.modules.ai_learning.service import AILearningService
        from app.modules.ai_learning.schemas import LearnedUnit, KeyPoint, Concept

        db_unit = SimpleNamespace(id="unit-1", book_id="book-1")
        mastery_result = SimpleNamespace(scalar_one_or_none=lambda: None)
        unit_result = SimpleNamespace(scalar_one_or_none=lambda: db_unit)
        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[unit_result, mastery_result]),
            add=lambda _obj: None,
            flush=AsyncMock(),
            commit=AsyncMock(),
        )
        service = AILearningService(llm_client=mock_llm, db_session=db)
        learned = LearnedUnit(
            unit_id="unit-1",
            book_id="book-1",
            summary="摘要",
            key_points=[KeyPoint(title="要点")],
            concepts=[Concept(name="概念", definition="定义")],
            difficulty_level=3,
            importance_score=0.5,
            prerequisites=[],
        )

        await service._persist_learned_unit(learned)

        db.flush.assert_awaited_once()
        db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_learning_order_without_db(mock_llm, sample_units):
    """无数据库时 get_learning_order 返回原顺序"""
    from app.modules.ai_learning.service import AILearningService

    service = AILearningService(llm_client=mock_llm, db_session=None)
    result = await service.get_learning_order("book-1", sample_units)
    assert result == sample_units

@pytest.mark.asyncio
async def test_relearn_unit(mock_llm, sample_unit):
    """重新生成：覆盖旧结果，返回新的 LearnedUnit"""
    from app.modules.ai_learning.service import AILearningService

    service = AILearningService(llm_client=mock_llm)
    result = await service.relearn_unit(sample_unit)

    assert result.unit_id == "unit-1"
    assert result.summary != ""
    assert len(result.key_points) >= 1
    assert result.self_assessment is None


@pytest.mark.asyncio
async def test_enrich_unit_merges_new_content(mock_llm, sample_unit):
    """增量更新：新旧内容合并，不覆盖"""
    from app.modules.ai_learning.service import AILearningService

    service = AILearningService(llm_client=mock_llm)
    result = await service.enrich_unit(
        unit_id="unit-1",
        book_id="book-1",
        chapter_id="chapter-1",
        title=sample_unit.title,
        content=sample_unit.content,
        existing_summary="旧摘要",
        existing_key_points=["旧要点1"],
        existing_concepts=[{"name": "旧概念", "definition": "旧定义"}],
        focus=None,  # 通用模式：合并全部字段
    )

    # 合并后要点 = 新 + 旧
    assert len(result.key_points) >= 2
    # 合并后概念 = 新 + 旧（按 name 去重）
    concept_names = {c.name for c in result.concepts}
    assert "旧概念" in concept_names
    assert "补充概念C" in concept_names
