package com.studyinghelper.mobile.data.repository

import androidx.room.withTransaction
import com.studyinghelper.mobile.data.db.KnowledgeUnitEntity
import com.studyinghelper.mobile.data.db.LearnerIntentProfileEntity
import com.studyinghelper.mobile.data.db.ModuleMicroPlanEntity
import com.studyinghelper.mobile.data.db.StudyDatabase
import com.studyinghelper.mobile.data.db.TeachingDesignEntity
import java.time.OffsetDateTime
import java.util.UUID
import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

class AdaptiveDesignRepository(
    private val database: StudyDatabase,
    private val aiRepository: AiRepository,
) {
    private val dao = database.studyDao()
    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true; prettyPrint = false }

    suspend fun inferProfile(bookId: String): LearnerIntentProfileEntity {
        val book = dao.getBook(bookId) ?: error("未找到书籍")
        val units = dao.getUnits(bookId)
        val now = OffsetDateTime.now().toString()
        val inferred = runCatching {
            val profile = inferProfileWithAi(book.title, book.readingMotivation, units)
            profile.toEntity(bookId, "ai_inferred", "draft", now)
        }.getOrElse {
            inferProfileByRules(bookId, book.readingMotivation, units, now)
        }
        dao.insertLearnerIntentProfiles(listOf(inferred))
        return inferred
    }

    suspend fun saveProfile(
        bookId: String,
        identityBackground: String,
        goalDepth: String,
        cognitivePref: String,
        restructureTolerance: String,
        timeBudgetMinutes: Int?,
    ): LearnerIntentProfileEntity {
        val old = dao.getLearnerIntentProfile(bookId)
        val now = OffsetDateTime.now().toString()
        val profile = LearnerIntentProfileEntity(
            id = old?.id ?: "android-profile-${UUID.randomUUID()}",
            userId = "anonymous",
            bookId = bookId,
            identityBackground = identityBackground,
            goalDepth = goalDepth,
            cognitivePref = cognitivePref,
            restructureTolerance = restructureTolerance,
            timeBudgetMinutes = timeBudgetMinutes,
            source = "user_set",
            status = "draft",
            extraJson = old?.extraJson ?: "{}",
            createdAt = old?.createdAt ?: now,
            updatedAt = now,
        )
        dao.insertLearnerIntentProfiles(listOf(profile))
        return profile
    }

    suspend fun confirmProfile(bookId: String): LearnerIntentProfileEntity {
        val old = dao.getLearnerIntentProfile(bookId) ?: inferProfile(bookId)
        val confirmed = old.copy(status = "confirmed", updatedAt = OffsetDateTime.now().toString())
        dao.insertLearnerIntentProfiles(listOf(confirmed))
        return confirmed
    }

    suspend fun generateDesign(bookId: String): TeachingDesignEntity {
        val profile = confirmProfile(bookId)
        val units = dao.getUnits(bookId).sortedBy { it.orderIndex }
        require(units.isNotEmpty()) { "没有可编排的知识单元" }
        val macro = runCatching {
            generateMacroWithAi(profile, units)
        }.getOrElse {
            generateMacroByRules(profile, units)
        }
        val now = OffsetDateTime.now().toString()
        val old = dao.getTeachingDesign(bookId)
        val version = (old?.version ?: 0) + 1
        val design = TeachingDesignEntity(
            id = "android-design-${UUID.randomUUID()}",
            userId = "anonymous",
            bookId = bookId,
            profileId = profile.id,
            macroDesignJson = json.encodeToString(macro),
            currentModuleIndex = 0,
            generatedModuleCount = macro.modules.size,
            adjustmentsJson = "[]",
            status = "draft",
            version = version,
            createdAt = now,
            updatedAt = now,
        )
        val plans = macro.modules.map { module ->
            val annotations = module.unitIds.map { unitId ->
                val unit = units.firstOrNull { it.id == unitId }
                UnitAnnotation(unitId = unitId, cognitiveMode = chooseHint(profile, unit))
            }
            ModuleMicroPlanEntity(
                id = "android-micro-${UUID.randomUUID()}",
                designId = design.id,
                bookId = bookId,
                userId = "anonymous",
                moduleIndex = module.moduleIndex,
                moduleTitle = module.title,
                orderedUnitIdsJson = json.encodeToString(module.unitIds),
                unitAnnotationsJson = json.encodeToString(annotations),
                moduleIntro = module.rationale,
                moduleStatus = "pending",
                moduleSummaryJson = null,
                parentDesignVersion = version,
                createdAt = now,
                updatedAt = now,
            )
        }
        database.withTransaction {
            dao.deleteModuleMicroPlans(listOf(bookId))
            dao.deleteTeachingDesigns(listOf(bookId))
            dao.insertTeachingDesigns(listOf(design))
            dao.insertModuleMicroPlans(plans)
            plans.flatMap { plan -> json.decodeFromString<List<UnitAnnotation>>(plan.unitAnnotationsJson) }
                .forEach { annotation -> dao.updateUnitCognitiveHint(annotation.unitId, annotation.cognitiveMode) }
        }
        return design
    }

    suspend fun activateDesign(bookId: String): TeachingDesignEntity {
        val design = dao.getTeachingDesign(bookId) ?: generateDesign(bookId)
        val plans = dao.getModuleMicroPlans(bookId).filter { it.designId == design.id }
        require(plans.isNotEmpty()) { "教学设计缺少模块编排" }
        val now = OffsetDateTime.now().toString()
        database.withTransaction {
            plans.forEach { plan ->
                dao.updateModuleStatus(plan.id, if (plan.moduleIndex == 0) "active" else "pending", now)
            }
            dao.updateTeachingDesignStatus(design.id, "active", 0, now)
        }
        return design.copy(status = "active", currentModuleIndex = 0, updatedAt = now)
    }

    suspend fun hasConfirmedDesign(bookId: String): Boolean {
        return dao.getActiveTeachingDesign(bookId) != null
    }

    private fun inferProfileWithAi(
        title: String,
        motivation: String?,
        units: List<KnowledgeUnitEntity>,
    ): ProfileDraft {
        val content = aiRepository.chatText(
            system = "你是学习系统的教学设计助手。只输出 JSON，不要输出 Markdown。",
            user = """
                根据书名、阅读动机和知识单元标题，推断学习者意图画像。
                输出 JSON：
                {
                  "identity_background": "expert|related|unrelated|unknown",
                  "goal_depth": "exam_memorize|apply_understand|general_interest",
                  "cognitive_pref": "vivid_analogy|rigorous_system|problem_driven",
                  "restructure_tolerance": "keep_book_order|moderate|aggressive",
                  "time_budget_minutes": 30
                }

                书名：$title
                阅读动机：${motivation.orEmpty()}
                单元标题：${units.take(20).joinToString("；") { it.title }}
            """.trimIndent(),
            maxTokens = 500,
        )
        return json.decodeFromString(extractJsonObject(content))
    }

    private fun generateMacroWithAi(
        profile: LearnerIntentProfileEntity,
        units: List<KnowledgeUnitEntity>,
    ): MacroDesign {
        val content = aiRepository.chatText(
            system = "你是适应性教学设计助手。只输出 JSON，不要输出 Markdown。",
            user = """
                请按学习者画像重组知识单元为学习模块。必须覆盖全部 unit_id，不能重复。
                输出 JSON：
                {
                  "global_strategy": "一句总策略",
                  "modules": [
                    {
                      "module_index": 0,
                      "title": "模块标题",
                      "unit_ids": ["unit-id"],
                      "core_concepts": ["概念"],
                      "strategy_tags": ["analogy"],
                      "rationale": "为什么这样编排"
                    }
                  ]
                }

                画像：identity=${profile.identityBackground}, goal=${profile.goalDepth}, pref=${profile.cognitivePref}, tolerance=${profile.restructureTolerance}
                单元：
                ${units.joinToString("\n") { "- ${it.id}: ${it.title}；概念=${conceptsOf(it).joinToString("/")}" }}
            """.trimIndent(),
            maxTokens = 1600,
        )
        return normalizeMacro(json.decodeFromString(extractJsonObject(content)), units)
    }

    private fun inferProfileByRules(
        bookId: String,
        motivation: String?,
        units: List<KnowledgeUnitEntity>,
        now: String,
    ): LearnerIntentProfileEntity {
        val text = "${motivation.orEmpty()} ${units.take(12).joinToString(" ") { it.title }}".lowercase()
        val goal = when {
            listOf("考试", "考研", "背", "记忆", "证书").any { it in text } -> "exam_memorize"
            listOf("项目", "应用", "实践", "工作").any { it in text } -> "apply_understand"
            else -> "general_interest"
        }
        val pref = when {
            listOf("题", "刷题", "问题").any { it in text } -> "problem_driven"
            listOf("例子", "通俗", "故事").any { it in text } -> "vivid_analogy"
            else -> "rigorous_system"
        }
        return LearnerIntentProfileEntity(
            id = "android-profile-${UUID.randomUUID()}",
            userId = "anonymous",
            bookId = bookId,
            goalDepth = goal,
            cognitivePref = pref,
            restructureTolerance = "moderate",
            timeBudgetMinutes = 30,
            source = "ai_inferred",
            status = "draft",
            extraJson = "{\"fallback\":\"rules\"}",
            createdAt = now,
            updatedAt = now,
        )
    }

    private fun generateMacroByRules(profile: LearnerIntentProfileEntity, units: List<KnowledgeUnitEntity>): MacroDesign {
        val modules = when (profile.restructureTolerance) {
            "keep_book_order" -> units.chunked(5).mapIndexed { index, chunk -> moduleFromUnits(index, chunk, "按书籍顺序推进") }
            "aggressive" -> groupByConcept(units).mapIndexed { index, chunk -> moduleFromUnits(index, chunk, "按共享概念跨章节重组") }
            else -> units.groupBy { it.chapterId }.values.mapIndexed { index, chunk -> moduleFromUnits(index, chunk, "按章节主题适度合并") }
        }
        return MacroDesign(
            globalStrategy = when (profile.cognitivePref) {
                "vivid_analogy" -> "先用类比建立直觉，再回到概念定义。"
                "problem_driven" -> "先抛问题，再围绕问题组织讲解和练习。"
                else -> "先建立结构，再逐层讲解核心概念。"
            },
            modules = modules.ifEmpty { listOf(moduleFromUnits(0, units, "默认模块")) },
        )
    }

    private fun groupByConcept(units: List<KnowledgeUnitEntity>): List<List<KnowledgeUnitEntity>> {
        return units.groupBy { conceptsOf(it).firstOrNull() ?: it.chapterId }
            .values
            .map { it.sortedBy { unit -> unit.orderIndex } }
    }

    private fun moduleFromUnits(index: Int, units: List<KnowledgeUnitEntity>, rationale: String): MacroModule {
        val concepts = units.flatMap { conceptsOf(it) }.distinct().take(5)
        return MacroModule(
            moduleIndex = index,
            title = concepts.firstOrNull()?.let { "模块 ${index + 1}：$it" } ?: "模块 ${index + 1}",
            unitIds = units.map { it.id },
            coreConcepts = concepts,
            strategyTags = listOf("android_local", if (units.size > 1) "chunked" else "single_unit"),
            rationale = rationale,
        )
    }

    private fun normalizeMacro(macro: MacroDesign, units: List<KnowledgeUnitEntity>): MacroDesign {
        val knownIds = units.map { it.id }.toSet()
        val seen = mutableSetOf<String>()
        val modules = macro.modules.mapIndexedNotNull { index, module ->
            val ids = module.unitIds.filter { it in knownIds && seen.add(it) }
            if (ids.isEmpty()) null else module.copy(moduleIndex = index, unitIds = ids)
        }.toMutableList()
        val missing = units.filter { it.id !in seen }
        if (missing.isNotEmpty()) modules += moduleFromUnits(modules.size, missing, "补齐未覆盖单元")
        return macro.copy(modules = modules)
    }

    private fun chooseHint(profile: LearnerIntentProfileEntity, unit: KnowledgeUnitEntity?): String {
        if (unit == null) return "understand"
        return when {
            profile.goalDepth == "exam_memorize" && (unit.importanceScore ?: 0f) >= 0.7f -> "memorize"
            (unit.difficultyLevel ?: 3) <= 1 && profile.restructureTolerance == "aggressive" -> "skip_if_mastered"
            else -> "understand"
        }
    }

    private fun conceptsOf(unit: KnowledgeUnitEntity): List<String> {
        val raw = unit.concepts.orEmpty()
        if (raw.isBlank()) return emptyList()
        return runCatching {
            json.parseToJsonElement(raw).jsonArray.mapNotNull { element ->
                when (element) {
                    is JsonObject -> element["name"]?.jsonPrimitive?.content
                    else -> element.jsonPrimitive.content
                }?.trim()?.takeIf { it.isNotEmpty() }
            }
        }.getOrDefault(emptyList())
    }

    private fun extractJsonObject(content: String): String {
        val clean = content.trim()
            .replace(Regex("^```(?:json)?\\s*", RegexOption.IGNORE_CASE), "")
            .replace(Regex("\\s*```$"), "")
            .trim()
        val start = clean.indexOf('{')
        val end = clean.lastIndexOf('}')
        require(start >= 0 && end > start) { "AI 响应不是有效 JSON" }
        return clean.substring(start, end + 1)
    }
}

private fun ProfileDraft.toEntity(
    bookId: String,
    source: String,
    status: String,
    now: String,
) = LearnerIntentProfileEntity(
    id = "android-profile-${UUID.randomUUID()}",
    userId = "anonymous",
    bookId = bookId,
    identityBackground = identityBackground,
    goalDepth = goalDepth,
    cognitivePref = cognitivePref,
    restructureTolerance = restructureTolerance,
    timeBudgetMinutes = timeBudgetMinutes,
    source = source,
    status = status,
    extraJson = "{}",
    createdAt = now,
    updatedAt = now,
)

@Serializable
data class MacroDesign(
    @kotlinx.serialization.SerialName("global_strategy") val globalStrategy: String,
    val modules: List<MacroModule>,
)

@Serializable
data class MacroModule(
    @kotlinx.serialization.SerialName("module_index") val moduleIndex: Int,
    val title: String,
    @kotlinx.serialization.SerialName("unit_ids") val unitIds: List<String>,
    @kotlinx.serialization.SerialName("core_concepts") val coreConcepts: List<String> = emptyList(),
    @kotlinx.serialization.SerialName("strategy_tags") val strategyTags: List<String> = emptyList(),
    val rationale: String = "",
)

@Serializable
data class UnitAnnotation(
    @kotlinx.serialization.SerialName("unit_id") val unitId: String,
    @kotlinx.serialization.SerialName("cognitive_mode") val cognitiveMode: String,
)

@Serializable
private data class ProfileDraft(
    @kotlinx.serialization.SerialName("identity_background") val identityBackground: String = "unknown",
    @kotlinx.serialization.SerialName("goal_depth") val goalDepth: String = "apply_understand",
    @kotlinx.serialization.SerialName("cognitive_pref") val cognitivePref: String = "rigorous_system",
    @kotlinx.serialization.SerialName("restructure_tolerance") val restructureTolerance: String = "moderate",
    @kotlinx.serialization.SerialName("time_budget_minutes") val timeBudgetMinutes: Int? = 30,
)
