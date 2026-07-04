"""教学策略选择"""
from typing import List
from app.modules.ai_learning.schemas import LearnedUnit
from app.modules.teaching.schemas import (
    TeachingStrategy, TeachingPhase, KnowledgeType, CognitiveLevel, UserTeachingProfile,
)

# 知识类型推断的关键词映射
_PROCEDURE_KEYWORDS = ("步骤", "流程", "如何", "怎么", "怎样", "操作", "执行", "实现", "编写")
_PRINCIPLE_KEYWORDS = ("原理", "为什么", "机制", "原因", "本质", "底层", "核心")


def _infer_knowledge_type(unit: LearnedUnit) -> KnowledgeType:
    """从知识单元内容推断知识类型"""
    kp_parts = []
    for kp in unit.key_points:
        if hasattr(kp, 'title'):
            kp_parts.append(kp.title)
        else:
            kp_parts.append(str(kp))
    key_points_text = " ".join(kp_parts).lower()
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

    pace = _select_pace(mastery, difficulty)
    scaffold = _select_scaffold(mastery, difficulty)

    # M4：AID 认知标注覆盖默认 pace（memorize 不求快，understand 可提速）
    hint = getattr(unit, "ai_cognitive_hint", None)
    if hint == "memorize" and pace == "fast":
        pace = "normal"
    elif hint == "understand" and pace == "slow":
        pace = "normal"

    return TeachingStrategy(
        explanation_style=_select_explanation_style(knowledge_type, preferred),
        visual_level=_select_visual_level(difficulty, knowledge_type),
        interaction_frequency="high" if mastery < 0.5 or knowledge_type == KnowledgeType.PROCEDURE else "medium",
        pace=pace,
        knowledge_type=knowledge_type.value,
        cognitive_level=_select_cognitive_level(difficulty, mastery),
        scaffold_level=scaffold,
        feedback_style=_select_feedback(mastery),
    )


def select_phases(unit: LearnedUnit, mastery: float) -> List[TeachingPhase]:
    """根据内容复杂度选择教学阶段

    - 简单内容（难度低且掌握度高）：ACTIVATE + CORE + EXAMPLE + RETRIEVAL
    - 中等内容：ACTIVATE + CORE + EXAMPLE + RETRIEVAL + CHECK + CONNECT
    - 复杂内容（难度高或掌握度低）：完整9阶段（含 INTRO + REFLECT）
    """
    # 基础阶段：所有内容都需要（CORE 后插入 EXAMPLE 示例说明）
    phases = [TeachingPhase.ACTIVATE, TeachingPhase.CORE, TeachingPhase.EXAMPLE, TeachingPhase.RETRIEVAL]

    # 简单内容：跳过部分阶段
    if unit.difficulty_level and unit.difficulty_level <= 2 and mastery > 0.7:
        return phases

    # 复杂内容：完整阶段（含 INTRO）
    if (unit.difficulty_level and unit.difficulty_level >= 4) or mastery < 0.3:
        phases = [
            TeachingPhase.ACTIVATE,
            TeachingPhase.INTRO,
            TeachingPhase.CORE,
            TeachingPhase.EXAMPLE,
            TeachingPhase.FEYNMAN,
            TeachingPhase.RETRIEVAL,
            TeachingPhase.CHECK,
            TeachingPhase.REFLECT,
            TeachingPhase.CONNECT,
        ]
        return phases

    # 中等内容：标准阶段（含 REFLECT）
    phases.extend([TeachingPhase.FEYNMAN, TeachingPhase.CHECK, TeachingPhase.REFLECT, TeachingPhase.CONNECT])
    return phases
