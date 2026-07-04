package com.studyinghelper.mobile.ui

import com.studyinghelper.mobile.data.repository.Concept
import com.studyinghelper.mobile.data.repository.KeyPoint
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

fun parseKeyPoints(json: String): List<KeyPoint> {
    return try {
        Json.parseToJsonElement(json).jsonArray.mapNotNull { element ->
            if (element is JsonPrimitive) {
                val content = element.content.trim()
                return@mapNotNull if (content.isNotEmpty()) KeyPoint(title = content) else null
            }
            val obj = element.jsonObject
            val title = obj["title"]?.jsonPrimitive?.content?.trim()?.takeIf { it.isNotEmpty() }
                ?: return@mapNotNull null
            val explanation = obj["explanation"]?.jsonPrimitive?.content?.trim()?.takeIf { it.isNotEmpty() }
            val examples = obj["examples"]?.jsonArray?.mapNotNull {
                it.jsonPrimitive.content.trim().takeIf { value -> value.isNotEmpty() }
            } ?: emptyList()
            KeyPoint(title = title, explanation = explanation, examples = examples)
        }
    } catch (_: Exception) {
        emptyList()
    }
}

fun parseConcepts(json: String): List<Concept> {
    return try {
        Json.parseToJsonElement(json).jsonArray.mapNotNull { element ->
            if (element is JsonPrimitive) {
                val content = element.content.trim()
                return@mapNotNull if (content.isNotEmpty()) Concept(name = content) else null
            }
            val obj = element.jsonObject
            val name = obj["name"]?.jsonPrimitive?.content?.trim()?.takeIf { it.isNotEmpty() }
                ?: return@mapNotNull null
            val definition = obj["definition"]?.jsonPrimitive?.content?.trim()?.takeIf { it.isNotEmpty() }
            val examples = obj["examples"]?.jsonArray?.mapNotNull {
                it.jsonPrimitive.content.trim().takeIf { value -> value.isNotEmpty() }
            } ?: emptyList()
            Concept(name = name, definition = definition, examples = examples)
        }
    } catch (_: Exception) {
        emptyList()
    }
}
