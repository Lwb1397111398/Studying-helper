"""知识图谱适配器 - AID 与 KG 之间的隔离层

AID 不直接 import KnowledgeGraphService 的 ORM 细节，只通过本适配器的纯数据结构交互。
这样 KG 内部重构不会波及 AID。所有方法 async，复用 KG 现有拓扑与图查询能力。
"""

import json
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeUnitModel, MasteryRecordModel


@dataclass
class UnitBrief:
    """单元摘要 - AID 编排所需的最小信息集"""

    unit_id: str
    title: str
    summary: str
    difficulty_level: int
    importance_score: float
    chapter_id: str
    order_index: int
    concepts: list[str] = field(default_factory=list)  # 概念名列表
    prerequisites: list[str] = field(default_factory=list)  # unit_id 或概念名
    mastery_score: Optional[float] = None  # 来自 MasteryRecord，无则 None


class KGAdapter:
    """知识图谱适配器：为 AID 提供图与单元查询，隔离 ORM"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_unit_briefs(self, book_id: str, user_id: str = "anonymous") -> list[UnitBrief]:
        """获取一本书所有单元的摘要信息（含掌握度）

        掌握度来自 MasteryRecord（replan 与 skip_if_mastered 需要）。
        """
        # 单元
        u_result = await self.db.execute(
            select(KnowledgeUnitModel)
            .where(KnowledgeUnitModel.book_id == book_id)
            .order_by(KnowledgeUnitModel.order_index)
        )
        units = u_result.scalars().all()

        # 掌握度映射
        m_result = await self.db.execute(
            select(MasteryRecordModel.knowledge_unit_id, MasteryRecordModel.mastery_score).where(
                MasteryRecordModel.user_id == user_id,
                MasteryRecordModel.knowledge_unit_id.in_([u.id for u in units]) if units else select(1) == 0,
            )
        )
        mastery_map: dict[str, float] = {}
        for unit_id_val, score in m_result.all():
            mastery_map[unit_id_val] = float(score) if score is not None else 0.0

        briefs: list[UnitBrief] = []
        for u in units:
            briefs.append(
                UnitBrief(
                    unit_id=u.id,
                    title=u.title or "",
                    summary=u.summary or "",
                    difficulty_level=u.difficulty_level or 3,
                    importance_score=u.importance_score if u.importance_score is not None else 0.5,
                    chapter_id=u.chapter_id or "",
                    order_index=u.order_index,
                    concepts=_parse_concepts(u.concepts),
                    prerequisites=_parse_str_list(u.prerequisites),
                    mastery_score=mastery_map.get(u.id),
                )
            )
        return briefs

    async def get_topological_layers(self, book_id: str) -> list[list[str]]:
        """拓扑分层：同层单元无依赖，可并行处理。复用 KG 服务。

        depends_on 语义：source depends on target（source 依赖 target）。
        """
        from app.modules.knowledge_graph.service import KnowledgeGraphService

        kg = KnowledgeGraphService(self.db)
        try:
            return await kg.get_topological_layers(book_id)
        except Exception:
            # KG 未构建时回退为空，AID 调用方据此回退为章节序
            return []

    async def get_concept_unit_map(self, book_id: str) -> dict[str, list[str]]:
        """概念 -> 持有该概念的单元 id 列表。

        这是 AID 宏观跨章节聚类的关键依据：同一概念出现在不同章节的多个单元，
        说明这些单元可围绕该概念组成学习模块。
        """
        briefs = await self.get_unit_briefs(book_id)
        concept_units: dict[str, list[str]] = {}
        for b in briefs:
            for c in b.concepts:
                c = c.strip()
                if c:
                    concept_units.setdefault(c, []).append(b.unit_id)
        # 只保留跨单元出现（或至少出现）的概念；单单元独占概念也保留，
        # 由 AID 决定如何用
        return concept_units

    async def get_unit_adjacency(
        self, book_id: str, relation_types: Optional[list[str]] = None
    ) -> dict[str, list[tuple[str, str, float]]]:
        """单元邻接表：unit_id -> [(neighbor_unit_id, relation_type, weight), ...]

        只返回 unit<->unit 的边（过滤掉 concept/chapter 端点）。
        AID 微观排序需要 depends_on（前置约束）与 similar_to（同组联想）。
        """
        from app.modules.knowledge_graph.service import KnowledgeGraphService

        kg = KnowledgeGraphService(self.db)
        try:
            graph = await kg.get_graph(book_id)
        except Exception:
            return {}

        unit_ids = {n.id for n in graph.nodes if n.node_type == "unit"}
        wanted = set(relation_types) if relation_types else None
        adj: dict[str, list[tuple[str, str, float]]] = {uid: [] for uid in unit_ids}
        for e in graph.edges:
            if e.source_id in unit_ids and e.target_id in unit_ids:
                if wanted and e.relation_type not in wanted:
                    continue
                adj[e.source_id].append((e.target_id, e.relation_type, e.weight))
                # similar_to 视为无向
                if e.relation_type in ("similar_to", "contrasts_with") and e.target_id in adj:
                    adj[e.target_id].append((e.source_id, e.relation_type, e.weight))
        return adj


# ---- 解析辅助 ----


def _parse_concepts(raw) -> list[str]:
    """解析 KnowledgeUnitModel.concepts（JSON 数组，元素可为字符串或 Concept 对象）"""
    if not raw:
        return []
    if isinstance(raw, list):
        items = raw
    else:
        try:
            items = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return [c.strip() for c in str(raw).split(",") if c.strip()]
    result: list[str] = []
    for c in items:
        if isinstance(c, dict):
            name = c.get("name", "")
            if name:
                result.append(name)
        elif isinstance(c, str) and c.strip():
            result.append(c.strip())
    return result


def _parse_str_list(raw) -> list[str]:
    """解析 prerequisites（JSON 数组，字符串列表）"""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    try:
        items = json.loads(raw)
        return [str(x) for x in items if x] if isinstance(items, list) else []
    except (json.JSONDecodeError, TypeError):
        return [p.strip() for p in str(raw).split(",") if p.strip()]
