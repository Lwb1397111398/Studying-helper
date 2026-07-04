package com.studyinghelper.mobile

fun canConfirmCreateBook(title: String): Boolean = title.isNotBlank()

fun canConfirmCreateText(first: String, second: String, requiresSecond: Boolean): Boolean {
    return first.isNotBlank() && (!requiresSecond || second.isNotBlank())
}

fun canSubmitTeachingQuestion(question: String): Boolean = question.isNotBlank()

fun teachingCompletedActionLabel(): String = "返回书籍"

fun teachingProgressUnitTitle(sessionStatus: String?, unitTitle: String?): String {
    return if (sessionStatus == "completed") "已完成" else unitTitle ?: "已完成"
}

fun canMoveExamPrevious(currentIndex: Int): Boolean = currentIndex > 0

fun canMoveExamNext(currentIndex: Int, total: Int): Boolean = currentIndex < total - 1

fun examAnswerHint(answer: String): String = if (answer.isBlank()) "尚未填写答案" else "已填写答案"

fun examScoreHint(score: Int): String = if (score == 0) "已选择 0 分" else "已自评分"

fun profileStatusLabel(status: String?): String = when (status) {
    "confirmed" -> "已确认"
    "draft" -> "草稿"
    else -> "未生成"
}

fun identityOptions() = listOf(
    "unknown" to "未知",
    "expert" to "专业",
    "related" to "相关",
    "unrelated" to "新手",
)

fun goalOptions() = listOf(
    "apply_understand" to "理解应用",
    "exam_memorize" to "考试记忆",
    "general_interest" to "兴趣了解",
)

fun prefOptions() = listOf(
    "rigorous_system" to "系统严谨",
    "vivid_analogy" to "生动类比",
    "problem_driven" to "问题驱动",
)

fun toleranceOptions() = listOf(
    "moderate" to "适度重组",
    "keep_book_order" to "保留顺序",
    "aggressive" to "大胆重组",
)
