"""AI学习服务 - 核心学习引擎"""

import asyncio
import json
import time
from typing import List, Optional, Callable
from datetime import datetime

from sqlalchemy import select

from app.common.errors import ServiceError, ErrorCode
from app.common.llm_client import LLMClient, LLMMessage
from app.db.models import KnowledgeUnitModel
from app.modules.knowledge_splitter.schemas import KnowledgeUnit, Chapter
from app.modules.ai_learning.schemas import (
    LearnedUnit,
    Concept,
    LearningContext,
    LearningProgress,
    BookLearningResult,
    BookOverview,
    ChapterOverview,
    LearningStatus,
)
from app.modules.ai_learning.prompts import build_understand_prompt, build_merge_prompt, build_enrich_prompt
from app.modules.ai_learning.token_optimizer import TokenOptimizer


class AILearningService:
    """AI学习服务"""

    def __init__(
        self,
        llm_client: LLMClient,
        db_session=None,
        token_budget: Optional[int] = None,
    ):
        self.llm = llm_client
        self.db = db_session
        self.token_budget = token_budget
        self.optimizer = TokenOptimizer()
        self._total_tokens_used = 0
        self._on_unit_learned = None  # 学完单元后的回调（用于图谱增量更新）

    # 超过此字符数视为"大单元"，启用递归摘要
    LARGE_UNIT_THRESHOLD = 2000

    async def learn_unit(
        self, unit: KnowledgeUnit, context: LearningContext
    ) -> LearnedUnit:
        """
        学习单个知识单元。

        流程：
        1. 判断单元大小：
           - 小单元（<=2000字）→ 直接调 LLM 分析
           - 大单元（>2000字）→ 递归摘要（Map-Reduce）
             a. 按段落切成子块（每块 <=2000字）
             b. 并发调 LLM 分析各子块（Map）
             c. 调 LLM 整合所有子块结果（Reduce）
        2. 直接返回 LearnedUnit（self_assessment=None）
        """
        if len(unit.content) > self.LARGE_UNIT_THRESHOLD:
            # ── 大单元：递归摘要 ──
            context_info = self._build_context_info(context, 0)
            understand_result = await self._learn_large_unit(
                unit, context_info
            )
            token_cost = 0  # 大单元内部不单独追踪 token
        else:
            # ── 小单元：单次 LLM 理解调用 ──
            context_info = self._build_context_info(context, 0)
            prompt = build_understand_prompt(
                content=unit.content,
                context_info=context_info,
            )
            response = await self.llm.chat(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.3,
            )
            token_cost = response.usage.get("total_tokens", 0)
            understand_result = (
                response.content
                if isinstance(response.content, dict)
                else json.loads(response.content)
            )

        concepts = [Concept(**c) for c in understand_result.get("concepts", [])]

        learned = LearnedUnit(
            unit_id=unit.id,
            book_id=unit.book_id,
            summary=understand_result.get("summary", ""),
            key_points=understand_result.get("key_points", []),
            concepts=concepts,
            difficulty_level=understand_result.get("difficulty_level", 3),
            importance_score=understand_result.get("importance_score", 0.5),
            prerequisites=understand_result.get("prerequisites", []),
            self_assessment=None,
            llm_model=getattr(self.llm, "model", "unknown"),
            token_cost=token_cost,
        )

        await self._persist_learned_unit(learned)
        return learned

    async def _learn_large_unit(
        self, unit: KnowledgeUnit, context_info: str
    ) -> dict:
        """递归摘要：大单元先分块分析，再整合"""
        import re

        # 按段落切子块（每块 <=2000 字符，不超过段落边界）
        paragraphs = re.split(r'\n\n+', unit.content)
        chunks: list[str] = []
        buf = ""
        for para in paragraphs:
            if len(buf) + len(para) + 2 <= self.LARGE_UNIT_THRESHOLD:
                buf += ("\n\n" if buf else "") + para
            else:
                if buf:
                    chunks.append(buf)
                # 单段就超长 → 硬切
                while len(para) > self.LARGE_UNIT_THRESHOLD:
                    chunks.append(para[:self.LARGE_UNIT_THRESHOLD])
                    para = para[self.LARGE_UNIT_THRESHOLD:]
                buf = para
        if buf:
            chunks.append(buf)

        # Map：并发分析各子块
        sub_results: list[dict] = []
        for chunk in chunks:
            prompt = build_understand_prompt(
                content=chunk,
                context_info=f"（这是大单元「{unit.title}」的一部分，请分析这段内容）",
            )
            resp = await self.llm.chat(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.3,
            )
            result = (
                resp.content
                if isinstance(resp.content, dict)
                else json.loads(resp.content)
            )
            sub_results.append(result)

        # 只有一块 → 不需要整合
        if len(sub_results) == 1:
            return sub_results[0]

        # Reduce：整合所有子块
        merge_prompt = build_merge_prompt(
            unit_title=unit.title,
            sub_results=sub_results,
            context_info=context_info,
        )
        merge_resp = await self.llm.chat(
            messages=[LLMMessage(role="user", content=merge_prompt)],
            temperature=0.3,
        )
        return (
            merge_resp.content
            if isinstance(merge_resp.content, dict)
            else json.loads(merge_resp.content)
        )

    async def _persist_learned_unit(self, learned: LearnedUnit) -> None:
        """将 AI 学习结果写回 knowledge_units 表"""
        if self.db is None:
            return

        result = await self.db.execute(
            select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == learned.unit_id)
        )
        db_unit = result.scalar_one_or_none()
        if db_unit is None:
            return

        db_unit.summary = learned.summary
        db_unit.key_points = json.dumps(learned.key_points, ensure_ascii=False)
        # 存完整 Concept 对象（含 definition/examples/related_concepts）
        db_unit.concepts = json.dumps(
            [{"name": c.name, "definition": c.definition,
              "examples": c.examples, "related_concepts": c.related_concepts}
             for c in learned.concepts],
            ensure_ascii=False,
        )
        # prerequisites 优先存 unit_id，其次存概念名
        db_unit.prerequisites = json.dumps(learned.prerequisites, ensure_ascii=False)
        db_unit.difficulty_level = learned.difficulty_level
        db_unit.importance_score = learned.importance_score

    async def _update_knowledge_graph(self, book_id: str, learned: LearnedUnit) -> None:
        """学完一个单元后，增量更新知识图谱"""
        if self.db is None:
            return

        from app.modules.knowledge_graph.service import KnowledgeGraphService
        from app.modules.ai_learning.schemas import Concept

        svc = KnowledgeGraphService(self.db)

        # 构建 unit_data（兼容 GraphBuilder 的输入格式）
        concepts_data = []
        for c in learned.concepts:
            if isinstance(c, Concept):
                concepts_data.append({
                    "name": c.name, "definition": c.definition,
                    "examples": c.examples, "related_concepts": c.related_concepts,
                })
            else:
                concepts_data.append(c)

        unit_data = {
            "id": learned.unit_id,
            "title": learned.summary[:50] if learned.summary else "未命名",
            "concepts": concepts_data,
            "prerequisites": learned.prerequisites,
            "summary": learned.summary,
            "key_points": learned.key_points,
            "difficulty_level": learned.difficulty_level,
            "importance_score": learned.importance_score,
        }

        try:
            await svc.update_unit_graph(book_id, unit_data)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"图谱增量更新失败: {e}")

    async def get_learning_order(
        self,
        book_id: str,
        units: List[KnowledgeUnit],
    ) -> List[KnowledgeUnit]:
        """
        基于知识图谱拓扑排序 + 前置掌握度，返回优化后的学习顺序。
        前置未掌握的单元自动排到前面。
        """
        if not self.db:
            return units

        from app.modules.knowledge_graph.service import KnowledgeGraphService
        kg_service = KnowledgeGraphService(self.db)

        try:
            ordered_ids = await kg_service.get_topological_order(book_id)
        except Exception:
            return units

        unit_map = {u.id: u for u in units}
        ordered = [unit_map[uid] for uid in ordered_ids if uid in unit_map]
        seen = {u.id for u in ordered}
        ordered.extend([u for u in units if u.id not in seen])
        return ordered

    async def learn_book(
        self,
        book_id: str,
        units: List[KnowledgeUnit],
        chapters: List[Chapter],
        on_progress: Optional[Callable] = None,
        max_concurrency: int = 3,
    ) -> BookLearningResult:
        """对整本书进行AI学习（并发处理，默认最多3个并发）"""
        units = await self.get_learning_order(book_id, units)
        start_time = time.time()
        learned_count = 0
        failed_count = 0
        total_token_cost = 0
        semaphore = asyncio.Semaphore(max_concurrency)
        previous_summary = None
        existing_concepts: List[str] = []

        async def _learn_one(i: int, unit: KnowledgeUnit):
            nonlocal learned_count, failed_count, total_token_cost, previous_summary

            # 检查token预算
            if self.token_budget and self._total_tokens_used >= self.token_budget:
                return

            async with semaphore:
                try:
                    context = self.optimizer.build_context(
                        unit, chapters, previous_summary, existing_concepts
                    )

                    result = await self.learn_unit(unit, context)

                    previous_summary = result.summary
                    existing_concepts.extend([c.name for c in result.concepts])
                    self._total_tokens_used += result.token_cost
                    total_token_cost += result.token_cost
                    learned_count += 1

                    # 触发图谱增量更新
                    await self._update_knowledge_graph(book_id, result)

                    if on_progress:
                        on_progress(i + 1, len(units), unit.title)

                except Exception:
                    failed_count += 1
                    if on_progress:
                        on_progress(i + 1, len(units), f"[失败] {unit.title}")

        await asyncio.gather(*[_learn_one(i, u) for i, u in enumerate(units)])

        return BookLearningResult(
            book_id=book_id,
            total_units=len(units),
            learned_count=learned_count,
            failed_count=failed_count,
            skipped_count=len(units) - learned_count - failed_count,
            total_token_cost=total_token_cost,
            duration_seconds=time.time() - start_time,
        )

    def _build_context_info(self, context: LearningContext, iteration: int) -> str:
        """构建上下文描述"""
        parts = []
        if iteration > 0:
            parts.append(f"这是第{iteration + 1}次深化学习，请重点关注之前识别的薄弱点。")
        if context.previous_unit_summary:
            parts.append(f"前一个知识点摘要：{context.previous_unit_summary}")
        if context.chapter_summary:
            parts.append(f"当前章节概述：{context.chapter_summary}")
        if context.existing_concepts:
            parts.append(f"已学概念：{', '.join(context.existing_concepts[:10])}")
        return "\n".join(parts) if parts else "无额外上下文"

    async def relearn_unit(self, unit: KnowledgeUnit) -> LearnedUnit:
        """
        重新生成指定知识单元的 AI 分析。
        直接用原文重新调 LLM，覆盖旧结果。适用于对生成结果不满意的情况。
        """
        context_info = self._build_context_info(LearningContext(), 0)
        prompt = build_understand_prompt(
            content=unit.content,
            context_info=context_info,
        )
        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.3,
        )
        understand_result = (
            response.content
            if isinstance(response.content, dict)
            else json.loads(response.content)
        )
        concepts = [Concept(**c) for c in understand_result.get("concepts", [])]
        learned = LearnedUnit(
            unit_id=unit.id,
            book_id=unit.book_id,
            summary=understand_result.get("summary", ""),
            key_points=understand_result.get("key_points", []),
            concepts=concepts,
            difficulty_level=understand_result.get("difficulty_level", 3),
            importance_score=understand_result.get("importance_score", 0.5),
            prerequisites=understand_result.get("prerequisites", []),
            self_assessment=None,
            llm_model=getattr(self.llm, "model", "unknown"),
            token_cost=response.usage.get("total_tokens", 0),
        )
        await self._persist_learned_unit(learned)
        return learned

    async def enrich_unit(
        self,
        unit_id: str,
        book_id: str,
        chapter_id: str,
        title: str,
        content: str,
        existing_summary: str,
        existing_key_points: list,
        existing_concepts: list,
        focus: str | None = None,
        instruction: str | None = None,
    ) -> LearnedUnit:
        """
        增量更新知识单元。在原有分析基础上补充细节，不覆盖。

        策略：
        - 把原文 + 现有摘要/要点一起发给 LLM
        - 要求 LLM 补充缺失的细节、例子、关联
        - 合并新旧结果后写回 DB

        参数:
            focus: 补充方向 — "examples"(例子) / "explanations"(解释) / "connections"(关联)
            instruction: 自由文本补充指令
        """
        enrich_instruction = "请基于以下原文和已有的分析结果，补充缺失的细节。"
        if focus == "examples":
            enrich_instruction = "请为以下知识补充更多具体示例，特别是实际应用中的例子。"
        elif focus == "explanations":
            enrich_instruction = "请对以下知识给出更深入、更易懂的解释，补充原理细节。"
        elif focus == "connections":
            enrich_instruction = "请补充以下知识与其他概念之间的关联和区别。"
        if instruction:
            enrich_instruction += f"\n\n补充要求：{instruction}"

        prompt = build_enrich_prompt(
            title=title,
            content=content[:2000],
            existing_summary=existing_summary,
            existing_key_points=existing_key_points,
            existing_concepts=existing_concepts,
            instruction=enrich_instruction,
        )
        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.4,
        )
        enriched = (
            response.content
            if isinstance(response.content, dict)
            else json.loads(response.content)
        )
        # 合并：新结果优先，旧结果补充
        merged_summary = enriched.get("summary") or existing_summary
        merged_points = list(dict.fromkeys(
            enriched.get("key_points", []) + existing_key_points
        ))
        # 概念合并：按 name 去重，新的优先
        existing_by_name = {c.get("name", ""): c for c in existing_concepts}
        new_by_name = {c.get("name", c if isinstance(c, str) else c.get("name", "")): c
                       for c in enriched.get("concepts", [])}
        merged_concepts = {**existing_by_name, **new_by_name}
        concepts = [Concept(**c) if isinstance(c, dict) else Concept(name=c, definition="")
                    for c in merged_concepts.values() if c]
        learned = LearnedUnit(
            unit_id=unit_id,
            book_id=book_id,
            summary=merged_summary,
            key_points=merged_points,
            concepts=concepts,
            difficulty_level=enriched.get("difficulty_level", 3),
            importance_score=enriched.get("importance_score", 0.5),
            prerequisites=enriched.get("prerequisites", []),
            self_assessment=None,
            llm_model=getattr(self.llm, "model", "unknown"),
            token_cost=response.usage.get("total_tokens", 0),
        )
        await self._persist_learned_unit(learned)
        return learned


class SelectiveLearningService:
    """选择性学习服务"""

    def __init__(self, llm_client: LLMClient, db_session=None):
        self.learning_service = AILearningService(llm_client, db_session)

    def get_book_overview(
        self,
        book_id: str,
        chapters: List[Chapter],
        units: List[KnowledgeUnit],
    ) -> BookOverview:
        """生成书籍概览"""
        chapter_overviews = []
        for chapter in chapters:
            chapter_units = [u for u in units if u.chapter_id == chapter.id]
            avg_difficulty = sum(
                u.difficulty_level or 3 for u in chapter_units
            ) / max(len(chapter_units), 1)
            chapter_overviews.append(
                ChapterOverview(
                    chapter_id=chapter.id,
                    title=chapter.title,
                    key_concepts_preview=[],  # 需要AI学习后填充
                    estimated_minutes=len(chapter_units) * 12,
                    difficulty_level=round(avg_difficulty),
                    unit_count=len(chapter_units),
                )
            )

        return BookOverview(
            book_id=book_id,
            title="",
            total_chapters=len(chapters),
            chapters=chapter_overviews,
        )

    async def learn_selected(
        self,
        book_id: str,
        chapter_ids: List[str],
        units: List[KnowledgeUnit],
        chapters: List[Chapter],
        on_progress: Optional[Callable] = None,
    ) -> BookLearningResult:
        """只学习用户选择的章节"""
        # 过滤选中章节的单元
        selected_units = [u for u in units if u.chapter_id in chapter_ids]
        selected_chapters = [c for c in chapters if c.id in chapter_ids]

        if not selected_units:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "选中的章节没有知识单元")

        return await self.learning_service.learn_book(
            book_id, selected_units, selected_chapters, on_progress
        )
