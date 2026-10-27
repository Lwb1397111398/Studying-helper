"""单元深度精读理解阶段（Step2 v2）。

职责：
- 用全书鸟瞰 + 章节上下文，把单元正文提炼成 claims / objectives（v2 schema）；
- 每条 claim 带 role_in_book 与可观察的 mastery_check；
- 产出写入 UnitLearningAsset（understanding_only，readiness=understanding_ready）；
- 给旧下游提供 to_legacy_view 适配器（剥掉 v2 专属字段）；
- 无 LLM / 校验失败时软失败，让调用方走既有 rule-based 兜底。

超长单元（> CONTENT_TRUNCATE）走 mapreduce.py 的 map-reduce 路径。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BookModel,
    ChapterModel,
    KnowledgeUnitModel,
    UnitLearningAssetModel,
)
from app.modules.learning_assets.models_domain import UnitLearningAssetPayload

logger = logging.getLogger(__name__)

# 正文进 prompt 的截断阈值；超过则走 map-reduce
CONTENT_TRUNCATE = 8000

CLAIM_TYPES = {"fact", "definition", "principle", "procedure", "example"}
ROLE_IN_BOOK = {
    "core_thesis_support",
    "key_mechanism",
    "supporting_detail",
    "example",
    "tangential",
}
COGNITIVE_LEVELS = {"remember", "understand", "apply", "analyze"}
VAGUE_PREFIXES = ("理解", "掌握", "知道", "明白", "了解", "熟悉")

# cognitive_level → 旧 ability 枚举
COG_TO_ABILITY = {
    "remember": "recall",
    "understand": "explain",
    "apply": "apply",
    "analyze": "differentiate",
}

UNDERSTANDING_PROMPT = """你是深度精读专家。请把下面这个学习单元读透，产出可教学、可检验的理解结果。
{overview_section}单元标题：{unit_title}
{extra_section}单元正文（可能已截断）：
{unit_content}

只输出 JSON，不要解释：
{{
  "unit_gist": "本单元在全书中的角色，一句话",
  "claims": [
    {{
      "text": "命题级表述（不是话题名）",
      "type": "fact|definition|principle|procedure|example",
      "role_in_book": "core_thesis_support|key_mechanism|supporting_detail|example|tangential",
      "mastery_check": "以“能”开头的可观察检验标准",
      "related_concepts": ["概念名"]
    }}
  ],
  "objectives": [
    {{
      "text": "学习目标",
      "cognitive_level": "remember|understand|apply|analyze",
      "covers_claims": [0, 1]
    }}
  ],
  "prerequisites": ["前置概念"]
}}

硬性要求：
1. mastery_check 必须是可观察行为，禁止“理解/掌握/知道”这类空话。
2. 除 role_in_book=tangential 外，每条 claim 都要被至少一个 objective 的 covers_claims 覆盖。
3. claims 控制在 3-8 条，宁少勿滥；covers_claims 用 claims 数组下标。
"""

@dataclass
class UnderstandingResult:
    """理解阶段结果（可直接当 stage1 输出）。"""

    ok: bool
    unit_id: str = ""
    content_hash: str = ""
    unit_gist: str = ""
    claims: list[dict[str, Any]] = field(default_factory=list)
    objectives: list[dict[str, Any]] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    overview_injected: bool = False
    partial: bool = False
    skipped: bool = False
    asset_id: Optional[str] = None
    error: str = ""

    def to_stage1_dict(self) -> dict[str, Any]:
        """转成 pipeline stage1 约定的 dict（v2 完整字段）。"""
        claims: list[dict[str, Any]] = []
        for i, c in enumerate(self.claims):
            claims.append(
                {
                    "id": c.get("id") or f"c_{i + 1}",
                    "claim_type": c.get("type") or c.get("claim_type") or "fact",
                    "importance": (
                        "supporting"
                        if (c.get("role_in_book") or "") == "tangential"
                        else "required"
                    ),
                    "text": c.get("text") or "",
                    "role_in_book": c.get("role_in_book") or "supporting_detail",
                    "mastery_check": c.get("mastery_check") or "",
                    "related_concepts": list(c.get("related_concepts") or []),
                    "evidence": list(c.get("evidence") or []),
                }
            )
        objectives: list[dict[str, Any]] = []
        for i, o in enumerate(self.objectives):
            cog = o.get("cognitive_level") or "understand"
            covers = [
                int(x)
                for x in (o.get("covers_claims") or [])
                if isinstance(x, int) or (isinstance(x, str) and x.isdigit())
            ]
            source_ids = [
                claims[ci]["id"] for ci in covers if 0 <= ci < len(claims)
            ]
            objectives.append(
                {
                    "id": o.get("id") or f"o_{i + 1}",
                    "description": o.get("description") or o.get("text") or "",
                    "ability": COG_TO_ABILITY.get(cog, "explain"),
                    "importance": "required",
                    "cognitive_level": cog,
                    "covers_claims": covers,
                    "source_claim_ids": source_ids,
                }
            )
        return {
            "understanding_version": "v2",
            "unit_type": "concept",
            "unit_gist": self.unit_gist,
            "central_question": self.unit_gist,
            "content_hash": self.content_hash,
            "overview_injected": self.overview_injected,
            "partial": self.partial,
            "claims": claims,
            "objectives": objectives,
            "prerequisites": list(self.prerequisites),
        }


def content_hash(text: str) -> str:
    """单元正文指纹（16 位十六进制，用于幂等判断）。"""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def precompute_enabled() -> bool:
    """是否在 AI 学习后预生成单元理解（默认开，可用环境变量关掉）。"""
    raw = (os.environ.get("UNDERSTANDING_PRECOMPUTE") or "").strip().lower()
    if raw in ("0", "false", "off", "no"):
        return False
    return True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_vague(text: str) -> bool:
    """mastery_check 是否是空话。"""
    t = (text or "").strip()
    if len(t) < 6:
        return True
    body = t[1:].strip() if t.startswith("能") else t
    return body.startswith(VAGUE_PREFIXES) and len(body) <= 12


def build_understanding_prompt(
    *,
    unit_title: str,
    unit_content: str,
    overview_block: str = "",
    extra_context: str = "",
) -> str:
    """拼理解阶段 prompt；正文按 CONTENT_TRUNCATE 截断。"""
    text = unit_content or ""
    if len(text) > CONTENT_TRUNCATE:
        text = text[:CONTENT_TRUNCATE] + "\n……（正文过长已截断）"
    overview_section = f"{overview_block.strip()}\n\n" if (overview_block or "").strip() else ""
    extra_section = f"{extra_context.strip()}\n" if (extra_context or "").strip() else ""
    return UNDERSTANDING_PROMPT.format(
        overview_section=overview_section,
        unit_title=unit_title or "（无标题）",
        extra_section=extra_section,
        unit_content=text,
    )


def build_overview_block(book: Any) -> tuple[str, bool]:
    """从 books.overview_json 拼全书鸟瞰片段；返回 (片段, 是否注入)。"""
    raw = getattr(book, "overview_json", None)
    if not raw:
        return "", False
    try:
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:  # noqa: BLE001
        return "", False
    if not isinstance(data, dict):
        return "", False
    lines = ["## 全书鸟瞰"]
    if data.get("core_thesis"):
        lines.append(f"核心论点：{data['core_thesis']}")
    if data.get("main_thread"):
        lines.append(f"主线：{data['main_thread']}")
    names = [
        str(c.get("name"))
        for c in (data.get("key_concepts") or [])
        if isinstance(c, dict) and c.get("name")
    ]
    if names:
        lines.append("关键概念：" + "、".join(names[:12]))
    if len(lines) == 1:
        return "", False
    return "\n".join(lines), True


def validate_understanding_raw(raw: Any) -> tuple[bool, str, dict[str, Any]]:
    """校验并规范化 LLM 原始产出。

    返回 (ok, error, normalized)。normalized 含 unit_gist/claims/objectives/prerequisites。
    """
    if not isinstance(raw, dict):
        return False, "raw is not a dict", {}

    gist = str(raw.get("unit_gist") or "").strip()
    if not gist:
        return False, "unit_gist is empty", {}

    raw_claims = raw.get("claims")
    if not isinstance(raw_claims, list) or not raw_claims:
        return False, "claims is empty", {}

    claims: list[dict[str, Any]] = []
    for i, c in enumerate(raw_claims):
        if not isinstance(c, dict):
            return False, f"claim {i} is not an object", {}
        text = str(c.get("text") or "").strip()
        if not text:
            return False, f"claim {i} text is empty", {}
        ctype = str(c.get("type") or c.get("claim_type") or "fact").strip()
        if ctype not in CLAIM_TYPES:
            return False, f"claim {i} type invalid: {ctype}", {}
        role = str(c.get("role_in_book") or "supporting_detail").strip()
        if role not in ROLE_IN_BOOK:
            return False, f"claim {i} role_in_book invalid: {role}", {}
        mastery = str(c.get("mastery_check") or "").strip()
        if _is_vague(mastery):
            return False, f"claim {i} mastery_check is vague: {mastery!r}", {}
        related = [
            str(x).strip()
            for x in (c.get("related_concepts") or [])
            if str(x).strip()
        ]
        claims.append(
            {
                "id": c.get("id") or f"c_{i + 1}",
                "text": text,
                "type": ctype,
                "role_in_book": role,
                "mastery_check": mastery,
                "related_concepts": related,
            }
        )

    raw_objectives = raw.get("objectives")
    if not isinstance(raw_objectives, list) or not raw_objectives:
        return False, "objectives is empty", {}

    objectives: list[dict[str, Any]] = []
    covered: set[int] = set()
    for i, o in enumerate(raw_objectives):
        if not isinstance(o, dict):
            return False, f"objective {i} is not an object", {}
        desc = str(o.get("text") or o.get("description") or "").strip()
        if len(desc) < 4:
            return False, f"objective {i} text too short", {}
        cog = str(o.get("cognitive_level") or "understand").strip()
        if cog not in COGNITIVE_LEVELS:
            return False, f"objective {i} cognitive_level invalid: {cog}", {}
        covers: list[int] = []
        for x in o.get("covers_claims") or []:
            try:
                idx = int(x)
            except (TypeError, ValueError):
                return False, f"objective {i} covers_claims not int: {x!r}", {}
            if not (0 <= idx < len(claims)):
                return False, f"objective {i} covers_claims out of range: {idx}", {}
            covers.append(idx)
            covered.add(idx)
        objectives.append(
            {
                "id": o.get("id") or f"o_{i + 1}",
                "text": desc,
                "cognitive_level": cog,
                "covers_claims": covers,
            }
        )

    for i, c in enumerate(claims):
        if c["role_in_book"] == "tangential":
            continue
        if i not in covered:
            return False, f"claim {i} not covered by any objective", {}

    prerequisites = [
        str(x).strip() for x in (raw.get("prerequisites") or []) if str(x).strip()
    ]
    return True, "", {
        "unit_gist": gist,
        "claims": claims,
        "objectives": objectives,
        "prerequisites": prerequisites,
    }


def to_legacy_view(understanding: Any) -> dict[str, Any]:
    """把 v2 理解产物降级成旧下游能吃的形状（剥掉 v2 专属字段）。"""
    if isinstance(understanding, UnderstandingResult):
        data = understanding.to_stage1_dict()
    elif isinstance(understanding, dict):
        data = dict(understanding)
    else:
        return {}

    legacy_claims = []
    for i, c in enumerate(data.get("claims") or []):
        legacy_claims.append(
            {
                "id": c.get("id") or f"c_{i + 1}",
                "claim_type": c.get("claim_type") or c.get("type") or "fact",
                "importance": c.get("importance") or "required",
                "text": c.get("text") or "",
                "evidence": list(c.get("evidence") or []),
            }
        )

    legacy_objectives = []
    for i, o in enumerate(data.get("objectives") or []):
        cog = o.get("cognitive_level") or "understand"
        legacy_objectives.append(
            {
                "id": o.get("id") or f"o_{i + 1}",
                "description": o.get("description") or o.get("text") or "",
                "ability": o.get("ability") or COG_TO_ABILITY.get(cog, "explain"),
                "importance": o.get("importance") or "required",
                "source_claim_ids": list(o.get("source_claim_ids") or []),
            }
        )

    return {
        "understanding_version": "v1",
        "unit_type": data.get("unit_type") or "concept",
        "central_question": data.get("central_question") or data.get("unit_gist") or "",
        "claims": legacy_claims,
        "objectives": legacy_objectives,
    }


async def _persist_understanding_only(
    session: AsyncSession,
    unit: Any,
    normalized: dict[str, Any],
    *,
    unit_hash: str,
    overview_injected: bool,
    partial: bool,
    prompt_version: str,
    model_name: str,
) -> UnitLearningAssetModel:
    """把理解结果落成 understanding_only 资产（不含教学设计）。"""
    result = UnderstandingResult(
        ok=True,
        unit_id=unit.id,
        content_hash=unit_hash,
        unit_gist=normalized.get("unit_gist") or "",
        claims=normalized.get("claims") or [],
        objectives=normalized.get("objectives") or [],
        prerequisites=normalized.get("prerequisites") or [],
        overview_injected=overview_injected,
        partial=partial,
    )
    stage1 = result.to_stage1_dict()

    payload = UnitLearningAssetPayload(
        unit_type="concept",
        central_question=stage1["central_question"],
        claims=[
            {
                "id": c["id"],
                "claim_type": c["claim_type"],
                "importance": c["importance"],
                "text": c["text"],
                "role_in_book": c["role_in_book"],
                "mastery_check": c["mastery_check"],
                "related_concepts": c["related_concepts"],
                "support_status": "unsupported",
            }
            for c in stage1["claims"]
        ],
        learning_objectives=[
            {
                "id": o["id"],
                "description": o["description"],
                "ability": o["ability"],
                "importance": o["importance"],
                "cognitive_level": o["cognitive_level"],
                "source_claim_ids": o["source_claim_ids"],
            }
            for o in stage1["objectives"]
        ],
        understanding_version="v2",
        unit_gist=stage1["unit_gist"],
        content_hash=unit_hash,
        overview_injected=overview_injected,
    )

    last_version = (
        await session.execute(
            select(UnitLearningAssetModel.version)
            .where(UnitLearningAssetModel.unit_id == unit.id)
            .order_by(UnitLearningAssetModel.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    next_version = int(last_version or 0) + 1

    # 旧的 understanding_only 资产标记为 superseded（教学资产不动）
    prev = (
        await session.execute(
            select(UnitLearningAssetModel).where(
                UnitLearningAssetModel.unit_id == unit.id,
                UnitLearningAssetModel.status == "active",
                UnitLearningAssetModel.readiness_status == "understanding_ready",
            )
        )
    ).scalars().all()
    for row in prev or []:
        row.status = "superseded"

    asset = UnitLearningAssetModel(
        id=str(uuid4()),
        unit_id=unit.id,
        version=next_version,
        status="active",
        readiness_status="understanding_ready",
        freshness_status="current",
        document_revision_id=None,
        payload_json=payload.model_dump_json(),
        schema_version="unit-asset-v1",
        prompt_version=prompt_version,
        model_name=model_name,
        created_at=_utc_now(),
        published_at=_utc_now(),
    )
    session.add(asset)
    await session.flush()
    result.asset_id = asset.id
    return asset


async def run_understanding(
    session: AsyncSession,
    unit_id: str,
    *,
    llm_client=None,
    force: bool = False,
    prompt_version: str = "understanding-v2",
    model_name: str = "llm",
) -> UnderstandingResult:
    """跑单元理解阶段。失败软返回（ok=False），不抛异常打断主流程。"""
    unit = (
        await session.execute(
            select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
        )
    ).scalar_one_or_none()
    if unit is None:
        return UnderstandingResult(ok=False, unit_id=unit_id, error="unit not found")

    unit_hash = content_hash(unit.content or "")

    if not force:
        existing = (
            await session.execute(
                select(UnitLearningAssetModel).where(
                    UnitLearningAssetModel.unit_id == unit_id,
                    UnitLearningAssetModel.status == "active",
                )
            )
        ).scalars().all()
        for row in existing or []:
            try:
                payload = json.loads(row.payload_json or "{}")
            except Exception:  # noqa: BLE001
                continue
            if (
                payload.get("understanding_version") == "v2"
                and payload.get("content_hash") == unit_hash
            ):
                return UnderstandingResult(
                    ok=True,
                    unit_id=unit_id,
                    content_hash=unit_hash,
                    unit_gist=payload.get("unit_gist") or "",
                    claims=list(payload.get("claims") or []),
                    objectives=list(payload.get("learning_objectives") or []),
                    overview_injected=bool(payload.get("overview_injected")),
                    skipped=True,
                    asset_id=getattr(row, "id", None),
                )

    book = (
        await session.execute(select(BookModel).where(BookModel.id == unit.book_id))
    ).scalar_one_or_none()
    chapter = (
        await session.execute(
            select(ChapterModel).where(ChapterModel.id == unit.chapter_id)
        )
    ).scalar_one_or_none()

    overview_block, overview_injected = build_overview_block(book) if book else ("", False)
    extra_lines = []
    if chapter is not None:
        if getattr(chapter, "title", None):
            extra_lines.append(f"章节标题：{chapter.title}")
        if getattr(chapter, "summary", None):
            extra_lines.append(f"章节摘要：{chapter.summary}")
    extra_context = "\n".join(extra_lines)

    if llm_client is None:
        return UnderstandingResult(
            ok=False,
            unit_id=unit_id,
            content_hash=unit_hash,
            error="llm client unavailable",
        )

    text = unit.content or ""
    partial = False
    normalized: dict[str, Any] = {}

    if len(text) > CONTENT_TRUNCATE:
        # 超长单元走 map-reduce
        from app.modules.learning_assets.mapreduce import run_understanding_mapreduce

        try:
            mr_claims, mr_meta = await run_understanding_mapreduce(
                text,
                chapter_summary=getattr(chapter, "summary", "") or "",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("mapreduce fail unit=%s: %s", unit_id, exc)
            mr_claims, mr_meta = [], {}
        if mr_claims:
            partial = bool(mr_meta.get("partial"))
            claims = []
            for i, c in enumerate(mr_claims):
                mastery = str(c.get("mastery_check") or "").strip()
                if _is_vague(mastery):
                    mastery = f"能用自己的话说明：{(c.get('text') or '')[:40]}"
                role = str(c.get("role_in_book") or "supporting_detail")
                if role not in ROLE_IN_BOOK:
                    role = "supporting_detail"
                claims.append(
                    {
                        "id": f"c_{i + 1}",
                        "text": str(c.get("text") or ""),
                        "type": "fact",
                        "role_in_book": role,
                        "mastery_check": mastery,
                        "related_concepts": list(c.get("related_concepts") or []),
                    }
                )
            claims = [c for c in claims if c["text"]]
            if claims:
                normalized = {
                    "unit_gist": mr_meta.get("unit_gist")
                    or f"{unit.title}（大单元合并理解）",
                    "claims": claims,
                    "objectives": [
                        {
                            "id": "o_1",
                            "text": f"能说明《{unit.title}》的核心命题及其作用",
                            "cognitive_level": "understand",
                            "covers_claims": [
                                i
                                for i, c in enumerate(claims)
                                if c["role_in_book"] != "tangential"
                            ],
                        }
                    ],
                    "prerequisites": [],
                }

    if not normalized:
        prompt = build_understanding_prompt(
            unit_title=unit.title or "",
            unit_content=text,
            overview_block=overview_block,
            extra_context=extra_context,
        )
        try:
            raw = await llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("understanding llm fail unit=%s: %s", unit_id, exc)
            return UnderstandingResult(
                ok=False,
                unit_id=unit_id,
                content_hash=unit_hash,
                error=f"llm error: {exc}",
            )
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:  # noqa: BLE001
                return UnderstandingResult(
                    ok=False,
                    unit_id=unit_id,
                    content_hash=unit_hash,
                    error="llm returned non-json",
                )
        ok, err, normalized = validate_understanding_raw(raw)
        if not ok:
            logger.warning("understanding invalid unit=%s: %s", unit_id, err)
            return UnderstandingResult(
                ok=False, unit_id=unit_id, content_hash=unit_hash, error=err
            )

    asset = await _persist_understanding_only(
        session,
        unit,
        normalized,
        unit_hash=unit_hash,
        overview_injected=overview_injected,
        partial=partial,
        prompt_version=prompt_version,
        model_name=model_name,
    )

    # 概念收编（失败不影响理解结果）
    try:
        from app.modules.learning_assets.concept_harvest import (
            harvest_from_understanding,
        )

        await harvest_from_understanding(
            session,
            unit.book_id,
            unit.id,
            getattr(unit, "chapter_id", None),
            normalized.get("claims") or [],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("concept harvest skip unit=%s: %s", unit_id, exc)

    return UnderstandingResult(
        ok=True,
        unit_id=unit_id,
        content_hash=unit_hash,
        unit_gist=normalized.get("unit_gist") or "",
        claims=normalized.get("claims") or [],
        objectives=normalized.get("objectives") or [],
        prerequisites=normalized.get("prerequisites") or [],
        overview_injected=overview_injected,
        partial=partial,
        asset_id=getattr(asset, "id", None),
    )


async def precompute_book_understanding(
    session: AsyncSession,
    book_id: str,
    *,
    llm_client=None,
    force: bool = False,
) -> dict[str, Any]:
    """整本书批量预生成单元理解；逐单元软失败，返回统计。"""
    units = (
        await session.execute(
            select(KnowledgeUnitModel)
            .where(KnowledgeUnitModel.book_id == book_id)
            .order_by(KnowledgeUnitModel.order_index)
        )
    ).scalars().all()

    stats = {
        "total": len(units or []),
        "ok": 0,
        "skipped": 0,
        "failed": 0,
        "partial": 0,
    }
    for unit in units or []:
        try:
            res = await run_understanding(
                session, unit.id, llm_client=llm_client, force=force
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("understanding crash unit=%s: %s", unit.id, exc)
            stats["failed"] += 1
            continue
        if not res.ok:
            stats["failed"] += 1
        elif res.skipped:
            stats["skipped"] += 1
        else:
            stats["ok"] += 1
            if res.partial:
                stats["partial"] += 1
    logger.info("precompute understanding book=%s stats=%s", book_id, stats)
    return stats
