package com.studyinghelper.mobile.data.sync

import com.studyinghelper.mobile.data.db.MIGRATION_1_2_STATEMENTS
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SyncDtosTest {
    private val json = Json { ignoreUnknownKeys = true; prettyPrint = true; encodeDefaults = true }

    @Test
    fun parsesWebSyncPackage() {
        val raw = """
            {
              "schema_version": "1.0",
              "exported_at": "2026-06-08T00:00:00Z",
              "source": "web",
              "user_id": "anonymous",
              "books": [
                {
                  "id": "book-1",
                  "user_id": "anonymous",
                  "title": "跨端测试",
                  "author": null,
                  "file_path": "test.txt",
                  "file_type": "txt",
                  "file_size_bytes": 10,
                  "parse_status": "completed",
                  "split_status": "completed",
                  "learn_status": "learning",
                  "total_chapters": 1,
                  "total_units": 1,
                  "learned_units": 0,
                  "reading_motivation": null,
                  "created_at": "2026-06-08T00:00:00Z",
                  "updated_at": "2026-06-08T00:00:00Z"
                }
              ],
              "chapters": [],
              "knowledge_units": [],
              "kg_nodes": [],
              "kg_edges": [],
              "mastery_records": [],
              "annotations": [],
              "learning_records": [],
              "daily_stats": [],
              "review_sessions": [],
              "teaching_sessions": [],
              "teaching_messages": [],
              "user_questions": [],
              "session_tests": [],
              "learning_efficiency": [],
              "learner_intent_profiles": [
                {
                  "id": "profile-1",
                  "user_id": "anonymous",
                  "book_id": "book-1",
                  "identity_background": "unknown",
                  "goal_depth": "apply_understand",
                  "cognitive_pref": "rigorous_system",
                  "restructure_tolerance": "moderate",
                  "time_budget_minutes": null,
                  "source": "ai_inferred",
                  "status": "confirmed",
                  "extra_json": "{}",
                  "created_at": "2026-06-08T00:00:00Z",
                  "updated_at": "2026-06-08T00:00:00Z"
                }
              ],
              "teaching_designs": [
                {
                  "id": "design-1",
                  "user_id": "anonymous",
                  "book_id": "book-1",
                  "profile_id": "profile-1",
                  "macro_design_json": "{\"modules\":[]}",
                  "current_module_index": 0,
                  "generated_module_count": 1,
                  "adjustments_json": "[]",
                  "status": "active",
                  "version": 1,
                  "created_at": "2026-06-08T00:00:00Z",
                  "updated_at": "2026-06-08T00:00:00Z"
                }
              ],
              "module_micro_plans": [
                {
                  "id": "micro-1",
                  "design_id": "design-1",
                  "book_id": "book-1",
                  "user_id": "anonymous",
                  "module_index": 0,
                  "module_title": "入门模块",
                  "ordered_unit_ids_json": "[\"unit-1\"]",
                  "unit_annotations_json": "[]",
                  "module_intro": "先建立整体认识",
                  "module_status": "active",
                  "module_summary_json": null,
                  "parent_design_version": 1,
                  "created_at": "2026-06-08T00:00:00Z",
                  "updated_at": "2026-06-08T00:00:00Z"
                }
              ]
            }
        """.trimIndent()

        val packageData = json.decodeFromString<SyncPackage>(raw)

        assertEquals(SYNC_SCHEMA_VERSION, packageData.schemaVersion)
        assertEquals("web", packageData.source)
        assertEquals("book-1", packageData.books.single().id)
        assertEquals("跨端测试", packageData.books.single().title)
        assertEquals("confirmed", packageData.learnerIntentProfiles.single().status)
        assertEquals("active", packageData.teachingDesigns.single().status)
        assertEquals(1, packageData.moduleMicroPlans.single().parentDesignVersion)
    }

    @Test
    fun previewsPackageCountsOverwrittenBooks() {
        val packageData = SyncPackage(
            exportedAt = "2026-06-08T00:00:00Z",
            source = "web",
            books = listOf(
                SyncBook(
                    id = "book-1",
                    userId = "anonymous",
                    title = "跨端测试",
                    filePath = "test.txt",
                    fileType = "txt",
                    fileSizeBytes = 10,
                    createdAt = "2026-06-08T00:00:00Z",
                    updatedAt = "2026-06-08T00:00:00Z",
                )
            ),
            knowledgeUnits = listOf(
                SyncKnowledgeUnit(
                    id = "unit-1",
                    bookId = "book-1",
                    chapterId = "chapter-1",
                    title = "知识单元",
                    content = "内容",
                    orderIndex = 0,
                    charOffsetStart = 0,
                    charOffsetEnd = 2,
                    aiCognitiveHint = "memorize",
                )
            ),
            learnerIntentProfiles = listOf(
                SyncLearnerIntentProfile(
                    id = "profile-1",
                    userId = "anonymous",
                    bookId = "book-1",
                    status = "confirmed",
                    createdAt = "2026-06-08T00:00:00Z",
                    updatedAt = "2026-06-08T00:00:00Z",
                )
            ),
            teachingDesigns = listOf(
                SyncTeachingDesign(
                    id = "design-1",
                    userId = "anonymous",
                    bookId = "book-1",
                    profileId = "profile-1",
                    status = "active",
                    createdAt = "2026-06-08T00:00:00Z",
                    updatedAt = "2026-06-08T00:00:00Z",
                )
            ),
            moduleMicroPlans = listOf(
                SyncModuleMicroPlan(
                    id = "micro-1",
                    designId = "design-1",
                    bookId = "book-1",
                    userId = "anonymous",
                    moduleIndex = 0,
                    parentDesignVersion = 1,
                    createdAt = "2026-06-08T00:00:00Z",
                    updatedAt = "2026-06-08T00:00:00Z",
                )
            ),
        )

        val preview = SyncPreview.fromPackage(packageData, setOf("book-1"))

        assertEquals("web", preview.source)
        assertEquals(1, preview.books)
        assertEquals(0, preview.chapters)
        assertEquals(1, preview.units)
        assertEquals(0, preview.reviewSessions)
        assertEquals(0, preview.teachingSessions)
        assertEquals(0, preview.teachingMessages)
        assertEquals(1, preview.learnerIntentProfiles)
        assertEquals(1, preview.teachingDesigns)
        assertEquals(1, preview.moduleMicroPlans)
        assertEquals(1, preview.overwrittenBooks)
    }

    @Test
    fun previewsAndroidExportPackageWithRound4ReturnImportCounts() {
        val packageData = SyncPackage(
            exportedAt = "2026-07-04T12:00:00Z",
            source = "android",
            books = listOf(
                SyncBook(
                    id = "round4-book",
                    userId = "anonymous",
                    title = "第四轮 Android 导出样例",
                    filePath = "android://manual/round4-book",
                    fileType = "manual",
                    fileSizeBytes = 0,
                    totalChapters = 1,
                    totalUnits = 1,
                    learnedUnits = 1,
                    createdAt = "2026-07-04T12:00:00Z",
                    updatedAt = "2026-07-04T12:00:00Z",
                )
            ),
            chapters = listOf(
                SyncChapter(
                    id = "round4-chapter",
                    bookId = "round4-book",
                    title = "默认章节",
                    chapterNumber = 1,
                    orderIndex = 0,
                )
            ),
            knowledgeUnits = listOf(
                SyncKnowledgeUnit(
                    id = "round4-unit",
                    bookId = "round4-book",
                    chapterId = "round4-chapter",
                    title = "主动复述",
                    content = "用自己的话复述可以暴露理解缺口。",
                    orderIndex = 0,
                    charOffsetStart = 0,
                    charOffsetEnd = 18,
                    aiCognitiveHint = "understand",
                )
            ),
            masteryRecords = listOf(
                SyncMasteryRecord(
                    id = "round4-mastery",
                    userId = "anonymous",
                    knowledgeUnitId = "round4-unit",
                    bookId = "round4-book",
                    masteryScore = 0.72f,
                    masteryLevel = "familiar",
                    nextReviewAt = "2026-07-05T12:00:00Z",
                    stability = 2.5f,
                    difficulty = 5.5f,
                    reps = 1,
                    scheduledDays = 1,
                    algorithm = "fsrs",
                )
            ),
            reviewSessions = listOf(
                SyncReviewSession(
                    id = "round4-review",
                    userId = "anonymous",
                    bookId = "round4-book",
                    reviewType = "exam",
                    questionsJson = "[]",
                    startedAt = "2026-07-04T12:00:00Z",
                    score = 80f,
                )
            ),
            teachingSessions = listOf(
                SyncTeachingSession(
                    id = "round4-teaching",
                    userId = "anonymous",
                    bookId = "round4-book",
                    unitIds = "[\"round4-unit\"]",
                    startedAt = "2026-07-04T12:00:00Z",
                )
            ),
            teachingMessages = listOf(
                SyncTeachingMessage(
                    id = "round4-message",
                    sessionId = "round4-teaching",
                    unitId = "round4-unit",
                    phase = "activate",
                    content = "先回想你如何复述。",
                    createdAt = "2026-07-04T12:00:00Z",
                )
            ),
            learnerIntentProfiles = listOf(
                SyncLearnerIntentProfile(
                    id = "round4-profile",
                    userId = "anonymous",
                    bookId = "round4-book",
                    status = "confirmed",
                    createdAt = "2026-07-04T12:00:00Z",
                    updatedAt = "2026-07-04T12:00:00Z",
                )
            ),
            teachingDesigns = listOf(
                SyncTeachingDesign(
                    id = "round4-design",
                    userId = "anonymous",
                    bookId = "round4-book",
                    profileId = "round4-profile",
                    status = "active",
                    createdAt = "2026-07-04T12:00:00Z",
                    updatedAt = "2026-07-04T12:00:00Z",
                )
            ),
            moduleMicroPlans = listOf(
                SyncModuleMicroPlan(
                    id = "round4-micro",
                    designId = "round4-design",
                    bookId = "round4-book",
                    userId = "anonymous",
                    moduleIndex = 0,
                    moduleTitle = "复述入门",
                    orderedUnitIdsJson = "[\"round4-unit\"]",
                    moduleStatus = "active",
                    createdAt = "2026-07-04T12:00:00Z",
                    updatedAt = "2026-07-04T12:00:00Z",
                )
            ),
        )

        val encoded = json.encodeToString(packageData)
        val decoded = json.decodeFromString<SyncPackage>(encoded)
        val preview = SyncPreview.fromPackage(decoded, setOf("round4-book"))

        assertEquals("android", preview.source)
        assertEquals(1, preview.books)
        assertEquals(1, preview.chapters)
        assertEquals(1, preview.units)
        assertEquals(1, preview.masteryRecords)
        assertEquals(1, preview.reviewSessions)
        assertEquals(1, preview.teachingSessions)
        assertEquals(1, preview.teachingMessages)
        assertEquals(1, preview.learnerIntentProfiles)
        assertEquals(1, preview.teachingDesigns)
        assertEquals(1, preview.moduleMicroPlans)
        assertEquals(1, preview.overwrittenBooks)
        assertEquals("fsrs", decoded.masteryRecords.single().algorithm)
        assertEquals("understand", decoded.knowledgeUnits.single().aiCognitiveHint)
    }

    @Test
    fun encodesAndroidSyncPackageWithSnakeCaseFields() {
        val packageData = SyncPackage(
            exportedAt = "2026-06-08T00:00:00Z",
            source = "android",
            books = emptyList(),
            knowledgeUnits = listOf(
                SyncKnowledgeUnit(
                    id = "unit-1",
                    bookId = "book-1",
                    chapterId = "chapter-1",
                    title = "知识单元",
                    content = "内容",
                    orderIndex = 0,
                    charOffsetStart = 0,
                    charOffsetEnd = 2,
                    aiCognitiveHint = "understand",
                )
            ),
        )

        val encoded = json.encodeToString(packageData)

        assertTrue(encoded.contains("\"schema_version\""))
        assertTrue(encoded.contains("\"exported_at\""))
        assertTrue(encoded.contains("\"knowledge_units\""))
        assertTrue(encoded.contains("\"ai_cognitive_hint\""))
        assertTrue(encoded.contains("\"learner_intent_profiles\""))
        assertTrue(encoded.contains("\"teaching_designs\""))
        assertTrue(encoded.contains("\"module_micro_plans\""))
        assertTrue(encoded.contains("\"mastery_records\""))
        assertTrue(encoded.contains("\"source\": \"android\""))
        assertTrue(encoded.contains("\"user_id\": \"anonymous\""))
    }

    @Test
    fun migrationAddsFsrsMasteryColumns() {
        val migrationSql = MIGRATION_1_2_STATEMENTS.joinToString("\n")

        assertTrue(migrationSql.contains("ALTER TABLE mastery_records ADD COLUMN stability"))
        assertTrue(migrationSql.contains("ALTER TABLE mastery_records ADD COLUMN difficulty"))
        assertTrue(migrationSql.contains("ALTER TABLE mastery_records ADD COLUMN lapses"))
        assertTrue(migrationSql.contains("ALTER TABLE mastery_records ADD COLUMN reps"))
        assertTrue(migrationSql.contains("ALTER TABLE mastery_records ADD COLUMN last_elapsed_days"))
        assertTrue(migrationSql.contains("ALTER TABLE mastery_records ADD COLUMN scheduled_days"))
        assertTrue(migrationSql.contains("ALTER TABLE mastery_records ADD COLUMN algorithm"))
    }
}
