"""考前模式测试"""

import pytest
from datetime import datetime
from app.modules.review.exam_mode import create_exam_session, evaluate_exam
from app.modules.review.schemas import ExamConfig, MasteryRecord, ReviewSession, ReviewQuestion


class TestCreateExamSession:
    """测试考试会话创建"""

    def test_basic_exam_creation(self, sample_knowledge_units, sample_mastery_records, sample_exam_config):
        """基本考试创建"""
        session = create_exam_session(
            user_id="user-1",
            book_id="book-1",
            chapter_ids=["chapter-1"],
            config=sample_exam_config,
            knowledge_units=sample_knowledge_units,
            mastery_records=sample_mastery_records,
        )
        assert session.user_id == "user-1"
        assert session.book_id == "book-1"
        assert session.review_type == 'exam'
        assert len(session.questions) > 0

    def test_weak_units_prioritized(self, sample_knowledge_units, sample_exam_config):
        """薄弱知识点优先"""
        # unit-2掌握度最低
        mastery_records = [
            MasteryRecord(
                id="mr-1", user_id="user-1", knowledge_unit_id="unit-1",
                mastery_score=0.9, mastery_level="mastered",
                next_review_at=datetime.now(),
            ),
            MasteryRecord(
                id="mr-2", user_id="user-1", knowledge_unit_id="unit-2",
                mastery_score=0.3, mastery_level="beginner",
                next_review_at=datetime.now(),
            ),
        ]

        config = ExamConfig(question_count=2, focus_on_weak=True)
        session = create_exam_session(
            user_id="user-1",
            book_id="book-1",
            chapter_ids=["chapter-1"],
            config=config,
            knowledge_units=sample_knowledge_units,
            mastery_records=mastery_records,
        )

        # unit-2（薄弱）应被包含
        unit_ids = [q.unit_id for q in session.questions]
        assert "unit-2" in unit_ids

    def test_confused_units_included(self, sample_knowledge_units, sample_exam_config):
        """有"不懂"标记的单元应被包含"""
        config = ExamConfig(question_count=2, focus_on_weak=True)
        session = create_exam_session(
            user_id="user-1",
            book_id="book-1",
            chapter_ids=["chapter-1"],
            config=config,
            knowledge_units=sample_knowledge_units,
            mastery_records=[],
            confused_unit_ids=["unit-1"],
        )

        unit_ids = [q.unit_id for q in session.questions]
        assert "unit-1" in unit_ids

    def test_empty_chapters(self, sample_exam_config):
        """空章节返回空会话"""
        session = create_exam_session(
            user_id="user-1",
            book_id="book-1",
            chapter_ids=["nonexistent"],
            config=sample_exam_config,
            knowledge_units=[],
            mastery_records=[],
        )
        assert len(session.questions) == 0

    def test_question_count_limit(self, sample_knowledge_units, sample_mastery_records):
        """题目数量限制"""
        config = ExamConfig(question_count=2)
        session = create_exam_session(
            user_id="user-1",
            book_id="book-1",
            chapter_ids=["chapter-1", "chapter-2"],
            config=config,
            knowledge_units=sample_knowledge_units,
            mastery_records=sample_mastery_records,
        )
        assert len(session.questions) <= 2

    def test_non_focus_on_weak(self, sample_knowledge_units, sample_mastery_records):
        """不关注薄弱点时随机选题"""
        config = ExamConfig(question_count=5, focus_on_weak=False)
        session = create_exam_session(
            user_id="user-1",
            book_id="book-1",
            chapter_ids=["chapter-1", "chapter-2"],
            config=config,
            knowledge_units=sample_knowledge_units,
            mastery_records=sample_mastery_records,
        )
        assert len(session.questions) > 0


class TestEvaluateExam:
    """测试考试评估"""

    def _create_test_session(self):
        """创建测试用会话"""
        return ReviewSession(
            user_id="user-1",
            book_id="book-1",
            review_type='exam',
            questions=[
                ReviewQuestion(
                    id="q-1", unit_id="unit-1",
                    question="什么是数组？", question_type="short_answer",
                    correct_answer="连续存储的数据结构",
                ),
                ReviewQuestion(
                    id="q-2", unit_id="unit-2",
                    question="什么是链表？", question_type="short_answer",
                    correct_answer="非连续存储的线性表",
                ),
                ReviewQuestion(
                    id="q-3", unit_id="unit-1",
                    question="数组的特点？", question_type="short_answer",
                    correct_answer="随机访问O(1)",
                ),
            ],
            started_at=datetime(2024, 1, 1, 10, 0, 0),
            ended_at=datetime(2024, 1, 1, 10, 30, 0),
        )

    def test_all_correct(self):
        """全部正确"""
        session = self._create_test_session()
        answers = {
            "q-1": "连续存储的数据结构",
            "q-2": "非连续存储的线性表",
            "q-3": "随机访问O(1)",
        }
        result = evaluate_exam(session, answers)
        assert result.score == 100.0
        assert result.passed is True
        assert result.correct_count == 3
        assert result.total_count == 3
        assert len(result.weak_points) == 0

    def test_all_wrong(self):
        """全部错误"""
        session = self._create_test_session()
        answers = {
            "q-1": "错误答案",
            "q-2": "错误答案",
            "q-3": "错误答案",
        }
        result = evaluate_exam(session, answers)
        assert result.score == 0.0
        assert result.passed is False
        assert result.correct_count == 0
        assert len(result.weak_points) == 3

    def test_partial_correct(self):
        """部分正确"""
        session = self._create_test_session()
        answers = {
            "q-1": "连续存储的数据结构",  # 正确
            "q-2": "错误答案",  # 错误
            "q-3": "随机访问O(1)",  # 正确
        }
        result = evaluate_exam(session, answers)
        assert result.score == pytest.approx(66.67, abs=0.1)
        assert result.passed is False  # < 70
        assert result.correct_count == 2

    def test_passing_score(self):
        """全部正确 - 及格"""
        session = self._create_test_session()
        answers = {
            "q-1": "连续存储的数据结构",
            "q-2": "非连续存储的线性表",
            "q-3": "随机访问O(1)",
        }
        result = evaluate_exam(session, answers)
        assert result.passed is True  # 100% >= 70%
        assert result.score == 100.0

    def test_weak_unit_identification(self):
        """识别薄弱单元"""
        session = self._create_test_session()
        answers = {
            "q-1": "正确",
            "q-2": "错误",  # unit-2
            "q-3": "错误",  # unit-1
        }
        result = evaluate_exam(session, answers)
        assert "unit-1" in result.recommended_review or "unit-2" in result.recommended_review

    def test_empty_answers(self):
        """空答案"""
        session = self._create_test_session()
        result = evaluate_exam(session, {})
        assert result.score == 0.0
        assert result.passed is False

    def test_time_spent(self):
        """计算用时"""
        session = self._create_test_session()
        result = evaluate_exam(session, {})
        assert result.time_spent_minutes == 30.0
