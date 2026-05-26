"""Token优化器 - 精简上下文、预估成本"""

from typing import List, Optional
from app.modules.knowledge_splitter.schemas import KnowledgeUnit, Chapter
from app.modules.ai_learning.schemas import LearningContext


class CostEstimate:
    def __init__(self, total_tokens: int, estimated_cost_usd: float, unit_count: int, actual_tokens: Optional[int] = None):
        self.total_tokens = total_tokens
        self.estimated_cost_usd = estimated_cost_usd
        self.unit_count = unit_count
        self.actual_tokens = actual_tokens


class TokenOptimizer:
    """Token优化器"""

    def build_context(
        self,
        unit: KnowledgeUnit,
        all_chapters: List[Chapter],
        previous_summary: Optional[str] = None,
        existing_concepts: List[str] = None,
    ) -> LearningContext:
        """
        构建精简的学习上下文。

        优化策略：
        1. 只传前一个单元的摘要（不是全文）
        2. 只传当前章节概述（不是全书）
        3. 只传已有的概念名称列表（不是完整定义）
        """
        chapter = next((c for c in all_chapters if c.id == unit.chapter_id), None)
        return LearningContext(
            previous_unit_summary=previous_summary,
            chapter_summary=chapter.summary if chapter else None,
            existing_concepts=existing_concepts or [],
            user_confusing_marks=[],
        )

    def estimate_cost(self, unit_count: int, avg_content_length: int = 2000) -> CostEstimate:
        """预估学习成本"""
        # 基于内容长度估算：1 token ≈ 4 字符，加 prompt 开销 500 tokens
        tokens_per_unit = avg_content_length // 4 + 500
        total = unit_count * tokens_per_unit
        return CostEstimate(
            total_tokens=total,
            estimated_cost_usd=total / 1000 * 0.03,
            unit_count=unit_count,
        )
