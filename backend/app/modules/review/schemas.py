"""复习引擎数据模型"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum
from uuid import uuid4


class MasteryRecord(BaseModel):
    """掌握度记录"""
    id: str
    user_id: str
    knowledge_unit_id: str
    book_id: str = ""
    mastery_score: float  # 0-1
    mastery_level: str  # 'beginner' | 'familiar' | 'proficient' | 'mastered'
    last_reviewed_at: Optional[datetime] = None
    next_review_at: datetime
    review_count: int = 0
    ease_factor: float = 2.5  # SM-2算法的难度因子
    interval_days: int = 1  # 当前间隔天数


class ReviewSession(BaseModel):
    """复习会话"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    book_id: str
    review_type: str  # 'spaced' | 'exam' | 'manual'
    questions: List['ReviewQuestion'] = []
    started_at: datetime = Field(default_factory=datetime.now)
    ended_at: Optional[datetime] = None


class ReviewQuestion(BaseModel):
    """复习题"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    unit_id: str
    question: str
    question_type: str
    options: Optional[List[str]] = None
    correct_answer: str
    user_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    answered_at: Optional[datetime] = None


class ExamConfig(BaseModel):
    """考前模式配置"""
    question_count: int = 20
    time_limit_minutes: int = 30
    passing_score: float = 70.0
    difficulty_distribution: Dict[str, float] = {'easy': 0.3, 'medium': 0.5, 'hard': 0.2}
    focus_on_weak: bool = True


class ExamResult(BaseModel):
    """考试结果"""
    session_id: str
    score: float
    passed: bool
    correct_count: int
    total_count: int
    weak_points: List[str]
    time_spent_minutes: int
    recommended_review: List[str]  # 建议复习的单元ID


class ExportFormat(str, Enum):
    MARKDOWN = "markdown"
    ANKI = "anki"
    WRONG_ANSWERS = "wrong_answers"
    MIND_MAP_MERMAID = "mind_map_mermaid"
    MIND_MAP_PLANTUML = "mind_map_plantuml"


class ExportResult(BaseModel):
    """导出结果"""
    format: ExportFormat
    content: str
    filename: str
    size_bytes: int


class ReviewFeedback(BaseModel):
    """复习反馈"""
    is_correct: bool
    correct_answer: str
    explanation: str
    next_review_at: datetime
    mastery_change: float


class MasteryAssessment(BaseModel):
    """掌握度评估报告"""
    unit_id: str
    score: float
    level: str
    dimensions: Dict[str, float]
    weak_points: List[str]
    recommended_review_at: datetime
