import pytest
from app.modules.ai_learning.schemas import LearnedUnit, Concept, SelfAssessment


@pytest.fixture
def sample_learned_units():
    """创建测试用的LearnedUnit列表"""
    units = []
    for i in range(10):
        units.append(LearnedUnit(
            unit_id=f"unit-{i}",
            book_id="book-1",
            summary=f"这是第{i}个单元的摘要",
            key_points=[f"要点{i}-1", f"要点{i}-2"],
            concepts=[Concept(name=f"概念{i}", definition=f"定义{i}")],
            difficulty_level=(i % 5) + 1,
            importance_score=0.5 + (i % 5) * 0.1,
            prerequisites=[],
            self_assessment=SelfAssessment(
                score=85,
                test_questions=[],
                self_answers=[],
                weak_points=[],
                needs_deepening=False
            )
        ))
    return units


@pytest.fixture
def style_analyzer():
    from app.modules.learning_plan.style_analyzer import LearningStyleAnalyzer
    return LearningStyleAnalyzer()
