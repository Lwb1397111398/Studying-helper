package com.studyinghelper.mobile.data.repository

import com.studyinghelper.mobile.data.db.KnowledgeUnitEntity
import com.studyinghelper.mobile.data.db.StudyDatabase
import com.studyinghelper.mobile.data.db.TeachingMessageEntity
import com.studyinghelper.mobile.data.db.TeachingSessionEntity
import com.studyinghelper.mobile.data.db.UserQuestionEntity
import java.time.OffsetDateTime
import java.util.UUID
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json

class TeachingRepository(
    private val database: StudyDatabase,
    private val aiRepository: AiRepository,
) {
    private val dao = database.studyDao()
    private val json = Json { ignoreUnknownKeys = true }

    suspend fun start(bookId: String): TeachingState {
        val units = getDesignedUnits(bookId)
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
            strategyJson = "{\"source\":\"android\",\"manual_advance\":true,\"aid_ordered\":true}",
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
        val answer = runCatching {
            aiRepository.answerTeachingQuestion(unit, trimmedQuestion)
        }.getOrElse {
            "我现在无法连接 AI，但可以先基于本地内容回答：这个问题应回到“${unit.title}”的核心定义和例子中理解。你可以先复述本单元摘要，再标出不确定的概念。"
        }
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
        val content = runCatching {
            aiRepository.generateTeachingContent(unit, phase.key, phase.title)
        }.getOrElse {
            buildFallbackTeachingContent(unit, phase)
        }
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

    private suspend fun getDesignedUnits(bookId: String): List<KnowledgeUnitEntity> {
        val allUnits = dao.getUnits(bookId).sortedBy { it.orderIndex }
        val plan = dao.getActiveModuleMicroPlan(bookId)
            ?: dao.getModuleMicroPlans(bookId).minByOrNull { it.moduleIndex }
            ?: return allUnits
        val orderedIds = runCatching {
            json.decodeFromString<List<String>>(plan.orderedUnitIdsJson)
        }.getOrDefault(emptyList())
        val byId = allUnits.associateBy { it.id }
        val designed = orderedIds.mapNotNull { byId[it] }
        return designed.ifEmpty { allUnits }
    }

    private fun buildFallbackTeachingContent(unit: KnowledgeUnitEntity, phase: TeachingPhase): String {
        val hint = when (unit.aiCognitiveHint) {
            "memorize" -> "本单元被标注为需要记忆，请优先抓住术语、定义和关键列表。"
            "skip_if_mastered" -> "如果你已经熟悉这个单元，可以快速自测后跳过。"
            else -> "本单元重点在理解，请先说明概念之间的关系。"
        }
        return "${phase.title}：${unit.title}\n$hint\n${unit.summary ?: unit.content.take(220)}"
    }

    companion object {
        /**
         * 完整的 9 阶段教学流程（与 Web 端对齐）
         */
        val TEACHING_PHASES = listOf(
            TeachingPhase("activate", "引入", "激活先验知识，建立学习动机"),
            TeachingPhase("intro", "导览", "概述学习目标和内容框架"),
            TeachingPhase("core", "讲解", "核心内容的详细讲解"),
            TeachingPhase("example", "示例", "通过例子加深理解"),
            TeachingPhase("feynman", "费曼", "用自己的话解释，检验真正理解"),
            TeachingPhase("retrieval", "检索", "主动回忆练习，强化记忆"),
            TeachingPhase("check", "检查", "理解检测，发现知识盲点"),
            TeachingPhase("reflect", "反思", "元认知反思，总结学习收获"),
            TeachingPhase("connect", "联结", "建立知识网络，关联已有知识"),
        )
    }
}

data class TeachingPhase(
    val key: String,
    val title: String,
    val description: String = ""
)

data class TeachingState(
    val session: TeachingSessionEntity,
    val units: List<KnowledgeUnitEntity>,
    val messages: List<TeachingMessageEntity>,
)
