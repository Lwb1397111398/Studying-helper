"""复习模块公共工具函数"""

import json
import re
from typing import Any, Dict, List


def check_answer(correct_answer: str, user_answer: str, question_type: str = "short_answer") -> bool:
    """检查答案是否正确，根据题型使用不同判分策略"""
    if not user_answer or not user_answer.strip():
        return False

    if question_type == "choice":
        return _check_choice(correct_answer, user_answer)
    elif question_type == "true_false":
        return _check_true_false(correct_answer, user_answer)
    elif question_type == "fill_blank":
        return _check_fill_blank(correct_answer, user_answer)
    elif question_type == "ordering":
        return _check_ordering(correct_answer, user_answer)
    elif question_type == "matching":
        return _check_matching(correct_answer, user_answer)
    else:
        return _check_short_answer(correct_answer, user_answer)


def _check_choice(correct: str, user: str) -> bool:
    """单选题：精确匹配"""
    return correct.strip() == user.strip()


def _check_true_false(correct: str, user: str) -> bool:
    """判断题：精确匹配"""
    return correct.strip() == user.strip()


def _check_fill_blank(correct: str, user: str) -> bool:
    """填空题：关键词匹配（忽略空格和标点）"""
    c = re.sub(r'[^\w]', '', correct.strip().lower())
    u = re.sub(r'[^\w]', '', user.strip().lower())
    return c == u or c in u or u in c


def _check_ordering(correct: str, user: str) -> bool:
    """排序题：JSON 数组比较"""
    try:
        correct_list = json.loads(correct)
        user_list = json.loads(user)
        if not isinstance(correct_list, list) or not isinstance(user_list, list):
            return False
        return correct_list == user_list
    except (json.JSONDecodeError, TypeError):
        return _check_short_answer(correct, user)


def _check_matching(correct: str, user: str) -> bool:
    """配对题：JSON 对象比较"""
    try:
        correct_pairs = json.loads(correct)
        user_pairs = json.loads(user)
        if not isinstance(correct_pairs, list) or not isinstance(user_pairs, list):
            return False
        # 按 left 排序后比较
        c_sorted = sorted(correct_pairs, key=lambda p: p.get("left", ""))
        u_sorted = sorted(user_pairs, key=lambda p: p.get("left", ""))
        return c_sorted == u_sorted
    except (json.JSONDecodeError, TypeError):
        return _check_short_answer(correct, user)


def _check_short_answer(correct_answer: str, user_answer: str) -> bool:
    """简答题：关键词匹配，支持中英文分词"""
    correct = correct_answer.strip().lower()
    user = user_answer.strip().lower()
    if correct == user:
        return True

    def _tokenize(text: str) -> set:
        """分词：中文按字切，英文按词切"""
        parts = re.split(r'[;，,、\s]+', text)
        tokens = set()
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if re.match(r'^[a-z0-9]+$', part):
                tokens.add(part)
            else:
                tokens.add(part)
                if len(part) >= 2:
                    for i in range(len(part) - 1):
                        tokens.add(part[i:i + 2])
        return tokens

    correct_tokens = _tokenize(correct)
    user_tokens = _tokenize(user)
    if not correct_tokens:
        return False
    matched = len(correct_tokens & user_tokens)
    return matched / len(correct_tokens) >= 0.5


def calibration_adjustment(confidence: int, is_correct: bool) -> tuple[float, str]:
    """校准测试：根据信心等级与实际正确性调整掌握度变化。

    Args:
        confidence: 信心等级 1-3（1=不确定, 2=较确定, 3=非常确定）
        is_correct: 实际是否正确

    Returns:
        (调整系数, 反馈文字)
        调整系数用于乘以 mastery_change：>1 放大, <1 缩小
    """
    if confidence <= 0 or confidence > 3:
        return 1.0, ""

    if is_correct:
        if confidence == 1:
            # 低信心+正确 = 低估自己，放大正面效果
            return 1.3, "你比自己以为的掌握得更好！"
        elif confidence == 3:
            # 高信心+正确 = 符合预期
            return 1.0, ""
        else:
            return 1.0, ""
    else:
        if confidence == 3:
            # 高信心+错误 = 过度自信，放大负面效果
            return 1.5, "注意：你对此过于自信，建议重新复习。"
        elif confidence == 1:
            # 低信心+错误 = 符合预期
            return 1.0, ""
        else:
            return 1.1, ""


def mastery_delta(quality: int, current_mastery: float) -> float:
    """根据 SM-2 quality 分和当前掌握度计算掌握度变化量。

    - quality 5 (完美): +0.15
    - quality 4 (正确): +0.08
    - quality 3 (犹豫正确): +0.03
    - quality 2 (部分错误): -0.05
    - quality 1 (完全错误): -0.10
    - quality 0 (完全不会): -0.15

    当前掌握度越高，提升越难（边际递减）。
    """
    base_delta = {5: 0.15, 4: 0.08, 3: 0.03, 2: -0.05, 1: -0.10, 0: -0.15}
    delta = base_delta.get(quality, 0.0)
    if delta > 0:
        delta *= (1.0 - current_mastery * 0.5)
    return round(delta, 4)


def _tokenize_simple(text: str) -> List[str]:
    """简单分词：中文按2-gram，英文按词"""
    parts = re.split(r'[;，,、\s]+', text.lower())
    tokens: List[str] = []
    for part in parts:
        if re.match(r'^[a-z0-9]+$', part):
            tokens.append(part)
        elif len(part) >= 2:
            for i in range(len(part) - 1):
                tokens.append(part[i:i + 2])
    return tokens


def evaluate_free_recall(
    student_recalled: str,
    reference_points: List[str],
    reference_summary: str = "",
) -> Dict[str, Any]:
    """评估自由回忆的质量（本地规则匹配，不依赖 LLM）。

    用于 LLM 不可用时的降级方案。
    """
    sentences = re.split(r'[。；\n]', student_recalled)
    sentences = [s.strip() for s in sentences if s.strip()]

    recalled_points = []
    matched_indices: set = set()

    for sentence in sentences:
        best_match = None
        best_score = 0.0
        for i, ref in enumerate(reference_points):
            if i in matched_indices:
                continue
            ref_tokens = set(_tokenize_simple(ref))
            sent_tokens = set(_tokenize_simple(sentence))
            if not ref_tokens:
                continue
            overlap = len(ref_tokens & sent_tokens) / len(ref_tokens)
            if overlap > best_score and overlap >= 0.3:
                best_score = overlap
                best_match = i
        if best_match is not None:
            matched_indices.add(best_match)
            recalled_points.append({
                "content": sentence,
                "matched_point": reference_points[best_match],
                "is_accurate": best_score >= 0.5,
            })

    total_ref = len(reference_points) or 1
    coverage = len(matched_indices) / total_ref
    accurate_count = sum(1 for p in recalled_points if p["is_accurate"])
    accuracy = accurate_count / len(recalled_points) if recalled_points else 0.0

    missed = [reference_points[i] for i in range(len(reference_points)) if i not in matched_indices]

    return {
        "coverage": round(coverage, 2),
        "accuracy": round(accuracy, 2),
        "depth": round((coverage + accuracy) / 2, 2),
        "recalled_points": recalled_points,
        "missed_points": missed,
        "incorrect_points": [],
        "overall_score": round((coverage * 0.4 + accuracy * 0.4 + 0.2) * 100, 1),
        "gap_report": f"覆盖率 {coverage:.0%}，准确性 {accuracy:.0%}。遗漏了 {len(missed)} 个要点。",
    }
