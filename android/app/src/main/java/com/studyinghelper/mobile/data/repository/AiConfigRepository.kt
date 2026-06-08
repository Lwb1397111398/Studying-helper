package com.studyinghelper.mobile.data.repository

import android.content.Context

class AiConfigRepository(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("ai_config", Context.MODE_PRIVATE)

    fun getConfig(): AiConfig {
        return AiConfig(
            apiKey = prefs.getString(KEY_API_KEY, "").orEmpty(),
            baseUrl = prefs.getString(KEY_BASE_URL, DEFAULT_BASE_URL).orEmpty().ifBlank { DEFAULT_BASE_URL },
            model = prefs.getString(KEY_MODEL, DEFAULT_MODEL).orEmpty().ifBlank { DEFAULT_MODEL },
        )
    }

    fun saveConfig(apiKey: String, baseUrl: String, model: String) {
        prefs.edit()
            .putString(KEY_API_KEY, apiKey.trim())
            .putString(KEY_BASE_URL, baseUrl.trim().ifBlank { DEFAULT_BASE_URL }.trimEnd('/'))
            .putString(KEY_MODEL, model.trim().ifBlank { DEFAULT_MODEL })
            .apply()
    }

    private companion object {
        const val KEY_API_KEY = "api_key"
        const val KEY_BASE_URL = "base_url"
        const val KEY_MODEL = "model"
        const val DEFAULT_BASE_URL = "https://api.openai.com/v1"
        const val DEFAULT_MODEL = "gpt-4o-mini"
    }
}

data class AiConfig(
    val apiKey: String,
    val baseUrl: String,
    val model: String,
)
