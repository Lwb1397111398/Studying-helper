"""知识图谱服务 - 核心业务逻辑（DB持久化版）"""

import json
from typing import List, Dict, Optional
from collections import deque

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ServiceError, ErrorCode
from app.db.models import KGNodeModel, KGEdgeModel
from app.modules.knowledge_graph.schemas import (
    KGNode, KGEdge, KnowledgeGraph, GraphStats,
    GraphQuery, SubGraph, VisualizationData,
    VisNode, VisEdge,
)
from app.modules.knowledge_graph.graph_builder import GraphBuilder
from app.modules.knowledge_graph.relation_detector import RelationDetector


class KnowledgeGraphService:
    """知识图谱服务（节点和边持久化到数据库）"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.builder = GraphBuilder()

    async def build_graph(
        self,
        book_id: str,
        units: list,
        chapters: list,
        mastery_records: list = None,
    ) -> KnowledgeGraph:
        """构建知识图谱并持久化到数据库（整本重建，保留手动边）"""
        if not units:
            raise ServiceError(ErrorCode.INSUFFICIENT_DATA, "没有知识单元数据，无法构建图谱")

        # 清除旧数据，但保留手动边
        manual_edges = await self._delete_book_graph(book_id, keep_manual_edges=True)

        # 构建图谱
        graph = self.builder.build_from_data(book_id, units, chapters, mastery_records)

        # 持久化节点
        for node in graph.nodes:
            self.db.add(KGNodeModel(
                id=node.id,
                node_type=node.node_type,
                label=node.label,
                book_id=book_id,
                content_summary=node.content_summary,
                difficulty_level=node.difficulty_level,
                importance_score=node.importance_score,
                mastery_score=node.mastery_score,
                mastery_level=node.mastery_level,
                size=node.size,
                color=node.color,
            ))

        # 持久化自动生成的边
        for edge in graph.edges:
            self.db.add(KGEdgeModel(
                id=edge.id,
                source_id=edge.source_id,
                target_id=edge.target_id,
                relation_type=edge.relation_type,
                weight=edge.weight,
                metadata_json=json.dumps(edge.metadata) if edge.metadata else None,
            ))

        # 恢复手动边（如果端点仍存在）
        existing_node_ids = {n.id for n in graph.nodes}
        for me in manual_edges:
            if me.source_id in existing_node_ids and me.target_id in existing_node_ids:
                self.db.add(KGEdgeModel(
                    id=me.id, source_id=me.source_id, target_id=me.target_id,
                    relation_type=me.relation_type, weight=me.weight,
                    metadata_json=me.metadata_json,
                ))

        await self.db.flush()
        return graph

    async def get_graph(self, book_id: str) -> KnowledgeGraph:
        """从数据库加载知识图谱"""
        nodes_result = await self.db.execute(
            select(KGNodeModel).where(KGNodeModel.book_id == book_id)
        )
        db_nodes = nodes_result.scalars().all()

        edges_result = await self.db.execute(
            select(KGEdgeModel).where(
                KGEdgeModel.source_id.in_([n.id for n in db_nodes])
            ) if db_nodes else select(KGEdgeModel).where(KGEdgeModel.source_id == "")
        )
        db_edges = edges_result.scalars().all()

        if not db_nodes:
            raise ServiceError(ErrorCode.NOT_FOUND, f"未找到书籍 {book_id} 的知识图谱")

        nodes = [
            KGNode(
                id=n.id, node_type=n.node_type, label=n.label,
                book_id=n.book_id, content_summary=n.content_summary,
                difficulty_level=n.difficulty_level,
                importance_score=n.importance_score,
                mastery_score=n.mastery_score,
                mastery_level=n.mastery_level,
                size=n.size, color=n.color,
            )
            for n in db_nodes
        ]

        node_ids = {n.id for n in nodes}
        edges = [
            KGEdge(
                id=e.id, source_id=e.source_id, target_id=e.target_id,
                relation_type=e.relation_type, weight=e.weight,
                metadata=json.loads(e.metadata_json) if e.metadata_json else None,
            )
            for e in db_edges
            if e.source_id in node_ids and e.target_id in node_ids
        ]

        stats = self.builder._calc_stats(nodes, edges)
        return KnowledgeGraph(book_id=book_id, nodes=nodes, edges=edges, stats=stats)

    async def query_neighbors(
        self,
        book_id: str,
        node_id: str,
        query: GraphQuery,
    ) -> SubGraph:
        """查询节点邻居（BFS）"""
        graph = await self.get_graph(book_id)

        node_map = {n.id: n for n in graph.nodes}
        center = node_map.get(node_id)
        if not center:
            raise ServiceError(ErrorCode.NOT_FOUND, f"节点 {node_id} 不存在")

        adj = _build_adjacency(graph.edges, query.relation_types, query.min_weight)

        visited = {node_id}
        queue = deque([(node_id, 0)])
        result_nodes: List[KGNode] = []
        result_edges: List[KGEdge] = []

        while queue:
            current_id, depth = queue.popleft()
            if depth >= query.max_depth:
                continue

            # 按 weight 降序遍历，让重要关系优先被发现
            neighbors = sorted(adj.get(current_id, []), key=lambda e: e.weight, reverse=True)

            for edge in neighbors:
                # depends_on 是有向边：只沿 source → target 方向遍历
                # 其他边是无向的
                if edge.relation_type == "depends_on":
                    if edge.source_id != current_id:
                        continue  # 只能从依赖方指向被依赖方
                    neighbor_id = edge.target_id
                elif edge.relation_type == "part_of":
                    if edge.source_id != current_id:
                        continue  # part_of 也是单向：unit → chapter
                    neighbor_id = edge.target_id
                else:
                    neighbor_id = edge.target_id if edge.source_id == current_id else edge.source_id

                if neighbor_id in visited:
                    continue

                neighbor = node_map.get(neighbor_id)
                if not neighbor:
                    continue

                if query.node_types and neighbor.node_type not in query.node_types:
                    continue

                visited.add(neighbor_id)
                result_nodes.append(neighbor)
                result_edges.append(edge)
                queue.append((neighbor_id, depth + 1))

        return SubGraph(center_node=center, nodes=result_nodes, edges=result_edges)

    async def find_path(
        self,
        book_id: str,
        source_id: str,
        target_id: str,
    ) -> Optional[List[KGEdge]]:
        """查找两节点间路径（BFS）"""
        graph = await self.get_graph(book_id)

        node_map = {n.id: n for n in graph.nodes}
        if source_id not in node_map:
            raise ServiceError(ErrorCode.NOT_FOUND, f"源节点 {source_id} 不存在")
        if target_id not in node_map:
            raise ServiceError(ErrorCode.NOT_FOUND, f"目标节点 {target_id} 不存在")

        if source_id == target_id:
            return []

        # 有向边（depends_on, part_of）只沿正向遍历，无向边双向遍历
        _DIRECTED_TYPES = {"depends_on", "part_of"}
        adj: Dict[str, List[KGEdge]] = {}
        for edge in graph.edges:
            if edge.relation_type in _DIRECTED_TYPES:
                # depends_on: source depends on target → 只从 source 走到 target
                adj.setdefault(edge.source_id, []).append(edge)
            else:
                adj.setdefault(edge.source_id, []).append(edge)
                adj.setdefault(edge.target_id, []).append(edge)

        visited = {source_id}
        queue = deque([(source_id, [])])

        while queue:
            current_id, path = queue.popleft()
            for edge in adj.get(current_id, []):
                # 有向边只正向：source→target；无向边双向
                if edge.relation_type in _DIRECTED_TYPES:
                    neighbor_id = edge.target_id
                else:
                    neighbor_id = edge.target_id if edge.source_id == current_id else edge.source_id
                if neighbor_id in visited:
                    continue
                new_path = path + [edge]
                if neighbor_id == target_id:
                    return new_path
                visited.add(neighbor_id)
                queue.append((neighbor_id, new_path))

        return None

    async def get_visualization_data(
        self,
        book_id: str,
        center_node_id: str = None,
        max_nodes: int = 100,
    ) -> VisualizationData:
        """获取可视化数据"""
        graph = await self.get_graph(book_id)

        if center_node_id:
            node_map = {n.id: n for n in graph.nodes}
            if center_node_id not in node_map:
                raise ServiceError(ErrorCode.NOT_FOUND, f"节点 {center_node_id} 不存在")
            query = GraphQuery(max_depth=2)
            sub = await self.query_neighbors(book_id, center_node_id, query)
            display_nodes = [sub.center_node] + sub.nodes
            display_edges = sub.edges
        else:
            display_nodes = graph.nodes[:max_nodes]
            node_ids = {n.id for n in display_nodes}
            display_edges = [e for e in graph.edges
                            if e.source_id in node_ids and e.target_id in node_ids]

        vis_nodes = [
            VisNode(
                id=node.id, label=node.label, group=node.node_type,
                size=node.size, color=node.color or "#999999",
                title=_build_node_title(node),
            )
            for node in display_nodes
        ]

        vis_edges = [
            VisEdge(
                from_id=edge.source_id, to_id=edge.target_id,
                label=edge.relation_type, width=edge.weight,
                dashes=edge.relation_type == "similar_to",
            )
            for edge in display_edges
        ]

        return VisualizationData(nodes=vis_nodes, edges=vis_edges, layout="force")

    async def add_edge(
        self,
        book_id: str,
        source_id: str,
        target_id: str,
        relation_type: str,
        weight: float = 1.0,
        is_manual: bool = True,
    ) -> KGEdge:
        """手动添加边（is_manual=True 的边在整本重建时保留）"""
        graph = await self.get_graph(book_id)

        node_map = {n.id: n for n in graph.nodes}
        if source_id not in node_map:
            raise ServiceError(ErrorCode.NOT_FOUND, f"源节点 {source_id} 不存在")
        if target_id not in node_map:
            raise ServiceError(ErrorCode.NOT_FOUND, f"目标节点 {target_id} 不存在")
        if source_id == target_id:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "不能创建自环边")

        for edge in graph.edges:
            if (edge.source_id == source_id and edge.target_id == target_id
                    and edge.relation_type == relation_type):
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "相同类型的边已存在")

        new_edge = KGEdge(
            source_id=source_id, target_id=target_id,
            relation_type=relation_type, weight=weight,
            metadata={"is_manual": is_manual},
        )

        self.db.add(KGEdgeModel(
            id=new_edge.id, source_id=source_id, target_id=target_id,
            relation_type=relation_type, weight=weight,
            metadata_json=json.dumps({"is_manual": is_manual}),
        ))
        await self.db.flush()

        return new_edge

    async def remove_edge(self, book_id: str, edge_id: str) -> None:
        """删除边"""
        result = await self.db.execute(
            select(KGEdgeModel).where(KGEdgeModel.id == edge_id)
        )
        edge = result.scalar_one_or_none()
        if not edge:
            raise ServiceError(ErrorCode.NOT_FOUND, f"边 {edge_id} 不存在")

        await self.db.execute(delete(KGEdgeModel).where(KGEdgeModel.id == edge_id))
        await self.db.flush()

    async def update_mastery(self, unit_id: str, mastery_score: float, mastery_level: str) -> None:
        """更新节点的掌握度信息"""
        result = await self.db.execute(
            select(KGNodeModel).where(KGNodeModel.id == unit_id)
        )
        node = result.scalar_one_or_none()
        if node:
            node.mastery_score = mastery_score
            node.mastery_level = mastery_level
            node.color = self.builder._calc_node_color(mastery_score)
            await self.db.flush()

    async def update_unit_graph(
        self,
        book_id: str,
        unit_data: dict,
    ) -> KnowledgeGraph:
        """
        增量更新：学完一个单元后，只更新该单元涉及的节点和边。

        流程：
        1. 删除该单元的旧 unit 节点 + 关联的 concept 节点 + 关联的边
        2. 基于新数据创建新的 unit 节点 + concept 节点
        3. 检测新节点与图中已有节点之间的关系，创建新边
        4. 返回更新后的完整图谱

        参数:
            book_id: 书籍ID
            unit_data: 单元数据，格式与 GraphBuilder.build_from_data 的 unit 一致
                      需包含 id, title, concepts, summary, difficulty_level 等
        """
        # 1. 找到该单元相关的旧节点（unit 节点 + 该单元关联的 concept 节点）
        old_unit_node_id = unit_data.get("id", "")

        # 找到该单元关联的 concept 节点（通过 related 边）
        concept_ids_result = await self.db.execute(
            select(KGEdgeModel.target_id).where(
                KGEdgeModel.source_id == old_unit_node_id,
                KGEdgeModel.relation_type == "related",
            )
        )
        old_concept_ids = [row[0] for row in concept_ids_result.all()]

        # 删除旧边（与该单元相关的所有边）
        await self.db.execute(
            delete(KGEdgeModel).where(
                (KGEdgeModel.source_id == old_unit_node_id)
                | (KGEdgeModel.target_id == old_unit_node_id)
            )
        )
        # 也删除 concept 节点的边
        if old_concept_ids:
            await self.db.execute(
                delete(KGEdgeModel).where(
                    KGEdgeModel.source_id.in_(old_concept_ids)
                    | KGEdgeModel.target_id.in_(old_concept_ids)
                )
            )

        # 删除旧节点
        await self.db.execute(
            delete(KGNodeModel).where(KGNodeModel.id == old_unit_node_id)
        )
        if old_concept_ids:
            await self.db.execute(
                delete(KGNodeModel).where(KGNodeModel.id.in_(old_concept_ids))
            )

        # 2. 加载图中所有已有节点和边
        existing_nodes_result = await self.db.execute(
            select(KGNodeModel).where(KGNodeModel.book_id == book_id)
        )
        existing_nodes = [
            KGNode(
                id=n.id, node_type=n.node_type, label=n.label,
                book_id=n.book_id, content_summary=n.content_summary,
                difficulty_level=n.difficulty_level,
                importance_score=n.importance_score,
                mastery_score=n.mastery_score,
                mastery_level=n.mastery_level,
                size=n.size, color=n.color,
            )
            for n in existing_nodes_result.scalars().all()
        ]

        existing_edges_result = await self.db.execute(
            select(KGEdgeModel).where(
                KGEdgeModel.source_id.in_([n.id for n in existing_nodes])
            )
        )
        existing_edges = [
            KGEdge(
                id=e.id, source_id=e.source_id, target_id=e.target_id,
                relation_type=e.relation_type, weight=e.weight,
                metadata=json.loads(e.metadata_json) if e.metadata_json else None,
            )
            for e in existing_edges_result.scalars().all()
        ]

        # 3. 为新单元创建节点
        builder = self.builder
        new_unit_node = builder._create_unit_node(unit_data, book_id, {})
        new_unit_node.color = builder._calc_node_color(None)
        new_unit_node.size = builder._calc_node_size(new_unit_node.importance_score)

        # 创建 concept 节点
        new_nodes = [new_unit_node]
        new_unit_concepts = _get_concepts_from_data(unit_data)
        concept_name_to_node = {}
        for concept_name in new_unit_concepts:
            c_node = builder._create_concept_node(concept_name, book_id)
            c_node.color = "#999999"
            concept_name_to_node[concept_name] = c_node
            new_nodes.append(c_node)

        # 4. 检测新节点与已有节点之间的关系
        detector = RelationDetector()
        new_edges = []

        # unit 与 concept 的 related 边
        for concept_name, c_node in concept_name_to_node.items():
            new_edges.append(KGEdge(
                source_id=new_unit_node.id,
                target_id=c_node.id,
                relation_type="related",
                weight=0.8,
            ))

        # 新 unit 与已有 unit 之间的相似度
        if existing_nodes:
            all_units_data = []
            for n in existing_nodes:
                if n.node_type == "unit":
                    all_units_data.append({
                        "id": n.id,
                        "title": n.label,
                        "concepts": [],  # 已有单元的概念需要从边反查
                    })
            all_units_data.append(unit_data)

            sim_edges = detector.detect_similar(all_units_data)
            # 只保留涉及新 unit 的边
            for e in sim_edges:
                if e.source_id == new_unit_node.id or e.target_id == new_unit_node.id:
                    new_edges.append(e)

            # 依赖检测
            dep_edges = detector.detect_dependencies(all_units_data)
            for e in dep_edges:
                if e.source_id == new_unit_node.id or e.target_id == new_unit_node.id:
                    new_edges.append(e)

        # 5. 持久化新节点和新边
        for node in new_nodes:
            self.db.add(KGNodeModel(
                id=node.id,
                node_type=node.node_type,
                label=node.label,
                book_id=book_id,
                content_summary=node.content_summary,
                difficulty_level=node.difficulty_level,
                importance_score=node.importance_score,
                mastery_score=node.mastery_score,
                mastery_level=node.mastery_level,
                size=node.size,
                color=node.color,
            ))

        for edge in new_edges:
            self.db.add(KGEdgeModel(
                id=edge.id,
                source_id=edge.source_id,
                target_id=edge.target_id,
                relation_type=edge.relation_type,
                weight=edge.weight,
                metadata_json=json.dumps(edge.metadata) if edge.metadata else None,
            ))

        await self.db.flush()

        # 6. 返回更新后的完整图谱
        return await self.get_graph(book_id)

    async def _delete_book_graph(self, book_id: str, keep_manual_edges: bool = True) -> list:
        """删除书籍的图谱数据。

        参数:
            keep_manual_edges: True 时保留手动添加的边（用于增量更新）
                               False 时全部删除（用于整本重建）

        返回:
            被保留的手动边列表（keep_manual_edges=True 时）
        """
        nodes_result = await self.db.execute(
            select(KGNodeModel.id).where(KGNodeModel.book_id == book_id)
        )
        node_ids = [row[0] for row in nodes_result.all()]

        manual_edges = []
        if node_ids:
            if keep_manual_edges:
                # 先查出手动边，重建后恢复
                all_edges_result = await self.db.execute(
                    select(KGEdgeModel).where(
                        KGEdgeModel.source_id.in_(node_ids)
                        | KGEdgeModel.target_id.in_(node_ids)
                    )
                )
                for e in all_edges_result.scalars().all():
                    meta = json.loads(e.metadata_json) if e.metadata_json else {}
                    if meta.get("is_manual"):
                        manual_edges.append(e)

            # 删除所有边
            await self.db.execute(
                delete(KGEdgeModel).where(
                    KGEdgeModel.source_id.in_(node_ids)
                    | KGEdgeModel.target_id.in_(node_ids)
                )
            )

        # 删除节点
        await self.db.execute(
            delete(KGNodeModel).where(KGNodeModel.book_id == book_id)
        )

        return manual_edges

    async def get_topological_order(self, book_id: str) -> List[str]:
        """返回知识单元的拓扑排序（前置在前）。基于 depends_on 边 BFS。

        depends_on 语义：source depends on target（source 依赖 target），
        即 target 是 source 的前置，target 应排在 source 前面。
        """
        graph = await self.get_graph(book_id)
        unit_ids = {n.id for n in graph.nodes if n.node_type == "unit"}
        in_degree = {uid: 0 for uid in unit_ids}
        adj = {uid: [] for uid in unit_ids}
        for edge in graph.edges:
            # depends_on: source depends on target → target 是前置
            # adj[target].append(source): target 完成后 source 入度减 1
            if edge.relation_type == "depends_on" and edge.source_id in unit_ids and edge.target_id in unit_ids:
                adj[edge.target_id].append(edge.source_id)
                in_degree[edge.source_id] += 1
        queue = [uid for uid, deg in in_degree.items() if deg == 0]
        order = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        for uid in unit_ids:
            if uid not in order:
                order.append(uid)
        return order

    async def get_topological_layers(self, book_id: str) -> List[List[str]]:
        """返回拓扑分层：同一层内的单元无依赖关系，可并行处理。"""
        graph = await self.get_graph(book_id)
        unit_ids = {n.id for n in graph.nodes if n.node_type == "unit"}
        in_degree = {uid: 0 for uid in unit_ids}
        adj: dict[str, list[str]] = {uid: [] for uid in unit_ids}
        for edge in graph.edges:
            # depends_on: source depends on target → target 是前置
            if edge.relation_type == "depends_on" and edge.source_id in unit_ids and edge.target_id in unit_ids:
                adj[edge.target_id].append(edge.source_id)
                in_degree[edge.source_id] += 1
        queue = [uid for uid, deg in in_degree.items() if deg == 0]
        layers: list[list[str]] = []
        while queue:
            layers.append(list(queue))
            next_queue = []
            for node in queue:
                for neighbor in adj[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            queue = next_queue
        # 未被拓扑排序覆盖的节点（存在环）放到最后一层
        ordered = {uid for layer in layers for uid in layer}
        remaining = [uid for uid in unit_ids if uid not in ordered]
        if remaining:
            layers.append(remaining)
        return layers


# ---- 辅助函数 ----

def _build_adjacency(
    edges: List[KGEdge],
    relation_types: Optional[List[str]] = None,
    min_weight: float = 0.0,
) -> Dict[str, List[KGEdge]]:
    """构建邻接表，支持过滤"""
    adj: Dict[str, List[KGEdge]] = {}
    for edge in edges:
        if relation_types and edge.relation_type not in relation_types:
            continue
        if edge.weight < min_weight:
            continue
        adj.setdefault(edge.source_id, []).append(edge)
        adj.setdefault(edge.target_id, []).append(edge)
    return adj


def _get_concepts_from_data(unit_data: dict) -> list:
    """从 unit_data 中提取概念列表（兼容字符串和 Concept 对象）"""
    concepts = unit_data.get("concepts", [])
    if not concepts:
        return []
    result = []
    for c in concepts:
        if isinstance(c, str):
            result.append(c)
        elif isinstance(c, dict):
            name = c.get("name", "")
            if name:
                result.append(name)
    return result


def _build_node_title(node: KGNode) -> str:
    """构建节点悬浮提示"""
    parts = [f"{node.label} ({node.node_type})"]
    if node.content_summary:
        parts.append(node.content_summary[:100])
    if node.mastery_level:
        parts.append(f"掌握度: {node.mastery_level}")
    return "\n".join(parts)
