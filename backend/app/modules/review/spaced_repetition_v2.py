"""
间隔重复算法 v2 - 集成 FSRS 和 SM-2

提供统一的接口，支持两种算法的平滑切换和数据迁移。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Tuple, Optional, Literal
from enum import Enum

from .fsrs import (
    FSRSScheduler,
    FSRSState,
    FSRSResult,
    migrate_sm2_to_fsrs,
    DEFAULT_PARAMETERS
)
from .spaced_repetition import (
    calculate_next_review as sm2_calculate_next_review,
    quality_from_correctness as sm2_quality_from_correctness
)


class Algorithm(str, Enum):
    SM2 = "sm2"
    FSRS = "fsrs"


@dataclass
class ReviewSchedule:
    """统一的复习调度结果"""
    next_review: datetime           # 下次复习时间
    interval_days: int              # 间隔天数
    algorithm: Algorithm            # 使用的算法
    quality: int                    # 质量分数 (0-5)
    mastery_change: float           # 掌握度变化

    # SM-2 专用参数
    ease_factor: Optional[float] = None
    repetitions: Optional[int] = None

    # FSRS 专用参数
    stability: Optional[float] = None
    difficulty: Optional[float] = None
    retrievability: Optional[float] = None
    lapses: Optional[int] = None
    scheduled_days: Optional[int] = None


class SpacedRepetitionV2:
    """间隔重复算法 v2 - 统一接口"""

    def __init__(
        self,
        algorithm: Algorithm = Algorithm.FSRS,
        fsrs_parameters: Optional[list] = None
    ):
        """
        初始化间隔重复调度器

        Args:
            algorithm: 默认算法
            fsrs_parameters: FSRS 参数，None 使用默认参数
        """
        self.algorithm = algorithm
        self.fsrs_scheduler = FSRSScheduler(fsrs_parameters)

    def calculate_next_review(
        self,
        quality: int,
        repetitions: int,
        ease_factor: float,
        interval: int,
        now: Optional[datetime] = None,
        algorithm: Optional[Algorithm] = None
    ) -> ReviewSchedule:
        """
        计算下次复习时间

        Args:
            quality: 回答质量 (0-5)
            repetitions: 连续正确次数
            ease_factor: 当前难度因子
            interval: 当前间隔天数
            now: 当前时间
            algorithm: 指定算法，None 使用默认算法

        Returns:
            ReviewSchedule: 复习调度结果
        """
        if now is None:
            now = datetime.now()

        if algorithm is None:
            algorithm = self.algorithm

        if algorithm == Algorithm.SM2:
            return self._calculate_sm2(quality, repetitions, ease_factor, interval, now)
        else:
            return self._calculate_fsrs(quality, repetitions, ease_factor, interval, now)

    def _calculate_sm2(
        self,
        quality: int,
        repetitions: int,
        ease_factor: float,
        interval: int,
        now: datetime
    ) -> ReviewSchedule:
        """SM-2 算法计算"""
        new_interval, new_ease, new_reps = sm2_calculate_next_review(
            quality, repetitions, ease_factor, interval
        )

        # 计算掌握度变化
        mastery_change = self._calculate_mastery_change_sm2(quality, repetitions)

        return ReviewSchedule(
            next_review=now + timedelta(days=new_interval),
            interval_days=new_interval,
            algorithm=Algorithm.SM2,
            quality=quality,
            mastery_change=mastery_change,
            ease_factor=new_ease,
            repetitions=new_reps
        )

    def _calculate_fsrs(
        self,
        quality: int,
        repetitions: int,
        ease_factor: float,
        interval: int,
        now: datetime
    ) -> ReviewSchedule:
        """FSRS 算法计算"""
        # 将 SM-2 参数迁移到 FSRS 状态
        stability, difficulty = migrate_sm2_to_fsrs(ease_factor, interval, repetitions)

        # 创建 FSRS 状态
        state = FSRSState(
            stability=stability,
            difficulty=difficulty,
            elapsed_days=0,
            scheduled_days=interval,
            reps=repetitions,
            lapses=0,
            last_review=now - timedelta(days=interval)
        )

        # 将质量分数 (0-5) 转换为 FSRS 评分 (1-4)
        grade = self._quality_to_grade(quality)

        # 计算下次复习
        result = self.fsrs_scheduler.next_review(state, grade, now)

        # 计算掌握度变化
        mastery_change = self._calculate_mastery_change_fsrs(quality, result.retrievability)

        return ReviewSchedule(
            next_review=result.next_review,
            interval_days=result.scheduled_days,
            algorithm=Algorithm.FSRS,
            quality=quality,
            mastery_change=mastery_change,
            stability=result.stability,
            difficulty=result.difficulty,
            retrievability=result.retrievability,
            lapses=state.lapses + (1 if quality < 3 else 0),
            scheduled_days=result.scheduled_days
        )

    def _quality_to_grade(self, quality: int) -> int:
        """将质量分数 (0-5) 转换为 FSRS 评分 (1-4)"""
        if quality <= 1:
            return 1  # AGAIN
        elif quality == 2:
            return 2  # HARD
        elif quality <= 4:
            return 3  # GOOD
        else:
            return 4  # EASY

    def _calculate_mastery_change_sm2(self, quality: int, repetitions: int) -> float:
        """计算 SM-2 的掌握度变化"""
        if quality < 3:
            # 回答失败
            return -0.15 - (0.05 * repetitions)  # 连续正确次数越多，失败惩罚越大
        else:
            # 回答成功
            base_gain = 0.1
            if quality == 5:
                base_gain = 0.15  # 完美回答额外奖励
            return base_gain + (0.02 * min(repetitions, 5))  # 连续正确有额外收益

    def _calculate_mastery_change_fsrs(self, quality: int, retrievability: float) -> float:
        """计算 FSRS 的掌握度变化"""
        if quality < 3:
            # 回答失败
            return -max(0.05, 0.2 * (1 - retrievability))  # 新卡答错也应产生负向变化
        else:
            # 回答成功
            base_gain = 0.1
            if quality == 4:
                base_gain = 0.15  # EASY 额外奖励
            # 可提取性越低（越难回忆），成功收益越大
            return base_gain + (0.1 * (1 - retrievability))

    def quality_from_correctness(
        self,
        is_correct: bool,
        response_time: float,
        avg_time: float,
        confidence: Optional[float] = None
    ) -> int:
        """
        根据正确性和响应时间计算质量分数

        Args:
            is_correct: 是否正确
            response_time: 响应时间（秒）
            avg_time: 平均响应时间（秒）
            confidence: 置信度 (0-1)，可选

        Returns:
            质量分数 (0-5)
        """
        # 基础质量分数
        base_quality = sm2_quality_from_correctness(is_correct, response_time, avg_time)

        # 如果有置信度，进行校准
        if confidence is not None:
            base_quality = self._adjust_quality_by_confidence(base_quality, confidence)

        return base_quality

    def _adjust_quality_by_confidence(self, quality: int, confidence: float) -> int:
        """根据置信度调整质量分数"""
        if confidence < 0.3:
            # 低置信度：即使正确也降低质量
            if quality >= 3:
                quality = max(3, quality - 1)
        elif confidence > 0.8:
            # 高置信度：正确时提高质量
            if quality >= 4:
                quality = min(5, quality + 1)
        return quality


# 全局实例
_default_scheduler = None


def get_scheduler(algorithm: Algorithm = Algorithm.FSRS) -> SpacedRepetitionV2:
    """获取间隔重复调度器实例"""
    global _default_scheduler
    if _default_scheduler is None or _default_scheduler.algorithm != algorithm:
        _default_scheduler = SpacedRepetitionV2(algorithm)
    return _default_scheduler


# 便捷函数
def calculate_next_review_v2(
    quality: int,
    repetitions: int,
    ease_factor: float,
    interval: int,
    algorithm: Algorithm = Algorithm.FSRS
) -> ReviewSchedule:
    """计算下次复习时间（便捷函数）"""
    scheduler = get_scheduler(algorithm)
    return scheduler.calculate_next_review(quality, repetitions, ease_factor, interval)


def quality_from_correctness_v2(
    is_correct: bool,
    response_time: float,
    avg_time: float,
    confidence: Optional[float] = None
) -> int:
    """计算质量分数（便捷函数）"""
    scheduler = get_scheduler()
    return scheduler.quality_from_correctness(is_correct, response_time, avg_time, confidence)
