"""用户与存储模块的Pydantic模型"""
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime


# ========== 学习风格（结构化的 learning_style_json） ==========

class LearningStyle(BaseModel):
    """学习风格偏好，四个维度各 0-1"""
    visual_score: float = Field(0.5, ge=0.0, le=1.0, description="视觉偏好：图表/思维导图")
    verbal_score: float = Field(0.5, ge=0.0, le=1.0, description="文字偏好：阅读/写作")
    active_score: float = Field(0.5, ge=0.0, le=1.0, description="主动偏好：练习/实践")
    sequential_score: float = Field(0.5, ge=0.0, le=1.0, description="顺序偏好：按步骤 vs 跳跃")


# ========== 用户相关 ==========

class UserCreate(BaseModel):
    username: str = Field(..., max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    daily_goal_minutes: int = 30
    preferred_language: str = "zh"


class UserUpdate(BaseModel):
    daily_goal_minutes: Optional[int] = None
    preferred_language: Optional[str] = None
    learning_style_json: Optional[str] = None


class User(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    daily_goal_minutes: int = 30
    preferred_language: str = "zh"
    learning_style_json: Optional[str] = None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class UserProfile(BaseModel):
    user: User
    total_books: int = 0
    total_learning_minutes: int = 0
    total_units_learned: int = 0
    current_streak: int = 0


# ========== 书籍相关 ==========

class BookCreate(BaseModel):
    title: str = Field(..., max_length=255)
    author: Optional[str] = Field(None, max_length=255)
    file_type: str = Field(..., max_length=50)
    file_size_bytes: int


class BookStatusUpdate(BaseModel):
    parse_status: Optional[str] = None
    split_status: Optional[str] = None
    learn_status: Optional[str] = None
    total_chapters: Optional[int] = None
    total_units: Optional[int] = None
    learned_units: Optional[int] = None


class Book(BaseModel):
    id: str
    user_id: str
    title: str
    author: Optional[str] = None
    file_path: str
    file_type: str
    file_size_bytes: int
    parse_status: str = "pending"
    split_status: str = "pending"
    learn_status: str = "pending"
    total_chapters: int = 0
    total_units: int = 0
    learned_units: int = 0
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ========== 学习记录相关 ==========

class LearningRecordCreate(BaseModel):
    user_id: str
    book_id: str
    session_id: str


class LearningRecordComplete(BaseModel):
    duration_minutes: Optional[int] = None
    units_covered: Optional[List[str]] = None
    questions_asked: int = 0
    test_score: Optional[float] = None
    annotations_created: int = 0


class LearningRecord(BaseModel):
    id: str
    user_id: str
    book_id: str
    session_id: str
    started_at: str
    ended_at: Optional[str] = None
    duration_minutes: Optional[int] = None
    units_covered: Optional[str] = None
    questions_asked: int = 0
    test_score: Optional[float] = None
    annotations_created: int = 0

    model_config = {"from_attributes": True}


class DailyStats(BaseModel):
    user_id: str
    date: str
    total_minutes: int = 0
    units_learned: int = 0
    units_reviewed: int = 0
    tests_taken: int = 0
    avg_test_score: float = 0
    streak_day: int = 0

    model_config = {"from_attributes": True}


# ========== 缓存相关 ==========

class CacheEntry(BaseModel):
    key: str
    value: str
    created_at: str
    expires_at: str
    access_count: int = 0

    model_config = {"from_attributes": True}
