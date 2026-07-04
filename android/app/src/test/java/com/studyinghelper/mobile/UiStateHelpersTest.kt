package com.studyinghelper.mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UiStateHelpersTest {
    @Test
    fun createDialogConfirmRequiresRequiredFields() {
        assertFalse(canConfirmCreateBook(""))
        assertFalse(canConfirmCreateBook("   "))
        assertTrue(canConfirmCreateBook("线性代数"))
        assertFalse(canConfirmCreateText(first = "", second = "内容", requiresSecond = true))
        assertFalse(canConfirmCreateText(first = "标题", second = "", requiresSecond = true))
        assertTrue(canConfirmCreateText(first = "标题", second = "内容", requiresSecond = true))
        assertTrue(canConfirmCreateText(first = "章节", second = "", requiresSecond = false))
    }

    @Test
    fun canSubmitTeachingQuestionRequiresNonBlankText() {
        assertFalse(canSubmitTeachingQuestion(""))
        assertFalse(canSubmitTeachingQuestion("   "))
        assertTrue(canSubmitTeachingQuestion("什么是拓扑排序？"))
    }

    @Test
    fun teachingProgressTitleShowsCompletedWhenSessionCompleted() {
        assertEquals("已完成", teachingProgressUnitTitle("completed", "最后一个单元"))
        assertEquals("最后一个单元", teachingProgressUnitTitle("active", "最后一个单元"))
        assertEquals("已完成", teachingProgressUnitTitle("active", null))
    }

    @Test
    fun teachingCompletedActionReturnsToBook() {
        assertEquals("返回书籍", teachingCompletedActionLabel())
    }

    @Test
    fun examNavigationDisablesOutOfBoundsMoves() {
        assertFalse(canMoveExamPrevious(0))
        assertTrue(canMoveExamPrevious(1))
        assertTrue(canMoveExamNext(currentIndex = 0, total = 2))
        assertFalse(canMoveExamNext(currentIndex = 1, total = 2))
        assertFalse(canMoveExamNext(currentIndex = 0, total = 0))
    }

    @Test
    fun examCompletionHintsReflectAnswerAndPositiveScore() {
        assertEquals("尚未填写答案", examAnswerHint(""))
        assertEquals("尚未填写答案", examAnswerHint("   "))
        assertEquals("已填写答案", examAnswerHint("答案"))
        assertEquals("已选择 0 分", examScoreHint(0))
        assertEquals("已自评分", examScoreHint(40))
    }

    @Test
    fun profileStatusLabelsCoverKnownStatesAndFallback() {
        assertEquals("已确认", profileStatusLabel("confirmed"))
        assertEquals("草稿", profileStatusLabel("draft"))
        assertEquals("未生成", profileStatusLabel(null))
        assertEquals("未生成", profileStatusLabel("unexpected"))
    }

    @Test
    fun teachingDesignOptionListsExposeStableValues() {
        assertEquals("未知", identityOptions().first { it.first == "unknown" }.second)
        assertEquals("理解应用", goalOptions().first { it.first == "apply_understand" }.second)
        assertEquals("系统严谨", prefOptions().first { it.first == "rigorous_system" }.second)
        assertEquals("适度重组", toleranceOptions().first { it.first == "moderate" }.second)
    }
}
