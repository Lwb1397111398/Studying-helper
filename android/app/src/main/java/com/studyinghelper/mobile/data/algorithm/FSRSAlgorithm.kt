package com.studyinghelper.mobile.data.algorithm

import java.time.LocalDateTime
import java.time.temporal.ChronoUnit
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min
import kotlin.math.round
import kotlin.math.pow

/**
 * FSRS (Free Spaced Repetition Scheduler) 算法实现
 *
 * 基于 FSRS v4 算法，提供更精确的遗忘曲线建模和个性化间隔计算。
 *
 * 参考文献：
 * - https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm
 * - https://arxiv.org/abs/2302.05797
 */
class FSRSAlgorithm(
    private val parameters: DoubleArray = DEFAULT_PARAMETERS
) {
    init {
        require(parameters.size == 17) { "FSRS 参数必须是 17 个浮点数" }
    }

    /**
     * 计算下次复习时间
     *
     * @param state 当前 FSRS 状态
     * @param grade 评分等级 (1-4)
     * @param now 当前时间
     * @return FSRS 计算结果
     */
    fun nextReview(
        state: FSRSState,
        grade: Int,
        now: LocalDateTime = LocalDateTime.now()
    ): FSRSResult {
        require(grade in 1..4) { "评分等级必须在 1-4 之间" }

        // 计算当前可提取性
        val elapsedDays = if (state.lastReview != null) {
            ChronoUnit.DAYS.between(state.lastReview, now).toInt()
        } else {
            0
        }

        // 新卡片初始化
        if (state.reps == 0) {
            return initCard(grade, now)
        }

        // 已有卡片更新
        return updateCard(state, grade, elapsedDays, now)
    }

    /**
     * 初始化新卡片
     */
    private fun initCard(grade: Int, now: LocalDateTime): FSRSResult {
        // 初始稳定性基于评分
        val stability = initialStability(grade)

        // 初始难度基于评分
        val difficulty = initialDifficulty(grade)

        // 计算间隔
        val scheduledDays = nextInterval(stability, difficulty)

        return FSRSResult(
            nextReview = now.plusDays(scheduledDays.toLong()),
            stability = stability,
            difficulty = difficulty,
            scheduledDays = scheduledDays,
            retrievability = 1.0
        )
    }

    /**
     * 更新现有卡片
     */
    private fun updateCard(
        state: FSRSState,
        grade: Int,
        elapsedDays: Int,
        now: LocalDateTime
    ): FSRSResult {
        // 计算当前可提取性
        val retrievability = retrievability(state.stability, elapsedDays)

        // 更新稳定性
        val newStability = updateStability(
            state.stability,
            state.difficulty,
            retrievability,
            grade,
            state.lapses
        )

        // 更新难度
        val newDifficulty = updateDifficulty(
            state.difficulty,
            grade
        )

        // 计算下次间隔
        val scheduledDays = if (grade == GRADE_AGAIN) {
            // 遗忘后重新学习
            nextInterval(newStability, newDifficulty)
        } else {
            nextInterval(newStability, newDifficulty)
        }

        val lapses = if (grade == GRADE_AGAIN) {
            state.lapses + 1
        } else {
            state.lapses
        }

        return FSRSResult(
            nextReview = now.plusDays(scheduledDays.toLong()),
            stability = newStability,
            difficulty = newDifficulty,
            scheduledDays = scheduledDays,
            retrievability = retrievability,
            lapses = lapses
        )
    }

    /**
     * 计算初始稳定性
     */
    private fun initialStability(grade: Int): Double {
        // w[0-3] 对应 again/hard/good/easy 的初始稳定性
        return parameters[grade - 1]
    }

    /**
     * 计算初始难度
     */
    private fun initialDifficulty(grade: Int): Double {
        // D_0(G) = w_7 * G_0^w_8
        val difficulty = parameters[7] * grade.toDouble().pow(parameters[8])
        return max(0.0, min(10.0, difficulty))
    }

    /**
     * 计算可提取性（回忆概率）
     *
     * 使用指数遗忘曲线：R(t) = e^(-t/S)
     */
    private fun retrievability(stability: Double, elapsedDays: Int): Double {
        if (stability <= 0) return 0.0
        return exp(-elapsedDays / stability)
    }

    /**
     * 更新稳定性
     *
     * FSRS v4 稳定性更新公式：
     * S'_d(G) = S * (e^(w_17) * (11 - D) * S^(-w_18) * (e^(w_19 * (1-R)) - 1) * w_20 + 1)
     */
    private fun updateStability(
        stability: Double,
        difficulty: Double,
        retrievability: Double,
        grade: Int,
        lapses: Int
    ): Double {
        val newStability = if (grade == GRADE_AGAIN) {
            // 遗忘：使用恢复因子
            parameters[11] * difficulty.pow(-parameters[12])
        } else {
            // 成功回忆：应用稳定性增长
            val hardPenalty = if (grade == GRADE_HARD) parameters[15] else 1.0
            val easyBonus = if (grade == GRADE_EASY) parameters[16] else 1.0

            // 稳定性增长因子
            val factor = (
                exp(parameters[14]) *
                (11 - difficulty) *
                stability.pow(-parameters[15]) *
                (exp(parameters[16] * (1 - retrievability)) - 1) *
                hardPenalty *
                easyBonus
            )

            stability * (factor + 1)
        }

        return max(0.01, newStability) // 最小稳定性 0.01 天
    }

    /**
     * 更新难度
     *
     * D'(G) = D - w_6 * (G - 3)
     */
    private fun updateDifficulty(difficulty: Double, grade: Int): Double {
        val newDifficulty = difficulty - parameters[6] * (grade - 3)
        return max(0.0, min(10.0, newDifficulty))
    }

    /**
     * 计算下次复习间隔
     *
     * I(S, D) = S * (10 - D) / 9
     */
    private fun nextInterval(stability: Double, difficulty: Double): Int {
        val interval = stability * (10 - difficulty) / 9
        // 最小间隔 1 天，最大间隔 365 天
        return max(1, min(365, round(interval).toInt()))
    }

    companion object {
        // FSRS v4 默认参数
        val DEFAULT_PARAMETERS = doubleArrayOf(
            0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01,
            1.49, 0.14, 0.94, 2.18, 0.05, 0.34, 1.26, 0.29, 2.61
        )

        // 评分等级
        const val GRADE_AGAIN = 1  // 完全忘记
        const val GRADE_HARD = 2   // 困难回忆
        const val GRADE_GOOD = 3   // 正常回忆
        const val GRADE_EASY = 4   // 轻松回忆

        /**
         * 将 SM-2 参数迁移到 FSRS 参数
         *
         * @param easeFactor SM-2 难度因子 (1.3-2.5)
         * @param intervalDays SM-2 间隔天数
         * @param repetitions SM-2 连续正确次数
         * @return Pair(stability, difficulty)
         */
        fun migrateFromSM2(
            easeFactor: Double,
            intervalDays: Int,
            repetitions: Int
        ): Pair<Double, Double> {
            // 稳定性估算：SM-2 间隔转换为 FSRS 稳定性
            val stability = intervalDays * 0.8

            // 难度估算：SM-2 ease_factor 转换为 FSRS 难度
            val difficulty = max(0.0, min(10.0, (2.5 - easeFactor) * 5))

            return Pair(stability, difficulty)
        }
    }
}

/**
 * FSRS 状态参数
 */
data class FSRSState(
    val stability: Double = 0.0,      // 稳定性（天）
    val difficulty: Double = 0.0,     // 难度（0-10）
    val elapsedDays: Int = 0,         // 已过天数
    val scheduledDays: Int = 0,       // 计划天数
    val reps: Int = 0,                // 复习次数
    val lapses: Int = 0,              // 遗忘次数
    val lastReview: LocalDateTime? = null
)

/**
 * FSRS 计算结果
 */
data class FSRSResult(
    val nextReview: LocalDateTime,    // 下次复习时间
    val stability: Double,           // 新稳定性
    val difficulty: Double,          // 新难度
    val scheduledDays: Int,          // 计划天数
    val retrievability: Double,      // 当前可提取性（回忆概率）
    val lapses: Int = 0              // 遗忘次数
)
