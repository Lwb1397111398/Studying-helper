package com.studyinghelper.mobile.data.repository

import com.studyinghelper.mobile.data.db.DailyStatsEntity
import com.studyinghelper.mobile.data.db.KnowledgeUnitEntity
import com.studyinghelper.mobile.data.db.ReviewSessionEntity
import com.studyinghelper.mobile.data.db.StudyDatabase
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.time.LocalDate
import java.time.OffsetDateTime
import java.util.UUID

class ExamRepository(private val database: StudyDatabase) {
    private val dao = database.studyDao()
    private val json = Json { prettyPrint = false }

    suspend fun generateExam(bookId: String, limit: Int = 10): List<ExamQuestion> {
        val units = dao.getUnits(bookId)
        require(units.isNotEmpty()) { "没有可考试的知识单元" }
        return units
            .sortedBy { it.orderIndex }
            .take(limit)
            .map { unit -> unit.toQuestion() }
    }

    suspend fun saveExamResult(bookId: String, questions: List<ExamQuestion>): ExamResultSummary {
        require(questions.isNotEmpty()) { "考试题目为空" }
        val now = OffsetDateTime.now()
        val score = questions.map { it.selfScore.coerceIn(0, 100) }.average().toFloat()
        dao.insertReviewSessions(
            listOf(
                ReviewSessionEntity(
                    id = "android-exam-${UUID.randomUUID()}",
                    userId = "anonymous",
                    bookId = bookId,
                    reviewType = "exam",
                    questionsJson = json.encodeToString(questions),
                    startedAt = now.toString(),
                    endedAt = now.toString(),
                    score = score,
                )
            )
        )
        updateDailyExamStats(score)
        return ExamResultSummary(score = score, total = questions.size)
    }

    private suspend fun updateDailyExamStats(score: Float) {
        val today = LocalDate.now().toString()
        val old = dao.getDailyStats("anonymous", today)
        val oldTests = old?.testsTaken ?: 0
        val oldAverage = old?.avgTestScore ?: 0f
        val newTests = oldTests + 1
        val newAverage = ((oldAverage * oldTests) + score) / newTests
        dao.insertDailyStats(
            listOf(
                DailyStatsEntity(
                    userId = "anonymous",
                    date = today,
                    totalMinutes = old?.totalMinutes ?: 0,
                    unitsLearned = old?.unitsLearned ?: 0,
                    unitsReviewed = old?.unitsReviewed ?: 0,
                    testsTaken = newTests,
                    avgTestScore = newAverage,
                    streakDay = old?.streakDay ?: 1,
                )
            )
        )
    }

    private fun KnowledgeUnitEntity.toQuestion(): ExamQuestion {
        val reference = summary?.takeIf { it.isNotBlank() }
            ?: explanation?.takeIf { it.isNotBlank() }
            ?: content.take(300)
        return ExamQuestion(
            id = "question-${UUID.randomUUID()}",
            unitId = id,
            unitTitle = title,
            prompt = "请用自己的话回忆：$title",
            referenceAnswer = reference,
        )
    }
}

@Serializable
data class ExamQuestion(
    val id: String,
    val unitId: String,
    val unitTitle: String,
    val prompt: String,
    val referenceAnswer: String,
    val userAnswer: String = "",
    val selfScore: Int = 0,
)

data class ExamResultSummary(val score: Float, val total: Int)

data class ExamState(
    val bookId: String,
    val questions: List<ExamQuestion>,
    val currentIndex: Int = 0,
    val result: ExamResultSummary? = null,
)
