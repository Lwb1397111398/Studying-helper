"""
FSRS (Free Spaced Repetition Scheduler) 算法实现

基于 FSRS v4 算法，提供更精确的遗忘曲线建模和个性化间隔计算。

参考文献：
- https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm
- https://arxiv.org/abs/2302.05797
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Tuple, Optional
import math

# FSRS v4 默认参数（经过大量数据验证）
DEFAULT_PARAMETERS = [
    0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01,
    1.49, 0.14, 0.94, 2.18, 0.05, 0.34, 1.26, 0.29, 2.61
]

# 评分等级
GRADE_AGAIN = 1  # 完全忘记
GRADE_HARD = 2   # 困难回忆
GRADE_GOOD = 3   # 正常回忆
GRADE_EASY = 4   # 轻松回忆


@dataclass
class FSRSState:
    """FSRS 状态参数"""
    stability: float = 0.0      # 稳定性（天）
    difficulty: float = 0.0     # 难度（0-10）
    elapsed_days: int = 0       # 已过天数
    scheduled_days: int = 0     # 计划天数
    reps: int = 0               # 复习次数
    lapses: int = 0             # 遗忘次数
    last_review: Optional[datetime] = None


@dataclass
class FSRSResult:
    """FSRS 计算结果"""
    next_review: datetime       # 下次复习时间
    stability: float           # 新稳定性
    difficulty: float          # 新难度
    scheduled_days: int        # 计划天数
    retrievability: float      # 当前可提取性（回忆概率）


class FSRSScheduler:
    """FSRS 调度器"""

    def __init__(self, parameters: Optional[list] = None):
        """
        初始化 FSRS 调度器

        Args:
            parameters: FSRS 参数列表，长度为 17。None 使用默认参数。
        """
        if parameters is None:
            self.w = DEFAULT_PARAMETERS
        else:
            if len(parameters) != 17:
                raise ValueError("FSRS 参数必须是 17 个浮点数")
            self.w = parameters

    def next_review(
        self,
        state: FSRSState,
        grade: int,
        now: Optional[datetime] = None
    ) -> FSRSResult:
        """
        计算下次复习时间

        Args:
            state: 当前 FSRS 状态
            grade: 评分等级 (1-4)
            now: 当前时间，默认为当前时间

        Returns:
            FSRSResult: 计算结果
        """
        if now is None:
            now = datetime.now()

        if grade < 1 or grade > 4:
            raise ValueError("评分等级必须在 1-4 之间")

        # 计算当前可提取性
        if state.last_review is not None:
            elapsed_days = (now - state.last_review).days
        else:
            elapsed_days = 0

        # 新卡片初始化
        if state.reps == 0:
            return self._init_card(grade, now)

        # 已有卡片更新
        return self._update_card(state, grade, elapsed_days, now)

    def _init_card(self, grade: int, now: datetime) -> FSRSResult:
        """初始化新卡片"""
        # 初始稳定性基于评分
        stability = self._initial_stability(grade)

        # 初始难度基于评分
        difficulty = self._initial_difficulty(grade)

        # 计算间隔
        scheduled_days = self._next_interval(stability, difficulty)

        return FSRSResult(
            next_review=now + timedelta(days=scheduled_days),
            stability=stability,
            difficulty=difficulty,
            scheduled_days=scheduled_days,
            retrievability=1.0
        )

    def _update_card(
        self,
        state: FSRSState,
        grade: int,
        elapsed_days: int,
        now: datetime
    ) -> FSRSResult:
        """更新现有卡片"""
        # 计算当前可提取性
        retrievability = self._retrievability(state.stability, elapsed_days)

        # 更新稳定性
        new_stability = self._update_stability(
            state.stability,
            state.difficulty,
            retrievability,
            grade,
            state.lapses
        )

        # 更新难度
        new_difficulty = self._update_difficulty(
            state.difficulty,
            grade
        )

        # 计算下次间隔
        if grade == GRADE_AGAIN:
            # 遗忘后重新学习
            scheduled_days = self._next_interval(new_stability, new_difficulty)
            lapses = state.lapses + 1
        else:
            scheduled_days = self._next_interval(new_stability, new_difficulty)
            lapses = state.lapses

        return FSRSResult(
            next_review=now + timedelta(days=scheduled_days),
            stability=new_stability,
            difficulty=new_difficulty,
            scheduled_days=scheduled_days,
            retrievability=retrievability
        )

    def _initial_stability(self, grade: int) -> float:
        """计算初始稳定性"""
        # w[0-3] 对应 again/hard/good/easy 的初始稳定性
        return self.w[grade - 1]

    def _initial_difficulty(self, grade: int) -> float:
        """计算初始难度"""
        # D_0(G) = w_7 * G_0^w_8
        # 简化：使用线性映射
        difficulty = self.w[7] * (grade ** self.w[8])
        return max(0.0, min(10.0, difficulty))

    def _retrievability(self, stability: float, elapsed_days: int) -> float:
        """
        计算可提取性（回忆概率）

        使用指数遗忘曲线：R(t) = e^(-t/S)
        """
        if stability <= 0:
            return 0.0
        return math.exp(-elapsed_days / stability)

    def _update_stability(
        self,
        stability: float,
        difficulty: float,
        retrievability: float,
        grade: int,
        lapses: int
    ) -> float:
        """
        更新稳定性

        FSRS v4 稳定性更新公式：
        S'_d(G) = S * (e^(w_17) * (11 - D) * S^(-w_18) * (e^(w_19 * (1-R)) - 1) * w_20 + 1)
        """
        if grade == GRADE_AGAIN:
            # 遗忘：使用恢复因子
            safe_difficulty = max(0.01, difficulty)
            stability = self.w[11] * (safe_difficulty ** (-self.w[12]))
        else:
            # 成功回忆：应用稳定性增长
            hard_penalty = self.w[15] if grade == GRADE_HARD else 1.0
            easy_bonus = self.w[16] if grade == GRADE_EASY else 1.0

            # 稳定性增长因子
            factor = (
                math.exp(self.w[14]) *
                (11 - difficulty) *
                (stability ** (-self.w[15])) *
                (math.exp(self.w[16] * (1 - retrievability)) - 1) *
                hard_penalty *
                easy_bonus
            )

            stability = stability * (factor + 1)

        return max(0.01, stability)  # 最小稳定性 0.01 天

    def _update_difficulty(self, difficulty: float, grade: int) -> float:
        """
        更新难度

        D'(G) = D - w_6 * (G - 3)
        """
        difficulty = difficulty - self.w[6] * (grade - 3)
        return max(0.0, min(10.0, difficulty))

    def _next_interval(self, stability: float, difficulty: float) -> int:
        """
        计算下次复习间隔

        I(S, D) = S * (10 - D) / 9
        """
        interval = stability * (10 - difficulty) / 9
        # 最小间隔 1 天，最大间隔 365 天
        interval = max(1, min(365, round(interval)))
        return interval


def create_fsrs_state_from_mastery_record(
    record: 'MasteryRecordModel'
) -> FSRSState:
    """从现有掌握度记录创建 FSRS 状态"""
    return FSRSState(
        stability=record.stability if hasattr(record, 'stability') else 0.0,
        difficulty=record.difficulty if hasattr(record, 'difficulty') else 5.0,
        elapsed_days=0,
        scheduled_days=record.interval_days,
        reps=record.repetitions,
        lapses=record.lapses if hasattr(record, 'lapses') else 0,
        last_review=record.last_review_at if hasattr(record, 'last_review_at') else None
    )


def migrate_sm2_to_fsrs(
    ease_factor: float,
    interval_days: int,
    repetitions: int
) -> Tuple[float, float]:
    """
    将 SM-2 参数迁移到 FSRS 参数

    Args:
        ease_factor: SM-2 难度因子 (1.3-2.5)
        interval_days: SM-2 间隔天数
        repetitions: SM-2 连续正确次数

    Returns:
        Tuple[float, float]: (stability, difficulty)
    """
    # 稳定性估算：SM-2 间隔转换为 FSRS 稳定性
    # 经验公式：stability ≈ interval * 0.8
    stability = interval_days * 0.8

    # 难度估算：SM-2 ease_factor 转换为 FSRS 难度
    # ease_factor 范围 [1.3, 2.5]，difficulty 范围 [0, 10]
    # 经验公式：difficulty = (2.5 - ease_factor) * 5
    difficulty = (2.5 - ease_factor) * 5
    difficulty = max(0.0, min(10.0, difficulty))

    return stability, difficulty
