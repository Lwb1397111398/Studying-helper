"""所有11张表的ORM模型"""
from uuid import uuid4
from sqlalchemy import (
    Column, String, Integer, Float, Text, ForeignKey,
    UniqueConstraint, PrimaryKeyConstraint, Index, DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from app.db.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserModel(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255))
    daily_goal_minutes = Column(Integer, default=30)
    preferred_language = Column(String(10), default="zh")
    learning_style_json = Column(Text)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class BookModel(Base):
    __tablename__ = "books"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    author = Column(String(255))
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    parse_status = Column(String(50), default="pending")
    split_status = Column(String(50), default="pending")
    learn_status = Column(String(50), default="pending")
    total_chapters = Column(Integer, default=0)
    total_units = Column(Integer, default=0)
    learned_units = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (
        Index("ix_books_user_id", "user_id"),
    )


class ChapterModel(Base):
    __tablename__ = "chapters"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    title = Column(String(255), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    parent_id = Column(String, ForeignKey("chapters.id"))
    level = Column(Integer, default=0)
    order_index = Column(Integer, nullable=False)
    summary = Column(Text)

    __table_args__ = (
        Index("ix_chapters_book_id", "book_id"),
    )


class KnowledgeUnitModel(Base):
    __tablename__ = "knowledge_units"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    chapter_id = Column(String, ForeignKey("chapters.id"), nullable=False)
    section_id = Column(String, ForeignKey("chapters.id"), nullable=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False)
    char_offset_start = Column(Integer, nullable=False)
    char_offset_end = Column(Integer, nullable=False)
    summary = Column(Text)
    key_points = Column(Text)
    concepts = Column(Text)            # JSON 数组，支持字符串或 Concept 对象
    prerequisites = Column(Text)       # JSON 数组：存 unit_id 列表或概念名字符串列表
    difficulty_level = Column(Integer)
    importance_score = Column(Float)

    __table_args__ = (
        Index("ix_knowledge_units_book_id", "book_id"),
        Index("ix_knowledge_units_chapter_id", "chapter_id"),
        Index("ix_knowledge_units_section_id", "section_id"),
    )


class MasteryRecordModel(Base):
    __tablename__ = "mastery_records"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    knowledge_unit_id = Column(String, ForeignKey("knowledge_units.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False, default="")
    mastery_score = Column(Float, nullable=False)
    mastery_level = Column(String(50), nullable=False)
    last_reviewed_at = Column(DateTime)
    next_review_at = Column(DateTime, nullable=False)
    review_count = Column(Integer, default=0)
    ease_factor = Column(Float, default=2.5)
    interval_days = Column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_unit_id", name="uq_mastery_user_unit"),
        Index("ix_mastery_records_user_id", "user_id"),
        Index("ix_mastery_records_next_review", "next_review_at"),
        Index("ix_mastery_user_next", "user_id", "next_review_at"),
    )


class AnnotationModel(Base):
    __tablename__ = "annotations"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    knowledge_unit_id = Column(String, ForeignKey("knowledge_units.id"), nullable=False)
    annotation_type = Column(String(20), nullable=False)
    content = Column(Text)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (
        Index("ix_annotations_user_id", "user_id"),
        Index("ix_annotations_knowledge_unit_id", "knowledge_unit_id"),
    )


class LearningRecordModel(Base):
    __tablename__ = "learning_records"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    session_id = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False, default=_utc_now)
    ended_at = Column(DateTime)
    duration_minutes = Column(Integer)
    units_covered = Column(Text)
    questions_asked = Column(Integer, default=0)
    test_score = Column(Float)
    annotations_created = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_learning_records_user_id", "user_id"),
        Index("ix_learning_records_book_id", "book_id"),
        Index("ix_learning_records_started_at", "started_at"),
    )


class KGNodeModel(Base):
    __tablename__ = "kg_nodes"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    node_type = Column(String(50), nullable=False)
    label = Column(String(255), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    content_summary = Column(Text)
    difficulty_level = Column(Integer)
    importance_score = Column(Float)
    mastery_score = Column(Float)
    mastery_level = Column(String(50))
    size = Column(Float, default=1.0)
    color = Column(String(50))

    __table_args__ = (
        Index("ix_kg_nodes_book_id", "book_id"),
    )


class KGEdgeModel(Base):
    __tablename__ = "kg_edges"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    source_id = Column(String, ForeignKey("kg_nodes.id"), nullable=False)
    target_id = Column(String, ForeignKey("kg_nodes.id"), nullable=False)
    relation_type = Column(String(50), nullable=False)
    weight = Column(Float, default=1.0)
    metadata_json = Column(Text)

    __table_args__ = (
        Index("ix_kg_edges_source_id", "source_id"),
        Index("ix_kg_edges_target_id", "target_id"),
        Index("ix_kg_edges_relation_type", "relation_type"),
    )


class CacheEntryModel(Base):
    __tablename__ = "cache_entries"
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    expires_at = Column(DateTime, nullable=False)
    access_count = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_cache_entries_expires_at", "expires_at"),
    )


class DailyStatsModel(Base):
    __tablename__ = "daily_stats"
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    date = Column(String, nullable=False)
    total_minutes = Column(Integer, default=0)
    units_learned = Column(Integer, default=0)
    units_reviewed = Column(Integer, default=0)
    tests_taken = Column(Integer, default=0)
    avg_test_score = Column(Float, default=0)
    streak_day = Column(Integer, default=0)

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "date", name="pk_daily_stats"),
    )


class ReviewSessionModel(Base):
    __tablename__ = "review_sessions"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    review_type = Column(String(20), nullable=False)
    questions_json = Column(Text, nullable=False, default="[]")
    started_at = Column(DateTime, nullable=False, default=_utc_now)
    ended_at = Column(DateTime)
    score = Column(Float)

    __table_args__ = (
        Index("ix_review_sessions_user_id", "user_id"),
        Index("ix_review_sessions_book_id", "book_id"),
    )


class TeachingSessionModel(Base):
    __tablename__ = "teaching_sessions"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    plan_session_id = Column(String, nullable=False, default="")
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    unit_ids = Column(Text, nullable=False, default="[]")  # JSON array
    current_unit_index = Column(Integer, default=0)
    current_phase = Column(String(20), default="intro")
    strategy_json = Column(Text, nullable=False, default="{}")
    status = Column(String(20), default="active")
    started_at = Column(DateTime, nullable=False, default=_utc_now)
    ended_at = Column(DateTime)

    __table_args__ = (
        Index("ix_teaching_sessions_user_id", "user_id"),
        Index("ix_teaching_sessions_book_id", "book_id"),
        Index("ix_teaching_sessions_status", "status"),
    )


class TeachingMessageModel(Base):
    __tablename__ = "teaching_messages"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, ForeignKey("teaching_sessions.id"), nullable=False)
    unit_id = Column(String, nullable=False)
    phase = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(String(20), default="text")
    created_at = Column(DateTime, nullable=False, default=_utc_now)

    __table_args__ = (
        Index("ix_teaching_messages_session_id", "session_id"),
    )


class UserQuestionModel(Base):
    __tablename__ = "user_questions"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, ForeignKey("teaching_sessions.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    intent = Column(String(20), nullable=False)
    follow_up_json = Column(Text, nullable=False, default="[]")
    asked_at = Column(DateTime, nullable=False, default=_utc_now)

    __table_args__ = (
        Index("ix_user_questions_session_id", "session_id"),
    )


class SessionTestModel(Base):
    __tablename__ = "session_tests"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, ForeignKey("teaching_sessions.id"), nullable=False)
    questions_json = Column(Text, nullable=False, default="[]")
    user_answers_json = Column(Text, nullable=False, default="[]")
    score = Column(Float)
    weak_points_json = Column(Text, nullable=False, default="[]")
    completed_at = Column(DateTime)

    __table_args__ = (
        Index("ix_session_tests_session_id", "session_id"),
    )
