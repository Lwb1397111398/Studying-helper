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
    reading_motivation = Column(Text, nullable=True)
    overview_json = Column(Text, nullable=True)
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
    explanation = Column(Text)  # AI 生成的教学讲解
    key_points = Column(Text)
    concepts = Column(Text)            # JSON 数组，支持字符串或 Concept 对象
    prerequisites = Column(Text)       # JSON 数组：存 unit_id 列表或概念名字符串列表
    difficulty_level = Column(Integer)
    importance_score = Column(Float)
    ai_cognitive_hint = Column(String(30))  # AID 标注：memorize|understand|skip_if_mastered

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
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    mastery_score = Column(Float, nullable=False)
    mastery_level = Column(String(50), nullable=False)
    last_reviewed_at = Column(DateTime)
    next_review_at = Column(DateTime, nullable=False)
    review_count = Column(Integer, default=0)
    ease_factor = Column(Float, default=2.5)
    interval_days = Column(Integer, default=1)

    # FSRS 算法参数
    stability = Column(Float, default=0.0)       # 稳定性（天）
    difficulty = Column(Float, default=5.0)       # 难度（0-10）
    lapses = Column(Integer, default=0)           # 遗忘次数
    reps = Column(Integer, default=0)             # 复习次数（FSRS 专用）
    last_elapsed_days = Column(Integer, default=0)  # 上次复习后的过期天数
    scheduled_days = Column(Integer, default=0)   # FSRS 计划天数
    algorithm = Column(String(20), default="sm2") # 使用的算法：sm2 或 fsrs

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
    annotation_type = Column(String(30), nullable=False)
    content = Column(Text)
    related_concepts_json = Column(Text, default="[]")  # JSON 数组：相关概念
    example = Column(Text)                              # 用户记录的例子
    cornell_cues = Column(Text, nullable=True)           # 线索栏：JSON 数组
    cornell_summary = Column(Text, nullable=True)        # 总结栏：1-2句话
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
    current_phase = Column(String(20), default="activate")
    strategy_json = Column(Text, nullable=False, default="{}")
    status = Column(String(20), default="active")
    started_at = Column(DateTime, nullable=False, default=_utc_now)
    ended_at = Column(DateTime)
    # Teaching session v2
    asset_id = Column(String(64), nullable=True)
    parent_session_id = Column(String(64), nullable=True)
    state_v2 = Column(String(40), nullable=True)
    completion_status = Column(String(40), nullable=True)
    pause_reason = Column(String(60), nullable=True)
    plan_snapshot_json = Column(Text, nullable=True)
    primary_unit_id = Column(String(64), nullable=True)

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
    assessment_json = Column(Text, nullable=True)  # AI 评估结果 JSON
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


class LearningEfficiencyModel(Base):
    """学习效率统计表"""
    __tablename__ = "learning_efficiency"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, ForeignKey("teaching_sessions.id"), nullable=False)
    unit_id = Column(String, nullable=False)
    phase = Column(String(20), nullable=False)
    duration_seconds = Column(Integer, nullable=False)
    interaction_count = Column(Integer, default=0)
    efficiency_score = Column(Float, default=0.0)  # 每分钟互动次数
    created_at = Column(DateTime, nullable=False, default=_utc_now)

    __table_args__ = (
        Index("ix_learning_efficiency_session_id", "session_id"),
        Index("ix_learning_efficiency_unit_id", "unit_id"),
    )



class LearnerIntentProfileModel(Base):
    """学习者意图画像 - 每本书一份，用户主动声明（区别于行为画像）"""
    __tablename__ = "learner_intent_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    # 四维 + 重组 tolerance
    identity_background = Column(String(50), nullable=False, default="unknown")
    goal_depth = Column(String(50), nullable=False, default="apply_understand")
    cognitive_pref = Column(String(50), nullable=False, default="rigorous_system")
    restructure_tolerance = Column(String(50), nullable=False, default="moderate")
    time_budget_minutes = Column(Integer)
    source = Column(String(20), nullable=False, default="ai_inferred")
    status = Column(String(20), nullable=False, default="draft")
    extra_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (
        UniqueConstraint("user_id", "book_id", name="uq_intent_profile_user_book"),
        Index("ix_intent_profiles_book_id", "book_id"),
    )


class TeachingDesignModel(Base):
    """教学设计总账 - 一本书的 AID 编排方案（渐进式：存进行到哪、生成哪些模块）"""
    __tablename__ = "teaching_designs"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    profile_id = Column(String, ForeignKey("learner_intent_profiles.id"))
    macro_design_json = Column(Text)
    current_module_index = Column(Integer, nullable=False, default=0)
    generated_module_count = Column(Integer, nullable=False, default=0)
    adjustments_json = Column(Text, nullable=False, default="[]")
    status = Column(String(20), nullable=False, default="draft")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (
        UniqueConstraint("user_id", "book_id", "version", name="uq_teaching_design_user_book_ver"),
        Index("ix_teaching_designs_book_id", "book_id"),
        Index("ix_teaching_designs_status", "status"),
    )


class ModuleMicroPlanModel(Base):
    """模块微观编排 - 进入某 Module 时生成，存重排后的 unit_ids 与重构标注"""
    __tablename__ = "module_micro_plans"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    design_id = Column(String, ForeignKey("teaching_designs.id"), nullable=False)
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    module_index = Column(Integer, nullable=False)
    module_title = Column(String(255), nullable=False, default="")
    ordered_unit_ids_json = Column(Text, nullable=False, default="[]")
    unit_annotations_json = Column(Text, nullable=False, default="[]")
    module_intro = Column(Text)
    module_status = Column(String(20), nullable=False, default="pending")
    module_summary_json = Column(Text)
    parent_design_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (
        UniqueConstraint("design_id", "module_index", name="uq_micro_plan_design_module"),
        Index("ix_module_micro_plans_book_status", "book_id", "module_status"),
    )


class DocumentModel(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    book_id = Column(String, ForeignKey("books.id"), nullable=False, index=True)
    source_type = Column(String(20), nullable=False)
    source_uri = Column(String(500), nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, nullable=False, default=_utc_now)


class DocumentRevisionModel(Base):
    __tablename__ = "document_revisions"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    revision_no = Column(Integer, nullable=False)
    source_hash = Column(String(128), nullable=False)
    parser_version = Column(String(50), nullable=False)
    normalization_version = Column(String(50), nullable=False)
    status = Column(String(20), default="processing")
    created_at = Column(DateTime, nullable=False, default=_utc_now)


class DocumentBlockModel(Base):
    __tablename__ = "document_blocks"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    document_revision_id = Column(String, ForeignKey("document_revisions.id"), nullable=False, index=True)
    chapter_id = Column(String, ForeignKey("chapters.id"), nullable=True, index=True)
    parent_block_id = Column(String, nullable=True)
    block_type = Column(String(30), nullable=False, default="paragraph")
    ordinal = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    text_hash = Column(String(128), nullable=False)
    page_index = Column(Integer, nullable=True)
    page_label = Column(String(50), nullable=True)
    metadata_json = Column(Text, default="{}")


class AnalysisJobModel(Base):
    __tablename__ = "analysis_jobs"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    scope_type = Column(String(20), nullable=False)
    scope_id = Column(String, nullable=False, index=True)
    status = Column(String(30), nullable=False, default="queued")
    wait_reason = Column(String(50), nullable=True)
    priority = Column(Integer, default=5)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    idempotency_key = Column(String(200), nullable=True, unique=True)
    lease_owner = Column(String(100), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    quality_result_json = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_analysis_jobs_scope", "scope_type", "scope_id"),
    )


class UnitLearningAssetModel(Base):
    """不可变版本的单元教学资产。"""
    __tablename__ = "unit_learning_assets"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    unit_id = Column(String, ForeignKey("knowledge_units.id"), nullable=False)
    version = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="draft")
    readiness_status = Column(String(30), nullable=False, default="pending")
    freshness_status = Column(String(30), nullable=False, default="current")
    quality_score = Column(Float, nullable=True)
    quality_profile = Column(String(80), nullable=True)
    quality_algorithm_version = Column(String(40), nullable=True)
    document_revision_id = Column(String, nullable=True)
    payload_json = Column(Text, nullable=False, default="{}")
    schema_version = Column(String(40), nullable=False, default="unit-asset-v1")
    prompt_version = Column(String(40), nullable=True)
    model_provider = Column(String(40), nullable=True)
    model_name = Column(String(80), nullable=True)
    analysis_job_id = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    published_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_unit_learning_assets_unit_id", "unit_id"),
        Index("ix_ula_unit_status", "unit_id", "status"),
        UniqueConstraint("unit_id", "version", name="uq_ula_unit_version"),
    )


class LearningAttemptModel(Base):
    """用户一次作答（不可覆盖）。"""
    __tablename__ = "learning_attempts"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, nullable=False)
    session_id = Column(String, nullable=True)
    assessment_item_id = Column(String, nullable=False)
    attempt_no = Column(Integer, nullable=False, default=1)
    response_json = Column(Text, nullable=False)
    submitted_at = Column(DateTime, nullable=False, default=_utc_now)
    device_id = Column(String, nullable=True)
    idempotency_key = Column(String(200), nullable=False)
    client_created_at = Column(DateTime, nullable=True)
    server_received_at = Column(DateTime, nullable=False, default=_utc_now)
    status = Column(String(30), nullable=False, default="submitted")

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_attempt_user_idem"),
        Index("ix_learning_attempts_session_id", "session_id"),
        Index("ix_learning_attempts_user_id", "user_id"),
    )


class LearningEvidenceModel(Base):
    """对作答的评价结果（追加新版本，不改 Attempt）。"""
    __tablename__ = "learning_evidences"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    attempt_id = Column(String, ForeignKey("learning_attempts.id"), nullable=False)
    user_id = Column(String, nullable=False)
    book_id = Column(String, nullable=False)
    unit_id = Column(String, nullable=False)
    objective_id = Column(String, nullable=False)
    criterion_id = Column(String, nullable=True)
    session_id = Column(String, nullable=True)
    source_type = Column(String(30), nullable=False)
    question_id = Column(String, nullable=True)
    claim_id = Column(String, nullable=True)
    ability = Column(String(30), nullable=True)
    result = Column(String(20), nullable=False)
    score = Column(Float, nullable=False)
    error_type = Column(String(40), nullable=True)
    evaluator_type = Column(String(20), nullable=False)
    evaluator_version = Column(String(40), nullable=True)
    evaluation_revision = Column(Integer, nullable=False, default=1)
    supersedes_evidence_id = Column(String, nullable=True)
    status = Column(String(20), nullable=False, default="active")
    invalid_reason = Column(String(100), nullable=True)
    hints_used = Column(Integer, nullable=False, default=0)
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now)

    __table_args__ = (
        Index("ix_learning_evidences_attempt_id", "attempt_id"),
        Index("ix_learning_evidences_user_id", "user_id"),
        Index("ix_learning_evidences_unit_id", "unit_id"),
        Index("ix_learning_evidences_session_id", "session_id"),
        Index("ix_learning_evidences_objective", "objective_id"),
    )


class BookConceptModel(Base):
    """全书概念词典（Step4）。"""
    __tablename__ = "book_concepts"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    book_id = Column(String, ForeignKey("books.id"), nullable=False)
    name = Column(String(200), nullable=False)
    definition = Column(Text, nullable=True)
    aliases = Column(Text, nullable=True, default="[]")
    first_unit_id = Column(String, nullable=True)
    first_chapter_id = Column(String, nullable=True)
    source = Column(String(20), nullable=False)  # overview | unit_harvest
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (
        UniqueConstraint("book_id", "name", name="uq_book_concept_name"),
        Index("ix_book_concepts_book_id", "book_id"),
    )

