"""基于知识单元数据生成多种题型（不依赖 LLM）"""

import json
import re
from typing import List, Optional
from uuid import uuid4

from app.modules.knowledge_splitter.schemas import KnowledgeUnit
from app.modules.review.schemas import ReviewQuestion


def generate_questions(
    unit: KnowledgeUnit,
    all_units: Optional[List[KnowledgeUnit]] = None,
    count: int = 3,
) -> List[ReviewQuestion]:
    """为一个知识单元生成多道不同题型的复习题。

    Args:
        unit: 目标知识单元
        all_units: 同书所有单元（用于生成干扰项）
        count: 生成题目数量
    """
    generators = [
        _gen_short_answer,
        _gen_fill_blank,
        _gen_choice,
        _gen_true_false,
        _gen_ordering,
        _gen_matching,
    ]
    questions: List[ReviewQuestion] = []
    for gen in generators:
        if len(questions) >= count:
            break
        q = gen(unit, all_units or [])
        if q:
            questions.append(q)
    return questions


# ---- 题型生成器 ----

def _gen_short_answer(unit: KnowledgeUnit, _all: List[KnowledgeUnit]) -> Optional[ReviewQuestion]:
    """简答题：基于 key_points 或 summary"""
    if unit.key_points:
        answer = "; ".join(unit.key_points[:3])
    elif unit.summary:
        answer = unit.summary[:200]
    else:
        answer = unit.content[:200]
    return ReviewQuestion(
        unit_id=unit.id,
        question=f"请解释：{unit.title}",
        question_type="short_answer",
        correct_answer=answer,
    )


def _gen_fill_blank(unit: KnowledgeUnit, _all: List[KnowledgeUnit]) -> Optional[ReviewQuestion]:
    """填空题：从 key_points 中提取关键词"""
    terms = _extract_key_terms(unit)
    if not terms:
        return None
    term = terms[0]
    # 用 summary 或 content 构造题干，将关键词替换为下划线
    source = unit.summary or unit.content
    if term not in source:
        # 如果关键词不在 source 中，构造简单题干
        question_text = f"{unit.title} 中，______ 是核心概念"
        answer = term
    else:
        question_text = source.replace(term, "______", 1)
        answer = term
    return ReviewQuestion(
        unit_id=unit.id,
        question=f"填空：{question_text[:150]}",
        question_type="fill_blank",
        correct_answer=answer,
    )


def _gen_choice(unit: KnowledgeUnit, all_units: List[KnowledgeUnit]) -> Optional[ReviewQuestion]:
    """单选题：4 选项，正确答案来自 concepts 或 key_points"""
    correct = None
    if unit.concepts:
        correct = unit.concepts[0]
    elif unit.key_points:
        correct = unit.key_points[0]
    if not correct:
        return None

    # 从其他单元收集干扰项
    distractors = []
    for u in all_units:
        if u.id == unit.id:
            continue
        if u.concepts:
            distractors.extend(u.concepts[:2])
        elif u.key_points:
            distractors.extend(u.key_points[:2])
        if len(distractors) >= 5:
            break

    # 干扰项不够时用占位
    while len(distractors) < 3:
        distractors.append(f"与 {unit.title} 无关的描述")

    options = [correct] + distractors[:3]
    # 打乱顺序（确定性：基于 unit id）
    seed = sum(ord(c) for c in unit.id) % 24
    options = options[seed % 4:] + options[:seed % 4]

    return ReviewQuestion(
        unit_id=unit.id,
        question=f"以下哪项最准确地描述了 {unit.title} 的核心要点？",
        question_type="choice",
        options=options,
        correct_answer=correct,
    )


def _gen_true_false(unit: KnowledgeUnit, all_units: List[KnowledgeUnit]) -> Optional[ReviewQuestion]:
    """判断题：约半数为正确陈述，半数为错误陈述（来自其他单元的内容）"""
    if not unit.key_points and not unit.summary:
        return None

    # 确定性地决定本次生成正确还是错误陈述
    seed = sum(ord(c) for c in unit.id) % 2
    statement = unit.key_points[0] if unit.key_points else unit.summary[:100]

    if seed == 1:
        # 生成错误陈述：用其他单元的内容冒充
        other_statements = []
        for u in all_units:
            if u.id == unit.id:
                continue
            if u.key_points:
                other_statements.append(u.key_points[0])
            elif u.summary:
                other_statements.append(u.summary[:80])
            if other_statements:
                break
        if other_statements:
            statement = other_statements[0]
            return ReviewQuestion(
                unit_id=unit.id,
                question=f"以下关于「{unit.title}」的陈述是否正确",
                question_type="true_false",
                options=["正确", "错误"],
                correct_answer="错误",
                statement=statement,
            )

    return ReviewQuestion(
        unit_id=unit.id,
        question=f"以下关于「{unit.title}」的陈述是否正确",
        question_type="true_false",
        options=["正确", "错误"],
        correct_answer="正确",
        statement=statement,
    )


def _gen_ordering(unit: KnowledgeUnit, _all: List[KnowledgeUnit]) -> Optional[ReviewQuestion]:
    """排序题：将 key_points 按正确顺序排列"""
    if not unit.key_points or len(unit.key_points) < 3:
        return None
    steps = unit.key_points[:5]
    return ReviewQuestion(
        unit_id=unit.id,
        question=f"请将 {unit.title} 的以下要点按逻辑顺序排列",
        question_type="ordering",
        options=steps,
        correct_answer=json.dumps(steps, ensure_ascii=False),
    )


def _gen_matching(unit: KnowledgeUnit, all_units: List[KnowledgeUnit]) -> Optional[ReviewQuestion]:
    """配对题：概念与简短描述配对"""
    if not unit.concepts:
        return None
    pairs = []
    for c in unit.concepts[:4]:
        # 概念名 → 从 summary 中截取相关片段作为描述
        desc = _find_definition(c, unit)
        pairs.append({"left": c, "right": desc})
    if len(pairs) < 2:
        return None
    return ReviewQuestion(
        unit_id=unit.id,
        question=f"请将 {unit.title} 中的概念与正确描述配对",
        question_type="matching",
        options=[f"{p['left']}: {p['right']}" for p in pairs],
        correct_answer=json.dumps(pairs, ensure_ascii=False),
    )


# ---- 辅助函数 ----

def _extract_key_terms(unit: KnowledgeUnit) -> List[str]:
    """从知识单元中提取关键词"""
    terms = []
    if unit.concepts:
        terms.extend(unit.concepts[:3])
    if unit.key_points:
        for kp in unit.key_points[:3]:
            # 取较短的要点作为关键词
            if len(kp) <= 20:
                terms.append(kp)
    return terms


def _find_definition(concept: str, unit: KnowledgeUnit) -> str:
    """从 summary/content 中提取概念的简短描述"""
    source = unit.summary or unit.content
    # 尝试找 "概念：描述" 或 "概念—描述" 模式
    pattern = re.escape(concept) + r'[：:\-—]\s*(.{10,60})'
    match = re.search(pattern, source)
    if match:
        return match.group(1).strip()
    # 回退：返回 summary 的前 50 字
    return source[:50]
