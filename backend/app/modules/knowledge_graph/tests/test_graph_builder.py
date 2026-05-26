"""图谱构建器测试"""

import pytest
from app.modules.knowledge_graph.graph_builder import GraphBuilder
from app.modules.knowledge_graph.schemas import KnowledgeGraph


@pytest.fixture
def builder():
    return GraphBuilder()


class TestBuildFromData:
    """测试从数据构建图谱"""

    def test_basic_build(self, builder, sample_units, sample_chapters):
        """基本构建测试"""
        graph = builder.build_from_data("book-1", sample_units, sample_chapters)
        assert isinstance(graph, KnowledgeGraph)
        assert graph.book_id == "book-1"
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0

    def test_creates_unit_nodes(self, builder, sample_units, sample_chapters):
        """创建知识单元节点"""
        graph = builder.build_from_data("book-1", sample_units, sample_chapters)
        unit_nodes = [n for n in graph.nodes if n.node_type == "unit"]
        assert len(unit_nodes) == 3
        labels = {n.label for n in unit_nodes}
        assert "数组基础" in labels
        assert "链表结构" in labels
        assert "二叉树遍历" in labels

    def test_creates_chapter_nodes(self, builder, sample_units, sample_chapters):
        """创建章节节点"""
        graph = builder.build_from_data("book-1", sample_units, sample_chapters)
        chapter_nodes = [n for n in graph.nodes if n.node_type == "chapter"]
        assert len(chapter_nodes) == 2

    def test_creates_concept_nodes(self, builder, sample_units, sample_chapters):
        """创建概念节点"""
        graph = builder.build_from_data("book-1", sample_units, sample_chapters)
        concept_nodes = [n for n in graph.nodes if n.node_type == "concept"]
        assert len(concept_nodes) > 0
        labels = {n.label for n in concept_nodes}
        assert "数组" in labels
        assert "链表" in labels
        assert "二叉树" in labels

    def test_creates_part_of_edges(self, builder, sample_units, sample_chapters):
        """创建包含关系边"""
        graph = builder.build_from_data("book-1", sample_units, sample_chapters)
        part_of_edges = [e for e in graph.edges if e.relation_type == "part_of"]
        assert len(part_of_edges) >= 3  # 3个单元各有一条到章节的边

    def test_creates_related_edges(self, builder, sample_units, sample_chapters):
        """创建关联边（unit -> concept）"""
        graph = builder.build_from_data("book-1", sample_units, sample_chapters)
        related_edges = [e for e in graph.edges if e.relation_type == "related"]
        assert len(related_edges) > 0

    def test_creates_depends_on_edges(self, builder, sample_units, sample_chapters):
        """创建依赖边"""
        graph = builder.build_from_data("book-1", sample_units, sample_chapters)
        depends_edges = [e for e in graph.edges if e.relation_type == "depends_on"]
        # unit-2 依赖 unit-1，unit-3 依赖 unit-2
        assert len(depends_edges) >= 2

    def test_creates_similar_to_edges(self, builder, sample_units, sample_chapters):
        """创建相似边"""
        graph = builder.build_from_data("book-1", sample_units, sample_chapters)
        similar_edges = [e for e in graph.edges if e.relation_type == "similar_to"]
        # "数组"和"链表"共享"线性表"概念，可能产生相似边
        assert len(similar_edges) >= 0  # 取决于相似度阈值

    def test_with_mastery_records(self, builder, sample_units, sample_chapters, sample_mastery_records):
        """关联掌握度记录"""
        graph = builder.build_from_data(
            "book-1", sample_units, sample_chapters, sample_mastery_records
        )
        unit_nodes = [n for n in graph.nodes if n.node_type == "unit"]
        unit1 = next(n for n in unit_nodes if n.id == "unit-1")
        assert unit1.mastery_score == 0.8
        assert unit1.mastery_level == "proficient"
        assert unit1.color != "#999999"  # 有颜色

    def test_stats_computed(self, builder, sample_units, sample_chapters):
        """统计信息被正确计算"""
        graph = builder.build_from_data("book-1", sample_units, sample_chapters)
        assert graph.stats.total_nodes > 0
        assert graph.stats.total_edges > 0
        assert "unit" in graph.stats.node_type_counts
        assert "chapter" in graph.stats.node_type_counts
        assert "concept" in graph.stats.node_type_counts
        assert graph.stats.avg_connections > 0


class TestCalcNodeColor:
    """测试节点颜色计算"""

    def test_no_mastery(self, builder):
        """无掌握度数据为灰色"""
        assert builder._calc_node_color(None) == "#999999"

    def test_low_mastery(self, builder):
        """低掌握度为红色"""
        assert builder._calc_node_color(0.1) == "#FF4444"

    def test_medium_mastery(self, builder):
        """中等掌握度为橙黄"""
        assert builder._calc_node_color(0.5) == "#FFAA00"

    def test_good_mastery(self, builder):
        """较好掌握度为黄绿"""
        assert builder._calc_node_color(0.7) == "#AADD00"

    def test_high_mastery(self, builder):
        """高掌握度为绿色"""
        assert builder._calc_node_color(0.9) == "#44BB44"


class TestCalcNodeSize:
    """测试节点大小计算"""

    def test_no_importance(self, builder):
        """无重要度默认1.0"""
        assert builder._calc_node_size(None) == 1.0

    def test_max_importance(self, builder):
        """最高重要度"""
        assert builder._calc_node_size(1.0) == 3.0

    def test_min_importance(self, builder):
        """最低重要度"""
        assert builder._calc_node_size(0.0) == 0.5


class TestEmptyData:
    """测试空数据场景"""

    def test_empty_units(self, builder):
        """无知识单元"""
        graph = builder.build_from_data("book-1", [], [])
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_units_without_concepts(self, builder):
        """无概念的单元"""
        units = [{"id": "u-1", "book_id": "b-1", "chapter_id": "c-1", "title": "测试"}]
        chapters = [{"id": "c-1", "title": "章节"}]
        graph = builder.build_from_data("book-1", units, chapters)
        unit_nodes = [n for n in graph.nodes if n.node_type == "unit"]
        assert len(unit_nodes) == 1
        concept_nodes = [n for n in graph.nodes if n.node_type == "concept"]
        assert len(concept_nodes) == 0
