package com.studyinghelper.mobile.data.repository

import com.studyinghelper.mobile.data.db.KnowledgeUnitEntity
import com.studyinghelper.mobile.data.db.StudyDatabase
import com.studyinghelper.mobile.data.db.TeachingMessageEntity
import com.studyinghelper.mobile.data.db.TeachingSessionEntity
import com.studyinghelper.mobile.data.db.UserQuestionEntity
import java.time.OffsetDateTime
import java.util.UUID

class TeachingRepository(
    private val database: StudyDatabase,
    private val aiRepository: AiRepository,
) {
    private val dao = database.studyDao()

    suspend fun start(bookId: String): TeachingState {
        val units = dao.getUnits(bookId).sortedBy { it.orderIndex }
        require(units.isNotEmpty()) { "没有可教学的知识单元" }
        val now = OffsetDateTime.now().toString()
        val session = TeachingSessionEntity(
            id = "android-teaching-${UUID.randomUUID()}",
            userId = "anonymous",
            planSessionId = "",
            bookId = bookId,
            unitIds = units.joinToString(prefix = "[\"", postfix = "\"]", separator = "\",\"") { it.id },
            currentUnitIndex = 0,
            currentPhase = TEACHING_PHASES.first().key,
            strategyJson = "{\"source\":\"android\",\"manual_advance\":true}",
            status = "active",
            startedAt = now,
            endedAt = null,
        )
        val message = createMessage(session.id, units.first(), TEACHING_PHASES.first())
        dao.insertTeachingSessions(listOf(session))
        dao.insertTeachingMessages(listOf(message))
        return TeachingState(session, units, listOf(message))
    }

    suspend fun advance(state: TeachingState): TeachingState {
        val phaseIndex = TEACHING_PHASES.indexOfFirst { it.key == state.session.currentPhase }.coerceAtLeast(0)
        val nextPhaseIndex = phaseIndex + 1
        val nextUnitIndex = if (nextPhaseIndex >= TEACHING_PHASES.size) {
            (state.session.currentUnitIndex ?: 0) + 1
        } else {
            state.session.currentUnitIndex ?: 0
        }
        if (nextUnitIndex >= state.units.size) {
            return finish(state)
        }
        val nextPhase = TEACHING_PHASES.getOrElse(nextPhaseIndex) { TEACHING_PHASES.first() }
        val updatedSession = state.session.copy(
            currentUnitIndex = nextUnitIndex,
            currentPhase = nextPhase.key,
        )
        val message = createMessage(updatedSession.id, state.units[nextUnitIndex], nextPhase)
        dao.insertTeachingSessions(listOf(updatedSession))
        dao.insertTeachingMessages(listOf(message))
        return state.copy(session = updatedSession, messages = state.messages + message)
    }

    suspend fun finish(state: TeachingState): TeachingState {
        val updatedSession = state.session.copy(status = "completed", endedAt = OffsetDateTime.now().toString())
        dao.insertTeachingSessions(listOf(updatedSession))
        return state.copy(session = updatedSession)
    }

    suspend fun answerQuestion(state: TeachingState, question: String): TeachingState {
        val trimmedQuestion = question.trim()
        require(trimmedQuestion.isNotEmpty()) { "问题不能为空" }
        val unit = state.units.getOrNull(state.session.currentUnitIndex ?: 0) ?: state.units.first()
        val answer = aiRepository.answerTeachingQuestion(unit, trimmedQuestion)
        val now = OffsetDateTime.now().toString()
        val savedQuestion = UserQuestionEntity(
            id = "android-question-${UUID.randomUUID()}",
            sessionId = state.session.id,
            question = trimmedQuestion,
            answer = answer,
            intent = "ask",
            followUpJson = "[]",
            askedAt = now,
        )
        val message = TeachingMessageEntity(
            id = "android-message-${UUID.randomUUID()}",
            sessionId = state.session.id,
            unitId = unit.id,
            phase = state.session.currentPhase ?: "ask",
            content = answer,
            contentType = "answer",
            assessmentJson = null,
            createdAt = now,
        )
        dao.insertUserQuestions(listOf(savedQuestion))
        dao.insertTeachingMessages(listOf(message))
        return state.copy(messages = state.messages + message)
    }

    private fun createMessage(sessionId: String, unit: KnowledgeUnitEntity, phase: TeachingPhase): TeachingMessageEntity {
        val content = aiRepository.generateTeachingContent(unit, phase.key, phase.title)
        val message = TeachingMessageEntity(
            id = "android-message-${UUID.randomUUID()}",
            sessionId = sessionId,
            unitId = unit.id,
            phase = phase.key,
            content = content,
            contentType = "text",
            assessmentJson = null,
            createdAt = OffsetDateTime.now().toString(),
        )
        return message
    }

    companion object {
        val TEACHING_PHASES = listOf(
            TeachingPhase("activate", "引入"),
            TeachingPhase("explain", "讲解"),
            TeachingPhase("analogy", "类比"),
            TeachingPhase("example", "示例"),
            TeachingPhase("check", "检查"),
            TeachingPhase("reflect", "反思"),
        )
    }
}

data class TeachingPhase(val key: String, val title: String)

data class TeachingState(
    val session: TeachingSessionEntity,
    val units: List<KnowledgeUnitEntity>,
    val messages: List<TeachingMessageEntity>,
)
