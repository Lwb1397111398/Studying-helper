"""SM-2间隔重复算法测试"""

import pytest
from app.modules.review.spaced_repetition import calculate_next_review, quality_from_correctness


class TestCalculateNextReview:
    """测试SM-2算法的下次复习计算"""

    def test_first_success(self):
        """首次成功回答：间隔1天"""
        interval, ease, _ = calculate_next_review(quality=4, repetitions=0, ease_factor=2.5, interval=1)
        assert interval == 1
        assert ease >= 2.5  # 难度因子应保持或增加

    def test_second_success(self):
        """第二次成功回答：间隔6天"""
        interval, ease, _ = calculate_next_review(quality=4, repetitions=1, ease_factor=2.5, interval=1)
        assert interval == 6

    def test_subsequent_success(self):
        """后续成功回答：间隔=前间隔*难度因子"""
        interval, ease, _ = calculate_next_review(quality=4, repetitions=2, ease_factor=2.5, interval=6)
        assert interval == round(6 * (2.5 + (0.1 - (5 - 4) * (0.08 + (5 - 4) * 0.02))))

    def test_failure_resets_interval(self):
        """失败回答：间隔重置为1天"""
        interval, ease, _ = calculate_next_review(quality=2, repetitions=5, ease_factor=2.5, interval=30)
        assert interval == 1

    def test_failure_resets_repetitions(self):
        """失败回答后再次成功：从头开始计数"""
        # 失败
        interval1, _, _ = calculate_next_review(quality=2, repetitions=3, ease_factor=2.5, interval=10)
        assert interval1 == 1
        # 再次成功（repetitions应重置为0，所以下次间隔1天）
        interval2, _, _ = calculate_next_review(quality=4, repetitions=0, ease_factor=2.5, interval=1)
        assert interval2 == 1

    def test_ease_factor_minimum(self):
        """难度因子最低不低于1.3"""
        # 连续多次失败
        _, ease, _ = calculate_next_review(quality=0, repetitions=0, ease_factor=1.3, interval=1)
        assert ease >= 1.3

    def test_ease_factor_increases_on_perfect(self):
        """完美回答增加难度因子"""
        _, ease_perfect, _ = calculate_next_review(quality=5, repetitions=2, ease_factor=2.5, interval=10)
        _, ease_normal, _ = calculate_next_review(quality=4, repetitions=2, ease_factor=2.5, interval=10)
        assert ease_perfect >= ease_normal

    def test_ease_factor_decreases_on_hard(self):
        """困难回答降低难度因子"""
        _, ease_hard, _ = calculate_next_review(quality=3, repetitions=2, ease_factor=2.5, interval=10)
        _, ease_easy, _ = calculate_next_review(quality=5, repetitions=2, ease_factor=2.5, interval=10)
        assert ease_hard <= ease_easy

    def test_boundary_quality_zero(self):
        """质量分数为0的情况"""
        interval, ease, _ = calculate_next_review(quality=0, repetitions=2, ease_factor=2.5, interval=10)
        assert interval == 1

    def test_boundary_quality_five(self):
        """质量分数为5的情况"""
        interval, _, _ = calculate_next_review(quality=5, repetitions=0, ease_factor=2.5, interval=1)
        assert interval == 1  # 首次成功


class TestQualityFromCorrectness:
    """测试正确性到质量分数的转换"""

    def test_correct_fast(self):
        """正确+快速回答：质量5"""
        quality = quality_from_correctness(is_correct=True, response_time=5.0, avg_time=10.0)
        assert quality == 5

    def test_correct_normal(self):
        """正确+正常速度：质量4"""
        quality = quality_from_correctness(is_correct=True, response_time=10.0, avg_time=10.0)
        assert quality == 4

    def test_correct_slow(self):
        """正确+慢速回答：质量3"""
        quality = quality_from_correctness(is_correct=True, response_time=15.0, avg_time=10.0)
        assert quality == 3

    def test_incorrect_fast(self):
        """错误+快速回答：质量2"""
        quality = quality_from_correctness(is_correct=False, response_time=5.0, avg_time=10.0)
        assert quality == 2

    def test_incorrect_slow(self):
        """错误+慢速回答：质量1"""
        quality = quality_from_correctness(is_correct=False, response_time=15.0, avg_time=10.0)
        assert quality == 1

    def test_invalid_avg_time(self):
        """平均时间无效时的默认行为"""
        quality = quality_from_correctness(is_correct=True, response_time=5.0, avg_time=0.0)
        assert quality == 4

    def test_incorrect_with_invalid_avg(self):
        """错误+无效平均时间"""
        quality = quality_from_correctness(is_correct=False, response_time=5.0, avg_time=-1.0)
        assert quality == 1
