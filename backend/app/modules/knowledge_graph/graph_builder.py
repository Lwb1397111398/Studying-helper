"""知识图谱构建器 - 从知识单元和章节数据构建图谱"""

import re
from typing import List, Optional
from collections import Counter

from app.modules.knowledge_graph.schemas import (
    KGNode, KGEdge, KnowledgeGraph, GraphStats,
)
from app.modules.knowledge_graph.relation_detector import RelationDetector


def _make_short_label(label: str, node_type: str, max_len: int = 12) -> str:
    """生成适合图谱显示的短标签。

    - chapter: 取最后一级标题（如 "第一编 总则 第二章 …… 第三节 X" → "第三节 X"）
    - unit: 截断到 max_len
    - concept: 通常较短，保持原样
    """
    if not label:
        return label

    if node_type == "chapter":
        # 按 "第X编/章/节" 分割，取最后一段
        parts = re.split(r'(?=第[一二三四五六七八九十百千\d]+[编章节回])', label)
        last = parts[-1].strip() if parts else label
        if len(last) > max_len:
            return last[:max_len - 1] + "…"
        return last

    if node_type == "unit":
        if len(label) > max_len:
            return label[:max_len - 1] + "…"
        return label

    # concept 等：保持原样，仅在过长时截断
    if len(label) > max_len:
        return label[:max_len - 1] + "…"
    return label


class GraphBuilder:
    """知识图谱构建器"""

    def build_from_data(
        self,
        book_id: str,
        units: list,
        chapters: list,
        mastery_records: list = None,
    ) -> KnowledgeGraph:
        """
        从知识单元和章节数据构建图谱。

        参数:
            book_id: 书籍ID
            units: 知识单元列表（字典或对象）
            chapters: 章节列表（字典或对象）
            mastery_records: 掌握度记录列表（可选）

        返回:
            KnowledgeGraph
        """
        # 构建掌握度映射: unit_id -> {score, level}
        mastery_map = {}
        if mastery_records:
            for mr in mastery_records:
                unit_id = mr.get("knowledge_unit_id") or mr.get("unit_id")
                if unit_id:
                    mastery_map[unit_id] = {
                        "score": mr.get("mastery_score", 0.0),
                        "level": mr.get("mastery_level", "beginner"),
                    }

        nodes: List[KGNode] = []
        edges: List[KGEdge] = []

        # 1. 创建 chapter 节点
        chapter_nodes = {}
        for ch in chapters:
            node = self._create_chapter_node(ch, book_id)
            chapter_nodes[_get_id(ch)] = node
            nodes.append(node)

        # 2. 创建 unit 节点
        unit_nodes = {}
        for unit in units:
            unit_id = _get_id(unit)
            unit_node = self._create_unit_node(unit, book_id, mastery_map)
            unit_nodes[unit_id] = unit_node
            nodes.append(unit_node)

        # 3. 使用 RelationDetector 检测关系
        detector = RelationDetector()
        edges.extend(detector.detect_part_of(units, chapters))
        edges.extend(detector.detect_similar(units))
        edges.extend(detector.detect_dependencies(units))

        # 4. 提取概念 → 创建 concept 节点
        concept_set: dict[str, KGNode] = {}
        concept_to_units: dict[str, list[str]] = {}
        for unit in units:
            unit_id = _get_id(unit)
            concepts = _get_concepts(unit)
            for concept_name in concepts:
                if concept_name not in concept_set:
                    concept_node = self._create_concept_node(concept_name, book_id)
                    concept_set[concept_name] = concept_node
                    nodes.append(concept_node)

                # 记录概念归属，供概念间共现分析使用
                concept_to_units.setdefault(concept_name, []).append(unit_id)

                # unit 关联 concept
                edges.append(KGEdge(
                    source_id=unit_id,
                    target_id=concept_set[concept_name].id,
                    relation_type="related",
                    weight=0.8,
                ))

        # 概念间共现关联：跨章节同现的概念视为 similar_to
        # 为 AID 宏观跨章节聚类提供概念级依据
        concept_node_ids = {name: node.id for name, node in concept_set.items()}
        edges.extend(detector.detect_concept_associations(
            concept_to_units, concept_node_ids
        ))

        # 5. 关联掌握度 → 更新节点颜色/大小
        for node in nodes:
            if node.node_type == "unit":
                mastery = mastery_map.get(node.id, {})
                node.mastery_score = mastery.get("score")
                node.mastery_level = mastery.get("level")
            node.color = self._calc_node_color(node.mastery_score)
            node.size = self._calc_node_size(node.importance_score)

        # 6. 计算统计信息
        stats = self._calc_stats(nodes, edges)

        return KnowledgeGraph(
            book_id=book_id,
            nodes=nodes,
            edges=edges,
            stats=stats,
        )

    def _create_unit_node(self, unit, book_id: str, mastery_map: dict = None) -> KGNode:
        """创建知识单元节点"""
        unit_id = _get_attr(unit, "id", "")
        mastery = (mastery_map or {}).get(unit_id, {})
        importance = _get_attr(unit, "importance_score")
        label = _get_attr(unit, "title", "未命名单元")
        return KGNode(
            id=unit_id,
            node_type="unit",
            label=label,
            short_label=_make_short_label(label, "unit"),
            book_id=book_id,
            content_summary=_get_attr(unit, "summary"),
            difficulty_level=_get_attr(unit, "difficulty_level"),
            importance_score=importance,
            mastery_score=mastery.get("score"),
            mastery_level=mastery.get("level"),
            size=1.0,
        )

    def _create_concept_node(self, concept: str, book_id: str) -> KGNode:
        """创建概念节点"""
        return KGNode(
            node_type="concept",
            label=concept,
            short_label=_make_short_label(concept, "concept"),
            book_id=book_id,
            size=0.8,
        )

    def _create_chapter_node(self, chapter, book_id: str) -> KGNode:
        """创建章节节点"""
        label = _get_attr(chapter, "title", "未命名章节")
        return KGNode(
            id=_get_attr(chapter, "id", ""),
            node_type="chapter",
            label=label,
            short_label=_make_short_label(label, "chapter"),
            book_id=book_id,
            size=1.5,
        )

    def _calc_node_color(self, mastery_score: Optional[float]) -> str:
        """根据掌握度计算颜色：红(低) → 黄(中) → 绿(高)，对齐5级掌握度体系"""
        if mastery_score is None:
            return "#999999"  # 灰色表示无数据
        if mastery_score < 0.20:
            return "#FF4444"  # 红色 - beginner
        elif mastery_score < 0.40:
            return "#FF8800"  # 橙色 - learning
        elif mastery_score < 0.65:
            return "#FFAA00"  # 橙黄 - familiar
        elif mastery_score < 0.85:
            return "#AADD00"  # 黄绿 - proficient
        else:
            return "#44BB44"  # 绿色 - mastered

    def _calc_node_size(self, importance: Optional[float]) -> float:
        """根据重要度计算节点大小"""
        if importance is None:
            return 1.0
        # 映射到 0.5 - 3.0 范围
        return 0.5 + importance * 2.5

    def _calc_stats(self, nodes: List[KGNode], edges: List[KGEdge]) -> GraphStats:
        """计算图谱统计信息"""
        node_type_counts = Counter(n.node_type for n in nodes)
        edge_type_counts = Counter(e.relation_type for e in edges)

        total_nodes = len(nodes)
        total_edges = len(edges)

        # 平均连接数 = 边数 * 2 / 节点数（每条边连接两个节点）
        avg_connections = (total_edges * 2 / total_nodes) if total_nodes > 0 else 0.0

        return GraphStats(
            total_nodes=total_nodes,
            total_edges=total_edges,
            node_type_counts=dict(node_type_counts),
            edge_type_counts=dict(edge_type_counts),
            avg_connections=round(avg_connections, 2),
        )


# ---- 辅助函数 ----

def _get_attr(obj, attr: str, default=None):
    """兼容字典和对象获取属性"""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _get_id(obj) -> str:
    """获取对象ID"""
    return str(_get_attr(obj, "id", ""))


def _get_concepts(unit) -> list:
    """从单元中提取概念名称列表（字符串）"""
    concepts = _get_attr(unit, "concepts")
    if concepts is None:
        return []
    if isinstance(concepts, str):
        try:
            import json
            concepts = json.loads(concepts)
        except (json.JSONDecodeError, TypeError):
            return [c.strip() for c in concepts.split(",") if c.strip()]
    if isinstance(concepts, list):
        # 兼容两种格式：纯字符串列表 或 结构化对象列表
        result = []
        for c in concepts:
            if isinstance(c, dict):
                name = c.get("name", "")
                if name:
                    result.append(name)
            elif isinstance(c, str) and c.strip():
                result.append(c.strip())
        return result
    return []
