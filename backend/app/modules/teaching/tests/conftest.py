"""教学模块测试 fixtures"""
import pytest
from app.modules.ai_learning.schemas import LearnedUnit, Concept, SelfAssessment, TestQuestion
from app.modules.ai_learning.tests.mock_llm import MockLLMClient
from app.modules.teaching.schemas import UserTeachingProfile


@pytest.fixture
def mock_llm():
    return MockLLMClient()


@pytest.fixture
def sample_unit():
    return LearnedUnit(
        unit_id="unit-1",
        book_id="book-1",
        summary="数组是一种线性表数据结构，它用连续的存储空间存储相同类型的元素。",
        key_points=["数组是线性表", "连续存储", "相同类型"],
        concepts=[
            Concept(name="数组", definition="用连续存储空间存储相同类型元素的数据结构",
                   examples=["int arr[10]"], related_concepts=["链表"])
        ],
        difficulty_level=2,
        importance_score=0.8,
        prerequisites=["变量", "数据类型"],
        self_assessment=SelfAssessment(
            score=85,
            test_questions=[
                TestQuestion(
                    question="什么是数组？",
                    question_type="short_answer",
                    correct_answer="用连续存储空间存储相同类型元素的数据结构",
                    explanation="数组是最基本的数据结构之一"
                )
            ],
            self_answers=["用连续存储空间存储相同类型元素的数据结构"],
            weak_points=[],
            needs_deepening=False
        )
    )


@pytest.fixture
def sample_unit_hard():
    """高难度知识单元"""
    return LearnedUnit(
        unit_id="unit-hard",
        book_id="book-1",
        summary="B+树是一种多路平衡查找树，所有叶子节点通过链表相连，支持高效的范围查询。",
        key_points=["多路平衡", "叶子链表", "范围查询", "磁盘友好"],
        concepts=[
            Concept(name="B+树", definition="多路平衡查找树，数据全在叶子节点，叶子通过链表连接",
                   examples=["数据库索引"], related_concepts=["B树", "红黑树"])
        ],
        difficulty_level=5,
        importance_score=0.95,
        prerequisites=["二叉树", "平衡树", "磁盘IO原理"],
        self_assessment=SelfAssessment(
            score=60,
            test_questions=[
                TestQuestion(
                    question="B+树与B树的核心区别是什么？",
                    question_type="short_answer",
                    correct_answer="B+树数据全在叶子节点，叶子通过链表连接，B树数据可在任意节点",
                    explanation="B+树的结构优化范围查询"
                )
            ],
            self_answers=[""],
            weak_points=["范围查询原理"],
            needs_deepening=True
        )
    )


@pytest.fixture
def sample_unit_procedure():
    """程序性知识单元"""
    return LearnedUnit(
        unit_id="unit-proc",
        book_id="book-1",
        summary="如何使用二分查找算法在有序数组中查找目标元素。",
        key_points=["步骤：确定左右边界", "步骤：计算中间位置", "步骤：比较并缩小范围", "步骤：重复直到找到或边界交叉"],
        concepts=[
            Concept(name="二分查找", definition="在有序数组中通过不断折半缩小搜索范围的算法",
                   examples=["在电话簿中查号码"], related_concepts=["线性查找"])
        ],
        difficulty_level=3,
        importance_score=0.85,
        prerequisites=["数组", "循环"],
        self_assessment=SelfAssessment(
            score=75,
            test_questions=[
                TestQuestion(
                    question="二分查找的前提条件是什么？",
                    question_type="short_answer",
                    correct_answer="数组必须是有序的",
                    explanation="二分查找依赖有序性"
                )
            ],
            self_answers=["数组有序"],
            weak_points=[],
            needs_deepening=False
        )
    )


@pytest.fixture
def sample_units(sample_unit, sample_unit_hard, sample_unit_procedure):
    return [sample_unit, sample_unit_hard, sample_unit_procedure]


@pytest.fixture
def sample_units_basic(sample_unit):
    return [sample_unit]


@pytest.fixture
def mock_user_profile():
    """普通用户画像"""
    return UserTeachingProfile(
        avg_mastery_score=0.5,
        total_sessions=5,
        preferred_style="",
        weakness_tags=["递归"],
        avg_test_score=0.65,
    )


@pytest.fixture
def mock_user_profile_advanced():
    """高水平用户画像"""
    return UserTeachingProfile(
        avg_mastery_score=0.85,
        total_sessions=20,
        preferred_style="theory_first",
        weakness_tags=[],
        avg_test_score=0.9,
    )


@pytest.fixture
def mock_user_profile_beginner():
    """新手用户画像"""
    return UserTeachingProfile(
        avg_mastery_score=0.15,
        total_sessions=1,
        preferred_style="",
        weakness_tags=["基础概念", "数据结构"],
        avg_test_score=0.3,
    )
