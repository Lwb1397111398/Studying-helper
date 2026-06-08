"""数据同步包模型"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


SCHEMA_VERSION = "1.0"


class SyncBook(BaseModel):
    id: str
    user_id: str
    title: str
    author: str | None = None
    file_path: str
    file_type: str
    file_size_bytes: int
    parse_status: str | None = "pending"
    split_status: str | None = "pending"
    learn_status: str | None = "pending"
    total_chapters: int | None = 0
    total_units: int | None = 0
    learned_units: int | None = 0
    reading_motivation: str | None = None
    created_at: datetime
    updated_at: datetime


class SyncChapter(BaseModel):
    id: str
    book_id: str
    title: str
    chapter_number: int
    parent_id: str | None = None
    level: int | None = 0
    order_index: int
    summary: str | None = None


class SyncKnowledgeUnit(BaseModel):
    id: str
    book_id: str
    chapter_id: str
    section_id: str | None = None
    title: str
    content: str
    order_index: int
    char_offset_start: int
    char_offset_end: int
    summary: str | None = None
    explanation: str | None = None
    key_points: str | None = None
    concepts: str | None = None
    prerequisites: str | None = None
    difficulty_level: int | None = None
    importance_score: float | None = None


class SyncMasteryRecord(BaseModel):
    id: str
    user_id: str
    knowledge_unit_id: str
    book_id: str
    mastery_score: float
    mastery_level: str
    last_reviewed_at: datetime | None = None
    next_review_at: datetime
    review_count: int | None = 0
    ease_factor: float | None = 2.5
    interval_days: int | None = 1


class SyncAnnotation(BaseModel):
    id: str
    user_id: str
    knowledge_unit_id: str
    annotation_type: str
    content: str | None = None
    related_concepts_json: str | None = "[]"
    example: str | None = None
    cornell_cues: str | None = None
    cornell_summary: str | None = None
    created_at: datetime
    updated_at: datetime


class SyncLearningRecord(BaseModel):
    id: str
    user_id: str
    book_id: str
    session_id: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_minutes: int | None = None
    units_covered: str | None = None
    questions_asked: int | None = 0
    test_score: float | None = None
    annotations_created: int | None = 0


class SyncKGNode(BaseModel):
    id: str
    node_type: str
    label: str
    book_id: str
    content_summary: str | None = None
    difficulty_level: int | None = None
    importance_score: float | None = None
    mastery_score: float | None = None
    mastery_level: str | None = None
    size: float | None = 1.0
    color: str | None = None


class SyncKGEdge(BaseModel):
    id: str
    source_id: str
    target_id: str
    relation_type: str
    weight: float | None = 1.0
    metadata_json: str | None = None


class SyncDailyStats(BaseModel):
    user_id: str
    date: str
    total_minutes: int | None = 0
    units_learned: int | None = 0
    units_reviewed: int | None = 0
    tests_taken: int | None = 0
    avg_test_score: float | None = 0
    streak_day: int | None = 0


class SyncReviewSession(BaseModel):
    id: str
    user_id: str
    book_id: str
    review_type: str
    questions_json: str
    started_at: datetime
    ended_at: datetime | None = None
    score: float | None = None


class SyncTeachingSession(BaseModel):
    id: str
    user_id: str
    plan_session_id: str | None = ""
    book_id: str
    unit_ids: str | None = "[]"
    current_unit_index: int | None = 0
    current_phase: str | None = "activate"
    strategy_json: str | None = "{}"
    status: str | None = "active"
    started_at: datetime
    ended_at: datetime | None = None


class SyncTeachingMessage(BaseModel):
    id: str
    session_id: str
    unit_id: str
    phase: str
    content: str
    content_type: str | None = "text"
    assessment_json: str | None = None
    created_at: datetime


class SyncUserQuestion(BaseModel):
    id: str
    session_id: str
    question: str
    answer: str
    intent: str
    follow_up_json: str | None = "[]"
    asked_at: datetime


class SyncSessionTest(BaseModel):
    id: str
    session_id: str
    questions_json: str | None = "[]"
    user_answers_json: str | None = "[]"
    score: float | None = None
    weak_points_json: str | None = "[]"
    completed_at: datetime | None = None


class SyncLearningEfficiency(BaseModel):
    id: str
    session_id: str
    unit_id: str
    phase: str
    duration_seconds: int
    interaction_count: int | None = 0
    efficiency_score: float | None = 0.0
    created_at: datetime


class SyncPackage(BaseModel):
    schema_version: str = SCHEMA_VERSION
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: Literal["web", "android"] = "web"
    user_id: str
    books: list[SyncBook] = Field(default_factory=list)
    chapters: list[SyncChapter] = Field(default_factory=list)
    knowledge_units: list[SyncKnowledgeUnit] = Field(default_factory=list)
    kg_nodes: list[SyncKGNode] = Field(default_factory=list)
    kg_edges: list[SyncKGEdge] = Field(default_factory=list)
    mastery_records: list[SyncMasteryRecord] = Field(default_factory=list)
    annotations: list[SyncAnnotation] = Field(default_factory=list)
    learning_records: list[SyncLearningRecord] = Field(default_factory=list)
    daily_stats: list[SyncDailyStats] = Field(default_factory=list)
    review_sessions: list[SyncReviewSession] = Field(default_factory=list)
    teaching_sessions: list[SyncTeachingSession] = Field(default_factory=list)
    teaching_messages: list[SyncTeachingMessage] = Field(default_factory=list)
    user_questions: list[SyncUserQuestion] = Field(default_factory=list)
    session_tests: list[SyncSessionTest] = Field(default_factory=list)
    learning_efficiency: list[SyncLearningEfficiency] = Field(default_factory=list)


class SyncPreviewBook(BaseModel):
    id: str
    title: str
    source_updated_at: datetime
    will_overwrite: bool = False
    local_title: str | None = None


class SyncPreviewResult(BaseModel):
    schema_version: str
    source: Literal["web", "android"]
    exported_at: datetime
    books_count: int
    chapters_count: int
    units_count: int
    mastery_records_count: int
    annotations_count: int = 0
    kg_nodes_count: int = 0
    kg_edges_count: int = 0
    daily_stats_count: int = 0
    learning_records_count: int = 0
    review_sessions_count: int = 0
    teaching_sessions_count: int = 0
    teaching_messages_count: int = 0
    user_questions_count: int = 0
    session_tests_count: int = 0
    learning_efficiency_count: int = 0
    books: list[SyncPreviewBook]


class SyncImportResult(BaseModel):
    books_imported: int
    chapters_imported: int
    units_imported: int
    mastery_records_imported: int
    overwritten_books: list[str] = Field(default_factory=list)
    annotations_imported: int = 0
    kg_nodes_imported: int = 0
    kg_edges_imported: int = 0
    learning_records_imported: int = 0
    daily_stats_imported: int = 0
    review_sessions_imported: int = 0
    teaching_sessions_imported: int = 0
    teaching_messages_imported: int = 0
    user_questions_imported: int = 0
    session_tests_imported: int = 0
    learning_efficiency_imported: int = 0
