package com.studyinghelper.mobile.data.update

/**
 * GitHub Release 上解析出的远端版本信息。
 */
data class RemoteRelease(
    val versionCode: Int,
    val versionName: String,
    val apkUrl: String,
    val apkSize: Long,
    /** Release 说明，已去掉元数据注释行。 */
    val releaseNotes: String,
    val htmlUrl: String,
)

/**
 * 检查更新结果，文案全部人话。
 */
sealed class UpdateCheckResult {
    /** 远端版本号更大，可以升级。 */
    data class UpdateAvailable(val release: RemoteRelease) : UpdateCheckResult()

    /** 已经是最新版。 */
    data class UpToDate(val remoteVersionCode: Int) : UpdateCheckResult()

    /** 检查失败，message 可直接展示给用户。 */
    data class Failed(val message: String) : UpdateCheckResult()
}

/**
 * Release 说明第一行的元数据注释：
 * `<!-- appupdate versionCode=21 versionName=1.0.21 -->`
 * GitHub 页面渲染时不可见，App 用正则解析。
 */
object UpdateMeta {
    private val REGEX = Regex("""<!--\s*appupdate\s+versionCode=(\d+)\s+versionName=([^\s>-]+)\s*-->""")

    /** 返回 (versionCode, versionName)，解析不到返回 null。 */
    fun parse(body: String?): Pair<Int, String>? {
        if (body.isNullOrBlank()) return null
        val match = REGEX.find(body) ?: return null
        val code = match.groupValues[1].toIntOrNull() ?: return null
        if (code <= 0) return null
        return code to match.groupValues[2]
    }

    /** 去掉元数据注释行后的正文，用作更新弹窗里的「更新内容」。 */
    fun notesWithoutMeta(body: String?): String {
        if (body.isNullOrBlank()) return ""
        val match = REGEX.find(body) ?: return body.trim()
        val line = body.lineSequence().firstOrNull { it.contains("appupdate") }
        return if (line != null) body.replace(line, "").trim() else body.trim()
    }
}
