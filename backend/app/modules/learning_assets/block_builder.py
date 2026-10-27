"""从 KnowledgeUnit 回填 Document / DocumentRevision / DocumentBlock。

事实来源：数据库 Chapter 无 content 列；持久化原文在 knowledge_units.content。
不依赖解析期 page_map（未持久化）。
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BookModel,
    DocumentBlockModel,
    DocumentModel,
    DocumentRevisionModel,
    KnowledgeUnitModel,
)

logger = logging.getLogger(__name__)

PARSER_VERSION = "legacy-unit-backfill-v1"
NORMALIZATION_VERSION = "text-normalizer-v1"


def _sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _units_source_hash(units: list[KnowledgeUnitModel]) -> str:
    parts = []
    for u in sorted(units, key=lambda x: (x.order_index, x.id)):
        parts.append(f"{u.id}|{u.order_index}|{u.content or ''}")
    return _sha256_text("\n".join(parts))


async def ensure_document_blocks_for_book(
    session: AsyncSession,
    book_id: str,
    *,
    force_new_revision: bool = False,
) -> str:
    """确保书本有 active DocumentRevision 与 blocks；幂等返回 revision_id。

    回填策略：每个 KnowledgeUnit 对应至少一个 paragraph block，
    metadata 记录 unit_id 与 char_offset（单元内坐标系提示，非全书权威）。
    """
    book = (
        await session.execute(select(BookModel).where(BookModel.id == book_id))
    ).scalar_one_or_none()
    if book is None:
        raise ValueError(f"book not found: {book_id}")

    units = (
        await session.execute(
            select(KnowledgeUnitModel)
            .where(KnowledgeUnitModel.book_id == book_id)
            .order_by(KnowledgeUnitModel.order_index, KnowledgeUnitModel.id)
        )
    ).scalars().all()
    if not units:
        raise ValueError(f"no knowledge units for book: {book_id}")

    content_hash = _units_source_hash(list(units))

    doc = (
        await session.execute(
            select(DocumentModel).where(
                DocumentModel.book_id == book_id,
                DocumentModel.status == "active",
            )
        )
    ).scalar_one_or_none()

    if doc is None:
        doc = DocumentModel(
            id=str(uuid4()),
            book_id=book_id,
            source_type=(book.file_type or "txt").lower(),
            source_uri=book.file_path or "",
            status="active",
        )
        session.add(doc)
        await session.flush()

    active_rev: Optional[DocumentRevisionModel] = (
        await session.execute(
            select(DocumentRevisionModel).where(
                DocumentRevisionModel.document_id == doc.id,
                DocumentRevisionModel.status == "active",
            )
        )
    ).scalar_one_or_none()

    if (
        active_rev is not None
        and not force_new_revision
        and active_rev.source_hash == content_hash
    ):
        return active_rev.id

    # supersede old
    if active_rev is not None:
        active_rev.status = "superseded"
        await session.flush()

    next_no = 1
    last = (
        await session.execute(
            select(DocumentRevisionModel)
            .where(DocumentRevisionModel.document_id == doc.id)
            .order_by(DocumentRevisionModel.revision_no.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last is not None:
        next_no = int(last.revision_no) + 1

    rev = DocumentRevisionModel(
        id=str(uuid4()),
        document_id=doc.id,
        revision_no=next_no,
        source_hash=content_hash,
        parser_version=PARSER_VERSION,
        normalization_version=NORMALIZATION_VERSION,
        status="processing",
    )
    session.add(rev)
    await session.flush()

    ordinal = 0
    for unit in units:
        text = unit.content or ""
        if not text.strip():
            continue
        meta = {
            "unit_id": unit.id,
            "unit_title": unit.title,
            "char_offset_start": unit.char_offset_start,
            "char_offset_end": unit.char_offset_end,
            "backfill": "knowledge_unit_content",
        }
        session.add(
            DocumentBlockModel(
                id=f"blk_{rev.id[:8]}_{ordinal:05d}",
                document_revision_id=rev.id,
                chapter_id=unit.chapter_id,
                parent_block_id=None,
                block_type="paragraph",
                ordinal=ordinal,
                text=text,
                text_hash=_sha256_text(text),
                page_index=None,
                page_label=None,
                metadata_json=json.dumps(meta, ensure_ascii=False),
            )
        )
        ordinal += 1

    if ordinal == 0:
        rev.status = "failed"
        await session.flush()
        raise ValueError(f"all units empty for book: {book_id}")

    rev.status = "active"
    await session.flush()
    logger.info(
        "document blocks backfilled book=%s revision=%s blocks=%s",
        book_id,
        rev.id,
        ordinal,
    )
    return rev.id


async def get_blocks_for_unit(
    session: AsyncSession,
    unit_id: str,
    document_revision_id: str | None = None,
) -> list[DocumentBlockModel]:
    """按 metadata.unit_id 查找块；revision 缺省时用该书 active revision。"""
    unit = (
        await session.execute(
            select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
        )
    ).scalar_one_or_none()
    if unit is None:
        return []

    rev_id = document_revision_id
    if rev_id is None:
        doc = (
            await session.execute(
                select(DocumentModel).where(
                    DocumentModel.book_id == unit.book_id,
                    DocumentModel.status == "active",
                )
            )
        ).scalar_one_or_none()
        if doc is None:
            return []
        rev = (
            await session.execute(
                select(DocumentRevisionModel).where(
                    DocumentRevisionModel.document_id == doc.id,
                    DocumentRevisionModel.status == "active",
                )
            )
        ).scalar_one_or_none()
        if rev is None:
            return []
        rev_id = rev.id

    blocks = (
        await session.execute(
            select(DocumentBlockModel)
            .where(DocumentBlockModel.document_revision_id == rev_id)
            .order_by(DocumentBlockModel.ordinal)
        )
    ).scalars().all()
    matched = []
    for b in blocks:
        try:
            meta = json.loads(b.metadata_json or "{}")
        except json.JSONDecodeError:
            meta = {}
        if meta.get("unit_id") == unit_id:
            matched.append(b)
    return matched
