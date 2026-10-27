"""FSRS 算法单元测试"""

import pytest
from datetime import datetime, timedelta
import math
from datetime import datetime, timedelta, timezone
from app.modules.review.fsrs import (
    FSRSScheduler,
    FSRSState,
    FSRSResult,
    migrate_sm2_to_fsrs,
    DEFAULT_PARAMETERS
)
from app.modules.review.spaced_repetition_v2 import Algorithm, SpacedRepetitionV2


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


class TestFSRSLapsesFix:
    """P1 修复：FSRS lapses 端到端记账（修复前该值永远 0/1，无法累积）。

    口径（与计划案一致）：
    - 仅 grade == GRADE_AGAIN（quality<=1）时 lapses+1，HARD/GOOD/EASY 不变；
    - 稳定性/难度更新使用更新前的旧 state.lapses；
    - 修复前快照（docs/superpowers/plans/logs/p1_pre_fix_snapshot.txt）证明：
      当前公式实现不读取 lapses，故修复不改变 stability/difficulty/scheduled_days，
      仅修正 lapses 记账；quality=2 的 lapses 由错误的 +1 修正为不变。
    - 数值测试统一用固定时钟与固定输入（第 10 轮评审要求）。
    """

    FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def _state(self, lapses=0, stability=5.0, difficulty=5.0, reps=3):
        return FSRSState(
            stability=stability, difficulty=difficulty, elapsed_days=0,
            scheduled_days=10, reps=reps, lapses=lapses, last_review=self.FIXED_NOW,
        )

    def test_again_increments_consecutively(self):
        """测试 1：已有历史的记录连续 AGAIN 3 次 → lapses 依次 1、2、3"""
        scheduler = FSRSScheduler()
        state = self._state(lapses=0)
        for expected in (1, 2, 3):
            result = scheduler.next_review(state, grade=1, now=self.FIXED_NOW)
            assert result.lapses == expected
            state = FSRSState(
                stability=result.stability, difficulty=result.difficulty,
                elapsed_days=0, scheduled_days=result.scheduled_days,
                reps=state.reps + 1, lapses=result.lapses, last_review=self.FIXED_NOW,
            )

    def test_good_keeps_lapses(self):
        """测试 2：lapses=2 后 GOOD 一次 → 仍为 2"""
        result = FSRSScheduler().next_review(self._state(lapses=2), grade=3, now=self.FIXED_NOW)
        assert result.lapses == 2

    def test_hard_easy_keep_lapses(self):
        """测试 3：lapses=2 后 HARD / EASY 各一次 → 仍为 2"""
        for grade in (2, 4):
            result = FSRSScheduler().next_review(self._state(lapses=2), grade=grade, now=self.FIXED_NOW)
            assert result.lapses == 2

    def test_quality_0_to_5_full_coverage(self):
        """测试 3b：quality 0~5 全覆盖 → 完整映射 0-2→AGAIN / 3→HARD / 4→GOOD / 5→EASY。

        映射行为变更（P1 修复，两处）：
        - quality=2 只可能来自答错（quality_from_correctness 仅在答错且快速时返回 2；
          置信度调整对正确答案保底 3），故 2 → AGAIN；与 Android 端"错题一律 AGAIN"
          及 SM-2"0-2 均失败"语义对齐。
        - quality=3 来自"答对但慢速/低置信度"（SM-2 语义"困难但正确"），改映射
          HARD（原 GOOD），修复旧映射 HARD 档位无输入的死档；间隔变短方向保守。
        """
        sched = SpacedRepetitionV2(Algorithm.FSRS)
        expected_grades = {0: 1, 1: 1, 2: 1, 3: 2, 4: 3, 5: 4}
        for quality in range(6):
            grade = sched._quality_to_grade(quality)
            assert grade == expected_grades[quality], f"quality={quality} 映射错误"
            assert (grade == 1) == (quality in (0, 1, 2)), f"quality={quality} AGAIN 判定错误"
            schedule = sched.calculate_next_review(
                quality, repetitions=3, ease_factor=2.5, interval=10,
                now=self.FIXED_NOW, lapses=0,
            )
            assert schedule.lapses == (1 if quality in (0, 1, 2) else 0), f"quality={quality} lapses 记账错误"

    def test_success_then_again_then_success_alternating(self):
        """测试 5（评审补充）：成功→遗忘→再恢复的交替场景，lapses 只增不消。

        reps 按真实业务路径递进（累计复习次数，与 Android 端 reviewCount 语义一致；
        repetitions=0 会触发 _init_card 新卡分支，仅首答合法）。
        GOOD(reps 3→4)→AGAIN(→5)→GOOD(→6)→AGAIN(→7)，同时断言 AGAIN 后
        stability 重落、恢复后重新增长（遗忘-恢复循环的调度行为）。
        """
        sched = SpacedRepetitionV2(Algorithm.FSRS)
        # 初始：已成功 3 次、间隔 10 天
        state_after_good = sched.calculate_next_review(
            4, repetitions=3, ease_factor=2.5, interval=10,
            now=self.FIXED_NOW, lapses=0,
        )
        assert state_after_good.lapses == 0
        assert state_after_good.repetitions == 4  # FSRS 路径累计 +1（reps 卡死修复）

        # 第一次 AGAIN
        after_again1 = sched.calculate_next_review(
            1, repetitions=state_after_good.repetitions, ease_factor=2.5, interval=10,
            now=self.FIXED_NOW, lapses=state_after_good.lapses,
        )
        assert after_again1.lapses == 1
        assert after_again1.stability < state_after_good.stability  # 遗忘后稳定性重落

        # 恢复 GOOD：lapses 保持 1
        after_recover = sched.calculate_next_review(
            4, repetitions=after_again1.repetitions, ease_factor=2.5,
            interval=after_again1.interval_days,
            now=self.FIXED_NOW, lapses=after_again1.lapses,
        )
        assert after_recover.lapses == 1

        # 第二次 AGAIN：lapses 累计到 2，不因中途成功被清零
        after_again2 = sched.calculate_next_review(
            0, repetitions=after_recover.repetitions, ease_factor=2.5,
            interval=after_recover.interval_days,
            now=self.FIXED_NOW, lapses=after_recover.lapses,
        )
        assert after_again2.lapses == 2

    def test_first_answer_enables_lapse_accounting_on_second(self):
        """测试 6（reps 卡死修复的端到端锁）：首答（rep=0，新卡）后 reps 必须=1，
        使第二次答题走 _update_card 开始累计 lapses。

        修复前：FSRS 路径 ReviewSchedule 不设 repetitions → service new_rep 回退
        旧值 0 → review_count 恒 0 → 每次都走 _init_card，lapses 永远为 0。
        """
        sched = SpacedRepetitionV2(Algorithm.FSRS)
        first = sched.calculate_next_review(
            1, repetitions=0, ease_factor=2.5, interval=1,
            now=self.FIXED_NOW, lapses=0,
        )
        assert first.repetitions == 1, "首答后累计复习次数必须为 1"
        # service 会把 new_rep=1 写回 review_count；第二次答题（首答错，不计 lapse：
        # _init_card 新卡语义，与 FSRS 主循环一致）走 _update_card 开始记账
        second = sched.calculate_next_review(
            1, repetitions=first.repetitions, ease_factor=2.5,
            interval=first.interval_days,
            now=self.FIXED_NOW, lapses=first.lapses,
        )
        assert second.lapses == 1

    def test_pre_fix_snapshot_non_again_unchanged(self):
        """测试 4：修复前快照复现——非 AGAIN 路径 stability/difficulty/scheduled_days 与修复前完全一致；
        AGAIN 路径调度数值也不变（当前公式不读取 lapses），仅 lapses 记账修正。
        快照来源：logs/p1_pre_fix_snapshot.txt（repetitions=3, ease=2.5, interval=10, 固定时钟）。
        安全边界：stability/difficulty 非负有限、scheduled_days 为正。
        """
        sched = SpacedRepetitionV2(Algorithm.FSRS)
        # quality=2 修复前为 (275.693091, 0.860000, 280)——错题被当 HARD 成功回忆，
        # 修复后走 AGAIN 分支，调度数值与 q0/q1 相同（快照见 logs/p1_pre_fix_snapshot.txt）
        # 复评第 2 轮新增：quality=3 从 GOOD 改映射 HARD，q3 数值更新为 HARD 路径值
        expected = {
            0: (2.744457, 1.720000, 3),
            1: (2.744457, 1.720000, 3),
            2: (2.744457, 1.720000, 3),
            3: (275.693091, 0.860000, 280),
            4: (931.079624, 0.000000, 365),
            5: (2417.237818, 0.000000, 365),
        }
        for quality, (stability, difficulty, days) in expected.items():
            r = sched.calculate_next_review(
                quality, repetitions=3, ease_factor=2.5, interval=10,
                now=self.FIXED_NOW, lapses=0,
            )
            assert abs(r.stability - stability) < 1e-4, f"quality={quality} stability 漂移"
            assert abs(r.difficulty - difficulty) < 1e-6, f"quality={quality} difficulty 漂移"
            assert r.scheduled_days == days, f"quality={quality} scheduled_days 漂移"
            # 安全边界
            assert r.stability >= 0 and math.isfinite(r.stability)
            assert r.difficulty >= 0 and math.isfinite(r.difficulty)
            assert r.scheduled_days > 0

    def test_result_default_lapses_zero(self):
        """构造兼容：不传 lapses 也能构造 FSRSResult 且默认 0（旧调用方零破坏）"""
        r = FSRSResult(
            next_review=self.FIXED_NOW, stability=1.0, difficulty=1.0,
            scheduled_days=1, retrievability=1.0,
        )
        assert r.lapses == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestFSRSExistingStatePassthrough:
    """R4：存量 FSRS 状态直通（stability/difficulty/last_review）。

    修复前：每轮 migrate_sm2_to_fsrs(ef, iv, reps) 重估，上一轮写回的真实
    stability 被丢弃，FSRS 演进被持续污染；Android 端早已直通（ReviewRepository.kt）。
    修复后：三参数均非 None → 直通；None → 维持旧估算路径（行为不变快照）。
    """

    FIXED_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_existing_state_bypasses_sm2_reestimate(self):
        """单元直通：存量 stability=5.0/difficulty=6.0 参与演进，而非 (8.0, 0.0) 重估值。"""
        sched = SpacedRepetitionV2(Algorithm.FSRS)
        schedule = sched.calculate_next_review(
            4, repetitions=3, ease_factor=2.5, interval=10,
            now=self.FIXED_NOW, lapses=1,
            stability=5.0, difficulty=6.0, last_review=self.FIXED_NOW - timedelta(days=3),
        )
        # SM-2 迁移估算值（修复前每轮走的路径）为 stability=8.0, difficulty=0.0
        est_s, est_d = migrate_sm2_to_fsrs(2.5, 10, 3)
        assert (est_s, est_d) == (8.0, 0.0)
        # 直通路径下输出从 (5.0, 6.0) 演进，与估算路径必然不同
        assert schedule.stability != pytest.approx(est_s)
        assert schedule.stability > 0

    def test_none_params_match_legacy_estimate_path(self):
        """单元兼容：不传三参数时输出与"显式传估算值"完全一致（None→旧路径等价证明）。"""
        sched = SpacedRepetitionV2(Algorithm.FSRS)
        legacy = sched.calculate_next_review(
            4, repetitions=3, ease_factor=2.5, interval=10,
            now=self.FIXED_NOW, lapses=1,
        )
        est_s, est_d = migrate_sm2_to_fsrs(2.5, 10, 3)
        explicit = sched.calculate_next_review(
            4, repetitions=3, ease_factor=2.5, interval=10,
            now=self.FIXED_NOW, lapses=1,
            stability=est_s, difficulty=est_d,
            last_review=self.FIXED_NOW - timedelta(days=10),
        )
        assert legacy.stability == pytest.approx(explicit.stability)
        assert legacy.difficulty == pytest.approx(explicit.difficulty)
        assert legacy.interval_days == explicit.interval_days

    def test_last_review_drives_elapsed_days(self):
        """elapsed_days 与 last_review 同源：3 天前复习 → elapsed=3。"""
        sched = SpacedRepetitionV2(Algorithm.FSRS)
        recent = sched.calculate_next_review(
            4, repetitions=3, ease_factor=2.5, interval=10,
            now=self.FIXED_NOW, lapses=1,
            stability=5.0, difficulty=6.0, last_review=self.FIXED_NOW - timedelta(days=3),
        )
        stale = sched.calculate_next_review(
            4, repetitions=3, ease_factor=2.5, interval=10,
            now=self.FIXED_NOW, lapses=1,
            stability=5.0, difficulty=6.0, last_review=self.FIXED_NOW - timedelta(days=9),
        )
        # 距上次复习越久，可提取性越低、成功回忆的稳定性增量越大
        assert stale.stability > recent.stability

    def test_future_last_review_clamps_elapsed_to_zero(self):
        """时钟漂移防御：last_review 在未来 → elapsed 截断为 0，不产生负值异常。"""
        sched = SpacedRepetitionV2(Algorithm.FSRS)
        schedule = sched.calculate_next_review(
            4, repetitions=3, ease_factor=2.5, interval=10,
            now=self.FIXED_NOW, lapses=1,
            stability=5.0, difficulty=6.0, last_review=self.FIXED_NOW + timedelta(days=1),
        )
        assert schedule.stability > 0

    def test_partial_none_stability_falls_back_to_estimate(self):
        """只传其一仍走估算（两值均非 None 才直通，保证状态对 (S, D) 一致）。"""
        sched = SpacedRepetitionV2(Algorithm.FSRS)
        legacy = sched.calculate_next_review(
            4, repetitions=3, ease_factor=2.5, interval=10,
            now=self.FIXED_NOW, lapses=1,
        )
        partial = sched.calculate_next_review(
            4, repetitions=3, ease_factor=2.5, interval=10,
            now=self.FIXED_NOW, lapses=1, stability=5.0,
        )
        assert partial.stability == pytest.approx(legacy.stability)
