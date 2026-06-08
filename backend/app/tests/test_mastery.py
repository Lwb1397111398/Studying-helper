"""掌握度工具测试"""

from app.common.mastery import score_to_mastery_level


def test_score_to_mastery_level_maps_thresholds():
    assert score_to_mastery_level(0.8) == "proficient"
    assert score_to_mastery_level(0.6) == "familiar"
    assert score_to_mastery_level(0.3) == "learning"
    assert score_to_mastery_level(0.29) == "new"


def test_score_to_mastery_level_clamps_score():
    assert score_to_mastery_level(2) == "proficient"
    assert score_to_mastery_level(-1) == "new"
