package com.studyinghelper.mobile.data.sync

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
              "learning_efficiency": []
            }
        """.trimIndent()

        val packageData = json.decodeFromString<SyncPackage>(raw)

        assertEquals(SYNC_SCHEMA_VERSION, packageData.schemaVersion)
        assertEquals("web", packageData.source)
        assertEquals("book-1", packageData.books.single().id)
        assertEquals("跨端测试", packageData.books.single().title)
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
                )
            ),
        )

        val preview = SyncPreview.fromPackage(packageData, setOf("book-1"))

        assertEquals("web", preview.source)
        assertEquals(1, preview.books)
        assertEquals(1, preview.units)
        assertEquals(1, preview.overwrittenBooks)
    }

    @Test
    fun encodesAndroidSyncPackageWithSnakeCaseFields() {
        val packageData = SyncPackage(
            exportedAt = "2026-06-08T00:00:00Z",
            source = "android",
            books = emptyList(),
        )

        val encoded = json.encodeToString(packageData)

        assertTrue(encoded.contains("\"schema_version\""))
        assertTrue(encoded.contains("\"exported_at\""))
        assertTrue(encoded.contains("\"knowledge_units\""))
        assertTrue(encoded.contains("\"mastery_records\""))
        assertTrue(encoded.contains("\"source\": \"android\""))
        assertTrue(encoded.contains("\"user_id\": \"anonymous\""))
    }
}
