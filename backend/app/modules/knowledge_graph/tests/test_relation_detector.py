"""关系检测器测试"""

import pytest
from app.modules.knowledge_graph.relation_detector import RelationDetector


@pytest.fixture
def detector():
    return RelationDetector()


class TestDetectSimilar:
    """测试相似关系检测"""

    def test_detects_similar_units(self, detector):
        """检测概念重叠的相似单元（Jaccard: 交集1/并集5=0.2）"""
        units = [
            {"id": "u-1", "concepts": ["数组", "线性表", "随机访问"]},
            {"id": "u-2", "concepts": ["链表", "线性表", "指针"]},
        ]
        edges = detector.detect_similar(units, threshold=0.1)
        assert len(edges) == 1
        assert edges[0].relation_type == "similar_to"
        assert edges[0].source_id == "u-1"
        assert edges[0].target_id == "u-2"

    def test_no_similar_when_below_threshold(self, detector):
        """低于阈值不检测为相似"""
        units = [
            {"id": "u-1", "concepts": ["数组", "线性表"]},
            {"id": "u-2", "concepts": ["哈希", "映射"]},
        ]
        edges = detector.detect_similar(units, threshold=0.7)
        assert len(edges) == 0

    def test_empty_concepts(self, detector):
        """空概念不产生边"""
        units = [
            {"id": "u-1", "concepts": []},
            {"id": "u-2", "concepts": ["数组"]},
        ]
        edges = detector.detect_similar(units)
        assert len(edges) == 0

    def test_multiple_similar(self, detector):
        """多个相似单元"""
        units = [
            {"id": "u-1", "concepts": ["数组", "排序"]},
            {"id": "u-2", "concepts": ["数组", "查找"]},
            {"id": "u-3", "concepts": ["数组", "遍历"]},
        ]
        edges = detector.detect_similar(units, threshold=0.3)
        # 所有两两组合都共享"数组"
        assert len(edges) == 3


class TestDetectDependencies:
    """测试依赖关系检测"""

    def test_detects_prerequisites(self, detector):
        """检测前置知识依赖"""
        units = [
            {"id": "u-1", "title": "数组基础", "concepts": ["数组"]},
            {"id": "u-2", "title": "链表结构", "concepts": ["链表"], "prerequisites": ["数组基础"]},
        ]
        edges = detector.detect_dependencies(units)
        assert len(edges) == 1
        assert edges[0].relation_type == "depends_on"
        assert edges[0].source_id == "u-2"
        assert edges[0].target_id == "u-1"

    def test_no_prerequisites(self, detector):
        """无前置知识不产生边"""
        units = [
            {"id": "u-1", "title": "数组", "concepts": ["数组"]},
            {"id": "u-2", "title": "链表", "concepts": ["链表"]},
        ]
        edges = detector.detect_dependencies(units)
        assert len(edges) == 0

    def test_chained_dependencies(self, detector):
        """链式依赖"""
        units = [
            {"id": "u-1", "title": "数组", "concepts": ["数组"]},
            {"id": "u-2", "title": "链表", "concepts": ["链表"], "prerequisites": ["数组"]},
            {"id": "u-3", "title": "树", "concepts": ["树"], "prerequisites": ["链表"]},
        ]
        edges = detector.detect_dependencies(units)
        assert len(edges) == 2

    def test_nonexistent_prerequisite_ignored(self, detector):
        """不存在的前置知识被忽略"""
        units = [
            {"id": "u-1", "title": "数组", "prerequisites": ["不存在的知识"]},
        ]
        edges = detector.detect_dependencies(units)
        assert len(edges) == 0


class TestDetectPartOf:
    """测试包含关系检测"""

    def test_unit_belongs_to_chapter(self, detector):
        """单元属于章节"""
        units = [
            {"id": "u-1", "chapter_id": "ch-1", "title": "数组"},
            {"id": "u-2", "chapter_id": "ch-2", "title": "树"},
        ]
        chapters = [
            {"id": "ch-1", "title": "基础"},
            {"id": "ch-2", "title": "高级"},
        ]
        edges = detector.detect_part_of(units, chapters)
        assert len(edges) == 2
        for edge in edges:
            assert edge.relation_type == "part_of"

    def test_chapter_not_in_list_ignored(self, detector):
        """章节不在列表中被忽略"""
        units = [
            {"id": "u-1", "chapter_id": "ch-unknown", "title": "数组"},
        ]
        chapters = [
            {"id": "ch-1", "title": "基础"},
        ]
        edges = detector.detect_part_of(units, chapters)
        assert len(edges) == 0

    def test_no_chapter_id(self, detector):
        """无章节ID的单元"""
        units = [
            {"id": "u-1", "title": "数组"},
        ]
        chapters = [{"id": "ch-1", "title": "基础"}]
        edges = detector.detect_part_of(units, chapters)
        assert len(edges) == 0


class TestDetectConceptAssociations:
    """测试概念间共现关联检测（AID 跨章节聚类的概念级依据）"""

    def test_real_cooccurrence_produces_edge(self, detector):
        """两个概念共同出现在 2 个单元中应产出边"""
        concept_to_units = {
            "概念A": ["u-1", "u-2"],
            "概念B": ["u-1", "u-2"],
            "概念C": ["u-3"],
        }
        concept_node_ids = {name: f"node-{name}" for name in concept_to_units}
        edges = detector.detect_concept_associations(concept_to_units, concept_node_ids)

        # 概念A 与 概念B 共现于 u-1、u-2（共现2，>= 阈值2）
        similar_pairs = [
            (e.source_id, e.target_id) for e in edges if e.relation_type == "similar_to"
        ]
        assert ("node-概念A", "node-概念B") in similar_pairs
        assert ("node-概念B", "node-概念A") in similar_pairs  # 双向
        # 概念C 独占 u-3，无共现，不应出现
        assert all("node-概念C" not in pair for pair in similar_pairs)

    def test_below_threshold_no_edge(self, detector):
        """共现数低于阈值不产出边"""
        concept_to_units = {
            "概念A": ["u-1"],
            "概念B": ["u-1"],  # 与 A 共现1次 < 默认阈值2
        }
        concept_node_ids = {name: f"node-{name}" for name in concept_to_units}
        edges = detector.detect_concept_associations(
            concept_to_units, concept_node_ids, min_cooccurrence=2
        )
        assert len(edges) == 0

    def test_empty_input(self, detector):
        """空输入返回空列表"""
        assert detector.detect_concept_associations({}, {}) == []
        assert detector.detect_concept_associations({"A": ["u-1"]}, {}) == []

    def test_weight_is_jaccard(self, detector):
        """权重应为共现数/并集数（Jaccard 式）"""
        concept_to_units = {
            "A": ["u-1", "u-2", "u-3"],
            "B": ["u-1", "u-2"],  # 共现2，并集3 → 2/3
        }
        concept_node_ids = {"A": "nA", "B": "nB"}
        edges = detector.detect_concept_associations(
            concept_to_units, concept_node_ids, min_cooccurrence=2
        )
        weights = [e.weight for e in edges]
        assert round(2 / 3, 3) in weights
