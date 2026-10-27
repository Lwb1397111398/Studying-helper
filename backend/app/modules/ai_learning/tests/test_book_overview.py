"""全书鸟瞰（Book Deep Overview）单元测试

覆盖：
- 规则化 degraded fallback
- LLM 成功路径校验与规范化
- LLM 失败 → degraded 不抛错
- 已有 overview 且 force=False 时复用
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.ai_learning.book_overview import (
    BookDeepOverview,
    build_degraded_overview,
    generate_book_deep_overview,
    _validate_and_normalize,
)
from app.modules.ai_learning.schemas import ChapterRoleItem


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


class _FakeDB:
    def __init__(self, book, chapters, units):
        self.book = book
        self.chapters = chapters
        self.units = units
        self.flushed = False
        self._calls = 0

    async def execute(self, _stmt):
        # 顺序：book → chapters → units
        self._calls += 1
        if self._calls == 1:
            return _FakeResult(self.book)
        if self._calls == 2:
            return _FakeResult(self.chapters)
        return _FakeResult(self.units)

    async def flush(self):
        self.flushed = True


def _book(**kwargs):
    base = dict(
        id="b1",
        title="测试之书",
        author="作者A",
        overview_json=None,
        updated_at=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _chapter(cid, title, order=0, level=0):
    return SimpleNamespace(
        id=cid,
        title=title,
        chapter_number=order + 1,
        order_index=order,
        level=level,
    )


def _unit(uid, chapter_id, title, content="正文内容"):
    return SimpleNamespace(
        id=uid,
        chapter_id=chapter_id,
        title=title,
        content=content,
        order_index=0,
    )


def test_build_degraded_overview_from_titles():
    book = _book()
    chapters = [_chapter("c1", "第一章"), _chapter("c2", "第二章")]
    ov = build_degraded_overview(book, chapters)
    assert ov.degraded is True
    assert "测试之书" in ov.core_thesis
    assert len(ov.chapter_roles) == 2
    assert ov.key_concepts == []
    assert ov.version == "v1"


def test_validate_and_normalize_fills_missing_roles():
    chapters = [_chapter("c1", "一"), _chapter("c2", "二")]
    raw = {
        "core_thesis": "核心论点",
        "main_thread": "主线说明两到三句。",
        "chapter_roles": [
            {"chapter_id": "c1", "role": "立论", "one_liner": "开篇"},
        ],
        "key_concepts": [
            {"name": "概念A", "definition": "定义A", "first_chapter_id": "c1", "aliases": []},
        ],
        "reading_guide": "先读第一章。",
        "degraded": False,
    }
    ov = _validate_and_normalize(raw, chapters)
    assert len(ov.chapter_roles) == 2
    assert {r.chapter_id for r in ov.chapter_roles} == {"c1", "c2"}
    assert ov.key_concepts[0].name == "概念A"


@pytest.mark.asyncio
async def test_generate_uses_llm_and_persists():
    book = _book()
    chapters = [_chapter("c1", "第一章")]
    units = [_unit("u1", "c1", "单元1", "这是一段足够长的正文" * 20)]
    db = _FakeDB(book, chapters, units)

    llm = MagicMock()
    llm.chat_json = AsyncMock(
        return_value={
            "core_thesis": "全书核心",
            "main_thread": "论证主线。",
            "chapter_roles": [
                {"chapter_id": "c1", "role": "立论", "one_liner": "开篇立论"},
            ],
            "key_concepts": [
                {"name": "X", "definition": "Y", "first_chapter_id": "c1", "aliases": []},
            ],
            "reading_guide": "建议先读核心概念。",
            "degraded": False,
        }
    )

    ov = await generate_book_deep_overview(db, "b1", llm_client=llm, force=True)
    assert ov.degraded is False
    assert ov.core_thesis == "全书核心"
    assert db.flushed is True
    assert book.overview_json is not None
    parsed = json.loads(book.overview_json)
    assert parsed["core_thesis"] == "全书核心"
    llm.chat_json.assert_awaited()


@pytest.mark.asyncio
async def test_generate_falls_back_when_llm_fails():
    book = _book()
    chapters = [_chapter("c1", "第一章")]
    units = [_unit("u1", "c1", "单元1")]
    db = _FakeDB(book, chapters, units)

    llm = MagicMock()
    llm.chat_json = AsyncMock(side_effect=RuntimeError("no key"))

    ov = await generate_book_deep_overview(db, "b1", llm_client=llm, force=True)
    assert ov.degraded is True
    assert db.flushed is True
    assert "降级" in (json.loads(book.overview_json)["core_thesis"])


@pytest.mark.asyncio
async def test_generate_reuses_existing_when_not_force():
    existing = BookDeepOverview(
        core_thesis="已有论点",
        main_thread="已有主线",
        chapter_roles=[ChapterRoleItem(chapter_id="c1", role="立论", one_liner="x")],
        key_concepts=[],
        reading_guide="导读",
        degraded=False,
    )
    book = _book(overview_json=existing.model_dump_json())
    db = _FakeDB(book, [], [])
    llm = MagicMock()
    llm.chat_json = AsyncMock()

    ov = await generate_book_deep_overview(db, "b1", llm_client=llm, force=False)
    assert ov.core_thesis == "已有论点"
    llm.chat_json.assert_not_called()
