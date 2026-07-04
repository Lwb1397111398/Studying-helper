"""Token优化器 v2 - 智能上下文管理

改进：
1. 智能上下文管理（基于相关性裁剪）
2. 修正中文token估算（1.8字符/token）
3. 更新模型价格配置
4. 添加动态上下文窗口
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from app.modules.knowledge_splitter.schemas import KnowledgeUnit, Chapter
from app.modules.ai_learning.schemas import LearningContext


@dataclass
class ModelPricing:
    """模型价格配置"""
    input_price_per_1m: float  # 输入价格 ($/1M tokens)
    output_price_per_1m: float  # 输出价格 ($/1M tokens)
    max_context_tokens: int  # 最大上下文 token 数


# 模型价格配置 (2024年价格)
MODEL_PRICING = {
    "gpt-4o": ModelPricing(2.5, 10.0, 128000),
    "gpt-4o-mini": ModelPricing(0.15, 0.6, 128000),
    "gpt-4-turbo": ModelPricing(10.0, 30.0, 128000),
    "gpt-3.5-turbo": ModelPricing(0.5, 1.5, 16385),
    "claude-3-5-sonnet": ModelPricing(3.0, 15.0, 200000),
    "claude-3-haiku": ModelPricing(0.25, 1.25, 200000),
    "claude-3-opus": ModelPricing(15.0, 75.0, 200000),
    "deepseek-chat": ModelPricing(0.14, 0.28, 128000),
    "qwen-turbo": ModelPricing(0.06, 0.06, 128000),
}


@dataclass
class CostEstimate:
    """成本估算"""
    total_tokens: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    unit_count: int
    model: str
    actual_tokens: Optional[int] = None


@dataclass
class OptimizedContext:
    """优化后的上下文"""
    current_unit: KnowledgeUnit
    prerequisites: List[str]
    related_context: str
    estimated_tokens: int
    context_quality: float  # 上下文质量分数 (0-1)


class TokenOptimizerV2:
    """Token优化器 v2"""

    # 中文 token 化比率（实测）
    CN_CHAR_PER_TOKEN = 1.8
    EN_CHAR_PER_TOKEN = 4.0

    # 默认配置
    DEFAULT_MAX_CONTEXT_TOKENS = 4000
    DEFAULT_SUMMARY_MAX_LENGTH = 200
    DEFAULT_RELEVANCE_THRESHOLD = 0.4

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o-mini"])

    def build_context(
        self,
        unit: KnowledgeUnit,
        all_chapters: List[Chapter],
        completed_units: List[KnowledgeUnit] = None,
        existing_concepts: List[str] = None,
        max_tokens: int = None,
    ) -> OptimizedContext:
        """
        构建优化的学习上下文

        Args:
            unit: 当前知识单元
            all_chapters: 所有章节
            completed_units: 已完成的单元
            existing_concepts: 已有概念列表
            max_tokens: 最大 token 数

        Returns:
            优化后的上下文
        """
        if max_tokens is None:
            max_tokens = self.pricing.max_context_tokens // 10  # 使用 10% 的上下文窗口

        # 获取当前章节
        chapter = next((c for c in all_chapters if c.id == unit.chapter_id), None)

        # 获取前置条件
        prerequisites = self._extract_prerequisites(unit)

        # 构建相关上下文
        related_context = self._build_related_context(
            unit, completed_units or [], existing_concepts or [], max_tokens
        )

        # 估算 token 数
        estimated_tokens = self._estimate_tokens(related_context)

        # 计算上下文质量
        context_quality = self._calculate_context_quality(
            unit, completed_units or [], related_context
        )

        return OptimizedContext(
            current_unit=unit,
            prerequisites=prerequisites,
            related_context=related_context,
            estimated_tokens=estimated_tokens,
            context_quality=context_quality,
        )

    def build_learning_context(
        self,
        unit: KnowledgeUnit,
        all_chapters: List[Chapter],
        completed_units: List[KnowledgeUnit] = None,
        existing_concepts: List[str] = None,
    ) -> LearningContext:
        """
        构建学习上下文（兼容旧版）

        Args:
            unit: 当前知识单元
            all_chapters: 所有章节
            completed_units: 已完成的单元
            existing_concepts: 已有概念列表

        Returns:
            学习上下文
        """
        optimized = self.build_context(
            unit, all_chapters, completed_units, existing_concepts
        )

        chapter = next((c for c in all_chapters if c.id == unit.chapter_id), None)

        return LearningContext(
            previous_unit_summary=self._get_previous_summary(completed_units),
            chapter_summary=chapter.summary if chapter else None,
            existing_concepts=existing_concepts or [],
            user_confusing_marks=[],
        )

    def estimate_cost(
        self,
        unit_count: int,
        avg_content_length: int = 2000,
        model: str = None,
    ) -> CostEstimate:
        """
        预估学习成本

        Args:
            unit_count: 单元数量
            avg_content_length: 平均内容长度（字符）
            model: 模型名称

        Returns:
            成本估算
        """
        if model is None:
            model = self.model

        pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o-mini"])

        # 估算每个单元的 token 数
        # 中文：1 token ≈ 1.8 字符
        # 英文：1 token ≈ 4 字符
        # 假设 70% 中文，30% 英文
        cn_chars = avg_content_length * 0.7
        en_chars = avg_content_length * 0.3
        tokens_per_unit = int(cn_chars / self.CN_CHAR_PER_TOKEN + en_chars / self.EN_CHAR_PER_TOKEN)

        # 加上 prompt 开销
        prompt_overhead = 500
        tokens_per_unit += prompt_overhead

        # 估算输入和输出 token
        input_tokens = unit_count * tokens_per_unit
        output_tokens = unit_count * (tokens_per_unit // 2)  # 输出通常是输入的一半
        total_tokens = input_tokens + output_tokens

        # 计算成本
        input_cost = (input_tokens / 1_000_000) * pricing.input_price_per_1m
        output_cost = (output_tokens / 1_000_000) * pricing.output_price_per_1m
        total_cost = input_cost + output_cost

        return CostEstimate(
            total_tokens=total_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=round(total_cost, 4),
            unit_count=unit_count,
            model=model,
        )

    def estimate_tokens(self, text: str) -> int:
        """
        准确估算 token 数

        Args:
            text: 文本

        Returns:
            token 数
        """
        return self._estimate_tokens(text)

    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数"""
        if not text:
            return 0

        # 统计中文字符
        cn_chars = len(re.findall(r'[一-鿿]', text))
        # 统计英文字符（包括数字和标点）
        en_chars = len(text) - cn_chars

        # 计算 token 数
        tokens = int(cn_chars / self.CN_CHAR_PER_TOKEN + en_chars / self.EN_CHAR_PER_TOKEN)

        return max(1, tokens)

    def _extract_prerequisites(self, unit: KnowledgeUnit) -> List[str]:
        """提取前置条件"""
        prerequisites = []
        if unit.prerequisites:
            if isinstance(unit.prerequisites, list):
                prerequisites = unit.prerequisites
            elif isinstance(unit.prerequisites, str):
                # 尝试解析 JSON
                try:
                    import json
                    prerequisites = json.loads(unit.prerequisites)
                except:
                    prerequisites = [unit.prerequisites]
        return prerequisites

    def _build_related_context(
        self,
        current_unit: KnowledgeUnit,
        completed_units: List[KnowledgeUnit],
        existing_concepts: List[str],
        max_tokens: int,
    ) -> str:
        """构建相关上下文"""
        context_parts = []

        # 1. 添加前置单元的摘要（按相关性排序）
        relevant_units = self._rank_units_by_relevance(current_unit, completed_units)
        for unit in relevant_units[:5]:  # 最多 5 个相关单元
            if unit.summary:
                # 压缩摘要
                compressed = self._compress_summary(unit.summary, self.DEFAULT_SUMMARY_MAX_LENGTH)
                context_parts.append(f"[{unit.title}] {compressed}")

        # 2. 添加已有概念（最多 10 个）
        if existing_concepts:
            concepts_str = ", ".join(existing_concepts[:10])
            context_parts.append(f"已有概念: {concepts_str}")

        # 3. 添加前置条件说明
        prerequisites = self._extract_prerequisites(current_unit)
        if prerequisites:
            prereq_str = ", ".join(prerequisites[:5])
            context_parts.append(f"前置知识: {prereq_str}")

        # 组合上下文
        context = "\n".join(context_parts)

        # 如果超过最大 token 数，进行裁剪
        if self._estimate_tokens(context) > max_tokens:
            context = self._trim_context(context, max_tokens)

        return context

    def _rank_units_by_relevance(
        self,
        current_unit: KnowledgeUnit,
        completed_units: List[KnowledgeUnit],
    ) -> List[KnowledgeUnit]:
        """按相关性排序单元"""
        if not completed_units:
            return []

        # 计算相关性分数
        scored_units = []
        for unit in completed_units:
            score = self._calculate_relevance(current_unit, unit)
            scored_units.append((unit, score))

        # 按分数降序排序
        scored_units.sort(key=lambda x: x[1], reverse=True)

        return [unit for unit, score in scored_units]

    def _calculate_relevance(
        self,
        current_unit: KnowledgeUnit,
        other_unit: KnowledgeUnit,
    ) -> float:
        """计算两个单元的相关性"""
        score = 0.0

        # 1. 同章节加分
        if current_unit.chapter_id == other_unit.chapter_id:
            score += 0.5

        # 2. 前置关系加分
        prerequisites = self._extract_prerequisites(current_unit)
        if other_unit.id in prerequisites:
            score += 0.3

        # 3. 概念重叠加分
        current_concepts = set(c.name for c in current_unit.concepts) if current_unit.concepts else set()
        other_concepts = set(c.name for c in other_unit.concepts) if other_unit.concepts else set()
        overlap = len(current_concepts & other_concepts)
        if overlap > 0:
            score += min(0.2, overlap * 0.05)

        # 4. 顺序接近加分
        order_diff = abs(current_unit.order_index - other_unit.order_index)
        if order_diff <= 3:
            score += 0.1

        return score

    def _compress_summary(self, summary: str, max_length: int) -> str:
        """压缩摘要"""
        if not summary:
            return ""

        if len(summary) <= max_length:
            return summary

        # 截断并添加省略号
        return summary[:max_length - 3] + "..."

    def _trim_context(self, context: str, max_tokens: int) -> str:
        """裁剪上下文"""
        lines = context.split("\n")
        trimmed_lines = []
        current_tokens = 0

        for line in lines:
            line_tokens = self._estimate_tokens(line)
            if current_tokens + line_tokens > max_tokens:
                break
            trimmed_lines.append(line)
            current_tokens += line_tokens

        return "\n".join(trimmed_lines)

    def _get_previous_summary(self, completed_units: List[KnowledgeUnit]) -> Optional[str]:
        """获取前一个单元的摘要"""
        if not completed_units:
            return None

        # 按顺序排序，取最后一个
        sorted_units = sorted(completed_units, key=lambda u: u.order_index)
        if sorted_units:
            return sorted_units[-1].summary

        return None

    def _calculate_context_quality(
        self,
        current_unit: KnowledgeUnit,
        completed_units: List[KnowledgeUnit],
        related_context: str,
    ) -> float:
        """计算上下文质量分数"""
        quality = 0.5  # 基础分数

        # 1. 有前置知识加分
        prerequisites = self._extract_prerequisites(current_unit)
        if prerequisites:
            completed_ids = set(u.id for u in completed_units)
            covered = sum(1 for p in prerequisites if p in completed_ids)
            if covered > 0:
                quality += 0.2 * (covered / len(prerequisites))

        # 2. 有相关上下文加分
        if related_context:
            quality += 0.2

        # 3. 有同章节内容加分
        same_chapter = [u for u in completed_units if u.chapter_id == current_unit.chapter_id]
        if same_chapter:
            quality += 0.1

        return min(1.0, quality)


# 便捷函数
def create_optimizer(model: str = "gpt-4o-mini") -> TokenOptimizerV2:
    """创建优化器实例"""
    return TokenOptimizerV2(model)


def estimate_tokens(text: str) -> int:
    """估算 token 数（便捷函数）"""
    optimizer = TokenOptimizerV2()
    return optimizer.estimate_tokens(text)
