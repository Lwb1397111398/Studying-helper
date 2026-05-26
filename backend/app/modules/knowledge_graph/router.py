"""知识图谱API路由"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ServiceError, ErrorCode, ERROR_STATUS_MAP
from app.db.database import get_db
from app.db.models import KnowledgeUnitModel, ChapterModel
from app.modules.knowledge_graph.schemas import (
    KnowledgeGraph, GraphQuery, SubGraph, VisualizationData, KGEdge,
)
from app.modules.knowledge_graph.service import KnowledgeGraphService

router = APIRouter(prefix="/api/v1/knowledge-graph", tags=["knowledge-graph"])


def _get_service(db: AsyncSession) -> KnowledgeGraphService:
    return KnowledgeGraphService(db)


class BuildGraphRequest(BaseModel):
    units: list
    chapters: list
    mastery_records: Optional[list] = None


class AddEdgeRequest(BaseModel):
    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0
    is_manual: bool = True  # 手动添加的边在重建时保留


async def _auto_build_graph(book_id: str, svc: KnowledgeGraphService) -> Optional[KnowledgeGraph]:
    """从数据库自动构建图谱"""
    units_result = await svc.db.execute(
        select(KnowledgeUnitModel)
        .where(KnowledgeUnitModel.book_id == book_id)
        .order_by(KnowledgeUnitModel.order_index)
    )
    db_units = list(units_result.scalars().all())

    chapters_result = await svc.db.execute(
        select(ChapterModel)
        .where(ChapterModel.book_id == book_id)
        .order_by(ChapterModel.order_index)
    )
    db_chapters = list(chapters_result.scalars().all())

    if not db_units:
        return None

    def _parse_json_field(field: str | None):
        if not field:
            return []
        import json
        try:
            return json.loads(field)
        except (json.JSONDecodeError, TypeError):
            return [s.strip() for s in field.split(",") if s.strip()]

    units_data = [
        {
            "id": u.id, "book_id": u.book_id, "chapter_id": u.chapter_id,
            "title": u.title, "content": u.content, "summary": u.summary,
            "concepts": _parse_json_field(u.concepts),
            "prerequisites": _parse_json_field(u.prerequisites),
            "difficulty_level": u.difficulty_level,
        }
        for u in db_units
    ]
    chapters_data = [
        {"id": c.id, "book_id": c.book_id, "title": c.title}
        for c in db_chapters
    ]

    return await svc.build_graph(book_id, units_data, chapters_data)


@router.post("/{book_id}/build")
async def build_graph(
    book_id: str,
    request: BuildGraphRequest,
    db: AsyncSession = Depends(get_db),
):
    """构建知识图谱"""
    try:
        svc = _get_service(db)
        graph = await svc.build_graph(
            book_id=book_id,
            units=request.units,
            chapters=request.chapters,
            mastery_records=request.mastery_records,
        )
        return graph.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/{book_id}")
async def get_graph(book_id: str, db: AsyncSession = Depends(get_db)):
    """获取知识图谱（不存在时自动构建）"""
    svc = _get_service(db)
    try:
        graph = await svc.get_graph(book_id)
        return graph.model_dump()
    except ServiceError as e:
        if e.code != ErrorCode.NOT_FOUND:
            raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)

        # 图谱不存在，尝试从数据库自动构建
        graph = await _auto_build_graph(book_id, svc)
        if graph is None:
            return {"book_id": book_id, "nodes": [], "edges": [], "stats": None}
        return graph.model_dump()


@router.get("/{book_id}/neighbors/{node_id}")
async def query_neighbors(
    book_id: str,
    node_id: str,
    node_types: Optional[List[str]] = Query(None),
    relation_types: Optional[List[str]] = Query(None),
    min_weight: float = Query(0.0),
    max_depth: int = Query(2),
    db: AsyncSession = Depends(get_db),
):
    """查询节点邻居"""
    try:
        svc = _get_service(db)
        query = GraphQuery(
            node_types=node_types,
            relation_types=relation_types,
            min_weight=min_weight,
            max_depth=max_depth,
        )
        subgraph = await svc.query_neighbors(book_id, node_id, query)
        return subgraph.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/{book_id}/path")
async def find_path(
    book_id: str,
    source_id: str = Query(..., description="源节点ID"),
    target_id: str = Query(..., description="目标节点ID"),
    db: AsyncSession = Depends(get_db),
):
    """查找两节点间路径"""
    try:
        svc = _get_service(db)
        path = await svc.find_path(book_id, source_id, target_id)
        if path is None:
            return {"found": False, "path": []}
        return {"found": True, "path": [e.model_dump() for e in path]}
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/{book_id}/visualization")
async def get_visualization(
    book_id: str,
    center_node_id: Optional[str] = Query(None),
    max_nodes: int = Query(100),
    db: AsyncSession = Depends(get_db),
):
    """获取可视化数据"""
    try:
        svc = _get_service(db)
        vis_data = await svc.get_visualization_data(book_id, center_node_id, max_nodes)
        return vis_data.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/{book_id}/edges")
async def add_edge(
    book_id: str,
    request: AddEdgeRequest,
    db: AsyncSession = Depends(get_db),
):
    """手动添加边"""
    try:
        svc = _get_service(db)
        edge = await svc.add_edge(
            book_id=book_id,
            source_id=request.source_id,
            target_id=request.target_id,
            relation_type=request.relation_type,
            weight=request.weight,
        )
        return edge.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.delete("/{book_id}/edges/{edge_id}")
async def remove_edge(
    book_id: str,
    edge_id: str,
    db: AsyncSession = Depends(get_db),
):
    """删除边"""
    try:
        svc = _get_service(db)
        await svc.remove_edge(book_id, edge_id)
        return {"success": True, "message": "边已删除"}
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


class UpdateUnitGraphRequest(BaseModel):
    """增量更新请求：传入单个单元的最新数据"""
    unit_id: str
    title: str
    concepts: list = []
    prerequisites: list = []
    summary: str = ""
    key_points: list = []
    difficulty_level: int = 3
    importance_score: float = 0.5


@router.post("/{book_id}/units/{unit_id}")
async def update_unit_graph(
    book_id: str,
    unit_id: str,
    request: UpdateUnitGraphRequest,
    db: AsyncSession = Depends(get_db),
):
    """增量更新：学完一个单元后更新图谱（不重建整张图）"""
    try:
        svc = _get_service(db)
        unit_data = {
            "id": unit_id,
            "title": request.title,
            "concepts": request.concepts,
            "prerequisites": request.prerequisites,
            "summary": request.summary,
            "key_points": request.key_points,
            "difficulty_level": request.difficulty_level,
            "importance_score": request.importance_score,
        }
        graph = await svc.update_unit_graph(book_id, unit_data)
        return graph.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)
