"""掌握度评估器测试"""

import pytest
from datetime import datetime
from app.modules.review.mastery_evaluator import evaluate_mastery


class TestEvaluateMastery:
    """测试5维度掌握度评估"""

    def test_basic_evaluation(self):
        """基本评估：中等水平"""
        result = evaluate_mastery(
            unit_id="unit-1",
            correct_count=7,
            total_count=10,
            response_times=[20.0, 25.0, 30.0],
            avg_response_time=30.0,
            consistency_scores=[0.7, 0.8, 0.6],
        )
        assert 0.0 <= result.score <= 1.0
        assert result.level in ['beginner', 'familiar', 'proficient', 'mastered']
        assert result.unit_id == "unit-1"

    def test_mastered_level(self):
        """高分评估：mastered等级"""
        result = evaluate_mastery(
            unit_id="unit-1",
            correct_count=10,
            total_count=10,
            response_times=[10.0, 12.0, 8.0],
            avg_response_time=30.0,
            consistency_scores=[0.9, 0.95, 0.92],
            explanation_score=0.95,
            application_score=0.9,
        )
        assert result.score >= 0.9
        assert result.level == 'mastered'

    def test_beginner_level(self):
        """低分评估：beginner等级"""
        result = evaluate_mastery(
            unit_id="unit-1",
            correct_count=1,
            total_count=10,
            response_times=[60.0, 55.0, 70.0],
            avg_response_time=30.0,
            consistency_scores=[0.2, 0.1, 0.15],
            explanation_score=0.1,
            application_score=0.1,
        )
        assert result.score < 0.4
        assert result.level == 'beginner'

    def test_proficient_level(self):
        """中高分评估：proficient等级"""
        result = evaluate_mastery(
            unit_id="unit-1",
            correct_count=8,
            total_count=10,
            response_times=[20.0, 25.0, 22.0],
            avg_response_time=30.0,
            consistency_scores=[0.7, 0.75, 0.8],
            explanation_score=0.7,
            application_score=0.6,
        )
        assert result.level in ['proficient', 'mastered']

    def test_confused_penalty(self):
        """"不懂"标记扣分"""
        result_no_confused = evaluate_mastery(
            unit_id="unit-1",
            correct_count=8,
            total_count=10,
            response_times=[20.0],
            avg_response_time=30.0,
            consistency_scores=[0.8],
            confused_count=0,
        )
        result_confused = evaluate_mastery(
            unit_id="unit-1",
            correct_count=8,
            total_count=10,
            response_times=[20.0],
            avg_response_time=30.0,
            consistency_scores=[0.8],
            confused_count=3,
        )
        # 有"不懂"标记的分数应更低
        assert result_confused.score < result_no_confused.score
        # 每个"不懂"扣0.05，3个扣0.15
        assert abs(result_no_confused.score - result_confused.score - 0.15) < 0.01

    def test_no_data(self):
        """无数据时的默认评估"""
        result = evaluate_mastery(
            unit_id="unit-1",
            correct_count=0,
            total_count=0,
            response_times=[],
            avg_response_time=30.0,
            consistency_scores=[],
        )
        assert result.score >= 0.0
        assert len(result.weak_points) > 0

    def test_weak_points_identification(self):
        """薄弱点识别"""
        result = evaluate_mastery(
            unit_id="unit-1",
            correct_count=3,
            total_count=10,
            response_times=[60.0],
            avg_response_time=30.0,
            consistency_scores=[0.2, 0.8],
            explanation_score=0.2,
            application_score=0.2,
            confused_count=2,
        )
        # 应识别多个薄弱点
        assert len(result.weak_points) >= 3

    def test_dimensions_complete(self):
        """维度分数完整性"""
        result = evaluate_mastery(
            unit_id="unit-1",
            correct_count=5,
            total_count=10,
            response_times=[30.0],
            avg_response_time=30.0,
            consistency_scores=[0.5],
        )
        assert 'recall_accuracy' in result.dimensions
        assert 'response_speed' in result.dimensions
        assert 'consistency' in result.dimensions
        assert 'explanation' in result.dimensions
        assert 'application' in result.dimensions

    def test_recommended_review_time(self):
        """推荐复习时间与掌握度相关"""
        result_high = evaluate_mastery(
            unit_id="unit-1",
            correct_count=10,
            total_count=10,
            response_times=[10.0],
            avg_response_time=30.0,
            consistency_scores=[0.95],
            explanation_score=0.95,
            application_score=0.95,
        )
        result_low = evaluate_mastery(
            unit_id="unit-2",
            correct_count=2,
            total_count=10,
            response_times=[60.0],
            avg_response_time=30.0,
            consistency_scores=[0.2],
            explanation_score=0.2,
            application_score=0.2,
        )
        # 掌握度高的推荐时间应更远
        assert result_high.recommended_review_at > result_low.recommended_review_at

    def test_score_bounds(self):
        """分数边界检查"""
        # 最高可能分数
        result_max = evaluate_mastery(
            unit_id="unit-1",
            correct_count=100,
            total_count=100,
            response_times=[1.0],
            avg_response_time=30.0,
            consistency_scores=[1.0],
            explanation_score=1.0,
            application_score=1.0,
            confused_count=0,
        )
        assert result_max.score <= 1.0

        # 最低可能分数
        result_min = evaluate_mastery(
            unit_id="unit-1",
            correct_count=0,
            total_count=100,
            response_times=[100.0],
            avg_response_time=30.0,
            consistency_scores=[0.0],
            explanation_score=0.0,
            application_score=0.0,
            confused_count=100,
        )
        assert result_min.score >= 0.0

    def test_calibrate_difficulty_no_data(self):
        """无校准时返回 LLM 原始难度"""
        from app.modules.review.mastery_evaluator import calibrate_difficulty
        result = calibrate_difficulty(llm_difficulty=3.0, mastery_score=None, calibration_count=0)
        assert result == 3.0

    def test_calibrate_difficulty_with_data(self):
        """有校准时加权混合：LLM 40% + 实际 60%"""
        from app.modules.review.mastery_evaluator import calibrate_difficulty
        # mastery_score=0.3 → actual_difficulty=5-0.3*4=3.8, weight=min(5/10,0.6)=0.5
        # result = 3.0*0.5 + 3.8*0.5 = 3.4
        result = calibrate_difficulty(llm_difficulty=3.0, mastery_score=0.3, calibration_count=5)
        assert 3.3 <= result <= 3.5

    def test_calibrate_difficulty_high_mastery(self):
        """掌握度高 → 校准后难度应下降"""
        from app.modules.review.mastery_evaluator import calibrate_difficulty
        # mastery_score=0.95 → actual_difficulty=5-0.95*4=1.2, weight=min(10/10,0.6)=0.6
        # result = 4.0*0.4 + 1.2*0.6 = 1.6+0.72 = 2.32
        result = calibrate_difficulty(llm_difficulty=4.0, mastery_score=0.95, calibration_count=10)
        assert 2.0 <= result <= 2.5
