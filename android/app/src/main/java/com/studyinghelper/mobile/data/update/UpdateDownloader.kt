package com.studyinghelper.mobile.data.update

import android.content.Context
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/**
 * 下载更新 APK：流式写入 .part 临时文件，校验字节数后改名正式文件。
 * 已存在同版本完整文件时直接复用，不重新下载。
 */
object UpdateDownloader {

    private const val BUFFER_SIZE = 64 * 1024

    /** APK 落盘位置：cacheDir/updates/update-<versionCode>.apk */
    fun apkFile(context: Context, versionCode: Int): File =
        File(File(context.cacheDir, "updates"), "update-$versionCode.apk")

    /**
     * 纯 JVM 的下载实现，dest 由调用方给定，方便单测。
     * @param expectedSize Release 资产里声明的字节数，>0 时下载完必须一致
     * @param onProgress 进度百分比 0~100
     * @return 下载完成的正式文件
     */
    fun download(
        url: String,
        dest: File,
        expectedSize: Long,
        onProgress: (Int) -> Unit = {},
    ): File {
        if (dest.exists() && expectedSize > 0 && dest.length() == expectedSize) {
            onProgress(100)
            return dest
        }
        dest.parentFile?.mkdirs()
        val part = File(dest.parentFile, dest.name + ".part")
        part.delete()
        try {
            val connection = URL(url).openConnection() as HttpURLConnection
            try {
                connection.requestMethod = "GET"
                connection.setRequestProperty("User-Agent", "studying-helper-mobile")
                connection.connectTimeout = 15_000
                connection.readTimeout = 30_000
                if (connection.responseCode != HttpURLConnection.HTTP_OK) {
                    throw IOException("下载失败（HTTP ${connection.responseCode}）")
                }
                val total = connection.contentLengthLong.let { if (it > 0) it else expectedSize }
                connection.inputStream.use { input ->
                    part.outputStream().use { output ->
                        val buffer = ByteArray(BUFFER_SIZE)
                        var read: Int
                        var downloaded = 0L
                        var lastProgress = -1
                        while (input.read(buffer).also { read = it } != -1) {
                            output.write(buffer, 0, read)
                            downloaded += read
                            if (total > 0) {
                                val progress = ((downloaded * 100) / total).toInt().coerceIn(0, 100)
                                if (progress != lastProgress) {
                                    onProgress(progress)
                                    lastProgress = progress
                                }
                            }
                        }
                        if (expectedSize > 0 && downloaded != expectedSize) {
                            throw IOException("下载不完整：应为 $expectedSize 字节，实际 $downloaded 字节")
                        }
                    }
                }
            } finally {
                connection.disconnect()
            }
            // 校验通过才转正，任何异常都保证不留半截包
            if (!part.renameTo(dest)) {
                throw IOException("更新文件转存失败")
            }
        } finally {
            part.delete()
        }
        onProgress(100)
        return dest
    }
}
