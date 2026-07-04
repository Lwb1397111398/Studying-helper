package com.studyinghelper.mobile.data.db

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(tableName = "books")
data class BookEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "user_id") val userId: String,
    val title: String,
    val author: String?,
    @ColumnInfo(name = "file_path") val filePath: String,
    @ColumnInfo(name = "file_type") val fileType: String,
    @ColumnInfo(name = "file_size_bytes") val fileSizeBytes: Int,
    @ColumnInfo(name = "parse_status") val parseStatus: String?,
    @ColumnInfo(name = "split_status") val splitStatus: String?,
    @ColumnInfo(name = "learn_status") val learnStatus: String?,
    @ColumnInfo(name = "total_chapters") val totalChapters: Int?,
    @ColumnInfo(name = "total_units") val totalUnits: Int?,
    @ColumnInfo(name = "learned_units") val learnedUnits: Int?,
    @ColumnInfo(name = "reading_motivation") val readingMotivation: String?,
    @ColumnInfo(name = "created_at") val createdAt: String,
    @ColumnInfo(name = "updated_at") val updatedAt: String,
)

@Entity(tableName = "chapters", indices = [Index("book_id")])
data class ChapterEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "book_id") val bookId: String,
    val title: String,
    @ColumnInfo(name = "chapter_number") val chapterNumber: Int,
    @ColumnInfo(name = "parent_id") val parentId: String?,
    val level: Int?,
    @ColumnInfo(name = "order_index") val orderIndex: Int,
    val summary: String?,
)

@Entity(tableName = "knowledge_units", indices = [Index("book_id"), Index("chapter_id")])
data class KnowledgeUnitEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "book_id") val bookId: String,
    @ColumnInfo(name = "chapter_id") val chapterId: String,
    @ColumnInfo(name = "section_id") val sectionId: String?,
    val title: String,
    val content: String,
    @ColumnInfo(name = "order_index") val orderIndex: Int,
    @ColumnInfo(name = "char_offset_start") val charOffsetStart: Int,
    @ColumnInfo(name = "char_offset_end") val charOffsetEnd: Int,
    val summary: String?,
    val explanation: String?,
    @ColumnInfo(name = "key_points") val keyPoints: String?,
    val concepts: String?,
    val prerequisites: String?,
    @ColumnInfo(name = "difficulty_level") val difficultyLevel: Int?,
    @ColumnInfo(name = "importance_score") val importanceScore: Float?,
    @ColumnInfo(name = "ai_cognitive_hint") val aiCognitiveHint: String? = null,
)

@Entity(tableName = "kg_nodes", indices = [Index("book_id")])
data class KgNodeEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "node_type") val nodeType: String,
    val label: String,
    @ColumnInfo(name = "book_id") val bookId: String,
    @ColumnInfo(name = "content_summary") val contentSummary: String?,
    @ColumnInfo(name = "difficulty_level") val difficultyLevel: Int?,
    @ColumnInfo(name = "importance_score") val importanceScore: Float?,
    @ColumnInfo(name = "mastery_score") val masteryScore: Float?,
    @ColumnInfo(name = "mastery_level") val masteryLevel: String?,
    val size: Float?,
    val color: String?,
)

@Entity(tableName = "kg_edges", indices = [Index("source_id"), Index("target_id")])
data class KgEdgeEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "source_id") val sourceId: String,
    @ColumnInfo(name = "target_id") val targetId: String,
    @ColumnInfo(name = "relation_type") val relationType: String,
    val weight: Float?,
    @ColumnInfo(name = "metadata_json") val metadataJson: String?,
)

@Entity(tableName = "mastery_records", indices = [Index("book_id"), Index("knowledge_unit_id")])
data class MasteryRecordEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "user_id") val userId: String,
    @ColumnInfo(name = "knowledge_unit_id") val knowledgeUnitId: String,
    @ColumnInfo(name = "book_id") val bookId: String,
    @ColumnInfo(name = "mastery_score") val masteryScore: Float,
    @ColumnInfo(name = "mastery_level") val masteryLevel: String,
    @ColumnInfo(name = "last_reviewed_at") val lastReviewedAt: String?,
    @ColumnInfo(name = "next_review_at") val nextReviewAt: String,
    @ColumnInfo(name = "review_count") val reviewCount: Int?,
    @ColumnInfo(name = "ease_factor") val easeFactor: Float?,
    @ColumnInfo(name = "interval_days") val intervalDays: Int?,
    // FSRS 算法参数
    @ColumnInfo(name = "stability") val stability: Float = 0f,
    @ColumnInfo(name = "difficulty") val difficulty: Float = 5f,
    @ColumnInfo(name = "lapses") val lapses: Int = 0,
    @ColumnInfo(name = "reps") val reps: Int = 0,
    @ColumnInfo(name = "last_elapsed_days") val lastElapsedDays: Int = 0,
    @ColumnInfo(name = "scheduled_days") val scheduledDays: Int = 0,
    @ColumnInfo(name = "algorithm") val algorithm: String = "sm2",
)

@Entity(tableName = "annotations", indices = [Index("knowledge_unit_id")])
data class AnnotationEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "user_id") val userId: String,
    @ColumnInfo(name = "knowledge_unit_id") val knowledgeUnitId: String,
    @ColumnInfo(name = "annotation_type") val annotationType: String,
    val content: String?,
    @ColumnInfo(name = "related_concepts_json") val relatedConceptsJson: String?,
    val example: String?,
    @ColumnInfo(name = "cornell_cues") val cornellCues: String?,
    @ColumnInfo(name = "cornell_summary") val cornellSummary: String?,
    @ColumnInfo(name = "created_at") val createdAt: String,
    @ColumnInfo(name = "updated_at") val updatedAt: String,
)

@Entity(tableName = "learning_records", indices = [Index("book_id")])
data class LearningRecordEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "user_id") val userId: String,
    @ColumnInfo(name = "book_id") val bookId: String,
    @ColumnInfo(name = "session_id") val sessionId: String,
    @ColumnInfo(name = "started_at") val startedAt: String,
    @ColumnInfo(name = "ended_at") val endedAt: String?,
    @ColumnInfo(name = "duration_minutes") val durationMinutes: Int?,
    @ColumnInfo(name = "units_covered") val unitsCovered: String?,
    @ColumnInfo(name = "questions_asked") val questionsAsked: Int?,
    @ColumnInfo(name = "test_score") val testScore: Float?,
    @ColumnInfo(name = "annotations_created") val annotationsCreated: Int?,
)

@Entity(tableName = "daily_stats", primaryKeys = ["user_id", "date"])
data class DailyStatsEntity(
    @ColumnInfo(name = "user_id") val userId: String,
    val date: String,
    @ColumnInfo(name = "total_minutes") val totalMinutes: Int?,
    @ColumnInfo(name = "units_learned") val unitsLearned: Int?,
    @ColumnInfo(name = "units_reviewed") val unitsReviewed: Int?,
    @ColumnInfo(name = "tests_taken") val testsTaken: Int?,
    @ColumnInfo(name = "avg_test_score") val avgTestScore: Float?,
    @ColumnInfo(name = "streak_day") val streakDay: Int?,
)

@Entity(tableName = "review_sessions", indices = [Index("book_id")])
data class ReviewSessionEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "user_id") val userId: String,
    @ColumnInfo(name = "book_id") val bookId: String,
    @ColumnInfo(name = "review_type") val reviewType: String,
    @ColumnInfo(name = "questions_json") val questionsJson: String,
    @ColumnInfo(name = "started_at") val startedAt: String,
    @ColumnInfo(name = "ended_at") val endedAt: String?,
    val score: Float?,
)

@Entity(tableName = "teaching_sessions", indices = [Index("book_id")])
data class TeachingSessionEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "user_id") val userId: String,
    @ColumnInfo(name = "plan_session_id") val planSessionId: String?,
    @ColumnInfo(name = "book_id") val bookId: String,
    @ColumnInfo(name = "unit_ids") val unitIds: String?,
    @ColumnInfo(name = "current_unit_index") val currentUnitIndex: Int?,
    @ColumnInfo(name = "current_phase") val currentPhase: String?,
    @ColumnInfo(name = "strategy_json") val strategyJson: String?,
    val status: String?,
    @ColumnInfo(name = "started_at") val startedAt: String,
    @ColumnInfo(name = "ended_at") val endedAt: String?,
)

@Entity(tableName = "teaching_messages", indices = [Index("session_id")])
data class TeachingMessageEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "session_id") val sessionId: String,
    @ColumnInfo(name = "unit_id") val unitId: String,
    val phase: String,
    val content: String,
    @ColumnInfo(name = "content_type") val contentType: String?,
    @ColumnInfo(name = "assessment_json") val assessmentJson: String?,
    @ColumnInfo(name = "created_at") val createdAt: String,
)

@Entity(tableName = "user_questions", indices = [Index("session_id")])
data class UserQuestionEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "session_id") val sessionId: String,
    val question: String,
    val answer: String,
    val intent: String,
    @ColumnInfo(name = "follow_up_json") val followUpJson: String?,
    @ColumnInfo(name = "asked_at") val askedAt: String,
)

@Entity(tableName = "session_tests", indices = [Index("session_id")])
data class SessionTestEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "session_id") val sessionId: String,
    @ColumnInfo(name = "questions_json") val questionsJson: String?,
    @ColumnInfo(name = "user_answers_json") val userAnswersJson: String?,
    val score: Float?,
    @ColumnInfo(name = "weak_points_json") val weakPointsJson: String?,
    @ColumnInfo(name = "completed_at") val completedAt: String?,
)

@Entity(tableName = "learning_efficiency", indices = [Index("session_id"), Index("unit_id")])
data class LearningEfficiencyEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "session_id") val sessionId: String,
    @ColumnInfo(name = "unit_id") val unitId: String,
    val phase: String,
    @ColumnInfo(name = "duration_seconds") val durationSeconds: Int,
    @ColumnInfo(name = "interaction_count") val interactionCount: Int?,
    @ColumnInfo(name = "efficiency_score") val efficiencyScore: Float?,
    @ColumnInfo(name = "created_at") val createdAt: String,
)

@Entity(
    tableName = "learner_intent_profiles",
    indices = [
        Index(value = ["user_id", "book_id"], unique = true),
        Index("book_id"),
    ],
)
data class LearnerIntentProfileEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "user_id") val userId: String,
    @ColumnInfo(name = "book_id") val bookId: String,
    @ColumnInfo(name = "identity_background") val identityBackground: String = "unknown",
    @ColumnInfo(name = "goal_depth") val goalDepth: String = "apply_understand",
    @ColumnInfo(name = "cognitive_pref") val cognitivePref: String = "rigorous_system",
    @ColumnInfo(name = "restructure_tolerance") val restructureTolerance: String = "moderate",
    @ColumnInfo(name = "time_budget_minutes") val timeBudgetMinutes: Int? = null,
    val source: String = "ai_inferred",
    val status: String = "draft",
    @ColumnInfo(name = "extra_json") val extraJson: String = "{}",
    @ColumnInfo(name = "created_at") val createdAt: String,
    @ColumnInfo(name = "updated_at") val updatedAt: String,
)

@Entity(
    tableName = "teaching_designs",
    indices = [
        Index(value = ["user_id", "book_id", "version"], unique = true),
        Index("book_id"),
        Index("status"),
    ],
)
data class TeachingDesignEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "user_id") val userId: String,
    @ColumnInfo(name = "book_id") val bookId: String,
    @ColumnInfo(name = "profile_id") val profileId: String? = null,
    @ColumnInfo(name = "macro_design_json") val macroDesignJson: String? = null,
    @ColumnInfo(name = "current_module_index") val currentModuleIndex: Int = 0,
    @ColumnInfo(name = "generated_module_count") val generatedModuleCount: Int = 0,
    @ColumnInfo(name = "adjustments_json") val adjustmentsJson: String = "[]",
    val status: String = "draft",
    val version: Int = 1,
    @ColumnInfo(name = "created_at") val createdAt: String,
    @ColumnInfo(name = "updated_at") val updatedAt: String,
)

@Entity(
    tableName = "module_micro_plans",
    indices = [
        Index(value = ["design_id", "module_index"], unique = true),
        Index(value = ["book_id", "module_status"]),
    ],
)
data class ModuleMicroPlanEntity(
    @PrimaryKey val id: String,
    @ColumnInfo(name = "design_id") val designId: String,
    @ColumnInfo(name = "book_id") val bookId: String,
    @ColumnInfo(name = "user_id") val userId: String,
    @ColumnInfo(name = "module_index") val moduleIndex: Int,
    @ColumnInfo(name = "module_title") val moduleTitle: String = "",
    @ColumnInfo(name = "ordered_unit_ids_json") val orderedUnitIdsJson: String = "[]",
    @ColumnInfo(name = "unit_annotations_json") val unitAnnotationsJson: String = "[]",
    @ColumnInfo(name = "module_intro") val moduleIntro: String? = null,
    @ColumnInfo(name = "module_status") val moduleStatus: String = "pending",
    @ColumnInfo(name = "module_summary_json") val moduleSummaryJson: String? = null,
    @ColumnInfo(name = "parent_design_version") val parentDesignVersion: Int = 1,
    @ColumnInfo(name = "created_at") val createdAt: String,
    @ColumnInfo(name = "updated_at") val updatedAt: String,
)
