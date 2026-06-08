"""自由回忆功能测试"""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.modules.review.service import ReviewService
from app.modules.review.schemas import FreeRecallResult, RecalledPoint
from app.modules.review.helpers import evaluate_free_recall, _tokenize_simple
from app.modules.knowledge_splitter.schemas import KnowledgeUnit
from app.common.errors import ServiceError


class _MockResult:
    def __init__(self, scalar_value=None):
        self._scalar = scalar_value

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return []


class _MockAsyncContext:
    def __init__(self):
        self.add = MagicMock()
        self._results = []

    def queue_result(self, result_or_scalar=None):
        if isinstance(result_or_scalar, _MockResult):
            self._results.append(result_or_scalar)
        else:
            self._results.append(_MockResult(result_or_scalar))

    async def execute(self, *args, **kwargs):
        if self._results:
            return self._results.pop(0)
        return _MockResult()


@pytest.fixture
def mock_db():
    return _MockAsyncContext()


@pytest.fixture
def service(mock_db):
    return ReviewService(mock_db)


@pytest.fixture
def sample_units():
    return [
        KnowledgeUnit(
            id="unit-1", book_id="book-1", chapter_id="ch-1",
            title="数组", content="数组内容",
            order_index=0, char_offset_start=0, char_offset_end=100,
            summary="数组是基本数据结构",
            key_points=["连续存储", "随机访问", "相同类型元素"],
        ),
    ]


class TestTokenizeSimple:
    """测试简单分词函数"""

    def test_chinese_text(self):
        tokens = _tokenize_simple("连续存储空间")
        assert len(tokens) > 0
        assert "连续" in tokens
        assert "存储" in tokens

    def test_english_text(self):
        tokens = _tokenize_simple("array is a data structure")
        assert "array" in tokens
        assert "data" in tokens
        assert "structure" in tokens

    def test_mixed_text(self):
        tokens = _tokenize_simple("数组array连续存储")
        assert "数组" in tokens or "array" in tokens

    def test_empty_text(self):
        tokens = _tokenize_simple("")
        assert tokens == []


class TestEvaluateFreeRecall:
    """测试本地自由回忆评估（无 LLM）"""

    def test_recall_with_matching_content(self):
        """回忆包含匹配内容"""
        key_points = ["连续存储", "随机访问", "相同类型元素"]
        student_answer = "数组是连续存储的数据结构，支持随机访问，所有元素类型相同"

        result = evaluate_free_recall(student_answer, key_points)
        assert result["coverage"] > 0
        assert result["overall_score"] > 0
        assert len(result["recalled_points"]) > 0

    def test_partial_recall(self):
        """部分回忆：只提到部分要点"""
        key_points = ["连续存储", "随机访问", "相同类型元素"]
        student_answer = "数组是连续存储的"

        result = evaluate_free_recall(student_answer, key_points)
        assert 0 < result["coverage"] <= 1
        assert len(result["missed_points"]) > 0

    def test_empty_answer(self):
        """空答案"""
        key_points = ["连续存储", "随机访问"]
        student_answer = ""

        result = evaluate_free_recall(student_answer, key_points)
        assert result["coverage"] == 0
        assert result["overall_score"] <= 50

    def test_wrong_answer(self):
        """完全错误的答案"""
        key_points = ["连续存储", "随机访问"]
        student_answer = "链表是一种树形结构"

        result = evaluate_free_recall(student_answer, key_points)
        assert result["accuracy"] <= 0.5

    def test_english_key_points(self):
        """英文要点"""
        key_points = ["continuous storage", "random access"]
        student_answer = "arrays use continuous storage and support random access"

        result = evaluate_free_recall(student_answer, key_points)
        assert result["coverage"] > 0


class TestFreeRecallResultModel:
    """测试 FreeRecallResult 数据模型"""

    def test_default_values(self):
        result = FreeRecallResult(question_id="q-1", unit_id="u-1")
        assert result.coverage == 0.0
        assert result.accuracy == 0.0
        assert result.depth == 0.0
        assert result.overall_score == 0.0
        assert result.recalled_points == []
        assert result.missed_points == []

    def test_full_result(self):
        result = FreeRecallResult(
            question_id="q-1",
            unit_id="u-1",
            coverage=0.8,
            accuracy=0.9,
            depth=0.7,
            overall_score=80,
            recalled_points=[
                RecalledPoint(content="连续存储", matched_point="连续存储", is_accurate=True),
            ],
            missed_points=["相同类型元素"],
            gap_report="覆盖了大部分要点",
            mastery_change=0.05,
        )
        assert result.overall_score == 80
        assert len(result.recalled_points) == 1
        assert result.mastery_change == 0.05


class TestStartFreeRecall:
    """测试开始自由回忆会话"""

    @pytest.mark.asyncio
    async def test_basic_start(self, service, sample_units):
        """基本开始自由回忆"""
        session = await service.start_free_recall("user-1", "book-1", ["unit-1"], sample_units)
        assert session.review_type == "free_recall"
        assert len(session.questions) == 1
        assert session.questions[0].question_type == "free_recall"
        assert session.questions[0].recall_context is not None

    @pytest.mark.asyncio
    async def test_recall_context_stores_key_points(self, service, sample_units):
        """recall_context 存储了原始要点"""
        session = await service.start_free_recall("user-1", "book-1", ["unit-1"], sample_units)
        ctx = session.questions[0].recall_context
        assert "key_points" in ctx
        assert "连续存储" in ctx["key_points"]

    @pytest.mark.asyncio
    async def test_empty_units_error(self, service):
        """空单元列表报错"""
        with pytest.raises(ServiceError) as exc_info:
            await service.start_free_recall("user-1", "book-1", [], [])
        assert exc_info.value.code.value == "INSUFFICIENT_DATA"
