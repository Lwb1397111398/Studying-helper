"""SM-2 间隔重复算法"""

from typing import Tuple

MAX_INTERVAL = 365  # 间隔上限：最长一年


def calculate_next_review(
    quality: int,
    repetitions: int,
    ease_factor: float,
    interval: int,
) -> Tuple[int, float, int]:
    """
    SM-2算法：计算下次复习时间和新的难度因子。

    参数:
        quality: 回答质量 (0-5)
        repetitions: 连续正确次数
        ease_factor: 当前难度因子
        interval: 当前间隔天数

    返回:
        (new_interval, new_ease_factor)
    """
    if quality < 3:
        # 回答失败：重置间隔和重复次数
        new_interval = 1
        new_repetitions = 0
    else:
        # 回答成功
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval * ease_factor)
        new_repetitions = repetitions + 1

    new_interval = min(new_interval, MAX_INTERVAL)

    # 更新难度因子
    # EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
    new_ease = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    # 难度因子最低不低于1.3
    new_ease = max(1.3, new_ease)

    return new_interval, new_ease, new_repetitions


def quality_from_correctness(
    is_correct: bool,
    response_time: float,
    avg_time: float,
) -> int:
    """
    根据回答正确性和速度计算SM-2质量分数 (0-5)。

    参数:
        is_correct: 是否回答正确
        response_time: 本次回答用时（秒）
        avg_time: 平均回答用时（秒）

    返回:
        质量分数 0-5
    """
    if avg_time <= 0:
        # 平均时间无效时使用默认判断
        if is_correct:
            return 4
        return 1

    speed_ratio = response_time / avg_time

    if is_correct:
        if speed_ratio < 0.8:
            # 正确 + 快速
            return 5
        elif speed_ratio <= 1.2:
            # 正确 + 正常速度
            return 4
        else:
            # 正确 + 慢速
            return 3
    else:
        if speed_ratio < 1.0:
            # 错误但快速作答（可能部分理解）
            return 2
        else:
            # 错误 + 慢速
            return 1
