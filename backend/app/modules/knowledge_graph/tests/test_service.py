"""知识图谱服务测试"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.database import Base
from app.modules.knowledge_graph.service import KnowledgeGraphService
from app.modules.knowledge_graph.schemas import (
    KnowledgeGraph, GraphQuery, SubGraph, VisualizationData,
)
from app.common.errors import ServiceError


@pytest_asyncio.fixture
async def db_session():
    """创建内存数据库"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def service(db_session):
    return KnowledgeGraphService(db_session)


@pytest_asyncio.fixture
async def built_graph(service, sample_units, sample_chapters, sample_mastery_records):
    """已构建的图谱"""
    return await service.build_graph("book-1", sample_units, sample_chapters, sample_mastery_records)


class TestBuildGraph:
    """测试构建图谱"""

    @pytest.mark.asyncio
    async def test_basic_build(self, service, sample_units, sample_chapters):
        """基本构建"""
        graph = await service.build_graph("book-1", sample_units, sample_chapters)
        assert isinstance(graph, KnowledgeGraph)
        assert graph.book_id == "book-1"
        assert len(graph.nodes) > 0

    @pytest.mark.asyncio
    async def test_stored_in_db(self, service, sample_units, sample_chapters):
        """构建后持久化到数据库"""
        await service.build_graph("book-1", sample_units, sample_chapters)
        graph = await service.get_graph("book-1")
        assert graph is not None
        assert graph.book_id == "book-1"

    @pytest.mark.asyncio
    async def test_empty_units_error(self, service):
        """空单元列表报错"""
        with pytest.raises(ServiceError) as exc_info:
            await service.build_graph("book-1", [], [])
        assert exc_info.value.code.value == "INSUFFICIENT_DATA"

    @pytest.mark.asyncio
    async def test_with_mastery(self, service, sample_units, sample_chapters, sample_mastery_records):
        """带掌握度构建"""
        graph = await service.build_graph("book-1", sample_units, sample_chapters, sample_mastery_records)
        unit_nodes = [n for n in graph.nodes if n.node_type == "unit"]
        unit1 = next(n for n in unit_nodes if n.id == "unit-1")
        assert unit1.mastery_score == 0.8


class TestGetGraph:
    """测试获取图谱"""

    @pytest.mark.asyncio
    async def test_existing_graph(self, service, built_graph):
        """获取已构建的图谱"""
        graph = await service.get_graph("book-1")
        assert graph.book_id == "book-1"

    @pytest.mark.asyncio
    async def test_nonexistent_graph(self, service):
        """获取不存在的图谱"""
        with pytest.raises(ServiceError) as exc_info:
            await service.get_graph("nonexistent")
        assert exc_info.value.code.value == "NOT_FOUND"


class TestQueryNeighbors:
    """测试查询邻居"""

    @pytest.mark.asyncio
    async def test_basic_query(self, service, built_graph):
        """基本邻居查询"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        node_id = unit_nodes[0].id
        query = GraphQuery(max_depth=2)
        subgraph = await service.query_neighbors("book-1", node_id, query)
        assert isinstance(subgraph, SubGraph)
        assert subgraph.center_node.id == node_id

    @pytest.mark.asyncio
    async def test_filter_by_node_type(self, service, built_graph):
        """按节点类型过滤"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        node_id = unit_nodes[0].id
        query = GraphQuery(node_types=["chapter"], max_depth=2)
        subgraph = await service.query_neighbors("book-1", node_id, query)
        for node in subgraph.nodes:
            assert node.node_type == "chapter"

    @pytest.mark.asyncio
    async def test_filter_by_relation_type(self, service, built_graph):
        """按关系类型过滤"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        node_id = unit_nodes[0].id
        query = GraphQuery(relation_types=["part_of"], max_depth=2)
        subgraph = await service.query_neighbors("book-1", node_id, query)
        for edge in subgraph.edges:
            assert edge.relation_type == "part_of"

    @pytest.mark.asyncio
    async def test_max_depth_limit(self, service, built_graph):
        """深度限制"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        node_id = unit_nodes[0].id
        query_shallow = GraphQuery(max_depth=1)
        query_deep = GraphQuery(max_depth=3)
        shallow = await service.query_neighbors("book-1", node_id, query_shallow)
        deep = await service.query_neighbors("book-1", node_id, query_deep)
        assert len(deep.nodes) >= len(shallow.nodes)

    @pytest.mark.asyncio
    async def test_nonexistent_node(self, service, built_graph):
        """不存在的节点"""
        query = GraphQuery()
        with pytest.raises(ServiceError) as exc_info:
            await service.query_neighbors("book-1", "nonexistent", query)
        assert exc_info.value.code.value == "NOT_FOUND"


class TestFindPath:
    """测试查找路径"""

    @pytest.mark.asyncio
    async def test_path_exists(self, service, built_graph):
        """存在路径"""
        path = await service.find_path("book-1", "unit-1", "unit-2")
        if path is not None:
            assert len(path) > 0
            assert all(isinstance(e.id, str) for e in path)

    @pytest.mark.asyncio
    async def test_same_node(self, service, built_graph):
        """相同节点返回空路径"""
        path = await service.find_path("book-1", "unit-1", "unit-1")
        assert path == []

    @pytest.mark.asyncio
    async def test_no_path(self, service, built_graph):
        """不存在路径（目标节点不存在）"""
        with pytest.raises(ServiceError):
            await service.find_path("book-1", "unit-1", "nonexistent")

    @pytest.mark.asyncio
    async def test_nonexistent_source(self, service, built_graph):
        """源节点不存在"""
        with pytest.raises(ServiceError):
            await service.find_path("book-1", "nonexistent", "unit-1")

    @pytest.mark.asyncio
    async def test_nonexistent_target(self, service, built_graph):
        """目标节点不存在"""
        with pytest.raises(ServiceError):
            await service.find_path("book-1", "unit-1", "nonexistent")


class TestGetVisualizationData:
    """测试获取可视化数据"""

    @pytest.mark.asyncio
    async def test_basic_visualization(self, service, built_graph):
        """基本可视化数据"""
        vis = await service.get_visualization_data("book-1")
        assert isinstance(vis, VisualizationData)
        assert len(vis.nodes) > 0
        assert vis.layout == "force"

    @pytest.mark.asyncio
    async def test_centered_visualization(self, service, built_graph):
        """以某节点为中心的可视化"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        vis = await service.get_visualization_data("book-1", center_node_id=unit_nodes[0].id)
        assert len(vis.nodes) > 0

    @pytest.mark.asyncio
    async def test_max_nodes_limit(self, service, built_graph):
        """最大节点数限制"""
        vis = await service.get_visualization_data("book-1", max_nodes=3)
        assert len(vis.nodes) <= 3

    @pytest.mark.asyncio
    async def test_vis_node_fields(self, service, built_graph):
        """可视化节点字段完整"""
        vis = await service.get_visualization_data("book-1")
        for node in vis.nodes:
            assert node.id
            assert node.label
            assert node.group
            assert node.size > 0
            assert node.color

    @pytest.mark.asyncio
    async def test_vis_edge_fields(self, service, built_graph):
        """可视化边字段完整"""
        vis = await service.get_visualization_data("book-1")
        for edge in vis.edges:
            assert edge.from_id
            assert edge.to_id
            assert edge.label
            assert edge.width > 0

    @pytest.mark.asyncio
    async def test_nonexistent_center(self, service, built_graph):
        """不存在的中心节点"""
        with pytest.raises(ServiceError):
            await service.get_visualization_data("book-1", center_node_id="nonexistent")


class TestAddEdge:
    """测试添加边"""

    @pytest.mark.asyncio
    async def test_basic_add(self, service, built_graph):
        """基本添加边"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        edge = await service.add_edge(
            "book-1", unit_nodes[0].id, unit_nodes[1].id, "related", 0.5
        )
        assert edge.source_id == unit_nodes[0].id
        assert edge.target_id == unit_nodes[1].id
        assert edge.relation_type == "related"
        assert edge.weight == 0.5

    @pytest.mark.asyncio
    async def test_nonexistent_source(self, service, built_graph):
        """源节点不存在"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        with pytest.raises(ServiceError) as exc_info:
            await service.add_edge("book-1", "nonexistent", unit_nodes[0].id, "related")
        assert exc_info.value.code.value == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_nonexistent_target(self, service, built_graph):
        """目标节点不存在"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        with pytest.raises(ServiceError):
            await service.add_edge("book-1", unit_nodes[0].id, "nonexistent", "related")

    @pytest.mark.asyncio
    async def test_self_loop_rejected(self, service, built_graph):
        """自环边被拒绝"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        with pytest.raises(ServiceError) as exc_info:
            await service.add_edge("book-1", unit_nodes[0].id, unit_nodes[0].id, "related")
        assert exc_info.value.code.value == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_duplicate_edge_rejected(self, service, built_graph):
        """重复边被拒绝"""
        unit_nodes = [n for n in built_graph.nodes if n.node_type == "unit"]
        await service.add_edge("book-1", unit_nodes[0].id, unit_nodes[1].id, "custom")
        with pytest.raises(ServiceError) as exc_info:
            await service.add_edge("book-1", unit_nodes[0].id, unit_nodes[1].id, "custom")
        assert exc_info.value.code.value == "VALIDATION_ERROR"


class TestRemoveEdge:
    """测试删除边"""

    @pytest.mark.asyncio
    async def test_basic_remove(self, service, built_graph):
        """基本删除边"""
        edge_id = built_graph.edges[0].id
        await service.remove_edge("book-1", edge_id)
        # 验证边已删除
        graph = await service.get_graph("book-1")
        remaining_ids = {e.id for e in graph.edges}
        assert edge_id not in remaining_ids

    @pytest.mark.asyncio
    async def test_nonexistent_edge(self, service, built_graph):
        """删除不存在的边"""
        with pytest.raises(ServiceError) as exc_info:
            await service.remove_edge("book-1", "nonexistent")
        assert exc_info.value.code.value == "NOT_FOUND"
