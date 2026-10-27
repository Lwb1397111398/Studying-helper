"""大单元 map-reduce 精读（Step7）。

目的：解决超长单元（>8000 字）导致的 claims 截断和 role 误分。
产物 schema 与现有 v2 完全一致（下游零改动）。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any



logger = logging.getLogger(__name__)

CONTENT_TRUNCATE = 8000  # 沿用现有阈值，抽成常量
MAPREDUCE_CHUNK = 6000  # 留 prompt 余量

MAP_PROMPT = """你是一个严格提取 claims 的工具，只从给定文本提取命题。
文本：
{chunk}
章节摘要：
{chapter_summary}

只输出 JSON：
{{
  "claims": [
    {{"text": "命题原文", "mastery_check": "能…的可观察标准"}}
  ],
  "key_points": ["要点"],
  "related_concepts": ["概念名"]
}}
"""

REDUCE_PROMPT = """你是 claims 归并与定调专家。
章节摘要：
{chapter_summary}
各分段提取结果：
{chunks_json}

合并去重后输出 JSON：
{{
  "claims": [
    {{
      "text": "...",
      "role_in_book": "core_thesis_support" | "key_mechanism" | "supporting_detail" | "example" | "tangential",
      "mastery_check": "能..."
    }}
  ],
  "unit_gist": "单元角色一句话",
  "key_points": ["要点"],
  "related_concepts": ["概念"]
}}
"""


def chunk_unit_text(text: str, chunk_size: int = MAPREDUCE_CHUNK) -> list[str]:
    """按标题/段落边界切分，目标 ≤ chunk_size。"""
    text = text or ""
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        window = text[start:end]
        cut = -1
        for m in re.finditer(r"(?m)^#+\s+.*$", window):
            if m.start() > chunk_size // 2:
                cut = m.start()
        if cut == -1:
            for m in re.finditer(r"\n\s*\n", window):
                if m.end() > chunk_size // 2:
                    cut = m.end()
        if cut > 0:
            end = start + cut
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


async def _map_chunk_llm(chunk: str, chapter_summary: str) -> dict[str, Any] | None:
    """单个 chunk LLM 提取；失败返回 None。"""
    from app.common.llm_client import LLMClient
    try:
        client = LLMClient()
        if not getattr(client, "api_key", ""):
            return None
        prompt = MAP_PROMPT.format(chunk=chunk[:MAPREDUCE_CHUNK], chapter_summary=chapter_summary)
        resp = await client.chat_json(messages=[{"role": "user", "content": prompt}], temperature=0.2)
        data = resp if isinstance(resp, dict) else json.loads(resp)
        return {
            "claims": data.get("claims") or [],
            "key_points": data.get("key_points") or [],
            "related_concepts": data.get("related_concepts") or [],
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("map chunk fail: %s", exc)
        return None


def _dedup_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for c in claims:
        t = re.sub(r"\s+", "", (c.get("text") or "")).lower()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(c)
    return out


async def _reduce_llm(chunk_results: list[dict[str, Any]], chapter_summary: str) -> dict[str, Any] | None:
    """reduce：合并 + 全局 role 判断；失败返回 None（调用方程序兜底）。"""
    from app.common.llm_client import LLMClient
    try:
        client = LLMClient()
        if not getattr(client, "api_key", ""):
            return None
        chunks_json = json.dumps(chunk_results, ensure_ascii=False)[:6000]
        prompt = REDUCE_PROMPT.format(chapter_summary=chapter_summary, chunks_json=chunks_json)
        resp = await client.chat_json(messages=[{"role": "user", "content": prompt}], temperature=0.2)
        data = resp if isinstance(resp, dict) else json.loads(resp)
        return data
    except Exception as exc:  # noqa: BLE001
        logger.warning("reduce fail: %s", exc)
        return None


def _reduce_fallback(chunk_results: list[dict[str, Any]]) -> dict[str, Any]:
    """程序兜底：合并 claims，默认 supporting_detail，从最强 claim 生成 1 条 mastery_check。"""
    merged: list[dict[str, Any]] = []
    kps: list[str] = []
    concepts: list[str] = []
    for r in chunk_results:
        merged.extend(r.get("claims") or [])
        kps.extend(r.get("key_points") or [])
        concepts.extend(r.get("related_concepts") or [])
    merged = _dedup_claims(merged)
    claims_out = []
    for c in merged:
        claims_out.append(
            {
                "text": c.get("text") or "",
                "role_in_book": c.get("role_in_book") or "supporting_detail",
                "mastery_check": c.get("mastery_check") or f"能复述：{(c.get('text') or '')[:30]}",
            }
        )
    return {
        "claims": claims_out,
        "unit_gist": "（程序合并）",
        "key_points": list(dict.fromkeys(kps)),
        "related_concepts": list(dict.fromkeys(concepts)),
    }


async def run_understanding_mapreduce(
    unit_text: str,
    *,
    chapter_summary: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """大单元 map-reduce 入口。

    返回 (claims, meta)。meta 含 unit_gist/key_points/related_concepts/partial。
    ≤ CONTENT_TRUNCATE 时返回 ([], {})，表示不需要 map-reduce（走现有单次路径）。
    """
    if len(unit_text or "") <= CONTENT_TRUNCATE:
        return [], {}
    chunks = chunk_unit_text(unit_text)
    results: list[dict[str, Any]] = []
    failed = 0
    for ch in chunks:
        r = await _map_chunk_llm(ch, chapter_summary)
        if r is None:
            failed += 1
        else:
            results.append(r)
    partial = failed > 0
    if not results:
        # 全部失败：让上游走现有 rule-based fallback
        return [], {"partial": True, "mapreduce_failed": True}
    reduced = await _reduce_llm(results, chapter_summary)
    if reduced is None:
        reduced = _reduce_fallback(results)
    claims = reduced.get("claims") or []
    meta = {
        "unit_gist": reduced.get("unit_gist") or "",
        "key_points": reduced.get("key_points") or [],
        "related_concepts": reduced.get("related_concepts") or [],
        "partial": partial,
    }
    return claims, meta
