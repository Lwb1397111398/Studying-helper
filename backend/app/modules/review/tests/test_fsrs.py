"""FSRS 算法单元测试"""

import pytest
from datetime import datetime, timedelta
from app.modules.review.fsrs import (
    FSRSScheduler,
    FSRSState,
    FSRSResult,
    migrate_sm2_to_fsrs,
    DEFAULT_PARAMETERS
)


class TestFSRSScheduler:
    """FSRS 调度器测试"""

    def setup_method(self):
        """测试前初始化"""
        self.scheduler = FSRSScheduler()

    def test_initialization(self):
        """测试初始化"""
        assert self.scheduler.w == DEFAULT_PARAMETERS
        assert len(self.scheduler.w) == 17

    def test_custom_parameters(self):
        """测试自定义参数"""
        custom_params = [0.5] * 17
        scheduler = FSRSScheduler(custom_params)
        assert scheduler.w == custom_params

    def test_invalid_parameters(self):
        """测试无效参数"""
        with pytest.raises(ValueError):
            FSRSScheduler([0.5] * 10)  # 长度错误

    def test_init_card_again(self):
        """测试新卡片初始化（AGAIN）"""
        now = datetime.now()
        state = FSRSState(reps=0)
        result = self.scheduler.next_review(state, grade=1, now=now)

        assert result.stability > 0
        assert 0 <= result.difficulty <= 10
        assert result.scheduled_days >= 1
        assert result.retrievability == 1.0
        assert result.next_review > now

    def test_init_card_good(self):
        """测试新卡片初始化（GOOD）"""
        now = datetime.now()
        state = FSRSState(reps=0)
        result = self.scheduler.next_review(state, grade=3, now=now)

        assert result.stability > 0
        assert result.scheduled_days >= 1
        assert result.next_review > now

    def test_init_card_easy(self):
        """测试新卡片初始化（EASY）"""
        now = datetime.now()
        state = FSRSState(reps=0)
        result = self.scheduler.next_review(state, grade=4, now=now)

        # EASY 应该有更长的间隔
        result_good = self.scheduler.next_review(FSRSState(reps=0), grade=3, now=now)
        assert result.scheduled_days >= result_good.scheduled_days

    def test_update_card_again(self):
        """测试卡片更新（AGAIN - 遗忘）"""
        now = datetime.now()
        state = FSRSState(
            stability=10.0,
            difficulty=5.0,
            reps=3,
            lapses=0,
            last_review=now - timedelta(days=5)
        )
        result = self.scheduler.next_review(state, grade=1, now=now)

        assert result.stability > 0
        assert result.scheduled_days >= 1
        # 遗忘后间隔应该缩短
        assert result.scheduled_days < 10

    def test_update_card_good(self):
        """测试卡片更新（GOOD - 成功回忆）"""
        now = datetime.now()
        state = FSRSState(
            stability=10.0,
            difficulty=5.0,
            reps=3,
            lapses=0,
            last_review=now - timedelta(days=5)
        )
        result = self.scheduler.next_review(state, grade=3, now=now)

        assert result.stability > 10.0  # 稳定性应该增加
        assert result.scheduled_days >= 5  # 间隔应该增加

    def test_update_card_easy(self):
        """测试卡片更新（EASY - 轻松回忆）"""
        now = datetime.now()
        state = FSRSState(
            stability=10.0,
            difficulty=5.0,
            reps=3,
            lapses=0,
            last_review=now - timedelta(days=5)
        )
        result = self.scheduler.next_review(state, grade=4, now=now)

        # EASY 应该比 GOOD 有更长的间隔
        result_good = self.scheduler.next_review(state, grade=3, now=now)
        assert result.scheduled_days >= result_good.scheduled_days

    def test_difficulty_update(self):
        """测试难度更新"""
        now = datetime.now()
        state = FSRSState(
            stability=10.0,
            difficulty=5.0,
            reps=3,
            lapses=0,
            last_review=now - timedelta(days=5)
        )

        # AGAIN 应该增加难度
        result_again = self.scheduler.next_review(state, grade=1, now=now)
        assert result_again.difficulty > 5.0

        # EASY 应该降低难度
        result_easy = self.scheduler.next_review(state, grade=4, now=now)
        assert result_easy.difficulty < 5.0

    def test_retrievability_calculation(self):
        """测试可提取性计算"""
        # 稳定性 10 天，经过 5 天
        r = self.scheduler._retrievability(10.0, 5)
        assert 0.5 < r < 1.0  # 应该在 50%-100% 之间

        # 稳定性 10 天，经过 10 天
        r = self.scheduler._retrievability(10.0, 10)
        assert 0.3 < r < 0.7  # 应该在 30%-70% 之间

        # 稳定性 10 天，经过 20 天
        r = self.scheduler._retrievability(10.0, 20)
        assert r < 0.3  # 应该低于 30%

    def test_interval_bounds(self):
        """测试间隔边界"""
        now = datetime.now()
        state = FSRSState(reps=0)

        # 最小间隔应该是 1 天
        result = self.scheduler.next_review(state, grade=1, now=now)
        assert result.scheduled_days >= 1

        # 最大间隔应该是 365 天
        state = FSRSState(
            stability=1000.0,
            difficulty=1.0,
            reps=10,
            lapses=0,
            last_review=now - timedelta(days=100)
        )
        result = self.scheduler.next_review(state, grade=4, now=now)
        assert result.scheduled_days <= 365

    def test_invalid_grade(self):
        """测试无效评分"""
        now = datetime.now()
        state = FSRSState(reps=0)

        with pytest.raises(ValueError):
            self.scheduler.next_review(state, grade=0, now=now)

        with pytest.raises(ValueError):
            self.scheduler.next_review(state, grade=5, now=now)


class TestSM2ToFSRSMigration:
    """SM-2 到 FSRS 迁移测试"""

    def test_basic_migration(self):
        """测试基本迁移"""
        stability, difficulty = migrate_sm2_to_fsrs(
            ease_factor=2.5,
            interval_days=10,
            repetitions=3
        )

        assert stability > 0
        assert 0 <= difficulty <= 10

    def test_high_ease_factor(self):
        """测试高难度因子（简单卡片）"""
        stability, difficulty = migrate_sm2_to_fsrs(
            ease_factor=2.5,
            interval_days=10,
            repetitions=3
        )

        # 高 ease_factor 应该对应低 difficulty
        assert difficulty < 5.0

    def test_low_ease_factor(self):
        """测试低难度因子（困难卡片）"""
        stability, difficulty = migrate_sm2_to_fsrs(
            ease_factor=1.3,
            interval_days=3,
            repetitions=1
        )

        # 低 ease_factor 应该对应高 difficulty
        assert difficulty > 5.0

    def test_stability_estimation(self):
        """测试稳定性估算"""
        stability, _ = migrate_sm2_to_fsrs(
            ease_factor=2.5,
            interval_days=10,
            repetitions=3
        )

        # 稳定性应该与间隔相关
        assert 5 < stability < 15


class TestFSRSIntegration:
    """FSRS 集成测试"""

    def test_learning_progression(self):
        """测试学习进度"""
        scheduler = FSRSScheduler()
        now = datetime.now()
        state = FSRSState(reps=0)

        # 模拟连续 3 次成功复习
        for i in range(3):
            result = scheduler.next_review(state, grade=3, now=now)
            state = FSRSState(
                stability=result.stability,
                difficulty=result.difficulty,
                reps=state.reps + 1,
                lapses=state.lapses,
                last_review=now,
                scheduled_days=result.scheduled_days
            )
            now = result.next_review

        # 稳定性应该逐渐增加
        assert state.stability > 0

    def test_forgetting_and_recovery(self):
        """测试遗忘和恢复"""
        scheduler = FSRSScheduler()
        now = datetime.now()

        # 先学习 3 次
        state = FSRSState(reps=0)
        for i in range(3):
            result = scheduler.next_review(state, grade=3, now=now)
            state = FSRSState(
                stability=result.stability,
                difficulty=result.difficulty,
                reps=state.reps + 1,
                lapses=state.lapses,
                last_review=now,
                scheduled_days=result.scheduled_days
            )
            now = result.next_review

        previous_scheduled_days = state.scheduled_days

        # 遗忘一次
        result = scheduler.next_review(state, grade=1, now=now)
        state = FSRSState(
            stability=result.stability,
            difficulty=result.difficulty,
            reps=0,
            lapses=state.lapses + 1,
            last_review=now,
            scheduled_days=result.scheduled_days
        )

        # 遗忘后间隔应该缩短
        assert result.scheduled_days < previous_scheduled_days

    def test_stability_bounds(self):
        """测试稳定性边界"""
        scheduler = FSRSScheduler()

        # 稳定性不能为负
        state = FSRSState(stability=0.01, difficulty=5.0, reps=1)
        result = scheduler.next_review(state, grade=1, now=datetime.now())
        assert result.stability > 0

    def test_difficulty_bounds(self):
        """测试难度边界"""
        scheduler = FSRSScheduler()

        # 难度应该在 0-10 之间
        state = FSRSState(stability=10.0, difficulty=0.0, reps=1)
        result = scheduler.next_review(state, grade=1, now=datetime.now())
        assert 0 <= result.difficulty <= 10

        state = FSRSState(stability=10.0, difficulty=10.0, reps=1)
        result = scheduler.next_review(state, grade=4, now=datetime.now())
        assert 0 <= result.difficulty <= 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
