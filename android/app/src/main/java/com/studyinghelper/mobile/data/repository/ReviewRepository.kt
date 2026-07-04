package com.studyinghelper.mobile.data.repository

import com.studyinghelper.mobile.data.algorithm.FSRSAlgorithm
import com.studyinghelper.mobile.data.algorithm.FSRSState
import com.studyinghelper.mobile.data.db.MasteryRecordEntity
import com.studyinghelper.mobile.data.db.StudyDatabase
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.UUID

/**
 * 复习仓库 - 管理间隔重复和掌握度更新
 */
class ReviewRepository(
    private val database: StudyDatabase,
    private val fsrsAlgorithm: FSRSAlgorithm = FSRSAlgorithm()
) {
    private val dao = database.studyDao()

    /**
     * 更新掌握度记录（使用 FSRS 算法）
     *
     * @param unitId 知识单元 ID
     * @param bookId 书籍 ID
     * @param isCorrect 是否回答正确
     * @param responseTime 响应时间（秒）
     * @param avgResponseTime 平均响应时间（秒）
     * @param confidenceLevel 置信度 (1-3, 0=未提供)
     */
    suspend fun updateMastery(
        unitId: String,
        bookId: String,
        isCorrect: Boolean,
        responseTime: Float = 0f,
        avgResponseTime: Float = 30f,
        confidenceLevel: Int = 0
    ) {
        val now = LocalDateTime.now()
        val existing = dao.getMastery(unitId)

        // 计算质量分数
        val quality = calculateQuality(isCorrect, responseTime, avgResponseTime, confidenceLevel)

        // 创建或更新 FSRS 状态
        val state = if (existing != null) {
            FSRSState(
                stability = existing.stability.toDouble(),
                difficulty = existing.difficulty.toDouble(),
                elapsedDays = calculateElapsedDays(existing.lastReviewedAt, now),
                scheduledDays = existing.scheduledDays,
                reps = existing.reps,
                lapses = existing.lapses,
                lastReview = parseDateTime(existing.lastReviewedAt)
            )
        } else {
            FSRSState(reps = 0)
        }

        // 计算下次复习
        val result = fsrsAlgorithm.nextReview(state, quality, now)

        // 计算掌握度变化
        val masteryChange = calculateMasteryChange(quality, result.retrievability)

        // 更新或创建掌握度记录
        if (existing != null) {
            val newScore = (existing.masteryScore + masteryChange).coerceIn(0f, 1f)
            val updated = existing.copy(
                masteryScore = newScore,
                masteryLevel = calculateMasteryLevel(newScore),
                lastReviewedAt = now.toString(),
                nextReviewAt = result.nextReview.toString(),
                reviewCount = (existing.reviewCount ?: 0) + 1,
                easeFactor = ((10 - result.difficulty) / 9 * 2.5).toFloat().coerceIn(1.3f, 2.5f),
                intervalDays = result.scheduledDays,
                stability = result.stability.toFloat(),
                difficulty = result.difficulty.toFloat(),
                lapses = result.lapses,
                reps = existing.reps + 1,
                lastElapsedDays = calculateElapsedDays(existing.lastReviewedAt, now),
                scheduledDays = result.scheduledDays,
                algorithm = "fsrs"
            )
            dao.insertMastery(listOf(updated))
        } else {
            val initialScore = masteryChange.coerceIn(0f, 1f)
            val newRecord = MasteryRecordEntity(
                id = "mastery-${UUID.randomUUID()}",
                userId = "anonymous",
                knowledgeUnitId = unitId,
                bookId = bookId,
                masteryScore = initialScore,
                masteryLevel = calculateMasteryLevel(initialScore),
                lastReviewedAt = now.toString(),
                nextReviewAt = result.nextReview.toString(),
                reviewCount = 1,
                easeFactor = ((10 - result.difficulty) / 9 * 2.5).toFloat().coerceIn(1.3f, 2.5f),
                intervalDays = result.scheduledDays,
                stability = result.stability.toFloat(),
                difficulty = result.difficulty.toFloat(),
                lapses = result.lapses,
                reps = 1,
                lastElapsedDays = 0,
                scheduledDays = result.scheduledDays,
                algorithm = "fsrs"
            )
            dao.insertMastery(listOf(newRecord))
        }
    }

    /**
     * 计算质量分数 (1-4)
     */
    private fun calculateQuality(
        isCorrect: Boolean,
        responseTime: Float,
        avgResponseTime: Float,
        confidenceLevel: Int
    ): Int {
        val baseQuality = if (isCorrect) {
            if (avgResponseTime <= 0) {
                3 // 默认 GOOD
            } else {
                val speedRatio = responseTime / avgResponseTime
                when {
                    speedRatio < 0.8 -> 4  // EASY
                    speedRatio <= 1.2 -> 3 // GOOD
                    else -> 2              // HARD
                }
            }
        } else {
            if (avgResponseTime <= 0 || responseTime / avgResponseTime < 1.0) {
                1 // AGAIN
            } else {
                1 // AGAIN
            }
        }

        // 根据置信度调整
        return when {
            confidenceLevel == 0 -> baseQuality
            confidenceLevel == 1 && baseQuality >= 3 -> maxOf(1, baseQuality - 1) // 低置信度，降低质量
            confidenceLevel == 3 && baseQuality >= 4 -> minOf(4, baseQuality + 1) // 高置信度，提高质量
            else -> baseQuality
        }
    }

    /**
     * 计算掌握度变化
     */
    private fun calculateMasteryChange(quality: Int, retrievability: Double): Float {
        return if (quality < 3) {
            // 回答失败
            (-0.2 * (1 - retrievability)).toFloat()
        } else {
            // 回答成功
            val baseGain = if (quality == 4) 0.15f else 0.1f
            (baseGain + 0.1 * (1 - retrievability)).toFloat()
        }
    }

    /**
     * 计算掌握度等级
     */
    private fun calculateMasteryLevel(score: Float): String {
        return when {
            score >= 0.85f -> "mastered"
            score >= 0.65f -> "proficient"
            score >= 0.40f -> "familiar"
            score >= 0.20f -> "learning"
            else -> "beginner"
        }
    }

    /**
     * 计算已过天数
     */
    private fun calculateElapsedDays(lastReviewedAt: String?, now: LocalDateTime): Int {
        if (lastReviewedAt == null) return 0
        val lastReview = parseDateTime(lastReviewedAt) ?: return 0
        return java.time.Duration.between(lastReview, now).toDays().toInt()
    }

    /**
     * 解析日期时间字符串
     */
    private fun parseDateTime(dateTimeStr: String?): LocalDateTime? {
        if (dateTimeStr == null) return null
        return try {
            LocalDateTime.parse(dateTimeStr, DateTimeFormatter.ISO_DATE_TIME)
        } catch (e: Exception) {
            try {
                OffsetDateTime.parse(dateTimeStr).toLocalDateTime()
            } catch (e2: Exception) {
                null
            }
        }
    }
}
