"""知识图谱路由测试"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.knowledge_graph.router import router, kg_service


@pytest.fixture
def client():
    """创建测试客户端"""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def built_graph_payload(sample_units, sample_chapters, sample_mastery_records):
    """构建图谱请求载荷"""
    return {
        "units": sample_units,
        "chapters": sample_chapters,
        "mastery_records": sample_mastery_records,
    }


class TestBuildGraphAPI:
    """测试构建图谱API"""

    def test_basic_build(self, client, built_graph_payload):
        """基本构建"""
        resp = client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["book_id"] == "book-1"
        assert len(data["nodes"]) > 0

    def test_build_without_mastery(self, client, sample_units, sample_chapters):
        """不带掌握度构建"""
        resp = client.post(
            "/api/v1/knowledge-graph/book-2/build",
            json={"units": sample_units, "chapters": sample_chapters},
        )
        assert resp.status_code == 200

    def test_build_empty_units(self, client):
        """空单元列表"""
        resp = client.post(
            "/api/v1/knowledge-graph/book-3/build",
            json={"units": [], "chapters": []},
        )
        assert resp.status_code == 422


class TestGetGraphAPI:
    """测试获取图谱API"""

    def test_get_existing(self, client, built_graph_payload):
        """获取已构建的图谱"""
        client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        resp = client.get("/api/v1/knowledge-graph/book-1")
        assert resp.status_code == 200
        assert resp.json()["book_id"] == "book-1"

    def test_get_nonexistent(self, client):
        """获取不存在的图谱"""
        resp = client.get("/api/v1/knowledge-graph/nonexistent")
        assert resp.status_code == 404


class TestQueryNeighborsAPI:
    """测试查询邻居API"""

    def test_basic_query(self, client, built_graph_payload):
        """基本邻居查询"""
        client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        resp = client.get("/api/v1/knowledge-graph/book-1/neighbors/unit-1")
        assert resp.status_code == 200
        data = resp.json()
        assert "center_node" in data
        assert "nodes" in data
        assert "edges" in data

    def test_with_filters(self, client, built_graph_payload):
        """带过滤条件查询"""
        client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        resp = client.get(
            "/api/v1/knowledge-graph/book-1/neighbors/unit-1",
            params={"node_types": ["chapter"], "max_depth": 1},
        )
        assert resp.status_code == 200

    def test_nonexistent_node(self, client, built_graph_payload):
        """不存在的节点"""
        client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        resp = client.get("/api/v1/knowledge-graph/book-1/neighbors/nonexistent")
        assert resp.status_code == 404


class TestFindPathAPI:
    """测试查找路径API"""

    def test_path_query(self, client, built_graph_payload):
        """路径查询"""
        client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        resp = client.get(
            "/api/v1/knowledge-graph/book-1/path",
            params={"source_id": "unit-1", "target_id": "unit-2"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "found" in data
        assert "path" in data

    def test_same_node_path(self, client, built_graph_payload):
        """相同节点路径"""
        client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        resp = client.get(
            "/api/v1/knowledge-graph/book-1/path",
            params={"source_id": "unit-1", "target_id": "unit-1"},
        )
        assert resp.status_code == 200
        assert resp.json()["found"] is True
        assert resp.json()["path"] == []


class TestVisualizationAPI:
    """测试可视化API"""

    def test_basic_visualization(self, client, built_graph_payload):
        """基本可视化"""
        client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        resp = client.get("/api/v1/knowledge-graph/book-1/visualization")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert "layout" in data

    def test_centered_visualization(self, client, built_graph_payload):
        """以节点为中心的可视化"""
        client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        resp = client.get(
            "/api/v1/knowledge-graph/book-1/visualization",
            params={"center_node_id": "unit-1"},
        )
        assert resp.status_code == 200


class TestAddEdgeAPI:
    """测试添加边API"""

    def test_basic_add(self, client, built_graph_payload):
        """基本添加边"""
        client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        resp = client.post(
            "/api/v1/knowledge-graph/book-1/edges",
            json={
                "source_id": "unit-1",
                "target_id": "unit-2",
                "relation_type": "related",
                "weight": 0.5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["relation_type"] == "related"

    def test_self_loop_rejected(self, client, built_graph_payload):
        """自环边被拒绝"""
        client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        resp = client.post(
            "/api/v1/knowledge-graph/book-1/edges",
            json={
                "source_id": "unit-1",
                "target_id": "unit-1",
                "relation_type": "related",
            },
        )
        assert resp.status_code == 400


class TestRemoveEdgeAPI:
    """测试删除边API"""

    def test_basic_remove(self, client, built_graph_payload):
        """基本删除边"""
        client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        # 先获取图谱找到一个边ID
        graph_resp = client.get("/api/v1/knowledge-graph/book-1")
        edges = graph_resp.json()["edges"]
        assert len(edges) > 0
        edge_id = edges[0]["id"]

        resp = client.delete(f"/api/v1/knowledge-graph/book-1/edges/{edge_id}")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_nonexistent_edge(self, client, built_graph_payload):
        """删除不存在的边"""
        client.post("/api/v1/knowledge-graph/book-1/build", json=built_graph_payload)
        resp = client.delete("/api/v1/knowledge-graph/book-1/edges/nonexistent")
        assert resp.status_code == 404
