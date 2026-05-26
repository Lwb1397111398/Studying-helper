"""教学策略选择"""
from app.modules.ai_learning.schemas import LearnedUnit
from app.modules.teaching.schemas import (
    TeachingStrategy, KnowledgeType, CognitiveLevel, UserTeachingProfile,
)

# 知识类型推断的关键词映射
_PROCEDURE_KEYWORDS = ("步骤", "流程", "如何", "怎么", "怎样", "操作", "执行", "实现", "编写")
_PRINCIPLE_KEYWORDS = ("原理", "为什么", "机制", "原因", "本质", "底层", "核心")


def _infer_knowledge_type(unit: LearnedUnit) -> KnowledgeType:
    """从知识单元内容推断知识类型"""
    key_points_text = " ".join(unit.key_points).lower()
    concepts_text = " ".join(c.name for c in unit.concepts).lower()

    for kw in _PROCEDURE_KEYWORDS:
        if kw in key_points_text or kw in concepts_text:
            return KnowledgeType.PROCEDURE

    for kw in _PRINCIPLE_KEYWORDS:
        if kw in key_points_text or kw in concepts_text:
            return KnowledgeType.PRINCIPLE

    if unit.concepts and any(c.definition for c in unit.concepts):
        return KnowledgeType.CONCEPT

    return KnowledgeType.FACT


def _select_cognitive_level(difficulty: int | None, mastery: float) -> str:
    """根据难度和掌握度选择认知层级"""
    if mastery < 0.3 or (difficulty and difficulty >= 4):
        return CognitiveLevel.REMEMBER.value
    if mastery > 0.7:
        return CognitiveLevel.ANALYZE.value
    if difficulty and difficulty >= 3:
        return CognitiveLevel.UNDERSTAND.value
    return CognitiveLevel.APPLY.value


def _select_scaffold(mastery: float, difficulty: int | None) -> str:
    """选择脚手架级别"""
    if mastery < 0.3 or (difficulty and difficulty >= 4):
        return "full"
    if mastery > 0.7:
        return "minimal"
    return "partial"


def _select_explanation_style(knowledge_type: KnowledgeType, preferred: str = "") -> str:
    """选择讲解风格"""
    if preferred:
        return preferred
    mapping = {
        KnowledgeType.PROCEDURE: "example_first",
        KnowledgeType.PRINCIPLE: "theory_first",
        KnowledgeType.CONCEPT: "analogy",
        KnowledgeType.FACT: "problem_based",
    }
    return mapping.get(knowledge_type, "balanced")


def _select_visual_level(difficulty: int | None, knowledge_type: KnowledgeType) -> str:
    """选择视觉辅助级别"""
    if (difficulty and difficulty >= 4) or knowledge_type == KnowledgeType.PROCEDURE:
        return "high"
    if (difficulty and difficulty <= 2) and knowledge_type == KnowledgeType.FACT:
        return "low"
    return "medium"


def _select_pace(mastery: float, difficulty: int | None) -> str:
    """选择教学节奏"""
    if mastery > 0.7 and (difficulty and difficulty <= 2):
        return "fast"
    if difficulty and difficulty >= 4:
        return "slow"
    return "normal"


def _select_feedback(mastery: float) -> str:
    """选择反馈风格"""
    if mastery < 0.3:
        return "immediate"
    if mastery > 0.7:
        return "delayed"
    return "guided"


def select_teaching_strategy(
    unit: LearnedUnit,
    user_profile: UserTeachingProfile | None = None,
) -> TeachingStrategy:
    """
    根据知识单元特征和用户画像选择教学策略。
    """
    mastery = user_profile.avg_mastery_score if user_profile else 0.5
    preferred = user_profile.preferred_style if user_profile else ""
    difficulty = unit.difficulty_level

    knowledge_type = _infer_knowledge_type(unit)

    return TeachingStrategy(
        explanation_style=_select_explanation_style(knowledge_type, preferred),
        visual_level=_select_visual_level(difficulty, knowledge_type),
        interaction_frequency="high" if mastery < 0.5 or knowledge_type == KnowledgeType.PROCEDURE else "medium",
        pace=_select_pace(mastery, difficulty),
        knowledge_type=knowledge_type.value,
        cognitive_level=_select_cognitive_level(difficulty, mastery),
        scaffold_level=_select_scaffold(mastery, difficulty),
        feedback_style=_select_feedback(mastery),
    )
