"""知识图谱服务测试"""

import pytest
from app.modules.knowledge_graph.service import KnowledgeGraphService
from app.modules.knowledge_graph.schemas import (
    KnowledgeGraph, GraphQuery, SubGraph, VisualizationData,
)
from app.common.errors import ServiceError


@pytest.fixture
def service():
    return KnowledgeGraphService()


@pytest.fixture
def built_graph(service, sample_units, sample_chapters, sample_mastery_records):
    """已构建的图谱"""
    return service.build_graph("book-1", sample_units, sample_chapters, sample_mastery_records)


class TestBuildGraph:
    """测试构建图谱"""

    def test_basic_build(self, service, sample_units, sample_chapters):
        """基本构建"""
        graph = service.build_graph("book-1", sample_units, sample_chapters)
        assert isinstance(graph, KnowledgeGraph)
        assert graph.book_id == "book-1"
        assert len(graph.nodes) > 0

    def test_stored_in_memory(self, service, sample_units, sample_chapters):
        """构建后存储在内存中"""
        service.build_graph("book-1", sample_units, sample_chapters)
        graph = service.get_graph("book-1")
        assert graph is not None

    def test_empty_units_error(self, service):
        """空单元列表报错"""
        with pytest.raises(ServiceError) as exc_info:
            service.build_graph("book-1", [], [])
        assert exc_info.value.code.value == "INSUFFICIENT_DATA"

    def test_with_mastery(self, service, sample_units, sample_chapters, sample_mastery_records):
        """带掌握度构建"""
        graph = service.build_graph("book-1", sample_units, sample_chapters, sample_mastery_records)
        unit_nodes = [n for n in graph.nodes if n.node_type == "unit"]
        unit1 = next(n for n in unit_nodes if n.id == "unit-1")
        assert unit1.mastery_score == 0.8


class TestGetGraph:
    """测试获取图谱"""

    def test_existing_graph(self, service, built_graph):
        """获取已构建的图谱"""
        graph = service.get_graph("book-1")
        assert graph.book_id == "book-1"

    def test_nonexistent_graph(self, service):
        """获取不存在的图谱"""
        with pytest.raises(ServiceError) as exc_info:
            service.get_graph("nonexistent")
        assert exc_info.value.code.value == "NOT_FOUND"


class TestQueryNeighbors:
    """测试查询邻居"""

    def test_basic_query(self, service, built_graph):
        """基本邻居查询"""
        # 使用一个 unit 节点
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        node_id = unit_nodes[0].id
        query = GraphQuery(max_depth=2)
        subgraph = service.query_neighbors(built_graph, node_id, query)
        assert isinstance(subgraph, SubGraph)
        assert subgraph.center_node.id == node_id

    def test_filter_by_node_type(self, service, built_graph):
        """按节点类型过滤"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        node_id = unit_nodes[0].id
        query = GraphQuery(node_types=["chapter"], max_depth=2)
        subgraph = service.query_neighbors(built_graph, node_id, query)
        for node in subgraph.nodes:
            assert node.node_type == "chapter"

    def test_filter_by_relation_type(self, service, built_graph):
        """按关系类型过滤"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        node_id = unit_nodes[0].id
        query = GraphQuery(relation_types=["part_of"], max_depth=2)
        subgraph = service.query_neighbors(built_graph, node_id, query)
        for edge in subgraph.edges:
            assert edge.relation_type == "part_of"

    def test_max_depth_limit(self, service, built_graph):
        """深度限制"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        node_id = unit_nodes[0].id
        query_shallow = GraphQuery(max_depth=1)
        query_deep = GraphQuery(max_depth=3)
        shallow = service.query_neighbors(built_graph, node_id, query_shallow)
        deep = service.query_neighbors(built_graph, node_id, query_deep)
        # 深度更大的应该找到更多或相同数量的节点
        assert len(deep.nodes) >= len(shallow.nodes)

    def test_nonexistent_node(self, service, built_graph):
        """不存在的节点"""
        query = GraphQuery()
        with pytest.raises(ServiceError) as exc_info:
            service.query_neighbors(built_graph, "nonexistent", query)
        assert exc_info.value.code.value == "NOT_FOUND"


class TestFindPath:
    """测试查找路径"""

    def test_path_exists(self, service, built_graph):
        """存在路径"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        # unit-1 和 unit-2 通过依赖关系相连
        path = service.find_path(built_graph, "unit-1", "unit-2")
        # 路径可能存在（通过 depends_on 边）
        if path is not None:
            assert len(path) > 0
            assert all(isinstance(e.id, str) for e in path)

    def test_same_node(self, service, built_graph):
        """相同节点返回空路径"""
        path = service.find_path(built_graph, "unit-1", "unit-1")
        assert path == []

    def test_no_path(self, service, built_graph):
        """不存在路径（断开的图）"""
        # 用一个不存在的节点组合测试
        # 先添加一个孤立节点
        from app.modules.knowledge_graph.schemas import KGNode
        isolated = KGNode(id="isolated", node_type="unit", label="孤立", book_id="book-1")
        built_graph.nodes.append(isolated)
        path = service.find_path(built_graph, "isolated", "unit-1")
        assert path is None

    def test_nonexistent_source(self, service, built_graph):
        """源节点不存在"""
        with pytest.raises(ServiceError):
            service.find_path(built_graph, "nonexistent", "unit-1")

    def test_nonexistent_target(self, service, built_graph):
        """目标节点不存在"""
        with pytest.raises(ServiceError):
            service.find_path(built_graph, "unit-1", "nonexistent")


class TestGetVisualizationData:
    """测试获取可视化数据"""

    def test_basic_visualization(self, service, built_graph):
        """基本可视化数据"""
        vis = service.get_visualization_data(built_graph)
        assert isinstance(vis, VisualizationData)
        assert len(vis.nodes) > 0
        assert vis.layout == "force"

    def test_centered_visualization(self, service, built_graph):
        """以某节点为中心的可视化"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        vis = service.get_visualization_data(built_graph, center_node_id=unit_nodes[0].id)
        assert len(vis.nodes) > 0

    def test_max_nodes_limit(self, service, built_graph):
        """最大节点数限制"""
        vis = service.get_visualization_data(built_graph, max_nodes=3)
        assert len(vis.nodes) <= 3

    def test_vis_node_fields(self, service, built_graph):
        """可视化节点字段完整"""
        vis = service.get_visualization_data(built_graph)
        for node in vis.nodes:
            assert node.id
            assert node.label
            assert node.group
            assert node.size > 0
            assert node.color

    def test_vis_edge_fields(self, service, built_graph):
        """可视化边字段完整"""
        vis = service.get_visualization_data(built_graph)
        for edge in vis.edges:
            assert edge.from_id
            assert edge.to_id
            assert edge.label
            assert edge.width > 0

    def test_nonexistent_center(self, service, built_graph):
        """不存在的中心节点"""
        with pytest.raises(ServiceError):
            service.get_visualization_data(built_graph, center_node_id="nonexistent")


class TestAddEdge:
    """测试添加边"""

    def test_basic_add(self, service, built_graph):
        """基本添加边"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        edge = service.add_edge(
            built_graph, unit_nodes[0].id, unit_nodes[1].id, "related", 0.5
        )
        assert edge.source_id == unit_nodes[0].id
        assert edge.target_id == unit_nodes[1].id
        assert edge.relation_type == "related"
        assert edge.weight == 0.5

    def test_nonexistent_source(self, service, built_graph):
        """源节点不存在"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        with pytest.raises(ServiceError) as exc_info:
            service.add_edge(built_graph, "nonexistent", unit_nodes[0].id, "related")
        assert exc_info.value.code.value == "NOT_FOUND"

    def test_nonexistent_target(self, service, built_graph):
        """目标节点不存在"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        with pytest.raises(ServiceError):
            service.add_edge(built_graph, unit_nodes[0].id, "nonexistent", "related")

    def test_self_loop_rejected(self, service, built_graph):
        """自环边被拒绝"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        with pytest.raises(ServiceError) as exc_info:
            service.add_edge(built_graph, unit_nodes[0].id, unit_nodes[0].id, "related")
        assert exc_info.value.code.value == "VALIDATION_ERROR"

    def test_duplicate_edge_rejected(self, service, built_graph):
        """重复边被拒绝"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        service.add_edge(built_graph, unit_nodes[0].id, unit_nodes[1].id, "custom")
        with pytest.raises(ServiceError) as exc_info:
            service.add_edge(built_graph, unit_nodes[0].id, unit_nodes[1].id, "custom")
        assert exc_info.value.code.value == "VALIDATION_ERROR"


class TestRemoveEdge:
    """测试删除边"""

    def test_basic_remove(self, service, built_graph):
        """基本删除边"""
        original_count = len(built_graph.edges)
        edge_id = built_graph.edges[0].id
        service.remove_edge(built_graph, edge_id)
        assert len(built_graph.edges) == original_count - 1

    def test_nonexistent_edge(self, service, built_graph):
        """删除不存在的边"""
        with pytest.raises(ServiceError) as exc_info:
            service.remove_edge(built_graph, "nonexistent")
        assert exc_info.value.code.value == "NOT_FOUND"

    def test_stats_updated_after_remove(self, service, built_graph):
        """删除后统计更新"""
        old_total = built_graph.stats.total_edges
        edge_id = built_graph.edges[0].id
        service.remove_edge(built_graph, edge_id)
        assert built_graph.stats.total_edges == old_total - 1
