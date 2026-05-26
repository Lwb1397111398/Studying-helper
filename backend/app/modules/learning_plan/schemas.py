from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from uuid import uuid4
from enum import Enum


class LearningStyle(BaseModel):
    """用户学习风格模型"""
    # 维度1：信息接收偏好（0-1，总和为1）
    visual_score: float = 0.25
    auditory_score: float = 0.25
    reading_score: float = 0.25
    kinesthetic_score: float = 0.25

    # 维度2：学习节奏偏好
    fast_paced: bool = False
    step_by_step: bool = True
    holistic: bool = False

    # 维度3：内容偏好
    example_heavy: bool = True
    theory_first: bool = False
    problem_based: bool = False

    # 维度4：交互偏好
    interactive: bool = True
    self_paced: bool = False

    # 置信度
    confidence: float = 0.0


class PlanStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class PlanSession(BaseModel):
    """方案中的单次学习会话"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_number: int
    unit_ids: List[str]
    estimated_minutes: int
    teaching_strategy: str
    prerequisites_check: List[str] = []


class Milestone(BaseModel):
    """学习里程碑"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    session_indices: List[int]
    reward_description: str


class LearningPlan(BaseModel):
    """学习方案"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    book_id: str
    user_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    sessions: List[PlanSession]
    total_estimated_minutes: int
    milestones: List[Milestone]
    style_snapshot: LearningStyle
    daily_goal_minutes: int = 30
    status: PlanStatus = PlanStatus.ACTIVE


class SessionPerformance(BaseModel):
    """会话表现"""
    correct_rate: float
    avg_response_time: float
    questions_asked: int
    duration_minutes: int
    feedback_rating: Optional[int] = None


class PlanUpdate(BaseModel):
    """方案更新信息"""
    adjusted: bool
    reason: Optional[str] = None
    next_session: Optional[PlanSession] = None
    milestone_reached: Optional[Milestone] = None


class SessionData(BaseModel):
    """会话数据（用于风格分析）"""
    content_types_viewed: Dict[str, float] = {}
    question_count: int = 0
    practice_correct_rate: float = 0.5
    practice_speed: float = 1.0
    chosen_path: List[str] = []
