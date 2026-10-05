package com.studyinghelper.mobile.data.update

import java.io.File
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/**
 * 下载器：进度单调、字节完整、不留半截包、同版本复用不联网。
 */
class UpdateDownloaderTest {

    @get:Rule
    val tmp = TemporaryFolder()

    private fun payload(): ByteArray = ByteArray(200_000) { i -> (i % 251).toByte() }

    @Test
    fun `下载完整且进度单调到100`() {
        val data = payload()
        val server = FakeHttpServer { httpResponse("200 OK", data) }
        val dest = File(tmp.root, "updates/update-99.apk")
        val progresses = mutableListOf<Int>()
        try {
            val file = UpdateDownloader.download(
                url = "http://127.0.0.1:${server.port}/app-release.apk",
                dest = dest,
                expectedSize = data.size.toLong(),
            ) { progresses.add(it) }
            assertEquals(dest, file)
            assertArrayEquals(data, file.readBytes())
            assertTrue(progresses.isNotEmpty())
            assertTrue("进度必须单调", progresses.zipWithNext().all { (a, b) -> a <= b })
            assertEquals(100, progresses.last())
        } finally {
            server.stop()
        }
    }

    @Test
    fun `字节数不符时抛异常且不留半截包`() {
        val data = payload()
        val server = FakeHttpServer { httpResponse("200 OK", data) }
        val dest = File(tmp.root, "updates/update-99.apk")
        try {
            var thrown = false
            try {
                UpdateDownloader.download(
                    url = "http://127.0.0.1:${server.port}/app-release.apk",
                    dest = dest,
                    expectedSize = data.size + 1L,
                )
            } catch (e: Exception) {
                thrown = true
                assertTrue(e.message!!.contains("不完整"))
            }
            assertTrue("必须因为字节数不符抛异常", thrown)
            assertEquals("失败后不留任何临时/半截文件", 0, dest.parentFile.listFiles()!!.size)
        } finally {
            server.stop()
        }
    }

    @Test
    fun `同版本完整文件直接复用不再联网`() {
        val data = payload()
        val server = FakeHttpServer { httpResponse("200 OK", data) }
        val dest = File(tmp.root, "updates/update-99.apk")
        try {
            UpdateDownloader.download(
                url = "http://127.0.0.1:${server.port}/app-release.apk",
                dest = dest,
                expectedSize = data.size.toLong(),
            )
            server.stop()
            // 服务器已关：若复用逻辑失效，这次调用会因连不上而抛异常
            var reused = false
            UpdateDownloader.download(
                url = "http://127.0.0.1:${server.port}/app-release.apk",
                dest = dest,
                expectedSize = data.size.toLong(),
            ) { reused = true }
            assertTrue(reused)
            assertEquals("复用时不得发起新请求", 1, server.requestCount)
        } finally {
            server.stop()
        }
    }

    @Test
    fun `HTTP错误时抛异常不留文件`() {
        val server = FakeHttpServer { httpResponse("404 Not Found") }
        val dest = File(tmp.root, "updates/update-99.apk")
        try {
            var thrown = false
            try {
                UpdateDownloader.download(
                    url = "http://127.0.0.1:${server.port}/app-release.apk",
                    dest = dest,
                    expectedSize = 100L,
                )
            } catch (e: Exception) {
                thrown = true
            }
            assertTrue(thrown)
            assertTrue(!dest.exists())
        } finally {
            server.stop()
        }
    }
}
