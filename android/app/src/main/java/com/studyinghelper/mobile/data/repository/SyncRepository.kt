package com.studyinghelper.mobile.data.repository

import androidx.room.withTransaction
import com.studyinghelper.mobile.data.db.AnnotationEntity
import com.studyinghelper.mobile.data.db.BookEntity
import com.studyinghelper.mobile.data.db.ChapterEntity
import com.studyinghelper.mobile.data.db.DailyStatsEntity
import com.studyinghelper.mobile.data.db.KgEdgeEntity
import com.studyinghelper.mobile.data.db.KgNodeEntity
import com.studyinghelper.mobile.data.db.KnowledgeUnitEntity
import com.studyinghelper.mobile.data.db.LearningEfficiencyEntity
import com.studyinghelper.mobile.data.db.LearningRecordEntity
import com.studyinghelper.mobile.data.db.MasteryRecordEntity
import com.studyinghelper.mobile.data.db.ReviewSessionEntity
import com.studyinghelper.mobile.data.db.SessionTestEntity
import com.studyinghelper.mobile.data.db.StudyDatabase
import com.studyinghelper.mobile.data.db.TeachingMessageEntity
import com.studyinghelper.mobile.data.db.TeachingSessionEntity
import com.studyinghelper.mobile.data.db.UserQuestionEntity
import com.studyinghelper.mobile.data.sync.SYNC_SCHEMA_VERSION
import com.studyinghelper.mobile.data.sync.SyncAnnotation
import com.studyinghelper.mobile.data.sync.SyncBook
import com.studyinghelper.mobile.data.sync.SyncChapter
import com.studyinghelper.mobile.data.sync.SyncDailyStats
import com.studyinghelper.mobile.data.sync.SyncKgEdge
import com.studyinghelper.mobile.data.sync.SyncKgNode
import com.studyinghelper.mobile.data.sync.SyncKnowledgeUnit
import com.studyinghelper.mobile.data.sync.SyncLearningEfficiency
import com.studyinghelper.mobile.data.sync.SyncLearningRecord
import com.studyinghelper.mobile.data.sync.SyncMasteryRecord
import com.studyinghelper.mobile.data.sync.SyncPackage
import com.studyinghelper.mobile.data.sync.SyncPreview
import com.studyinghelper.mobile.data.sync.SyncReviewSession
import com.studyinghelper.mobile.data.sync.SyncSessionTest
import com.studyinghelper.mobile.data.sync.SyncTeachingMessage
import com.studyinghelper.mobile.data.sync.SyncTeachingSession
import com.studyinghelper.mobile.data.sync.SyncUserQuestion
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.time.OffsetDateTime

class SyncRepository(private val database: StudyDatabase) {
    private val dao = database.studyDao()
    private val json = Json { ignoreUnknownKeys = true; prettyPrint = true; encodeDefaults = true }

    suspend fun previewPackage(content: String): SyncPreview {
        val packageData = json.decodeFromString<SyncPackage>(content)
        require(packageData.schemaVersion == SYNC_SCHEMA_VERSION) { "不支持的同步包版本: ${packageData.schemaVersion}" }
        require(packageData.books.isNotEmpty()) { "同步包中没有书籍数据" }
        validatePackageScope(packageData)
        val localBookIds = dao.getBooks().map { it.id }.toSet()
        return SyncPreview.fromPackage(packageData, localBookIds)
    }

    suspend fun importPackage(content: String): ImportResult {
        val packageData = json.decodeFromString<SyncPackage>(content)
        require(packageData.schemaVersion == SYNC_SCHEMA_VERSION) { "不支持的同步包版本: ${packageData.schemaVersion}" }
        val bookIds = packageData.books.map { it.id }
        require(bookIds.isNotEmpty()) { "同步包中没有书籍数据" }
        validatePackageScope(packageData)
        val localBookIds = dao.getBooks().map { it.id }.toSet()
        val overwrittenBooks = bookIds.filter { it in localBookIds }

        database.withTransaction {
            val unitIds = dao.getUnitIds(bookIds)
            val nodeIds = dao.getNodeIds(bookIds)
            val sessionIds = dao.getTeachingSessionIds(bookIds)
            if (unitIds.isNotEmpty()) dao.deleteAnnotations(unitIds)
            if (nodeIds.isNotEmpty()) dao.deleteKgEdges(nodeIds)
            if (sessionIds.isNotEmpty()) {
                dao.deleteTeachingMessages(sessionIds)
                dao.deleteUserQuestions(sessionIds)
                dao.deleteSessionTests(sessionIds)
                dao.deleteLearningEfficiency(sessionIds)
            }
            dao.deleteMastery(bookIds)
            dao.deleteLearningRecords(bookIds)
            dao.deleteReviewSessions(bookIds)
            dao.deleteTeachingSessions(bookIds)
            dao.deleteKgNodes(bookIds)
            dao.deleteUnits(bookIds)
            dao.deleteChapters(bookIds)
            dao.deleteBooks(bookIds)

            val dates = packageData.dailyStats.map { it.date }
            if (dates.isNotEmpty()) dao.deleteDailyStats("anonymous", dates)

            dao.insertBooks(packageData.books.map { it.toEntity() })
            dao.insertChapters(packageData.chapters.map { it.toEntity() })
            dao.insertUnits(packageData.knowledgeUnits.map { it.toEntity() })
            dao.insertKgNodes(packageData.kgNodes.map { it.toEntity() })
            dao.insertKgEdges(packageData.kgEdges.map { it.toEntity() })
            dao.insertMastery(packageData.masteryRecords.map { it.toEntity() })
            dao.insertAnnotations(packageData.annotations.map { it.toEntity() })
            dao.insertLearningRecords(packageData.learningRecords.map { it.toEntity() })
            dao.insertDailyStats(packageData.dailyStats.map { it.toEntity() })
            dao.insertReviewSessions(packageData.reviewSessions.map { it.toEntity() })
            dao.insertTeachingSessions(packageData.teachingSessions.map { it.toEntity() })
            dao.insertTeachingMessages(packageData.teachingMessages.map { it.toEntity() })
            dao.insertUserQuestions(packageData.userQuestions.map { it.toEntity() })
            dao.insertSessionTests(packageData.sessionTests.map { it.toEntity() })
            dao.insertLearningEfficiency(packageData.learningEfficiency.map { it.toEntity() })
        }

        return ImportResult(
            books = packageData.books.size,
            chapters = packageData.chapters.size,
            units = packageData.knowledgeUnits.size,
            masteryRecords = packageData.masteryRecords.size,
            annotations = packageData.annotations.size,
            learningRecords = packageData.learningRecords.size,
            reviewSessions = packageData.reviewSessions.size,
            teachingSessions = packageData.teachingSessions.size,
            teachingMessages = packageData.teachingMessages.size,
            overwrittenBooks = overwrittenBooks,
        )
    }

    private fun validatePackageScope(packageData: SyncPackage) {
        val bookIds = packageData.books.map { it.id }.toSet()
        val chapterIds = packageData.chapters.map { it.id }.toSet()
        val unitIds = packageData.knowledgeUnits.map { it.id }.toSet()
        val nodeIds = packageData.kgNodes.map { it.id }.toSet()
        val teachingSessionIds = packageData.teachingSessions.map { it.id }.toSet()

        require(packageData.chapters.all { it.bookId in bookIds }) { "同步包包含不属于导入书籍的章节" }
        require(packageData.chapters.all { it.parentId == null || it.parentId in chapterIds }) { "同步包包含不属于导入章节树的父章节" }
        require(packageData.knowledgeUnits.all { it.bookId in bookIds }) { "同步包包含不属于导入书籍的知识单元" }
        require(packageData.knowledgeUnits.all { it.chapterId in chapterIds }) { "同步包包含不属于导入章节的知识单元" }
        require(packageData.kgNodes.all { it.bookId in bookIds }) { "同步包包含不属于导入书籍的图谱节点" }
        require(packageData.kgEdges.all { it.sourceId in nodeIds && it.targetId in nodeIds }) { "同步包包含不属于导入图谱的关系" }
        require(packageData.masteryRecords.all { it.bookId in bookIds && it.knowledgeUnitId in unitIds }) { "同步包包含不属于导入书籍的掌握度记录" }
        require(packageData.annotations.all { it.knowledgeUnitId in unitIds }) { "同步包包含不属于导入书籍的注释" }
        require(packageData.learningRecords.all { it.bookId in bookIds }) { "同步包包含不属于导入书籍的学习记录" }
        require(packageData.reviewSessions.all { it.bookId in bookIds }) { "同步包包含不属于导入书籍的复习记录" }
        require(packageData.teachingSessions.all { it.bookId in bookIds }) { "同步包包含不属于导入书籍的教学会话" }
        require(packageData.teachingMessages.all { it.sessionId in teachingSessionIds }) { "同步包包含不属于导入教学会话的教学消息" }
        require(packageData.userQuestions.all { it.sessionId in teachingSessionIds }) { "同步包包含不属于导入教学会话的用户提问" }
        require(packageData.sessionTests.all { it.sessionId in teachingSessionIds }) { "同步包包含不属于导入教学会话的阶段测试" }
        require(packageData.learningEfficiency.all { it.sessionId in teachingSessionIds && it.unitId in unitIds }) { "同步包包含不属于导入范围的学习效率记录" }
    }

    suspend fun exportPackage(): String {
        val books = dao.getBooks()
        require(books.isNotEmpty()) { "没有可导出的书籍" }
        val packageData = SyncPackage(
            exportedAt = OffsetDateTime.now().toString(),
            source = "android",
            books = books.map { it.toSync() },
            chapters = dao.getChapters().map { it.toSync() },
            knowledgeUnits = dao.getKnowledgeUnits().map { it.toSync() },
            kgNodes = dao.getKgNodes().map { it.toSync() },
            kgEdges = dao.getKgEdges().map { it.toSync() },
            masteryRecords = dao.getMasteryRecords().map { it.toSync() },
            annotations = dao.getAnnotations().map { it.toSync() },
            learningRecords = dao.getLearningRecords().map { it.toSync() },
            dailyStats = dao.getDailyStats().map { it.toSync() },
            reviewSessions = dao.getReviewSessions().map { it.toSync() },
            teachingSessions = dao.getTeachingSessions().map { it.toSync() },
            teachingMessages = dao.getTeachingMessages().map { it.toSync() },
            userQuestions = dao.getUserQuestions().map { it.toSync() },
            sessionTests = dao.getSessionTests().map { it.toSync() },
            learningEfficiency = dao.getLearningEfficiency().map { it.toSync() },
        )
        return json.encodeToString(packageData)
    }
}

data class ImportResult(
    val books: Int,
    val chapters: Int,
    val units: Int,
    val masteryRecords: Int,
    val annotations: Int,
    val learningRecords: Int,
    val reviewSessions: Int,
    val teachingSessions: Int,
    val teachingMessages: Int,
    val overwrittenBooks: List<String>,
)

private fun SyncBook.toEntity() = BookEntity(id, "anonymous", title, author, filePath, fileType, fileSizeBytes, parseStatus, splitStatus, learnStatus, totalChapters, totalUnits, learnedUnits, readingMotivation, createdAt, updatedAt)
private fun BookEntity.toSync() = SyncBook(id, userId, title, author, filePath, fileType, fileSizeBytes, parseStatus, splitStatus, learnStatus, totalChapters, totalUnits, learnedUnits, readingMotivation, createdAt, updatedAt)
private fun SyncChapter.toEntity() = ChapterEntity(id, bookId, title, chapterNumber, parentId, level, orderIndex, summary)
private fun ChapterEntity.toSync() = SyncChapter(id, bookId, title, chapterNumber, parentId, level, orderIndex, summary)
private fun SyncKnowledgeUnit.toEntity() = KnowledgeUnitEntity(id, bookId, chapterId, sectionId, title, content, orderIndex, charOffsetStart, charOffsetEnd, summary, explanation, keyPoints, concepts, prerequisites, difficultyLevel, importanceScore)
private fun KnowledgeUnitEntity.toSync() = SyncKnowledgeUnit(id, bookId, chapterId, sectionId, title, content, orderIndex, charOffsetStart, charOffsetEnd, summary, explanation, keyPoints, concepts, prerequisites, difficultyLevel, importanceScore)
private fun SyncKgNode.toEntity() = KgNodeEntity(id, nodeType, label, bookId, contentSummary, difficultyLevel, importanceScore, masteryScore, masteryLevel, size, color)
private fun KgNodeEntity.toSync() = SyncKgNode(id, nodeType, label, bookId, contentSummary, difficultyLevel, importanceScore, masteryScore, masteryLevel, size, color)
private fun SyncKgEdge.toEntity() = KgEdgeEntity(id, sourceId, targetId, relationType, weight, metadataJson)
private fun KgEdgeEntity.toSync() = SyncKgEdge(id, sourceId, targetId, relationType, weight, metadataJson)
private fun SyncMasteryRecord.toEntity() = MasteryRecordEntity(id, "anonymous", knowledgeUnitId, bookId, masteryScore, masteryLevel, lastReviewedAt, nextReviewAt, reviewCount, easeFactor, intervalDays)
private fun MasteryRecordEntity.toSync() = SyncMasteryRecord(id, userId, knowledgeUnitId, bookId, masteryScore, masteryLevel, lastReviewedAt, nextReviewAt, reviewCount, easeFactor, intervalDays)
private fun SyncAnnotation.toEntity() = AnnotationEntity(id, "anonymous", knowledgeUnitId, annotationType, content, relatedConceptsJson, example, cornellCues, cornellSummary, createdAt, updatedAt)
private fun AnnotationEntity.toSync() = SyncAnnotation(id, userId, knowledgeUnitId, annotationType, content, relatedConceptsJson, example, cornellCues, cornellSummary, createdAt, updatedAt)
private fun SyncLearningRecord.toEntity() = LearningRecordEntity(id, "anonymous", bookId, sessionId, startedAt, endedAt, durationMinutes, unitsCovered, questionsAsked, testScore, annotationsCreated)
private fun LearningRecordEntity.toSync() = SyncLearningRecord(id, userId, bookId, sessionId, startedAt, endedAt, durationMinutes, unitsCovered, questionsAsked, testScore, annotationsCreated)
private fun SyncDailyStats.toEntity() = DailyStatsEntity("anonymous", date, totalMinutes, unitsLearned, unitsReviewed, testsTaken, avgTestScore, streakDay)
private fun DailyStatsEntity.toSync() = SyncDailyStats(userId, date, totalMinutes, unitsLearned, unitsReviewed, testsTaken, avgTestScore, streakDay)
private fun SyncReviewSession.toEntity() = ReviewSessionEntity(id, "anonymous", bookId, reviewType, questionsJson, startedAt, endedAt, score)
private fun ReviewSessionEntity.toSync() = SyncReviewSession(id, userId, bookId, reviewType, questionsJson, startedAt, endedAt, score)
private fun SyncTeachingSession.toEntity() = TeachingSessionEntity(id, "anonymous", planSessionId, bookId, unitIds, currentUnitIndex, currentPhase, strategyJson, status, startedAt, endedAt)
private fun TeachingSessionEntity.toSync() = SyncTeachingSession(id, userId, planSessionId, bookId, unitIds, currentUnitIndex, currentPhase, strategyJson, status, startedAt, endedAt)
private fun SyncTeachingMessage.toEntity() = TeachingMessageEntity(id, sessionId, unitId, phase, content, contentType, assessmentJson, createdAt)
private fun TeachingMessageEntity.toSync() = SyncTeachingMessage(id, sessionId, unitId, phase, content, contentType, assessmentJson, createdAt)
private fun SyncUserQuestion.toEntity() = UserQuestionEntity(id, sessionId, question, answer, intent, followUpJson, askedAt)
private fun UserQuestionEntity.toSync() = SyncUserQuestion(id, sessionId, question, answer, intent, followUpJson, askedAt)
private fun SyncSessionTest.toEntity() = SessionTestEntity(id, sessionId, questionsJson, userAnswersJson, score, weakPointsJson, completedAt)
private fun SessionTestEntity.toSync() = SyncSessionTest(id, sessionId, questionsJson, userAnswersJson, score, weakPointsJson, completedAt)
private fun SyncLearningEfficiency.toEntity() = LearningEfficiencyEntity(id, sessionId, unitId, phase, durationSeconds, interactionCount, efficiencyScore, createdAt)
private fun LearningEfficiencyEntity.toSync() = SyncLearningEfficiency(id, sessionId, unitId, phase, durationSeconds, interactionCount, efficiencyScore, createdAt)
