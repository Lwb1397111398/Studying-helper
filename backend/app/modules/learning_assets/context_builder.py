"""阶段 0：确定性分析上下文构建（不重复整章）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BookModel, ChapterModel, KnowledgeUnitModel
from app.modules.learning_assets.block_builder import (
    ensure_document_blocks_for_book,
    get_blocks_for_unit,
)


@dataclass
class AnalysisContext:
    book_id: str
    chapter_id: Optional[str]
    unit_id: str
    document_revision_id: str
    book_context_text: str
    chapter_context_text: str
    unit_text: str
    unit_title: str
    unit_blocks: List[dict[str, Any]] = field(default_factory=list)
    adjacency_blocks: List[dict[str, Any]] = field(default_factory=list)
    retrieval_blocks: List[dict[str, Any]] = field(default_factory=list)
    known_concepts: List[str] = field(default_factory=list)
    sent_block_ids: List[str] = field(default_factory=list)
    token_budget: int = 6000
    source_revision_hint: str = ""

    def to_pipeline_ctx(self) -> dict[str, Any]:
        """兼容 pipeline 现有 ctx 形状。"""
        return {
            "unit_id": self.unit_id,
            "book_id": self.book_id,
            "chapter_id": self.chapter_id,
            "unit_text": self.unit_text,
            "unit_title": self.unit_title,
            "document_revision_id": self.document_revision_id,
            "blocks": self.unit_blocks,
            "adjacency_blocks": self.adjacency_blocks,
            "book_context_text": self.book_context_text,
            "chapter_context_text": self.chapter_context_text,
            "known_concepts": self.known_concepts,
            "sent_block_ids": self.sent_block_ids,
            "token_budget": self.token_budget,
        }


def _estimate_tokens(text: str) -> int:
    # 粗估：中文约 1.5 字/token，英文约 4 char/token — 用保守 char/2
    return max(1, len(text or "") // 2)


def _trim_blocks_to_budget(
    primary: List[dict[str, Any]],
    adjacency: List[dict[str, Any]],
    book_ctx: str,
    chapter_ctx: str,
    budget: int,
) -> tuple[List[dict[str, Any]], List[dict[str, Any]], str, str]:
    """优先级：unit blocks > adjacency > chapter > book。永不丢掉 unit。"""
    used = sum(_estimate_tokens(b.get("text") or "") for b in primary)
    used += _estimate_tokens(chapter_ctx) + _estimate_tokens(book_ctx)
    kept_adj: List[dict[str, Any]] = []
    for b in adjacency:
        t = _estimate_tokens(b.get("text") or "")
        if used + t <= budget:
            kept_adj.append(b)
            used += t
        else:
            break
    if used > budget:
        # 压缩 chapter/book
        chapter_ctx = chapter_ctx[:200]
        book_ctx = book_ctx[:120]
    return primary, kept_adj, book_ctx, chapter_ctx


async def build_analysis_context(
    session: AsyncSession,
    unit_id: str,
    *,
    token_budget: int = 6000,
    adjacency_count: int = 2,
) -> AnalysisContext:
    unit = (
        await session.execute(
            select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
        )
    ).scalar_one_or_none()
    if unit is None:
        raise ValueError(f"unit not found: {unit_id}")

    book = (
        await session.execute(select(BookModel).where(BookModel.id == unit.book_id))
    ).scalar_one_or_none()
    chapter = None
    if unit.chapter_id:
        chapter = (
            await session.execute(
                select(ChapterModel).where(ChapterModel.id == unit.chapter_id)
            )
        ).scalar_one_or_none()

    rev_id = await ensure_document_blocks_for_book(session, unit.book_id)
    unit_blocks_orm = await get_blocks_for_unit(session, unit_id, rev_id)
    unit_blocks = [
        {
            "id": b.id,
            "text": b.text,
            "ordinal": b.ordinal,
            "chapter_id": b.chapter_id,
            "metadata": json.loads(b.metadata_json or "{}"),
        }
        for b in unit_blocks_orm
    ]

    # adjacency: same revision, neighboring ordinals
    adjacency: List[dict[str, Any]] = []
    if unit_blocks_orm:
        from app.db.models import DocumentBlockModel

        ordinals = {b.ordinal for b in unit_blocks_orm}
        min_o, max_o = min(ordinals), max(ordinals)
        neighbors = (
            await session.execute(
                select(DocumentBlockModel)
                .where(DocumentBlockModel.document_revision_id == rev_id)
                .where(
                    DocumentBlockModel.ordinal >= max(0, min_o - adjacency_count),
                )
                .where(DocumentBlockModel.ordinal <= max_o + adjacency_count)
                .order_by(DocumentBlockModel.ordinal)
            )
        ).scalars().all()
        unit_ids_set = {b.id for b in unit_blocks_orm}
        for b in neighbors:
            if b.id in unit_ids_set:
                continue
            adjacency.append(
                {
                    "id": b.id,
                    "text": b.text,
                    "ordinal": b.ordinal,
                    "chapter_id": b.chapter_id,
                }
            )

    known_concepts: List[str] = []
    if unit.concepts:
        try:
            raw = json.loads(unit.concepts)
            if isinstance(raw, list):
                for c in raw:
                    if isinstance(c, str):
                        known_concepts.append(c)
                    elif isinstance(c, dict) and c.get("name"):
                        known_concepts.append(str(c["name"]))
        except json.JSONDecodeError:
            pass

    book_ctx = f"书名：{(book.title if book else '')}；作者：{(book.author if book and book.author else '')}"
    if book and book.reading_motivation:
        book_ctx += f"；动机：{book.reading_motivation[:80]}"
    # Step2：判空注入全书鸟瞰（degraded / 缺失则不注入）
    if book and getattr(book, "overview_json", None):
        try:
            from app.modules.ai_learning.schemas import BookDeepOverview

            ov = BookDeepOverview.model_validate_json(book.overview_json)
            if not ov.degraded and ov.core_thesis:
                book_ctx += f"；核心论点：{ov.core_thesis[:120]}"
                if ov.main_thread:
                    book_ctx += f"；主线：{ov.main_thread[:160]}"
                # 本章角色
                if unit.chapter_id:
                    for r in ov.chapter_roles or []:
                        if r.chapter_id == unit.chapter_id:
                            book_ctx += f"；本章角色：{r.role}/{r.one_liner[:60]}"
                            break
                # 概念清单名（控制长度）
                names = [c.name for c in (ov.key_concepts or []) if c.name][:20]
                if names:
                    book_ctx += f"；全书概念：{'、'.join(names)}"
        except Exception:
            pass
    chapter_ctx = ""
    if chapter:
        chapter_ctx = f"章节：{chapter.title}"
        if chapter.summary:
            chapter_ctx += f"；摘要：{chapter.summary[:200]}"

    unit_blocks, adjacency, book_ctx, chapter_ctx = _trim_blocks_to_budget(
        unit_blocks, adjacency, book_ctx, chapter_ctx, token_budget
    )
    sent_ids = [b["id"] for b in unit_blocks] + [b["id"] for b in adjacency]

    return AnalysisContext(
        book_id=unit.book_id,
        chapter_id=unit.chapter_id,
        unit_id=unit_id,
        document_revision_id=rev_id,
        book_context_text=book_ctx,
        chapter_context_text=chapter_ctx,
        unit_text=unit.content or "",
        unit_title=unit.title or "",
        unit_blocks=unit_blocks,
        adjacency_blocks=adjacency,
        known_concepts=known_concepts,
        sent_block_ids=sent_ids,
        token_budget=token_budget,
        source_revision_hint=unit_blocks[0].get("id", "") if unit_blocks else "",
    )
