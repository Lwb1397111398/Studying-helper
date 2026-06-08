"""复习服务测试"""

import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from app.modules.review.service import ReviewService
from app.modules.review.schemas import (
    MasteryRecord, ExamConfig, ExportFormat,
)
from app.modules.knowledge_splitter.schemas import KnowledgeUnit
from app.common.errors import ServiceError


def _make_session_row(session, book_id="book-1"):
    """创建模拟的 ReviewSessionModel 行"""
    row = MagicMock()
    row.book_id = book_id
    row.user_id = "user-1"
    row.review_type = session.review_type
    row.started_at = session.started_at
    row.questions_json = json.dumps(
        [{"id": q.id, "unit_id": q.unit_id, "question": q.question,
          "question_type": q.question_type, "options": q.options,
          "correct_answer": q.correct_answer, "user_answer": q.user_answer,
          "is_correct": q.is_correct, "pairs": q.pairs,
          "sequence": q.sequence, "statement": q.statement}
         for q in session.questions],
        ensure_ascii=False,
    )
    return row


def _make_session_result(session_row):
    """创建模拟的查询结果，scalar_one_or_none 返回 session_row"""
    result = _MockResult(session_row)
    return result


class _MockResult:
    """模拟 SQLAlchemy 查询结果"""
    def __init__(self, scalar_value=None):
        self._scalar = scalar_value

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return []


class _MockAsyncContext:
    """模拟 async db session"""

    def __init__(self):
        self.add = MagicMock()
        self._results = []
        self._default_result = _MockResult()

    def queue_result(self, result_or_scalar=None):
        """排队一个查询结果。传 _MockResult 直接用，传其他值则包成 _MockResult"""
        if isinstance(result_or_scalar, _MockResult):
            self._results.append(result_or_scalar)
        else:
            self._results.append(_MockResult(result_or_scalar))

    async def execute(self, *args, **kwargs):
        if self._results:
            return self._results.pop(0)
        return self._default_result


@pytest.fixture
def mock_db():
    """创建 mock db session"""
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
            key_points=["连续存储", "随机访问"],
        ),
        KnowledgeUnit(
            id="unit-2", book_id="book-1", chapter_id="ch-1",
            title="链表", content="链表内容",
            order_index=1, char_offset_start=100, char_offset_end=200,
            summary="链表是动态结构",
            key_points=["非连续存储"],
        ),
    ]


@pytest.fixture
def sample_mastery():
    now = datetime.now(timezone.utc)
    return [
        MasteryRecord(
            id="mr-1", user_id="user-1", knowledge_unit_id="unit-1",
            book_id="book-1",
            mastery_score=0.8, mastery_level="proficient",
            next_review_at=now - timedelta(hours=1),
            review_count=5, ease_factor=2.5, interval_days=6,
        ),
        MasteryRecord(
            id="mr-2", user_id="user-1", knowledge_unit_id="unit-2",
            book_id="book-1",
            mastery_score=0.3, mastery_level="beginner",
            next_review_at=now + timedelta(days=5),
            review_count=1, ease_factor=2.5, interval_days=1,
        ),
    ]


class TestGetDueReviews:
    """测试获取到期复习"""

    def test_returns_due_records(self, service, sample_mastery):
        """返回到期的记录"""
        due = service.get_due_reviews("user-1", "book-1", sample_mastery)
        assert len(due) == 1
        assert due[0].id == "mr-1"

    def test_empty_when_none_due(self, service):
        """无到期记录时返回空列表"""
        now = datetime.now(timezone.utc)
        records = [
            MasteryRecord(
                id="mr-1", user_id="user-1", knowledge_unit_id="unit-1",
                book_id="book-1",
                mastery_score=0.8, mastery_level="proficient",
                next_review_at=now + timedelta(days=10),
            ),
        ]
        due = service.get_due_reviews("user-1", "book-1", records)
        assert len(due) == 0

    def test_sorted_by_due_time(self, service):
        """按到期时间排序"""
        now = datetime.now(timezone.utc)
        records = [
            MasteryRecord(
                id="mr-1", user_id="user-1", knowledge_unit_id="unit-1",
                book_id="book-1",
                mastery_score=0.5, mastery_level="familiar",
                next_review_at=now - timedelta(hours=2),
            ),
            MasteryRecord(
                id="mr-2", user_id="user-1", knowledge_unit_id="unit-2",
                book_id="book-1",
                mastery_score=0.5, mastery_level="familiar",
                next_review_at=now - timedelta(hours=1),
            ),
        ]
        due = service.get_due_reviews("user-1", "book-1", records)
        assert due[0].id == "mr-1"

    def test_filters_by_book_id(self, service):
        """按 book_id 过滤"""
        now = datetime.now(timezone.utc)
        records = [
            MasteryRecord(
                id="mr-1", user_id="user-1", knowledge_unit_id="unit-1",
                book_id="book-1",
                mastery_score=0.5, mastery_level="familiar",
                next_review_at=now - timedelta(hours=1),
            ),
            MasteryRecord(
                id="mr-2", user_id="user-1", knowledge_unit_id="unit-2",
                book_id="book-2",
                mastery_score=0.5, mastery_level="familiar",
                next_review_at=now - timedelta(hours=1),
            ),
        ]
        due = service.get_due_reviews("user-1", "book-1", records)
        assert len(due) == 1
        assert due[0].id == "mr-1"


class TestStartReview:
    """测试开始复习"""

    @pytest.mark.asyncio
    async def test_basic_start(self, service, sample_units):
        """基本开始复习"""
        session = await service.start_review("user-1", "book-1", ["unit-1"], sample_units)
        assert session.user_id == "user-1"
        assert session.review_type == "spaced"
        assert len(session.questions) > 0

    @pytest.mark.asyncio
    async def test_multiple_units(self, service, sample_units):
        """多单元复习"""
        session = await service.start_review("user-1", "book-1", ["unit-1", "unit-2"], sample_units)
        # 每单元生成多道不同题型
        unit_ids = {q.unit_id for q in session.questions}
        assert "unit-1" in unit_ids
        assert "unit-2" in unit_ids

    @pytest.mark.asyncio
    async def test_empty_units_error(self, service):
        """空单元列表报错"""
        with pytest.raises(ServiceError) as exc_info:
            await service.start_review("user-1", "book-1", [], [])
        assert exc_info.value.code.value == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_invalid_unit_skipped(self, service, sample_units):
        """无效单元ID被跳过"""
        session = await service.start_review(
            "user-1", "book-1", ["unit-1", "nonexistent"], sample_units
        )
        # 只有 unit-1 生成了题目，nonexistent 被跳过
        unit_ids = {q.unit_id for q in session.questions}
        assert unit_ids == {"unit-1"}


class TestSubmitReviewAnswer:
    """测试提交复习答案"""

    @pytest.mark.asyncio
    async def test_correct_answer(self, service, sample_units, mock_db):
        """正确答案反馈"""
        session = await service.start_review("user-1", "book-1", ["unit-1"], sample_units)
        question = session.questions[0]

        s_row = _make_session_row(session)
        # submit_review_answer 调用链：
        # 1. execute → result (scalar_one_or_none → s_row, 检查 session 存在)
        # 2. _load_session_questions → execute → result (scalar_one_or_none → s_row)
        # 3. _get_mastery → execute → result (scalar_one_or_none → None)
        # 4. _upsert_mastery → execute → result (scalar_one_or_none → None)
        # 5. _save_session → execute → result (scalar_one_or_none → None)
        mock_db.queue_result(_make_session_result(s_row))
        mock_db.queue_result(_make_session_result(s_row))
        mock_db.queue_result(_make_session_result(None))
        mock_db.queue_result(_make_session_result(None))
        mock_db.queue_result(_make_session_result(None))

        feedback = await service.submit_review_answer(
            session.id, question.id, question.correct_answer,
            user_id="user-1",
        )
        assert feedback.is_correct is True
        assert feedback.mastery_change > 0

    @pytest.mark.asyncio
    async def test_wrong_answer(self, service, sample_units, mock_db):
        """错误答案反馈"""
        session = await service.start_review("user-1", "book-1", ["unit-1"], sample_units)
        question = session.questions[0]

        s_row = _make_session_row(session)
        mock_db.queue_result(_make_session_result(s_row))
        mock_db.queue_result(_make_session_result(s_row))
        mock_db.queue_result(_make_session_result(None))
        mock_db.queue_result(_make_session_result(None))
        mock_db.queue_result(_make_session_result(None))

        feedback = await service.submit_review_answer(
            session.id, question.id, "完全错误的答案xyz",
            user_id="user-1",
        )
        assert feedback.is_correct is False
        assert feedback.mastery_change < 0

    @pytest.mark.asyncio
    async def test_invalid_session(self, service, mock_db):
        """无效会话ID"""
        mock_db.queue_result(None)

        with pytest.raises(ServiceError) as exc_info:
            await service.submit_review_answer("nonexistent", "q-1", "答案", user_id="user-1")
        assert exc_info.value.code.value == "NOT_FOUND"


class TestAssessMastery:
    """测试掌握度评估"""

    def test_with_history(self, service):
        """有复习历史的评估"""
        history = [
            {"is_correct": True, "response_time": 20.0, "score": 0.8},
            {"is_correct": True, "response_time": 25.0, "score": 0.85},
            {"is_correct": False, "response_time": 30.0, "score": 0.4},
        ]
        result = service.assess_mastery("user-1", "unit-1", history)
        assert 0.0 <= result.score <= 1.0
        assert result.level in ['beginner', 'learning', 'familiar', 'proficient', 'mastered']

    def test_without_history(self, service):
        """无复习历史的评估"""
        result = service.assess_mastery("user-1", "unit-1", [])
        assert result.unit_id == "unit-1"

    def test_with_confused(self, service):
        """有"不懂"标记的评估"""
        history = [
            {"is_correct": True, "response_time": 20.0, "score": 0.8},
        ]
        result_no = service.assess_mastery("user-1", "unit-1", history, confused_count=0)
        result_yes = service.assess_mastery("user-1", "unit-1", history, confused_count=2)
        assert result_yes.score < result_no.score


class TestStartExam:
    """测试考前模式"""

    @pytest.mark.asyncio
    async def test_basic_exam(self, service, sample_units, sample_mastery):
        """基本考试创建"""
        config = ExamConfig(question_count=2)
        session = await service.start_exam(
            "user-1", "book-1", ["ch-1"], config, sample_units, sample_mastery
        )
        assert session.review_type == 'exam'
        assert len(session.questions) > 0


class TestSubmitExam:
    """测试提交考试"""

    @pytest.mark.asyncio
    async def test_basic_submit(self, service, sample_units, sample_mastery, mock_db):
        """基本提交考试"""
        config = ExamConfig(question_count=2)
        session = await service.start_exam(
            "user-1", "book-1", ["ch-1"], config, sample_units, sample_mastery
        )

        answers = {}
        for q in session.questions:
            answers[q.id] = q.correct_answer

        s_row = _make_session_row(session)
        # submit_exam: load_session_questions, _save_session
        mock_db.queue_result(_make_session_result(s_row))
        mock_db.queue_result(_make_session_result(None))  # _save_session

        result = await service.submit_exam(session.id, answers, user_id="user-1")
        assert result.score == 100.0
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_invalid_session(self, service, mock_db):
        """无效会话"""
        mock_db.queue_result(_make_session_result(None))

        with pytest.raises(ServiceError):
            await service.submit_exam("nonexistent", {}, user_id="user-1")


class TestExport:
    """测试导出功能"""

    def test_markdown_export(self, service):
        """Markdown导出"""
        result = service.export(
            "测试书", ExportFormat.MARKDOWN,
            [{"id": "ch-1", "title": "基础", "chapter_number": 1}],
            [{"id": "u-1", "chapter_id": "ch-1", "title": "数组", "summary": "摘要"}],
            {"u-1": {"score": 0.8, "level": "proficient"}},
        )
        assert result.format == ExportFormat.MARKDOWN
        assert "测试书" in result.content

    def test_anki_export(self, service):
        """Anki导出"""
        result = service.export(
            "测试书", ExportFormat.ANKI,
            [], [{"id": "u-1", "title": "数组", "summary": "摘要"}],
            {},
        )
        assert result.format == ExportFormat.ANKI

    def test_wrong_answers_export(self, service):
        """错题集导出"""
        result = service.export(
            "测试书", ExportFormat.WRONG_ANSWERS,
            [], [], {},
            wrong_questions=[{"question": "问题", "correct_answer": "答案"}],
        )
        assert result.format == ExportFormat.WRONG_ANSWERS

    def test_mindmap_mermaid_export(self, service):
        """Mermaid导出"""
        result = service.export(
            "测试书", ExportFormat.MIND_MAP_MERMAID,
            [{"id": "ch-1", "title": "基础", "chapter_number": 1}],
            [{"id": "u-1", "chapter_id": "ch-1", "title": "数组"}],
            {},
        )
        assert result.format == ExportFormat.MIND_MAP_MERMAID

    def test_mindmap_plantuml_export(self, service):
        """PlantUML导出"""
        result = service.export(
            "测试书", ExportFormat.MIND_MAP_PLANTUML,
            [{"id": "ch-1", "title": "基础", "chapter_number": 1}],
            [{"id": "u-1", "chapter_id": "ch-1", "title": "数组"}],
            {},
        )
        assert result.format == ExportFormat.MIND_MAP_PLANTUML
