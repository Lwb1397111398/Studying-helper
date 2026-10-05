package com.studyinghelper.mobile.data.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * UpdateChecker 全链路：假 GitHub 返回不同状态码和响应体，验证解析、比较、错误文案。
 */
class UpdateCheckerTest {

    private fun releaseJson(versionCode: Int, versionName: String, includeApk: Boolean = true): String {
        val assets = if (includeApk) {
            """"assets": [
                {"name": "app-release.apk", "size": 123456,
                 "browser_download_url": "https://example.com/app-release.apk"}
            ],"""
        } else {
            """"assets": [],"""
        }
        return """{
            "html_url": "https://github.com/o/r/releases/tag/latest",
            "body": "<!-- appupdate versionCode=$versionCode versionName=$versionName -->\n- 修复已知问题\n- 优化同步",
            $assets
            "tag_name": "latest",
            "unknown_field": 1
        }"""
    }

    private fun checker(port: Int) = UpdateChecker(owner = "o", repo = "r", baseUrl = "http://127.0.0.1:$port")

    @Test
    fun `远端版本号更大时返回可更新并带全字段`() {
        val server = FakeHttpServer { httpResponse("200 OK", releaseJson(99, "1.0.99").toByteArray()) }
        try {
            val result = checker(server.port).check(currentVersionCode = 21)
            val available = result as UpdateCheckResult.UpdateAvailable
            assertEquals(99, available.release.versionCode)
            assertEquals("1.0.99", available.release.versionName)
            assertEquals("https://example.com/app-release.apk", available.release.apkUrl)
            assertEquals(123456L, available.release.apkSize)
            assertEquals("- 修复已知问题\n- 优化同步", available.release.releaseNotes)
        } finally {
            server.stop()
        }
    }

    @Test
    fun `远端版本号相同时为已是最新`() {
        val server = FakeHttpServer { httpResponse("200 OK", releaseJson(21, "1.0.21").toByteArray()) }
        try {
            val result = checker(server.port).check(currentVersionCode = 21)
            assertEquals(21, (result as UpdateCheckResult.UpToDate).remoteVersionCode)
        } finally {
            server.stop()
        }
    }

    @Test
    fun `远端版本号更低时不算更新`() {
        val server = FakeHttpServer { httpResponse("200 OK", releaseJson(5, "1.0.5").toByteArray()) }
        try {
            val result = checker(server.port).check(currentVersionCode = 21)
            assertTrue(result is UpdateCheckResult.UpToDate)
        } finally {
            server.stop()
        }
    }

    @Test
    fun `请求头必须带 User-Agent`() {
        val server = FakeHttpServer { head ->
            assertTrue("缺少 User-Agent 头", head.contains("User-Agent:"))
            httpResponse("200 OK", releaseJson(21, "1.0.21").toByteArray())
        }
        try {
            checker(server.port).check(1)
        } finally {
            server.stop()
        }
    }

    @Test
    fun `404 时提示还没有发布过版本`() {
        val server = FakeHttpServer { httpResponse("404 Not Found") }
        try {
            val result = checker(server.port).check(1)
            assertTrue((result as UpdateCheckResult.Failed).message.contains("还没有发布过"))
        } finally {
            server.stop()
        }
    }

    @Test
    fun `403 时提示限流`() {
        val server = FakeHttpServer { httpResponse("403 Forbidden") }
        try {
            val result = checker(server.port).check(1)
            assertTrue((result as UpdateCheckResult.Failed).message.contains("限流"))
        } finally {
            server.stop()
        }
    }

    @Test
    fun `说明缺少元数据时报告数据不完整`() {
        val server = FakeHttpServer {
            httpResponse("200 OK", """{"body": "没有注释", "assets": []}""".toByteArray())
        }
        try {
            val result = checker(server.port).check(1)
            assertTrue((result as UpdateCheckResult.Failed).message.contains("不完整"))
        } finally {
            server.stop()
        }
    }

    @Test
    fun `发布页没有安装包时报安装包缺失`() {
        val server = FakeHttpServer { httpResponse("200 OK", releaseJson(99, "1.0.99", includeApk = false).toByteArray()) }
        try {
            val result = checker(server.port).check(1)
            assertTrue((result as UpdateCheckResult.Failed).message.contains("安装包"))
        } finally {
            server.stop()
        }
    }
}

/**
 * 元数据注释解析的纯函数测试。
 */
class UpdateMetaTest {

    @Test
    fun `解析标准元数据行`() {
        val body = "<!-- appupdate versionCode=21 versionName=1.0.21 -->\n正文"
        assertEquals(21 to "1.0.21", UpdateMeta.parse(body))
    }

    @Test
    fun `缺元数据返回null`() {
        assertNull(UpdateMeta.parse("普通说明"))
        assertNull(UpdateMeta.parse(null))
        assertNull(UpdateMeta.parse("<!-- appupdate versionCode=0 versionName=1.0.0 -->"))
    }

    @Test
    fun `正文剥离元数据注释`() {
        val body = "<!-- appupdate versionCode=21 versionName=1.0.21 -->\n- 第一条\n- 第二条"
        assertEquals("- 第一条\n- 第二条", UpdateMeta.notesWithoutMeta(body))
        assertEquals("普通说明", UpdateMeta.notesWithoutMeta("普通说明"))
    }
}
