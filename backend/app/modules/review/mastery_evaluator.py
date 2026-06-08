"""掌握度评估器 - 5维度评估模型"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

from app.modules.review.schemas import MasteryAssessment


# 维度权重配置
DIMENSION_WEIGHTS = {
    'recall_accuracy': 0.3,   # 回忆准确率
    'response_speed': 0.15,   # 回答速度
    'consistency': 0.2,       # 多次测试表现稳定性
    'explanation': 0.2,       # 解释能力
    'application': 0.15,      # 应用能力
}

# 掌握度等级阈值（5级体系）
LEVEL_THRESHOLDS = [
    (0.85, 'mastered'),
    (0.65, 'proficient'),
    (0.40, 'familiar'),
    (0.20, 'learning'),
    (0.00, 'beginner'),
]


def evaluate_mastery(
    unit_id: str,
    correct_count: int,
    total_count: int,
    response_times: List[float],
    avg_response_time: float,
    consistency_scores: List[float],
    explanation_score: float = 0.5,
    application_score: float = 0.5,
    confused_count: int = 0,
) -> MasteryAssessment:
    """
    评估知识单元的掌握度。

    参数:
        unit_id: 知识单元ID
        correct_count: 正确回答数
        total_count: 总回答数
        response_times: 各次回答用时列表
        avg_response_time: 基准平均回答用时
        consistency_scores: 历次测试得分列表 (0-1)
        explanation_score: 解释能力得分 (0-1)
        application_score: 应用能力得分 (0-1)
        confused_count: "不懂"标记次数

    返回:
        MasteryAssessment 掌握度评估报告
    """
    weak_points = []

    # 1. 回忆准确率
    if total_count > 0:
        recall_accuracy = correct_count / total_count
    else:
        recall_accuracy = 0.0
        weak_points.append("尚无答题记录")

    # 2. 回答速度
    if response_times and avg_response_time > 0:
        avg_actual = sum(response_times) / len(response_times)
        speed_ratio = avg_actual / avg_response_time
        # 速度得分：越快越高，但有下限
        if speed_ratio <= 0.5:
            response_speed = 1.0
        elif speed_ratio <= 1.0:
            response_speed = 0.5 + 0.5 * (1.0 - speed_ratio) / 0.5
        elif speed_ratio <= 2.0:
            response_speed = 0.5 * (2.0 - speed_ratio)
        else:
            response_speed = 0.0
        response_speed = max(0.0, min(1.0, response_speed))
    else:
        response_speed = 0.5  # 无数据时给中间值

    # 3. 一致性（多次测试表现稳定性）
    if len(consistency_scores) >= 2:
        mean_score = sum(consistency_scores) / len(consistency_scores)
        variance = sum((s - mean_score) ** 2 for s in consistency_scores) / len(consistency_scores)
        # 方差越小一致性越高
        consistency = max(0.0, 1.0 - variance * 4)
    elif len(consistency_scores) == 1:
        consistency = consistency_scores[0]
    else:
        consistency = 0.5

    # 4. 解释能力（直接使用外部评估分数）
    explanation = max(0.0, min(1.0, explanation_score))

    # 5. 应用能力
    application = max(0.0, min(1.0, application_score))

    # 构建各维度分数
    dimensions = {
        'recall_accuracy': recall_accuracy,
        'response_speed': response_speed,
        'consistency': consistency,
        'explanation': explanation,
        'application': application,
    }

    # 加权计算总分
    score = sum(
        dimensions[dim] * weight
        for dim, weight in DIMENSION_WEIGHTS.items()
    )

    # "不懂"标记扣分：每个扣0.05
    score -= confused_count * 0.05
    score = max(0.0, min(1.0, score))

    # 确定等级
    level = 'beginner'
    for threshold, level_name in LEVEL_THRESHOLDS:
        if score >= threshold:
            level = level_name
            break

    # 识别薄弱点
    if recall_accuracy < 0.6:
        weak_points.append("回忆准确率偏低")
    if response_speed < 0.4:
        weak_points.append("回答速度较慢")
    if consistency < 0.5:
        weak_points.append("测试表现不稳定")
    if explanation < 0.4:
        weak_points.append("解释能力不足")
    if application < 0.4:
        weak_points.append("应用能力不足")
    if confused_count > 0:
        weak_points.append(f"有{confused_count}个'不懂'标记")

    # 根据掌握度推荐复习时间（5级体系）
    if score >= 0.85:
        days = 30
    elif score >= 0.65:
        days = 14
    elif score >= 0.40:
        days = 7
    elif score >= 0.20:
        days = 3
    else:
        days = 1

    recommended_review_at = datetime.now(timezone.utc) + timedelta(days=days)

    return MasteryAssessment(
        unit_id=unit_id,
        score=round(score, 4),
        level=level,
        dimensions={k: round(v, 4) for k, v in dimensions.items()},
        weak_points=weak_points,
        recommended_review_at=recommended_review_at,
    )


def calibrate_difficulty(
    llm_difficulty: float,
    mastery_score: float | None,
    calibration_count: int,
) -> float:
    """
    用真实掌握度反向校准 LLM 给出的难度。

    校准公式：
    - actual_difficulty = 5 - mastery_score * 4  （掌握差=难度高）
    - weight = min(calibration_count / 10, 0.6)  （最多 60% 权重给实际数据）
    - result = llm_difficulty * (1 - weight) + actual_difficulty * weight

    参数:
        llm_difficulty: LLM 给出的难度 (1-5)
        mastery_score: 掌握度分数 (0-1)，None 时不校准
        calibration_count: 已校准次数

    返回:
        校准后的难度 (1-5)
    """
    if mastery_score is None or calibration_count == 0:
        return llm_difficulty

    actual_difficulty = max(1.0, min(5.0, 5.0 - mastery_score * 4.0))
    weight = min(calibration_count / 10.0, 0.6)
    calibrated = llm_difficulty * (1.0 - weight) + actual_difficulty * weight
    return round(max(1.0, min(5.0, calibrated)), 2)
