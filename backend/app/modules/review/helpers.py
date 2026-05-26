"""复习模块公共工具函数"""

import re


def check_answer(correct_answer: str, user_answer: str) -> bool:
    """检查答案是否正确（关键词匹配，支持中英文分词）"""
    if not user_answer or not user_answer.strip():
        return False
    correct = correct_answer.strip().lower()
    user = user_answer.strip().lower()
    if correct == user:
        return True

    def _tokenize(text: str) -> set:
        """分词：中文按字切，英文按词切，再去停用词"""
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
