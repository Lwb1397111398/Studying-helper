from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import uuid4
from enum import Enum

from app.modules.ai_learning.schemas import TestQuestion


class TeachingPhase(str, Enum):
    ACTIVATE = "activate"
    INTRO = "intro"
    CORE = "core"
    FEYNMAN = "feynman"      # 费曼学习法：用自己的话解释
    RETRIEVAL = "retrieval"  # 检索练习：回忆前置单元
    CHECK = "check"
    REFLECT = "reflect"
    CONNECT = "connect"


class KnowledgeType(str, Enum):
    CONCEPT = "concept"
    PRINCIPLE = "principle"
    PROCEDURE = "procedure"
    FACT = "fact"


class CognitiveLevel(str, Enum):
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"


class TeachingStrategy(BaseModel):
    """教学策略配置"""
    explanation_style: str = "balanced"  # 'example_first' | 'theory_first' | 'analogy' | 'problem_based'
    visual_level: str = "medium"  # 'high' | 'medium' | 'low'
    interaction_frequency: str = "medium"  # 'high' | 'medium' | 'low'
    pace: str = "normal"  # 'fast' | 'normal' | 'slow'
    knowledge_type: str = "concept"  # KnowledgeType
    cognitive_level: str = "understand"  # CognitiveLevel
    scaffold_level: str = "full"  # 'full' | 'partial' | 'minimal'
    feedback_style: str = "immediate"  # 'immediate' | 'delayed' | 'guided'
    phases: List[TeachingPhase] = Field(default_factory=lambda: [
        TeachingPhase.ACTIVATE, TeachingPhase.INTRO, TeachingPhase.CORE,
        TeachingPhase.FEYNMAN, TeachingPhase.CHECK, TeachingPhase.REFLECT, TeachingPhase.CONNECT,
    ])


class UserTeachingProfile(BaseModel):
    """用户教学画像（教学策略选择的输入）"""
    avg_mastery_score: float = 0.5
    total_sessions: int = 0
    preferred_style: str = ""
    weakness_tags: List[str] = []
    avg_test_score: float = 0.5


class TeachingMessage(BaseModel):
    """教学消息"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    unit_id: str
    phase: TeachingPhase
    content: str
    content_type: str = "text"  # 'text' | 'diagram' | 'code' | 'formula'
    next_phase: Optional[TeachingPhase] = None  # 下一个待进行的阶段
    requires_answer: bool = False  # 是否需要学生回答（CHECK/REFLECT 阶段）
    assessment: Optional[dict] = None  # AI 评估结果（学生回答后填充）
    created_at: datetime = Field(default_factory=datetime.now)


class UserQuestion(BaseModel):
    """用户提问"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    question: str
    answer: str
    intent: str  # 'concept' | 'principle' | 'example' | 'comparison' | 'application'
    follow_up_questions: List[str]
    asked_at: datetime = Field(default_factory=datetime.now)


class Annotation(BaseModel):
    """笔记/标记（支持康奈尔笔记）"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    knowledge_unit_id: str
    annotation_type: str  # 'concept' | 'question' | ... | 'cornell_note'
    content: Optional[str] = None
    related_concepts: List[str] = []
    example: Optional[str] = None
    cornell_cues: List[str] = []          # 线索栏
    cornell_summary: Optional[str] = None # 总结栏
    created_at: datetime = Field(default_factory=datetime.now)


class CornellNote(BaseModel):
    """康奈尔笔记响应"""
    annotation_id: str
    knowledge_unit_id: str
    notes: str
    cues: List[str] = []
    summary: Optional[str] = None
    ai_generated: bool = False


class SessionTest(BaseModel):
    """会话测试"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    questions: List[TestQuestion]
    user_answers: List[str] = []
    score: Optional[float] = None
    weak_points: List[str] = []
    completed_at: Optional[datetime] = None


class TeachingSession(BaseModel):
    """教学会话"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    plan_session_id: str
    book_id: str
    unit_ids: List[str]
    current_unit_index: int = 0
    current_phase: TeachingPhase = TeachingPhase.ACTIVATE
    started_at: datetime = Field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None
    status: str = "active"  # 'active' | 'paused' | 'completed'
    strategy: TeachingStrategy = Field(default_factory=TeachingStrategy)


class FeynmanAssessment(BaseModel):
    """费曼解释评估结果"""
    completeness: float = 0.5    # 覆盖率 0-1
    accuracy: float = 0.5        # 准确性 0-1
    depth: float = 0.5           # 深度 0-1
    overall_score: float = 50    # 综合分 0-100
    covered_points: List[str] = []
    missed_points: List[str] = []
    inaccurate_points: List[str] = []
    feedback: str = ""
    suggestion: str = ""
    should_advance: bool = True


class SessionSummary(BaseModel):
    """会话总结"""
    session_id: str
    duration_minutes: int
    units_covered: int
    questions_asked: int
    test_score: Optional[float]
    annotations_created: int
    ai_summary: Optional[str] = None  # AI 生成的学习总结
