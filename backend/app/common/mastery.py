"""掌握度计算工具"""


def score_to_mastery_level(score: float) -> str:
    clamped = min(max(score, 0.0), 1.0)
    if clamped >= 0.8:
        return "proficient"
    if clamped >= 0.6:
        return "familiar"
    if clamped >= 0.3:
        return "learning"
    return "new"
