"""教学策略选择 v2 - 智能化升级

改进：
1. 基于连续值的教学策略（替代布尔值）
2. 改进知识类型推断（支持LLM辅助）
3. 双向自适应调整
4. 考虑前置依赖的阶段选择
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
from app.modules.ai_learning.schemas import LearnedUnit
from app.modules.teaching.schemas import (
    TeachingStrategy, TeachingPhase, KnowledgeType, CognitiveLevel, UserTeachingProfile,
)


@dataclass
class ContinuousTeachingStrategy:
    """连续值教学策略"""
    # 知识类型
    knowledge_type: str

    # 认知层级（0-4连续值）
    cognitive_level: float = 0.5  # 0=REMEMBER, 1=UNDERSTAND, 2=APPLY, 3=ANALYZE, 4=CREATE

    # 脚手架级别（0-1连续值）
    scaffold_level: float = 0.5  # 0=minimal, 1=full

    # 教学节奏（0-1连续值）
    pace: float = 0.5  # 0=slow, 1=fast

    # 交互频率（0-1连续值）
    interaction_frequency: float = 0.5  # 0=low, 1=high

    # 视觉辅助（0-1连续值）
    visual_level: float = 0.5  # 0=low, 1=high

    # 反馈风格（0-1连续值）
    feedback_style: float = 0.5  # 0=immediate, 1=delayed

    # 讲解风格
    explanation_style: str = "balanced"

    # 置信度（0-1）
    confidence: float = 0.5


@dataclass
class TeachingContext:
    """教学上下文"""
    unit: LearnedUnit
    user_profile: Optional[UserTeachingProfile] = None
    mastery_score: float = 0.5
    prerequisite_mastery: Dict[str, float] = None
    recent_performance: List[Dict[str, Any]] = None
    confusion_signals: int = 0
    question_count: int = 0
    avg_response_time: float = 30.0

    def __post_init__(self):
        if self.prerequisite_mastery is None:
            self.prerequisite_mastery = {}
        if self.recent_performance is None:
            self.recent_performance = []


class KnowledgeTypeInferrer:
    """知识类型推断器"""

    # 关键词映射（更全面）
    PROCEDURE_KEYWORDS = {
        "步骤", "流程", "如何", "怎么", "怎样", "操作", "执行", "实现", "编写",
        "方法", "技巧", "过程", "阶段", "环节", "顺序", "次序", "先后",
        "第一", "第二", "首先", "然后", "接着", "最后", "开始", "结束",
    }

    PRINCIPLE_KEYWORDS = {
        "原理", "为什么", "机制", "原因", "本质", "底层", "核心",
        "规律", "法则", "定理", "公式", "模型", "理论", "假设",
        "因为", "所以", "导致", "引起", "产生", "形成", "决定",
    }

    CONCEPT_KEYWORDS = {
        "概念", "定义", "术语", "含义", "意思", "解释", "说明",
        "是指", "表示", "代表", "指的是", "意味着", "定义为",
    }

    FACT_KEYWORDS = {
        "事实", "数据", "统计", "历史", "时间", "地点", "人物",
        "年份", "日期", "数量", "比例", "百分比", "指标",
    }

    @classmethod
    def infer(cls, unit: LearnedUnit) -> str:
        """从知识单元内容推断知识类型"""
        # 收集所有文本
        kp_parts = []
        for kp in unit.key_points:
            if hasattr(kp, 'title'):
                kp_parts.append(kp.title)
            else:
                kp_parts.append(str(kp))
        key_points_text = " ".join(kp_parts).lower()
        concepts_text = " ".join(c.name for c in unit.concepts).lower()
        content_text = unit.content[:1000].lower() if unit.content else ""

        all_text = f"{key_points_text} {concepts_text} {content_text}"

        # 计算各类型关键词的匹配分数
        scores = {
            KnowledgeType.PROCEDURE.value: cls._count_keywords(all_text, cls.PROCEDURE_KEYWORDS),
            KnowledgeType.PRINCIPLE.value: cls._count_keywords(all_text, cls.PRINCIPLE_KEYWORDS),
            KnowledgeType.CONCEPT.value: cls._count_keywords(all_text, cls.CONCEPT_KEYWORDS),
            KnowledgeType.FACT.value: cls._count_keywords(all_text, cls.FACT_KEYWORDS),
        }

        # 如果有明确定义的概念，增加 CONCEPT 分数
        if unit.concepts and any(c.definition for c in unit.concepts):
            scores[KnowledgeType.CONCEPT.value] += 2

        # 返回分数最高的类型
        max_type = max(scores.items(), key=lambda x: x[1])
        if max_type[1] > 0:
            return max_type[0]

        return KnowledgeType.FACT.value

    @classmethod
    def _count_keywords(cls, text: str, keywords: set) -> int:
        """统计关键词出现次数"""
        return sum(1 for kw in keywords if kw in text)


class CognitiveLevelSelector:
    """认知层级选择器"""

    @staticmethod
    def select(difficulty: Optional[int], mastery: float, prerequisite_mastery: Dict[str, float] = None) -> float:
        """
        选择认知层级（连续值）

        Args:
            difficulty: 难度等级 (1-5)
            mastery: 掌握度 (0-1)
            prerequisite_mastery: 前置知识掌握度

        Returns:
            认知层级 (0-4)
        """
        # 基础层级基于掌握度和难度
        if mastery < 0.2:
            base_level = 0.0  # REMEMBER
        elif mastery < 0.4:
            base_level = 1.0  # UNDERSTAND
        elif mastery < 0.6:
            base_level = 2.0  # APPLY
        elif mastery < 0.8:
            base_level = 3.0  # ANALYZE
        else:
            base_level = 4.0  # CREATE

        # 根据难度调整
        if difficulty:
            difficulty_factor = (difficulty - 3) / 2  # -1 到 1
            base_level += difficulty_factor

        # 根据前置知识掌握度调整
        if prerequisite_mastery:
            avg_prerequisite = sum(prerequisite_mastery.values()) / len(prerequisite_mastery)
            if avg_prerequisite < 0.5:
                # 前置知识不足，降低认知层级
                base_level = max(0, base_level - 0.5)

        return max(0.0, min(4.0, base_level))


class ScaffoldSelector:
    """脚手架级别选择器"""

    @staticmethod
    def select(
        mastery: float,
        difficulty: Optional[int],
        confusion_signals: int = 0,
        recent_performance: List[Dict[str, Any]] = None
    ) -> float:
        """
        选择脚手架级别（连续值）

        Args:
            mastery: 掌握度 (0-1)
            difficulty: 难度等级 (1-5)
            confusion_signals: 困惑信号数量
            recent_performance: 最近表现

        Returns:
            脚手架级别 (0-1)
        """
        # 基础级别基于掌握度
        base_level = 1.0 - mastery

        # 根据难度调整
        if difficulty:
            difficulty_factor = (difficulty - 3) / 4  # -0.5 到 0.5
            base_level += difficulty_factor

        # 根据困惑信号调整
        if confusion_signals > 0:
            base_level += confusion_signals * 0.1

        # 根据最近表现调整
        if recent_performance:
            recent_accuracy = sum(1 for p in recent_performance if p.get('is_correct', False)) / len(recent_performance)
            if recent_accuracy < 0.5:
                base_level += 0.2
            elif recent_accuracy > 0.8:
                base_level -= 0.1

        return max(0.0, min(1.0, base_level))


class PaceSelector:
    """教学节奏选择器"""

    @staticmethod
    def select(
        mastery: float,
        difficulty: Optional[int],
        avg_response_time: float = 30.0,
        recent_performance: List[Dict[str, Any]] = None
    ) -> float:
        """
        选择教学节奏（连续值）

        Args:
            mastery: 掌握度 (0-1)
            difficulty: 难度等级 (1-5)
            avg_response_time: 平均响应时间（秒）
            recent_performance: 最近表现

        Returns:
            教学节奏 (0-1)
        """
        # 基础节奏基于掌握度
        base_pace = mastery

        # 根据难度调整
        if difficulty:
            difficulty_factor = (3 - difficulty) / 4  # -0.5 到 0.5
            base_pace += difficulty_factor

        # 根据响应时间调整
        if avg_response_time > 60:
            # 响应慢，降低节奏
            base_pace -= 0.2
        elif avg_response_time < 15:
            # 响应快，提高节奏
            base_pace += 0.1

        # 根据最近表现调整
        if recent_performance:
            recent_accuracy = sum(1 for p in recent_performance if p.get('is_correct', False)) / len(recent_performance)
            if recent_accuracy > 0.8:
                base_pace += 0.1
            elif recent_accuracy < 0.5:
                base_pace -= 0.2

        return max(0.0, min(1.0, base_pace))


class InteractionFrequencySelector:
    """交互频率选择器"""

    @staticmethod
    def select(
        mastery: float,
        knowledge_type: str,
        question_count: int = 0,
        confusion_signals: int = 0
    ) -> float:
        """
        选择交互频率（连续值）

        Args:
            mastery: 掌握度 (0-1)
            knowledge_type: 知识类型
            question_count: 提问次数
            confusion_signals: 困惑信号数量

        Returns:
            交互频率 (0-1)
        """
        # 基础频率基于掌握度（掌握度低时需要更多交互）
        base_frequency = 1.0 - mastery

        # 根据知识类型调整
        if knowledge_type == KnowledgeType.PROCEDURE.value:
            # 程序性知识需要更多交互
            base_frequency += 0.2
        elif knowledge_type == KnowledgeType.CONCEPT.value:
            # 概念性知识需要适度交互
            base_frequency += 0.1

        # 根据提问次数调整
        if question_count > 3:
            # 用户主动提问多，降低系统交互频率
            base_frequency -= 0.2

        # 根据困惑信号调整
        if confusion_signals > 0:
            base_frequency += confusion_signals * 0.1

        return max(0.0, min(1.0, base_frequency))


class VisualLevelSelector:
    """视觉辅助级别选择器"""

    @staticmethod
    def select(difficulty: Optional[int], knowledge_type: str) -> float:
        """
        选择视觉辅助级别（连续值）

        Args:
            difficulty: 难度等级 (1-5)
            knowledge_type: 知识类型

        Returns:
            视觉辅助级别 (0-1)
        """
        # 基础级别基于难度
        base_level = 0.5
        if difficulty:
            base_level = (difficulty - 1) / 4  # 0 到 1

        # 根据知识类型调整
        if knowledge_type == KnowledgeType.PROCEDURE.value:
            # 程序性知识需要更多视觉辅助
            base_level += 0.2
        elif knowledge_type == KnowledgeType.FACT.value:
            # 事实性知识需要较少视觉辅助
            base_level -= 0.2

        return max(0.0, min(1.0, base_level))


class FeedbackStyleSelector:
    """反馈风格选择器"""

    @staticmethod
    def select(mastery: float, confusion_signals: int = 0) -> float:
        """
        选择反馈风格（连续值）

        Args:
            mastery: 掌握度 (0-1)
            confusion_signals: 困惑信号数量

        Returns:
            反馈风格 (0-1)
        """
        # 基础风格基于掌握度
        base_style = mastery

        # 根据困惑信号调整
        if confusion_signals > 0:
            # 困惑时需要更即时的反馈
            base_style -= confusion_signals * 0.1

        return max(0.0, min(1.0, base_style))


class PhaseSelector:
    """教学阶段选择器"""

    @staticmethod
    def select(
        unit: LearnedUnit,
        mastery: float,
        prerequisite_mastery: Dict[str, float] = None
    ) -> List[TeachingPhase]:
        """
        选择教学阶段

        Args:
            unit: 知识单元
            mastery: 掌握度
            prerequisite_mastery: 前置知识掌握度

        Returns:
            教学阶段列表
        """
        difficulty = unit.difficulty_level or 3

        # 计算复杂度分数
        complexity_score = PhaseSelector._calculate_complexity(
            difficulty, mastery, prerequisite_mastery
        )

        # 基础阶段
        phases = [TeachingPhase.ACTIVATE, TeachingPhase.CORE, TeachingPhase.FEYNMAN, TeachingPhase.RETRIEVAL]

        # 根据复杂度添加阶段
        if complexity_score >= 0.7:
            # 高复杂度：完整阶段
            phases = [
                TeachingPhase.ACTIVATE,
                TeachingPhase.INTRO,
                TeachingPhase.CORE,
                TeachingPhase.FEYNMAN,
                TeachingPhase.RETRIEVAL,
                TeachingPhase.CHECK,
                TeachingPhase.REFLECT,
                TeachingPhase.CONNECT,
            ]
        elif complexity_score >= 0.4:
            # 中等复杂度：添加检查和反思
            phases.extend([TeachingPhase.CHECK, TeachingPhase.REFLECT, TeachingPhase.CONNECT])
        # 低复杂度：保持基础阶段

        return phases

    @staticmethod
    def _calculate_complexity(
        difficulty: int,
        mastery: float,
        prerequisite_mastery: Dict[str, float] = None
    ) -> float:
        """
        计算内容复杂度

        Returns:
            复杂度分数 (0-1)
        """
        # 难度贡献
        difficulty_score = (difficulty - 1) / 4  # 0 到 1

        # 掌握度贡献（掌握度低增加复杂度）
        mastery_score = 1.0 - mastery

        # 前置知识贡献
        prerequisite_score = 0.0
        if prerequisite_mastery:
            avg_prerequisite = sum(prerequisite_mastery.values()) / len(prerequisite_mastery)
            prerequisite_score = 1.0 - avg_prerequisite

        # 加权平均
        complexity = (
            difficulty_score * 0.4 +
            mastery_score * 0.4 +
            prerequisite_score * 0.2
        )

        return max(0.0, min(1.0, complexity))


class AdaptiveStrategyManager:
    """自适应策略管理器"""

    @staticmethod
    def adapt_strategy(
        strategy: ContinuousTeachingStrategy,
        interaction_data: Dict[str, Any]
    ) -> ContinuousTeachingStrategy:
        """
        根据交互数据自适应调整策略

        Args:
            strategy: 当前策略
            interaction_data: 交互数据

        Returns:
            调整后的策略
        """
        new_strategy = ContinuousTeachingStrategy(
            knowledge_type=strategy.knowledge_type,
            cognitive_level=strategy.cognitive_level,
            scaffold_level=strategy.scaffold_level,
            pace=strategy.pace,
            interaction_frequency=strategy.interaction_frequency,
            visual_level=strategy.visual_level,
            feedback_style=strategy.feedback_style,
            explanation_style=strategy.explanation_style,
            confidence=strategy.confidence,
        )

        # 提取交互数据
        question_count = interaction_data.get('question_count', 0)
        correct_rate = interaction_data.get('correct_rate', 0.5)
        confusion_count = interaction_data.get('confusion_count', 0)
        avg_response_time = interaction_data.get('avg_response_time', 30.0)

        # 双向自适应调整

        # 1. 根据正确率调整节奏和脚手架
        if correct_rate > 0.8:
            # 表现好：加速，减少脚手架
            new_strategy.pace = min(1.0, strategy.pace + 0.1)
            new_strategy.scaffold_level = max(0.0, strategy.scaffold_level - 0.1)
        elif correct_rate < 0.5:
            # 表现差：减速，增加脚手架
            new_strategy.pace = max(0.0, strategy.pace - 0.1)
            new_strategy.scaffold_level = min(1.0, strategy.scaffold_level + 0.1)

        # 2. 根据困惑信号调整交互频率和脚手架
        if confusion_count > 0:
            new_strategy.interaction_frequency = min(1.0, strategy.interaction_frequency + 0.1)
            new_strategy.scaffold_level = min(1.0, strategy.scaffold_level + 0.1)

        # 3. 根据响应时间调整节奏
        if avg_response_time > 60:
            new_strategy.pace = max(0.0, strategy.pace - 0.1)
        elif avg_response_time < 15:
            new_strategy.pace = min(1.0, strategy.pace + 0.1)

        # 4. 根据提问次数调整交互频率
        if question_count > 3:
            # 用户主动提问多，降低系统交互
            new_strategy.interaction_frequency = max(0.0, strategy.interaction_frequency - 0.1)

        return new_strategy


def select_teaching_strategy_v2(context: TeachingContext) -> ContinuousTeachingStrategy:
    """
    选择教学策略 v2

    Args:
        context: 教学上下文

    Returns:
        连续值教学策略
    """
    # 推断知识类型
    knowledge_type = KnowledgeTypeInferrer.infer(context.unit)

    # 选择认知层级
    cognitive_level = CognitiveLevelSelector.select(
        context.unit.difficulty_level,
        context.mastery_score,
        context.prerequisite_mastery
    )

    # 选择脚手架级别
    scaffold_level = ScaffoldSelector.select(
        context.mastery_score,
        context.unit.difficulty_level,
        context.confusion_signals,
        context.recent_performance
    )

    # 选择教学节奏
    pace = PaceSelector.select(
        context.mastery_score,
        context.unit.difficulty_level,
        context.avg_response_time,
        context.recent_performance
    )

    # 选择交互频率
    interaction_frequency = InteractionFrequencySelector.select(
        context.mastery_score,
        knowledge_type,
        context.question_count,
        context.confusion_signals
    )

    # 选择视觉辅助
    visual_level = VisualLevelSelector.select(
        context.unit.difficulty_level,
        knowledge_type
    )

    # 选择反馈风格
    feedback_style = FeedbackStyleSelector.select(
        context.mastery_score,
        context.confusion_signals
    )

    # 选择讲解风格
    explanation_style = _select_explanation_style(knowledge_type)

    return ContinuousTeachingStrategy(
        knowledge_type=knowledge_type,
        cognitive_level=cognitive_level,
        scaffold_level=scaffold_level,
        pace=pace,
        interaction_frequency=interaction_frequency,
        visual_level=visual_level,
        feedback_style=feedback_style,
        explanation_style=explanation_style,
        confidence=0.7,
    )


def select_teaching_phases_v2(context: TeachingContext) -> List[TeachingPhase]:
    """
    选择教学阶段 v2

    Args:
        context: 教学上下文

    Returns:
        教学阶段列表
    """
    return PhaseSelector.select(
        context.unit,
        context.mastery_score,
        context.prerequisite_mastery
    )


def _select_explanation_style(knowledge_type: str) -> str:
    """选择讲解风格"""
    mapping = {
        KnowledgeType.PROCEDURE.value: "example_first",
        KnowledgeType.PRINCIPLE.value: "theory_first",
        KnowledgeType.CONCEPT.value: "analogy",
        KnowledgeType.FACT.value: "problem_based",
    }
    return mapping.get(knowledge_type, "balanced")


def convert_to_legacy_strategy(strategy: ContinuousTeachingStrategy) -> TeachingStrategy:
    """将连续值策略转换为旧版策略格式"""
    return TeachingStrategy(
        explanation_style=strategy.explanation_style,
        visual_level=_convert_continuous_to_level(strategy.visual_level, ["low", "medium", "high"]),
        interaction_frequency=_convert_continuous_to_level(strategy.interaction_frequency, ["low", "medium", "high"]),
        pace=_convert_continuous_to_level(strategy.pace, ["slow", "normal", "fast"]),
        knowledge_type=strategy.knowledge_type,
        cognitive_level=_convert_continuous_to_cognitive_level(strategy.cognitive_level),
        scaffold_level=_convert_continuous_to_level(strategy.scaffold_level, ["minimal", "partial", "full"]),
        feedback_style=_convert_continuous_to_level(strategy.feedback_style, ["immediate", "guided", "delayed"]),
    )


def _convert_continuous_to_level(value: float, levels: List[str]) -> str:
    """将连续值转换为离散级别"""
    if value < 0.33:
        return levels[0]
    elif value < 0.67:
        return levels[1]
    else:
        return levels[2]


def _convert_continuous_to_cognitive_level(value: float) -> str:
    """将连续值转换为认知层级"""
    if value < 0.5:
        return CognitiveLevel.REMEMBER.value
    elif value < 1.5:
        return CognitiveLevel.UNDERSTAND.value
    elif value < 2.5:
        return CognitiveLevel.APPLY.value
    elif value < 3.5:
        return CognitiveLevel.ANALYZE.value
    else:
        return "CREATE"
