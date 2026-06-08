package com.studyinghelper.mobile.data.sync

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

const val SYNC_SCHEMA_VERSION = "1.0"

@Serializable
data class SyncPackage(
    @SerialName("schema_version") val schemaVersion: String = SYNC_SCHEMA_VERSION,
    @SerialName("exported_at") val exportedAt: String,
    val source: String = "android",
    @SerialName("user_id") val userId: String = "anonymous",
    val books: List<SyncBook> = emptyList(),
    val chapters: List<SyncChapter> = emptyList(),
    @SerialName("knowledge_units") val knowledgeUnits: List<SyncKnowledgeUnit> = emptyList(),
    @SerialName("kg_nodes") val kgNodes: List<SyncKgNode> = emptyList(),
    @SerialName("kg_edges") val kgEdges: List<SyncKgEdge> = emptyList(),
    @SerialName("mastery_records") val masteryRecords: List<SyncMasteryRecord> = emptyList(),
    val annotations: List<SyncAnnotation> = emptyList(),
    @SerialName("learning_records") val learningRecords: List<SyncLearningRecord> = emptyList(),
    @SerialName("daily_stats") val dailyStats: List<SyncDailyStats> = emptyList(),
    @SerialName("review_sessions") val reviewSessions: List<SyncReviewSession> = emptyList(),
    @SerialName("teaching_sessions") val teachingSessions: List<SyncTeachingSession> = emptyList(),
    @SerialName("teaching_messages") val teachingMessages: List<SyncTeachingMessage> = emptyList(),
    @SerialName("user_questions") val userQuestions: List<SyncUserQuestion> = emptyList(),
    @SerialName("session_tests") val sessionTests: List<SyncSessionTest> = emptyList(),
    @SerialName("learning_efficiency") val learningEfficiency: List<SyncLearningEfficiency> = emptyList(),
)

@Serializable
data class SyncBook(
    val id: String,
    @SerialName("user_id") val userId: String,
    val title: String,
    val author: String? = null,
    @SerialName("file_path") val filePath: String,
    @SerialName("file_type") val fileType: String,
    @SerialName("file_size_bytes") val fileSizeBytes: Int,
    @SerialName("parse_status") val parseStatus: String? = "pending",
    @SerialName("split_status") val splitStatus: String? = "pending",
    @SerialName("learn_status") val learnStatus: String? = "pending",
    @SerialName("total_chapters") val totalChapters: Int? = 0,
    @SerialName("total_units") val totalUnits: Int? = 0,
    @SerialName("learned_units") val learnedUnits: Int? = 0,
    @SerialName("reading_motivation") val readingMotivation: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
data class SyncChapter(
    val id: String,
    @SerialName("book_id") val bookId: String,
    val title: String,
    @SerialName("chapter_number") val chapterNumber: Int,
    @SerialName("parent_id") val parentId: String? = null,
    val level: Int? = 0,
    @SerialName("order_index") val orderIndex: Int,
    val summary: String? = null,
)

@Serializable
data class SyncKnowledgeUnit(
    val id: String,
    @SerialName("book_id") val bookId: String,
    @SerialName("chapter_id") val chapterId: String,
    @SerialName("section_id") val sectionId: String? = null,
    val title: String,
    val content: String,
    @SerialName("order_index") val orderIndex: Int,
    @SerialName("char_offset_start") val charOffsetStart: Int,
    @SerialName("char_offset_end") val charOffsetEnd: Int,
    val summary: String? = null,
    val explanation: String? = null,
    @SerialName("key_points") val keyPoints: String? = null,
    val concepts: String? = null,
    val prerequisites: String? = null,
    @SerialName("difficulty_level") val difficultyLevel: Int? = null,
    @SerialName("importance_score") val importanceScore: Float? = null,
)

@Serializable
data class SyncKgNode(
    val id: String,
    @SerialName("node_type") val nodeType: String,
    val label: String,
    @SerialName("book_id") val bookId: String,
    @SerialName("content_summary") val contentSummary: String? = null,
    @SerialName("difficulty_level") val difficultyLevel: Int? = null,
    @SerialName("importance_score") val importanceScore: Float? = null,
    @SerialName("mastery_score") val masteryScore: Float? = null,
    @SerialName("mastery_level") val masteryLevel: String? = null,
    val size: Float? = 1f,
    val color: String? = null,
)

@Serializable
data class SyncKgEdge(
    val id: String,
    @SerialName("source_id") val sourceId: String,
    @SerialName("target_id") val targetId: String,
    @SerialName("relation_type") val relationType: String,
    val weight: Float? = 1f,
    @SerialName("metadata_json") val metadataJson: String? = null,
)

@Serializable
data class SyncMasteryRecord(
    val id: String,
    @SerialName("user_id") val userId: String,
    @SerialName("knowledge_unit_id") val knowledgeUnitId: String,
    @SerialName("book_id") val bookId: String,
    @SerialName("mastery_score") val masteryScore: Float,
    @SerialName("mastery_level") val masteryLevel: String,
    @SerialName("last_reviewed_at") val lastReviewedAt: String? = null,
    @SerialName("next_review_at") val nextReviewAt: String,
    @SerialName("review_count") val reviewCount: Int? = 0,
    @SerialName("ease_factor") val easeFactor: Float? = 2.5f,
    @SerialName("interval_days") val intervalDays: Int? = 1,
)

@Serializable
data class SyncAnnotation(
    val id: String,
    @SerialName("user_id") val userId: String,
    @SerialName("knowledge_unit_id") val knowledgeUnitId: String,
    @SerialName("annotation_type") val annotationType: String,
    val content: String? = null,
    @SerialName("related_concepts_json") val relatedConceptsJson: String? = "[]",
    val example: String? = null,
    @SerialName("cornell_cues") val cornellCues: String? = null,
    @SerialName("cornell_summary") val cornellSummary: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
data class SyncLearningRecord(
    val id: String,
    @SerialName("user_id") val userId: String,
    @SerialName("book_id") val bookId: String,
    @SerialName("session_id") val sessionId: String,
    @SerialName("started_at") val startedAt: String,
    @SerialName("ended_at") val endedAt: String? = null,
    @SerialName("duration_minutes") val durationMinutes: Int? = null,
    @SerialName("units_covered") val unitsCovered: String? = null,
    @SerialName("questions_asked") val questionsAsked: Int? = 0,
    @SerialName("test_score") val testScore: Float? = null,
    @SerialName("annotations_created") val annotationsCreated: Int? = 0,
)

@Serializable
data class SyncDailyStats(
    @SerialName("user_id") val userId: String,
    val date: String,
    @SerialName("total_minutes") val totalMinutes: Int? = 0,
    @SerialName("units_learned") val unitsLearned: Int? = 0,
    @SerialName("units_reviewed") val unitsReviewed: Int? = 0,
    @SerialName("tests_taken") val testsTaken: Int? = 0,
    @SerialName("avg_test_score") val avgTestScore: Float? = 0f,
    @SerialName("streak_day") val streakDay: Int? = 0,
)

@Serializable
data class SyncReviewSession(
    val id: String,
    @SerialName("user_id") val userId: String,
    @SerialName("book_id") val bookId: String,
    @SerialName("review_type") val reviewType: String,
    @SerialName("questions_json") val questionsJson: String,
    @SerialName("started_at") val startedAt: String,
    @SerialName("ended_at") val endedAt: String? = null,
    val score: Float? = null,
)

@Serializable
data class SyncTeachingSession(
    val id: String,
    @SerialName("user_id") val userId: String,
    @SerialName("plan_session_id") val planSessionId: String? = "",
    @SerialName("book_id") val bookId: String,
    @SerialName("unit_ids") val unitIds: String? = "[]",
    @SerialName("current_unit_index") val currentUnitIndex: Int? = 0,
    @SerialName("current_phase") val currentPhase: String? = "activate",
    @SerialName("strategy_json") val strategyJson: String? = "{}",
    val status: String? = "active",
    @SerialName("started_at") val startedAt: String,
    @SerialName("ended_at") val endedAt: String? = null,
)

@Serializable
data class SyncTeachingMessage(
    val id: String,
    @SerialName("session_id") val sessionId: String,
    @SerialName("unit_id") val unitId: String,
    val phase: String,
    val content: String,
    @SerialName("content_type") val contentType: String? = "text",
    @SerialName("assessment_json") val assessmentJson: String? = null,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class SyncUserQuestion(
    val id: String,
    @SerialName("session_id") val sessionId: String,
    val question: String,
    val answer: String,
    val intent: String,
    @SerialName("follow_up_json") val followUpJson: String? = "[]",
    @SerialName("asked_at") val askedAt: String,
)

@Serializable
data class SyncSessionTest(
    val id: String,
    @SerialName("session_id") val sessionId: String,
    @SerialName("questions_json") val questionsJson: String? = "[]",
    @SerialName("user_answers_json") val userAnswersJson: String? = "[]",
    val score: Float? = null,
    @SerialName("weak_points_json") val weakPointsJson: String? = "[]",
    @SerialName("completed_at") val completedAt: String? = null,
)

@Serializable
data class SyncLearningEfficiency(
    val id: String,
    @SerialName("session_id") val sessionId: String,
    @SerialName("unit_id") val unitId: String,
    val phase: String,
    @SerialName("duration_seconds") val durationSeconds: Int,
    @SerialName("interaction_count") val interactionCount: Int? = 0,
    @SerialName("efficiency_score") val efficiencyScore: Float? = 0f,
    @SerialName("created_at") val createdAt: String,
)
