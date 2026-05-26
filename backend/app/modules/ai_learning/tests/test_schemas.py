"""LearnedUnit schemas 测试"""

import pytest
from app.modules.ai_learning.schemas import LearnedUnit, SelfAssessment


def test_learned_unit_self_assessment_optional():
    """self_assessment 应为可选字段，不传也能构造"""
    unit = LearnedUnit(
        unit_id="u1",
        book_id="b1",
        summary="摘要",
        key_points=["要点1"],
        concepts=[],
        difficulty_level=3,
        importance_score=0.5,
        prerequisites=[],
    )
    assert unit.self_assessment is None


def test_learned_unit_with_calibration_fields():
    """新增校准字段：calibrated_difficulty 和 calibration_count"""
    unit = LearnedUnit(
        unit_id="u1",
        book_id="b1",
        summary="摘要",
        key_points=["要点1"],
        concepts=[],
        difficulty_level=3,
        importance_score=0.5,
        prerequisites=[],
        calibrated_difficulty=3.5,
        calibration_count=2,
    )
    assert unit.calibrated_difficulty == 3.5
    assert unit.calibration_count == 2


def test_learned_unit_calibration_defaults():
    """校准字段默认值：calibrated_difficulty=None, calibration_count=0"""
    unit = LearnedUnit(
        unit_id="u1",
        book_id="b1",
        summary="摘要",
        key_points=["要点1"],
        concepts=[],
        difficulty_level=3,
        importance_score=0.5,
        prerequisites=[],
    )
    assert unit.calibrated_difficulty is None
    assert unit.calibration_count == 0
