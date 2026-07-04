"""AID 知识图谱适配器测试"""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.database import Base
from app.db.models import (
    UserModel,
    BookModel,
    ChapterModel,
    KnowledgeUnitModel,
    MasteryRecordModel,
)
from app.modules.adaptive_design.kg_adapter import KGAdapter, UnitBrief


@pytest_asyncio.fixture
async def db_session():
    """内存数据库 + 单用户"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        # 单用户
        session.add(UserModel(id="anonymous", username="anonymous"))
        # 书（必填 file_path/file_type/file_size_bytes）
        session.add(BookModel(
            id="book-1", user_id="anonymous", title="测试书", author="",
            file_path="/tmp/test.pdf", file_type="pdf", file_size_bytes=100,
        ))
        # 两章
        session.add(ChapterModel(
            id="ch-1", book_id="book-1", title="第一章",
            chapter_number=1, order_index=0, level=1,
        ))
        session.add(ChapterModel(
            id="ch-2", book_id="book-1", title="第二章",
            chapter_number=2, order_index=1, level=1,
        ))
        # 三个单元，跨章节共享概念「线性表」
        # unit-3 prerequisites 指向 unit-2（产生 depends_on 边，拓扑可用）
        session.add(KnowledgeUnitModel(
            id="unit-1", book_id="book-1", chapter_id="ch-1", title="数组基础",
            content="...", order_index=0, char_offset_start=0, char_offset_end=10,
            summary="数组是线性表", difficulty_level=2, importance_score=0.8,
            concepts=json.dumps(["数组", "线性表"]),
        ))
        session.add(KnowledgeUnitModel(
            id="unit-2", book_id="book-1", chapter_id="ch-1", title="链表",
            content="...", order_index=1, char_offset_start=10, char_offset_end=20,
            summary="链表也是线性表", difficulty_level=3, importance_score=0.7,
            concepts=json.dumps(["链表", "线性表"]),
            prerequisites=json.dumps(["unit-1"]),
        ))
        session.add(KnowledgeUnitModel(
            id="unit-3", book_id="book-1", chapter_id="ch-2", title="二叉树",
            content="...", order_index=2, char_offset_start=20, char_offset_end=30,
            summary="树结构", difficulty_level=4, importance_score=0.9,
            concepts=json.dumps(["二叉树", "遍历"]),
            prerequisites=json.dumps(["unit-2"]),
        ))
        # 掌握度（next_review_at 为 NOT NULL）
        from datetime import datetime, timedelta, timezone
        session.add(MasteryRecordModel(
            id="mr-1", user_id="anonymous", knowledge_unit_id="unit-1", book_id="book-1",
            mastery_score=0.8, mastery_level="proficient",
            next_review_at=datetime.now(timezone.utc) + timedelta(days=1),
        ))
        await session.flush()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def adapter(db_session):
    return KGAdapter(db_session)


class TestGetUnitBriefs:
    """测试单元摘要查询"""

    @pytest.mark.asyncio
    async def test_returns_all_units(self, adapter):
        briefs = await adapter.get_unit_briefs("book-1")
        assert len(briefs) == 3
        assert all(isinstance(b, UnitBrief) for b in briefs)

    @pytest.mark.asyncio
    async def test_ordered_by_index(self, adapter):
        briefs = await adapter.get_unit_briefs("book-1")
        assert [b.unit_id for b in briefs] == ["unit-1", "unit-2", "unit-3"]

    @pytest.mark.asyncio
    async def test_concepts_parsed(self, adapter):
        briefs = await adapter.get_unit_briefs("book-1")
        u1 = next(b for b in briefs if b.unit_id == "unit-1")
        assert "数组" in u1.concepts and "线性表" in u1.concepts

    @pytest.mark.asyncio
    async def test_mastery_attached(self, adapter):
        briefs = await adapter.get_unit_briefs("book-1")
        u1 = next(b for b in briefs if b.unit_id == "unit-1")
        assert u1.mastery_score == 0.8
        u3 = next(b for b in briefs if b.unit_id == "unit-3")
        assert u3.mastery_score is None  # 无掌握度记录


class TestGetConceptUnitMap:
    """测试概念->单元映射（AID 跨章节聚类依据）"""

    @pytest.mark.asyncio
    async def test_shared_concept_spans_units(self, adapter):
        cmap = await adapter.get_concept_unit_map("book-1")
        # 「线性表」跨 unit-1 和 unit-2
        assert set(cmap["线性表"]) == {"unit-1", "unit-2"}

    @pytest.mark.asyncio
    async def test_unique_concept_single_unit(self, adapter):
        cmap = await adapter.get_concept_unit_map("book-1")
        assert cmap["二叉树"] == ["unit-3"]

    @pytest.mark.asyncio
    async def test_empty_book(self, adapter):
        cmap = await adapter.get_concept_unit_map("nonexistent")
        assert cmap == {}


class TestGetTopologicalLayers:
    """测试拓扑分层（复用 KG 服务）"""

    @pytest.mark.asyncio
    async def test_layers_respect_dependencies(self, adapter, db_session):
        # 先构建图谱（产生 depends_on 边）
        from app.modules.knowledge_graph.service import KnowledgeGraphService
        kg = KnowledgeGraphService(db_session)
        units = [
            {"id": "unit-1", "title": "数组基础", "concepts": ["数组", "线性表"],
             "difficulty_level": 2, "importance_score": 0.8},
            {"id": "unit-2", "title": "链表", "concepts": ["链表", "线性表"],
             "prerequisites": ["unit-1"], "difficulty_level": 3, "importance_score": 0.7},
            {"id": "unit-3", "title": "二叉树", "concepts": ["二叉树", "遍历"],
             "prerequisites": ["unit-2"], "difficulty_level": 4, "importance_score": 0.9},
        ]
        chapters = [{"id": "ch-1", "title": "第一章"}, {"id": "ch-2", "title": "第二章"}]
        await kg.build_graph("book-1", units, chapters)

        layers = await adapter.get_topological_layers("book-1")
        # unit-1 无前置 → 第一层；unit-2 依赖 unit-1 → 第二层；unit-3 依赖 unit-2 → 第三层
        assert len(layers) >= 2
        flat = [uid for layer in layers for uid in layer]
        assert flat.index("unit-1") < flat.index("unit-2") < flat.index("unit-3")

    @pytest.mark.asyncio
    async def test_no_graph_returns_empty(self, adapter):
        """KG 未构建时返回空，AID 调用方据此回退章节序"""
        layers = await adapter.get_topological_layers("nonexistent")
        assert layers == []


class TestGetUnitAdjacency:
    """测试单元邻接表"""

    @pytest.mark.asyncio
    async def test_dependency_edges(self, adapter, db_session):
        from app.modules.knowledge_graph.service import KnowledgeGraphService
        kg = KnowledgeGraphService(db_session)
        units = [
            {"id": "unit-1", "title": "数组", "concepts": ["数组"],
             "difficulty_level": 2, "importance_score": 0.8},
            {"id": "unit-2", "title": "链表", "concepts": ["链表"],
             "prerequisites": ["unit-1"], "difficulty_level": 3, "importance_score": 0.7},
        ]
        await kg.build_graph("book-1", units, [{"id": "ch-1", "title": "第一章"}])

        adj = await adapter.get_unit_adjacency("book-1")
        # unit-2 depends_on unit-1：adj[unit-2] 含 (unit-1, depends_on, ...)
        neighbors = [(n, rt) for (n, rt, _) in adj["unit-2"]]
        assert ("unit-1", "depends_on") in neighbors

    @pytest.mark.asyncio
    async def test_empty_when_no_graph(self, adapter):
        assert await adapter.get_unit_adjacency("nonexistent") == {}
