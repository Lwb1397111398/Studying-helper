package com.studyinghelper.mobile.data.update

import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * 检查更新：GET GitHub releases/latest，解析元数据注释与 APK 资产。
 * 纯 JVM 实现，可脱离 Android 单测；baseUrl 可注入指向假服务器。
 */
class UpdateChecker(
    private val owner: String = "Lwb1397111398",
    private val repo: String = "Studying-helper",
    private val baseUrl: String = "https://api.github.com",
    private val token: String? = null,
) {
    @Serializable
    private data class GhAsset(
        val name: String = "",
        val size: Long = 0,
        @kotlinx.serialization.SerialName("browser_download_url") val browserDownloadUrl: String = "",
    )

    @Serializable
    private data class GhRelease(
        @kotlinx.serialization.SerialName("html_url") val htmlUrl: String = "",
        val body: String? = null,
        val assets: List<GhAsset> = emptyList(),
    )

    private val json = Json { ignoreUnknownKeys = true }

    fun check(currentVersionCode: Int): UpdateCheckResult {
        val release = try {
            fetchLatest()
        } catch (e: ReleaseHttpException) {
            return UpdateCheckResult.Failed(
                when (e.code) {
                    404 -> "发布页还没有发布过任何版本"
                    401 -> "GitHub 访问令牌无效，请检查令牌配置"
                    403 -> "GitHub 访问被限流，请稍后再试"
                    else -> "检查更新失败（HTTP ${e.code}）"
                }
            )
        } catch (e: IOException) {
            return UpdateCheckResult.Failed("网络连接失败，请检查网络后重试")
        } ?: return UpdateCheckResult.Failed("检查更新失败，返回数据为空")

        val meta = UpdateMeta.parse(release.body)
            ?: return UpdateCheckResult.Failed("发布页数据不完整，暂时无法判断新版本")
        val apk = release.assets.firstOrNull { it.name.endsWith(".apk", ignoreCase = true) }
            ?: return UpdateCheckResult.Failed("发布页里没有找到安装包")

        val remote = RemoteRelease(
            versionCode = meta.first,
            versionName = meta.second,
            apkUrl = apk.browserDownloadUrl,
            apkSize = apk.size,
            releaseNotes = UpdateMeta.notesWithoutMeta(release.body),
            htmlUrl = release.htmlUrl,
        )
        return if (remote.versionCode > currentVersionCode) {
            UpdateCheckResult.UpdateAvailable(remote)
        } else {
            UpdateCheckResult.UpToDate(remote.versionCode)
        }
    }

    private fun fetchLatest(): GhRelease? {
        val connection = URL("$baseUrl/repos/$owner/$repo/releases/latest").openConnection() as HttpURLConnection
        try {
            // GitHub 强制要求 User-Agent，缺了直接 403
            connection.requestMethod = "GET"
            connection.setRequestProperty("User-Agent", "studying-helper-mobile")
            connection.setRequestProperty("Accept", "application/vnd.github+json")
            connection.connectTimeout = 10_000
            connection.readTimeout = 10_000
            if (!token.isNullOrBlank()) {
                connection.setRequestProperty("Authorization", "Bearer $token")
            }
            val code = connection.responseCode
            if (code != HttpURLConnection.HTTP_OK) {
                throw ReleaseHttpException(code)
            }
            val text = connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            return json.decodeFromString(GhRelease.serializer(), text)
        } finally {
            connection.disconnect()
        }
    }

    private class ReleaseHttpException(val code: Int) : IOException("HTTP $code")
}
