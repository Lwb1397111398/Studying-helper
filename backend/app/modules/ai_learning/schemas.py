"""AI学习数据模型"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import uuid4
from enum import Enum


class LearningStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NEEDS_DEEPENING = "needs_deepening"
    FAILED = "failed"


class KeyPoint(BaseModel):
    """结构化要点"""
    title: str
    explanation: str = ""
    examples: List[str] = []


class Concept(BaseModel):
    """核心概念"""
    name: str
    definition: str
    examples: List[str] = []
    related_concepts: List[str] = []


class TestQuestion(BaseModel):
    """测试题"""
    question: str
    question_type: str  # 'choice' | 'fill_blank' | 'short_answer' | 'matching' | 'ordering' | 'true_false'
    options: Optional[List[str]] = None
    correct_answer: str
    explanation: str
    # 连线题: 概念与定义配对
    pairs: Optional[List[dict]] = None
    # 排序题: 正确顺序
    sequence: Optional[List[str]] = None
    # 判断题: 陈述内容
    statement: Optional[str] = None


class SelfAssessment(BaseModel):
    """AI自评结果"""
    score: float  # 0-100
    test_questions: List[TestQuestion]
    self_answers: List[str]
    weak_points: List[str]
    needs_deepening: bool


class LearnedUnit(BaseModel):
    """AI学习完成后的知识单元"""
    unit_id: str
    book_id: str
    summary: str
    explanation: str = ""  # AI 教学讲解
    key_points: List[KeyPoint]
    concepts: List[Concept]
    difficulty_level: int  # 1-5
    importance_score: float  # 0-1
    prerequisites: List[str]
    self_assessment: Optional[SelfAssessment] = None
    calibrated_difficulty: Optional[float] = None
    calibration_count: int = 0
    learned_at: datetime = Field(default_factory=datetime.now)
    llm_model: str = ""
    token_cost: int = 0


class LearningContext(BaseModel):
    """学习上下文"""
    previous_unit_summary: Optional[str] = None
    chapter_summary: Optional[str] = None
    existing_concepts: List[str] = []
    user_confusing_marks: List[str] = []


class LearningProgress(BaseModel):
    """学习进度"""
    book_id: str
    total_units: int
    learned_units: int
    failed_units: int
    current_unit_id: Optional[str]
    estimated_remaining_minutes: int
    started_at: datetime
    last_activity_at: datetime


class BookLearningResult(BaseModel):
    """整本书学习结果"""
    book_id: str
    total_units: int
    learned_count: int
    failed_count: int
    skipped_count: int
    total_token_cost: int
    duration_seconds: float


class ChapterOverview(BaseModel):
    """章节概览"""
    chapter_id: str
    title: str
    key_concepts_preview: List[str]
    estimated_minutes: int
    difficulty_level: int
    unit_count: int


class BookOverview(BaseModel):
    """书籍概览"""
    book_id: str
    title: str
    total_chapters: int
    chapters: List[ChapterOverview]
