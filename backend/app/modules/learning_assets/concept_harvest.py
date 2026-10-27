"""全书概念词典收编（Step4）

纯程序 upsert，零 LLM。
- overview 生成后收编 key_concepts
- 单元理解产出后收编 related_concepts（名称级）
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BookConceptModel

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _norm_name(name: str) -> str:
    return (name or "").strip()


def _parse_aliases(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    except Exception:
        pass
    return []


def _dump_aliases(aliases: list[str]) -> str:
    # unique preserve order
    seen = set()
    out = []
    for a in aliases:
        a = a.strip()
        if a and a not in seen:
            seen.add(a)
            out.append(a)
    return json.dumps(out, ensure_ascii=False)


async def harvest_concepts(
    session: AsyncSession,
    book_id: str,
    concepts: Iterable[dict[str, Any]],
    source: str,
    *,
    default_unit_id: Optional[str] = None,
    default_chapter_id: Optional[str] = None,
) -> dict[str, int]:
    """统一收编入口。

    concepts 项字段：
      name (必填), definition?, aliases?, first_unit_id?, first_chapter_id?

    合并规则：
    - 精确 name 或 aliases 命中 → 补充 aliases / first_*（先到先得，不覆盖已有 definition）
    - 未命中 → 新增
    """
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    rows = list(
        (
            await session.execute(
                select(BookConceptModel).where(BookConceptModel.book_id == book_id)
            )
        ).scalars().all()
    )
    by_name = {r.name: r for r in rows}
    alias_to_name: dict[str, str] = {}
    for r in rows:
        alias_to_name[r.name] = r.name
        for a in _parse_aliases(r.aliases):
            alias_to_name[a] = r.name

    for raw in concepts:
        if not isinstance(raw, dict):
            stats["skipped"] += 1
            continue
        name = _norm_name(str(raw.get("name") or ""))
        if not name:
            stats["skipped"] += 1
            continue
        definition = raw.get("definition")
        if definition is not None:
            definition = str(definition).strip() or None
        incoming_aliases = raw.get("aliases") or []
        if not isinstance(incoming_aliases, list):
            incoming_aliases = []
        incoming_aliases = [str(a).strip() for a in incoming_aliases if str(a).strip()]
        first_unit = raw.get("first_unit_id") or default_unit_id
        first_chapter = raw.get("first_chapter_id") or default_chapter_id

        hit_name = None
        if name in by_name:
            hit_name = name
        elif name in alias_to_name:
            hit_name = alias_to_name[name]
        else:
            for a in incoming_aliases:
                if a in alias_to_name:
                    hit_name = alias_to_name[a]
                    break

        if hit_name is None:
            row = BookConceptModel(
                id=str(uuid4()),
                book_id=book_id,
                name=name,
                definition=definition,
                aliases=_dump_aliases(incoming_aliases),
                first_unit_id=first_unit,
                first_chapter_id=first_chapter,
                source=source,
                created_at=_utc_now(),
                updated_at=_utc_now(),
            )
            session.add(row)
            by_name[name] = row
            alias_to_name[name] = name
            for a in incoming_aliases:
                alias_to_name[a] = name
            stats["inserted"] += 1
            continue

        row = by_name[hit_name]
        changed = False
        # definition: 先到先得，仅在空时写入
        if definition and not (row.definition or "").strip():
            row.definition = definition
            changed = True
        # aliases 合并
        existing = _parse_aliases(row.aliases)
        merged = existing[:]
        # 若命中的是别名路径且 name 不同于 row.name，把 name 也并入 aliases
        if name != row.name and name not in merged:
            merged.append(name)
        for a in incoming_aliases:
            if a != row.name and a not in merged:
                merged.append(a)
        if merged != existing:
            row.aliases = _dump_aliases(merged)
            changed = True
            for a in merged:
                alias_to_name[a] = row.name
        if first_unit and not row.first_unit_id:
            row.first_unit_id = first_unit
            changed = True
        if first_chapter and not row.first_chapter_id:
            row.first_chapter_id = first_chapter
            changed = True
        if changed:
            row.updated_at = _utc_now()
            stats["updated"] += 1
        else:
            stats["skipped"] += 1

    await session.flush()
    logger.info("harvest_concepts book=%s source=%s stats=%s", book_id, source, stats)
    return stats


async def harvest_from_overview(
    session: AsyncSession,
    book_id: str,
    overview: Any,
) -> dict[str, int]:
    """从 BookDeepOverview / dict 收编 key_concepts。"""
    concepts = []
    key_concepts = getattr(overview, "key_concepts", None)
    if key_concepts is None and isinstance(overview, dict):
        key_concepts = overview.get("key_concepts") or []
    for c in key_concepts or []:
        if hasattr(c, "model_dump"):
            d = c.model_dump()
        elif isinstance(c, dict):
            d = c
        else:
            continue
        concepts.append(
            {
                "name": d.get("name"),
                "definition": d.get("definition"),
                "aliases": d.get("aliases") or [],
                "first_chapter_id": d.get("first_chapter_id") or None,
            }
        )
    return await harvest_concepts(session, book_id, concepts, source="overview")


async def harvest_from_understanding(
    session: AsyncSession,
    book_id: str,
    unit_id: str,
    chapter_id: Optional[str],
    claims: list[dict[str, Any]] | list[Any],
) -> dict[str, int]:
    """从单元 claims.related_concepts 收编名称（无定义也可入库，definition 空）。"""
    concepts = []
    seen = set()
    for c in claims or []:
        if hasattr(c, "related_concepts"):
            related = c.related_concepts or []
        elif isinstance(c, dict):
            related = c.get("related_concepts") or []
        else:
            continue
        for name in related:
            n = _norm_name(str(name))
            if not n or n in seen:
                continue
            seen.add(n)
            concepts.append(
                {
                    "name": n,
                    "definition": None,
                    "aliases": [],
                    "first_unit_id": unit_id,
                    "first_chapter_id": chapter_id,
                }
            )
    if not concepts:
        return {"inserted": 0, "updated": 0, "skipped": 0}
    return await harvest_concepts(
        session,
        book_id,
        concepts,
        source="unit_harvest",
        default_unit_id=unit_id,
        default_chapter_id=chapter_id,
    )


async def list_book_concepts(session: AsyncSession, book_id: str) -> list[BookConceptModel]:
    rows = (
        await session.execute(
            select(BookConceptModel)
            .where(BookConceptModel.book_id == book_id)
            .order_by(BookConceptModel.name)
        )
    ).scalars().all()
    return list(rows)
