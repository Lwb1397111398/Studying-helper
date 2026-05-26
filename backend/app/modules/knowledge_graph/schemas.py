"""知识图谱数据模型"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from uuid import uuid4


class KGNode(BaseModel):
    """知识图谱节点"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    node_type: str              # 'unit' | 'concept' | 'chapter'
    label: str
    book_id: str
    content_summary: Optional[str] = None
    difficulty_level: Optional[int] = None
    importance_score: Optional[float] = None
    mastery_score: Optional[float] = None
    mastery_level: Optional[str] = None
    size: float = 1.0
    color: Optional[str] = None


class KGEdge(BaseModel):
    """知识图谱边"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: str
    target_id: str
    relation_type: str          # 'depends_on' | 'similar_to' | 'contrasts_with' | 'part_of' | 'related'
    weight: float = 1.0
    metadata: Optional[dict] = None


class GraphStats(BaseModel):
    """图谱统计"""
    total_nodes: int
    total_edges: int
    node_type_counts: Dict[str, int]
    edge_type_counts: Dict[str, int]
    avg_connections: float


class KnowledgeGraph(BaseModel):
    """知识图谱"""
    book_id: str
    nodes: List[KGNode]
    edges: List[KGEdge]
    stats: GraphStats


class ConceptDetail(BaseModel):
    """概念的详细信息（从 AI 学习模块流入）"""
    name: str
    definition: str = ""
    examples: List[str] = []
    related_concepts: List[str] = []


class GraphQuery(BaseModel):
    """图谱查询参数"""
    node_types: Optional[List[str]] = None
    relation_types: Optional[List[str]] = None
    min_weight: float = 0.0
    max_depth: int = 2
    include_mastery: bool = True


class SubGraph(BaseModel):
    """子图"""
    center_node: KGNode
    nodes: List[KGNode]
    edges: List[KGEdge]


class VisNode(BaseModel):
    """可视化节点"""
    id: str
    label: str
    group: str
    size: float
    color: str
    title: str


class VisEdge(BaseModel):
    """可视化边"""
    from_id: str
    to_id: str
    label: str
    width: float
    dashes: bool = False


class VisualizationData(BaseModel):
    """可视化数据"""
    nodes: List[VisNode]
    edges: List[VisEdge]
    layout: str  # 'force' | 'hierarchical' | 'circular'
