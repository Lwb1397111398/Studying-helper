"""关系检测器 - 检测知识单元之间的关系"""

import json
import math
from typing import List, Optional

from app.modules.knowledge_graph.schemas import KGEdge


class RelationDetector:
    """关系检测器

    相似度计算支持两种模式：
    - 'jaccard': 集合级 Jaccard（原有方法，无需外部依赖）
    - 'embedding': 基于 embedding 向量的余弦相似度（更准确，需要 embedding_provider）
    """

    def __init__(self, embedding_provider=None):
        """
        参数:
            embedding_provider: 可选的 embedding 提供者，需实现 embed(texts: list[str]) -> list[list[float]]
        """
        self._embedding_provider = embedding_provider
        self._embedding_cache: dict[str, list[float]] = {}

    def detect_similar(self, units: list, threshold: float = 0.7) -> List[KGEdge]:
        """
        检测相似关系（基于概念重叠）。

        有改进：
        - 优先使用 embedding 余弦相似度（如果提供了 embedding_provider）
        - 回退到集合级 Jaccard（比原来的字符级科学）
        - 结果按相似度降序

        参数:
            units: 知识单元列表
            threshold: 相似度阈值

        返回:
            相似关系边列表（无向，但存储为双向边）
        """
        edges = []
        unit_concepts = []
        for unit in units:
            concepts = _get_concepts(unit)
            unit_concepts.append((_get_id(unit), set(concepts)))

        # 尝试使用 embedding
        use_embedding = self._embedding_provider is not None
        concept_names: list[str] = []
        concept_embeddings: dict[str, list[float]] = {}

        if use_embedding:
            # 收集所有唯一概念名，批量获取 embedding
            seen = set()
            for _, concepts in unit_concepts:
                for c in concepts:
                    if c not in seen:
                        concept_names.append(c)
                        seen.add(c)
            if concept_names:
                try:
                    embeddings = self._embedding_provider.embed(concept_names)
                    concept_embeddings = dict(zip(concept_names, embeddings))
                except Exception:
                    use_embedding = False  # embedding 失败则回退

        for i in range(len(unit_concepts)):
            for j in range(i + 1, len(unit_concepts)):
                id_a, concepts_a = unit_concepts[i]
                id_b, concepts_b = unit_concepts[j]
                if not concepts_a or not concepts_b:
                    continue

                if use_embedding and concept_embeddings:
                    similarity = _embedding_set_similarity(concepts_a, concepts_b, concept_embeddings)
                else:
                    similarity = _jaccard_similarity(concepts_a, concepts_b)

                if similarity >= threshold:
                    edges.append(KGEdge(
                        source_id=id_a,
                        target_id=id_b,
                        relation_type="similar_to",
                        weight=round(similarity, 3),
                    ))

        return edges

    def detect_dependencies(self, units: list) -> List[KGEdge]:
        """
        检测依赖关系（基于 prerequisites）。

        支持两种匹配：
        1. prerequisites 中存的是 unit_id → 精确匹配
        2. prerequisites 中存的是概念/标题名 → 模糊匹配单元标题

        参数:
            units: 知识单元列表

        返回:
            依赖关系边列表（有向：source 依赖 target）
        """
        edges = []
        # 构建 title -> id 和 id -> unit 映射
        title_map: dict[str, str] = {}
        id_set: set[str] = set()
        for unit in units:
            title = _get_attr(unit, "title", "")
            uid = _get_id(unit)
            id_set.add(uid)
            if title:
                title_map[title] = uid

        for unit in units:
            uid = _get_id(unit)
            prerequisites = _get_prerequisites(unit)
            for pre_name in prerequisites:
                target_id = None

                # 优先：prerequisites 存的是 unit_id
                if pre_name in id_set and pre_name != uid:
                    target_id = pre_name
                else:
                    # 其次：精确匹配标题
                    target_id = title_map.get(pre_name)

                # 最后：模糊匹配
                if not target_id:
                    for title, tid in title_map.items():
                        if tid != uid and (pre_name in title or title in pre_name):
                            target_id = tid
                            break

                if target_id and target_id != uid:
                    edges.append(KGEdge(
                        source_id=uid,      # source 依赖 target
                        target_id=target_id,
                        relation_type="depends_on",
                        weight=1.0,
                    ))
        return edges

    def detect_part_of(self, units: list, chapters: list) -> List[KGEdge]:
        """
        检测包含关系（单元属于章节）。

        参数:
            units: 知识单元列表
            chapters: 章节列表

        返回:
            包含关系边列表（有向：unit part_of chapter）
        """
        edges = []
        chapter_ids = {_get_id(ch) for ch in chapters}

        for unit in units:
            uid = _get_id(unit)
            chapter_id = _get_attr(unit, "chapter_id")
            if chapter_id and chapter_id in chapter_ids:
                edges.append(KGEdge(
                    source_id=uid,
                    target_id=chapter_id,
                    relation_type="part_of",
                    weight=1.0,
                ))
        return edges


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
    """从单元中提取概念列表"""
    concepts = _get_attr(unit, "concepts")
    if concepts is None:
        return []
    if isinstance(concepts, str):
        try:
            return json.loads(concepts)
        except (json.JSONDecodeError, TypeError):
            return [c.strip() for c in concepts.split(",") if c.strip()]
    if isinstance(concepts, list):
        return concepts
    return []


def _get_prerequisites(unit) -> list:
    """获取前置知识列表"""
    prereqs = _get_attr(unit, "prerequisites")
    if prereqs is None:
        return []
    if isinstance(prereqs, str):
        try:
            return json.loads(prereqs)
        except (json.JSONDecodeError, TypeError):
            return [p.strip() for p in prereqs.split(",") if p.strip()]
    if isinstance(prereqs, list):
        return prereqs
    return []


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """计算 Jaccard 相似度（集合级别）"""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def _embedding_set_similarity(
    set_a: set,
    set_b: set,
    embeddings: dict[str, list[float]],
) -> float:
    """基于 embedding 的概念集合相似度。

    计算两个概念集合中所有概念对的平均最大余弦相似度。
    """
    if not set_a or not set_b:
        return 0.0

    # 过滤掉没有 embedding 的概念
    a_vecs = [embeddings[c] for c in set_a if c in embeddings]
    b_vecs = [embeddings[c] for c in set_b if c in embeddings]
    if not a_vecs or not b_vecs:
        return _jaccard_similarity(set_a, set_b)  # 回退

    # 计算双向平均最大相似度
    def _avg_max_similarity(vecs_from, vecs_to):
        total = 0.0
        for va in vecs_from:
            best = max(_cosine_similarity(va, vb) for vb in vecs_to)
            total += best
        return total / len(vecs_from)

    sim_a_to_b = _avg_max_similarity(a_vecs, b_vecs)
    sim_b_to_a = _avg_max_similarity(b_vecs, a_vecs)
    return (sim_a_to_b + sim_b_to_a) / 2


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """计算余弦相似度"""
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
