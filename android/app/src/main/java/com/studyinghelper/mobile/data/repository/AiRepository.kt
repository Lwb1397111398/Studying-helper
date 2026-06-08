package com.studyinghelper.mobile.data.repository

import com.studyinghelper.mobile.data.db.KnowledgeUnitEntity
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

class AiRepository(private val configRepository: AiConfigRepository) {
    private val json = Json { ignoreUnknownKeys = true; prettyPrint = false }

    fun analyzeUnit(unit: KnowledgeUnitEntity): AiAnalysisResult {
        val content = chat(
            system = "你是学习辅助助手。请只输出 JSON，不要输出 Markdown。",
            user = """
                请分析下面的知识单元，输出 JSON：
                {
                  "summary": "100字以内摘要",
                  "explanation": "面向初学者的详细讲解",
                  "key_points": ["关键点1", "关键点2"],
                  "concepts": ["概念1", "概念2"]
                }

                标题：${unit.title}
                内容：${unit.content.take(6000)}
            """.trimIndent(),
            maxTokens = 1200,
        )
        return parseAnalysisContent(content)
    }

    fun generateTeachingContent(unit: KnowledgeUnitEntity, phase: String, phaseTitle: String): String {
        val instruction = when (phase) {
            "activate" -> "用一个问题或生活场景引入，激活学习者已有经验。"
            "explain" -> "用清晰分层的方式讲解核心概念。"
            "analogy" -> "给出贴近日常生活的类比，说明相同点和局限。"
            "example" -> "给出具体示例，并指出如何迁移到原知识点。"
            "check" -> "提出一个简短检查题，引导学习者自测理解。"
            "reflect" -> "总结本单元，并给出反思提示。"
            else -> "生成适合当前阶段的教学内容。"
        }
        return chat(
            system = "你是手机端学习助教。教学阶段必须由用户手动推进，不要要求自动跳转。",
            user = """
                请为下面知识单元生成“$phaseTitle”阶段的教学内容。
                要求：$instruction
                字数控制在 300 字以内，语气自然，直接输出正文。

                标题：${unit.title}
                内容：${unit.content.take(6000)}
                已有摘要：${unit.summary.orEmpty()}
                已有讲解：${unit.explanation.orEmpty()}
            """.trimIndent(),
            maxTokens = 800,
        ).trim()
    }

    fun answerTeachingQuestion(unit: KnowledgeUnitEntity, question: String): String {
        return chat(
            system = "你是手机端学习助教。回答要围绕当前知识单元，简明、准确、可操作。",
            user = """
                学习者正在学习下面知识单元，并提出了问题。请直接回答问题。

                标题：${unit.title}
                内容：${unit.content.take(6000)}
                已有摘要：${unit.summary.orEmpty()}
                已有讲解：${unit.explanation.orEmpty()}

                问题：$question
            """.trimIndent(),
            maxTokens = 800,
        ).trim()
    }

    private fun chat(system: String, user: String, maxTokens: Int): String {
        val config = configRepository.getConfig()
        require(config.apiKey.isNotBlank()) { "请先配置 API Key" }
        val request = ChatRequest(
            model = config.model,
            messages = listOf(ChatMessage("system", system), ChatMessage("user", user)),
            temperature = 0.2,
            maxTokens = maxTokens,
        )
        val responseText = postChatCompletions(config, request)
        return json.parseToJsonElement(responseText)
            .jsonObject["choices"]
            ?.jsonArray
            ?.firstOrNull()
            ?.jsonObject
            ?.get("message")
            ?.jsonObject
            ?.get("content")
            ?.jsonPrimitive
            ?.content
            ?: error("AI 响应缺少内容")
    }

    private fun postChatCompletions(config: AiConfig, request: ChatRequest): String {
        val url = URL("${config.baseUrl.trimEnd('/')}/chat/completions")
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 30_000
            readTimeout = 120_000
            doOutput = true
            setRequestProperty("Authorization", "Bearer ${config.apiKey}")
            setRequestProperty("Content-Type", "application/json")
        }
        try {
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(json.encodeToString(request))
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val body = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            if (code !in 200..299) error("AI 请求失败：HTTP $code ${body.take(200)}")
            return body
        } finally {
            connection.disconnect()
        }
    }

    private fun parseAnalysisContent(content: String): AiAnalysisResult {
        val jsonText = extractJsonObject(content)
        val root = json.parseToJsonElement(jsonText).jsonObject
        return AiAnalysisResult(
            summary = root.stringValue("summary"),
            explanation = root.stringValue("explanation"),
            keyPoints = root.stringList("key_points"),
            concepts = root.stringList("concepts"),
        )
    }

    private fun extractJsonObject(content: String): String {
        val withoutFence = content.trim()
            .replace(Regex("^```(?:json)?\\s*", RegexOption.IGNORE_CASE), "")
            .replace(Regex("\\s*```$"), "")
            .trim()
        val start = withoutFence.indexOf('{')
        val end = withoutFence.lastIndexOf('}')
        require(start >= 0 && end > start) { "AI 响应不是有效 JSON" }
        return withoutFence.substring(start, end + 1)
    }

    private fun JsonObject.stringValue(name: String): String {
        return this[name]?.jsonPrimitive?.content.orEmpty().trim()
    }

    private fun JsonObject.stringList(name: String): List<String> {
        return this[name]?.jsonArray?.mapNotNull { item -> item.jsonPrimitive.content.trim().takeIf { it.isNotEmpty() } }.orEmpty()
    }
}

@Serializable
private data class ChatRequest(
    val model: String,
    val messages: List<ChatMessage>,
    val temperature: Double,
    @SerialName("max_tokens") val maxTokens: Int,
)

@Serializable
private data class ChatMessage(
    val role: String,
    val content: String,
)

data class AiAnalysisResult(
    val summary: String,
    val explanation: String,
    @SerialName("key_points") val keyPoints: List<String>,
    val concepts: List<String>,
)
