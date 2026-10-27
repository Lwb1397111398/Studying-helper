package com.studyinghelper.mobile.data.algorithm

import java.time.LocalDateTime
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * FSRS 算法锁定测试（与后端 P1 口径对齐）：
 * - 仅 AGAIN（grade=1）递增 lapses，HARD/GOOD/EASY 保持；
 * - 连续 AGAIN 依次 1、2、3；
 * - 存量 lapses 直通（输入 2 输出仍为 2）。
 */
class FSRSAlgorithmTest {
    private val algorithm = FSRSAlgorithm()
    private val now: LocalDateTime = LocalDateTime.of(2026, 1, 1, 0, 0)

    private fun stateWith(lapses: Int) = FSRSState(
        stability = 5.0,
        difficulty = 5.0,
        elapsedDays = 0,
        scheduledDays = 10,
        reps = 3,
        lapses = lapses,
        lastReview = now.minusDays(10),
    )

    @Test
    fun `again 增加 lapses 其余等级保持`() {
        assertEquals(3, algorithm.nextReview(stateWith(2), FSRSAlgorithm.GRADE_AGAIN, now).lapses)
        assertEquals(2, algorithm.nextReview(stateWith(2), FSRSAlgorithm.GRADE_HARD, now).lapses)
        assertEquals(2, algorithm.nextReview(stateWith(2), FSRSAlgorithm.GRADE_GOOD, now).lapses)
        assertEquals(2, algorithm.nextReview(stateWith(2), FSRSAlgorithm.GRADE_EASY, now).lapses)
    }

    @Test
    fun `连续 again 依次累积 1 2 3`() {
        var state = FSRSState(reps = 1, lapses = 0, lastReview = now.minusDays(1))
        var cursor = now
        for (expected in listOf(1, 2, 3)) {
            cursor = cursor.plusDays(1)
            val result = algorithm.nextReview(state, FSRSAlgorithm.GRADE_AGAIN, cursor)
            assertEquals(expected, result.lapses)
            state = FSRSState(
                stability = result.stability,
                difficulty = result.difficulty,
                scheduledDays = result.scheduledDays,
                reps = state.reps + 1,
                lapses = result.lapses,
                lastReview = cursor,
            )
        }
    }

    @Test
    fun `新卡首评不计遗忘`() {
        val result = algorithm.nextReview(FSRSState(reps = 0), FSRSAlgorithm.GRADE_AGAIN, now)
        assertEquals(0, result.lapses)
        assertTrue(result.stability > 0)
    }
}
