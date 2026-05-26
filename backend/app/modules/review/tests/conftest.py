"""复习引擎测试夹具"""

import pytest
from datetime import datetime, timedelta
from app.modules.review.schemas import MasteryRecord, ExamConfig
from app.modules.knowledge_splitter.schemas import KnowledgeUnit


@pytest.fixture
def sample_knowledge_units():
    """示例知识单元列表"""
    return [
        KnowledgeUnit(
            id="unit-1",
            book_id="book-1",
            chapter_id="chapter-1",
            title="数组基础",
            content="数组是一种线性表，用连续的存储空间存储相同类型的元素。",
            order_index=0,
            char_offset_start=0,
            char_offset_end=100,
            summary="数组是基本的数据结构，支持随机访问。",
            key_points=["连续存储", "随机访问O(1)", "固定大小"],
            difficulty_level=2,
        ),
        KnowledgeUnit(
            id="unit-2",
            book_id="book-1",
            chapter_id="chapter-1",
            title="链表结构",
            content="链表是一种物理存储单元上非连续的线性表。",
            order_index=1,
            char_offset_start=100,
            char_offset_end=200,
            summary="链表通过指针连接节点，支持动态大小。",
            key_points=["非连续存储", "插入删除O(1)", "需要额外指针空间"],
            difficulty_level=3,
        ),
        KnowledgeUnit(
            id="unit-3",
            book_id="book-1",
            chapter_id="chapter-2",
            title="二叉树遍历",
            content="二叉树的遍历包括前序、中序、后序和层序遍历。",
            order_index=2,
            char_offset_start=200,
            char_offset_end=300,
            summary="二叉树遍历是树结构的基本操作。",
            key_points=["前序：根左右", "中序：左根右", "后序：左右根"],
            difficulty_level=4,
        ),
    ]


@pytest.fixture
def sample_mastery_records():
    """示例掌握度记录"""
    now = datetime.now()
    return [
        MasteryRecord(
            id="mr-1",
            user_id="user-1",
            knowledge_unit_id="unit-1",
            mastery_score=0.8,
            mastery_level="proficient",
            last_reviewed_at=now - timedelta(days=2),
            next_review_at=now - timedelta(days=1),  # 已到期
            review_count=5,
            ease_factor=2.5,
            interval_days=6,
        ),
        MasteryRecord(
            id="mr-2",
            user_id="user-1",
            knowledge_unit_id="unit-2",
            mastery_score=0.3,
            mastery_level="beginner",
            last_reviewed_at=now - timedelta(days=1),
            next_review_at=now - timedelta(hours=1),  # 已到期
            review_count=1,
            ease_factor=2.5,
            interval_days=1,
        ),
        MasteryRecord(
            id="mr-3",
            user_id="user-1",
            knowledge_unit_id="unit-3",
            mastery_score=0.95,
            mastery_level="mastered",
            last_reviewed_at=now - timedelta(days=5),
            next_review_at=now + timedelta(days=10),  # 未到期
            review_count=10,
            ease_factor=2.8,
            interval_days=30,
        ),
    ]


@pytest.fixture
def sample_exam_config():
    """示例考试配置"""
    return ExamConfig(
        question_count=5,
        time_limit_minutes=10,
        passing_score=70.0,
        difficulty_distribution={'easy': 0.3, 'medium': 0.5, 'hard': 0.2},
        focus_on_weak=True,
    )


@pytest.fixture
def sample_chapters():
    """示例章节列表"""
    return [
        {"id": "chapter-1", "title": "基础数据结构", "chapter_number": 1},
        {"id": "chapter-2", "title": "树与图", "chapter_number": 2},
    ]
