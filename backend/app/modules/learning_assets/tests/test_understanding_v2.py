"""Step2 单元精读理解阶段测试。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.learning_assets.understanding import (
    UnderstandingResult,
    content_hash,
    to_legacy_view,
    validate_understanding_raw,
    build_understanding_prompt,
    run_understanding,
    _persist_understanding_only,
)


def _valid_raw(**overrides):
    raw = {
        "unit_gist": "本单元支撑全书核心论点中的关键机制。",
        "claims": [
            {
                "text": "反向传播利用链式法则高效计算梯度",
                "type": "principle",
                "role_in_book": "key_mechanism",
                "mastery_check": "能用自己的话解释反向传播如何用链式法则算梯度",
                "related_concepts": ["反向传播", "梯度"],
            },
            {
                "text": "深层网络容易出现梯度消失",
                "type": "fact",
                "role_in_book": "core_thesis_support",
                "mastery_check": "能说明为何层数增加会加剧梯度消失",
                "related_concepts": ["梯度消失"],
            },
            {
                "text": "某教材插图仅作示意",
                "type": "fact",
                "role_in_book": "tangential",
                "mastery_check": "能指出插图只是示意、不是证明",
                "related_concepts": [],
            },
            {
                "text": "可用残差连接缓解梯度问题",
                "type": "procedure",
                "role_in_book": "supporting_detail",
                "mastery_check": "能举出一个用残差连接的网络例子",
                "related_concepts": ["残差连接"],
            },
        ],
        "objectives": [
            {
                "text": "解释反向传播与梯度消失的关系",
                "cognitive_level": "understand",
                "covers_claims": [0, 1],
            },
            {
                "text": "能提出一种缓解梯度问题的做法",
                "cognitive_level": "apply",
                "covers_claims": [3],
            },
        ],
        "prerequisites": ["链式法则", "导数"],
    }
    raw.update(overrides)
    return raw


def test_content_hash_stable():
    assert content_hash("abc") == content_hash("abc")
    assert len(content_hash("abc")) == 16
    assert content_hash("a") != content_hash("b")


def test_validate_ok():
    ok, err, norm = validate_understanding_raw(_valid_raw())
    assert ok, err
    assert len(norm["claims"]) == 4
    assert norm["unit_gist"]


def test_validate_rejects_vague_mastery():
    raw = _valid_raw()
    raw["claims"][0]["mastery_check"] = "理解反向传播"
    ok, err, _ = validate_understanding_raw(raw)
    assert not ok
    assert "mastery_check" in err


def test_validate_rejects_uncovered_non_tangential():
    raw = _valid_raw()
    raw["objectives"] = [
        {"text": "只覆盖第一条", "cognitive_level": "remember", "covers_claims": [0]},
    ]
    ok, err, _ = validate_understanding_raw(raw)
    assert not ok
    assert "not covered" in err


def test_validate_rejects_bad_enum():
    raw = _valid_raw()
    raw["claims"][0]["type"] = "nonsense"
    ok, err, _ = validate_understanding_raw(raw)
    assert not ok
    assert "type" in err


def test_to_legacy_view_strips_v2_fields():
    result = UnderstandingResult(
        ok=True,
        unit_id="u1",
        content_hash="abcd",
        unit_gist="角色一句话",
        claims=[
            {
                "text": "命题A",
                "type": "principle",
                "role_in_book": "key_mechanism",
                "mastery_check": "能解释A为什么成立",
                "related_concepts": ["A"],
            },
            {
                "text": "命题B",
                "type": "fact",
                "role_in_book": "supporting_detail",
                "mastery_check": "能复述B的条件",
                "related_concepts": [],
            },
            {
                "text": "命题C",
                "type": "definition",
                "role_in_book": "example",
                "mastery_check": "能举出C的例子",
                "related_concepts": [],
            },
        ],
        objectives=[
            {
                "text": "目标1",
                "cognitive_level": "understand",
                "covers_claims": [0, 1, 2],
            }
        ],
    )
    legacy = to_legacy_view(result)
    assert "role_in_book" not in legacy["claims"][0]
    assert "mastery_check" not in legacy["claims"][0]
    assert legacy["claims"][0]["text"] == "命题A"
    assert legacy["central_question"] == "角色一句话"
    assert legacy["objectives"][0]["description"] == "目标1"
    assert "ability" in legacy["objectives"][0]


def test_prompt_includes_overview_when_present():
    prompt = build_understanding_prompt(
        unit_title="反向传播",
        unit_content="正文" * 100,
        overview_block="## 全书鸟瞰\n核心论点：深度学习靠多层表示",
        extra_context="章节标题：第3章",
    )
    assert "全书鸟瞰" in prompt
    assert "mastery_check" in prompt
    assert "covers_claims" in prompt


def test_prompt_truncates_long_content():
    long = "字" * 20000
    prompt = build_understanding_prompt(
        unit_title="t",
        unit_content=long,
        overview_block="",
    )
    # 正文区被截断，不会把 20000 字全塞进 prompt
    assert long not in prompt
    assert "字" * 100 in prompt


@pytest.mark.asyncio
async def test_run_understanding_no_llm_fails_soft():
    unit = SimpleNamespace(
        id="u1",
        book_id="b1",
        chapter_id="c1",
        title="单元",
        content="足够长的正文内容用于哈希",
        concepts=None,
    )
    book = SimpleNamespace(id="b1", overview_json=None, title="B", author=None)
    chapter = SimpleNamespace(id="c1", title="章", summary=None)

    class FakeDB:
        def __init__(self):
            self._n = 0

        async def execute(self, _stmt):
            self._n += 1

            class R:
                def __init__(self, v):
                    self._v = v

                def scalar_one_or_none(self):
                    return self._v

                def scalars(self):
                    return self

                def all(self):
                    return self._v if isinstance(self._v, list) else []

            # force=True: unit -> book -> chapter -> (no llm) return
            mapping = {1: unit, 2: book, 3: chapter}
            return R(mapping.get(self._n))

        async def flush(self):
            pass

    res = await run_understanding(FakeDB(), "u1", llm_client=None, force=True)
    assert res.ok is False
    assert res.error


@pytest.mark.asyncio
async def test_run_understanding_llm_success_and_idempotent_skip(monkeypatch):
    unit = SimpleNamespace(
        id="u1",
        book_id="b1",
        chapter_id="c1",
        title="反向传播",
        content="链式法则与梯度计算。" * 20,
        concepts=None,
    )
    book = SimpleNamespace(id="b1", overview_json=None, title="DL", author=None)
    chapter = SimpleNamespace(id="c1", title="第3章", summary=None)

    stored = {"payload": None, "asset": None}

    class FakeDB:
        def __init__(self):
            self.phase = "first"
            self.added = []
            self._q = 0

        async def execute(self, stmt):
            self._q += 1

            class R:
                def __init__(self, v):
                    self._v = v

                def scalar_one_or_none(self):
                    if isinstance(self._v, list):
                        return self._v[0] if self._v else None
                    return self._v

                def scalars(self):
                    return self

                def all(self):
                    return self._v if isinstance(self._v, list) else []

            if self.phase == "first":
                # unit, book, chapter, last version, prev actives
                order = [unit, book, chapter, None, []]
                idx = min(self._q - 1, len(order) - 1)
                # detect by call count within first phase carefully
                if self._q == 1:
                    return R(unit)
                if self._q == 2:
                    return R(book)
                if self._q == 3:
                    return R(chapter)
                if self._q == 4:
                    return R(None)  # last version
                if self._q == 5:
                    return R([])  # prev actives
                return R(None)
            # second phase force=False: unit, existing assets list
            if self._q == 1:
                return R(unit)
            if self._q == 2:
                return R([stored["asset"]] if stored["asset"] is not None else [])
            return R(None)

        def add(self, obj):
            self.added.append(obj)
            if hasattr(obj, "payload_json"):
                stored["payload"] = obj.payload_json
                stored["asset"] = obj

        async def flush(self):
            pass

    llm = MagicMock()
    llm.chat_json = AsyncMock(return_value=_valid_raw())

    db = FakeDB()
    res1 = await run_understanding(db, "u1", llm_client=llm, force=True)
    assert res1.ok is True
    assert res1.unit_gist
    assert len(res1.claims) >= 3
    assert db.added, "should persist asset"
    assert llm.chat_json.await_count >= 1

    # 幂等
    db2 = FakeDB()
    db2.phase = "second"
    db2._q = 0
    calls_before = llm.chat_json.await_count
    res2 = await run_understanding(db2, "u1", llm_client=llm, force=False)
    assert res2.ok is True
    assert res2.skipped is True
    assert llm.chat_json.await_count == calls_before


@pytest.mark.asyncio
async def test_pipeline_stage2_uses_legacy_adapter():
    """完整管线：stage2 收到的 understanding 不应含 v2 字段。"""
    from app.modules.learning_assets.pipeline import default_rule_stage2
    from app.modules.learning_assets.understanding import to_legacy_view

    captured = {}

    def stage1(_ctx):
        return UnderstandingResult(
            ok=True,
            unit_id="u1",
            content_hash="h",
            unit_gist="gist",
            claims=[
                {
                    "text": f"命题{i}",
                    "type": "fact",
                    "role_in_book": "supporting_detail" if i < 3 else "tangential",
                    "mastery_check": f"能用自己的话说明命题{i}",
                    "related_concepts": [],
                }
                for i in range(3)
            ],
            objectives=[
                {
                    "text": "目标",
                    "cognitive_level": "understand",
                    "covers_claims": [0, 1, 2],
                }
            ],
        ).to_stage1_dict()

    def stage2(understanding, ctx):
        captured["understanding"] = understanding
        return default_rule_stage2(understanding, ctx)

    v2 = stage1({})
    legacy = to_legacy_view(v2)
    stage2(legacy, {"unit_text": "x"})
    assert "role_in_book" not in captured["understanding"]["claims"][0]
    assert "mastery_check" not in captured["understanding"]["claims"][0]
