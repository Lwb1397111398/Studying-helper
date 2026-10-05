package com.studyinghelper.mobile.data.update

import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.InetAddress
import java.net.ServerSocket
import kotlin.concurrent.thread

/**
 * 手写 ServerSocket 假 GitHub：AGP 单测禁用 com.sun.net.httpserver，只能裸写。
 * 每个连接读完请求头（到空行为止）就回一段预置字节，不解析请求体。
 */
class FakeHttpServer(private val handler: (requestHead: String) -> ByteArray) {

    private val server = ServerSocket(0, 16, InetAddress.getByName("127.0.0.1"))

    val port: Int get() = server.localPort

    @Volatile
    var requestCount = 0
        private set

    private val worker = thread(isDaemon = true) {
        while (!server.isClosed) {
            val socket = try {
                server.accept()
            } catch (_: Exception) {
                break
            }
            try {
                socket.use { s ->
                    val reader = BufferedReader(InputStreamReader(s.getInputStream(), Charsets.ISO_8859_1))
                    val head = StringBuilder()
                    while (true) {
                        val line = reader.readLine() ?: break
                        if (line.isEmpty()) break
                        head.append(line).append('\n')
                    }
                    requestCount++
                    s.getOutputStream().apply {
                        write(handler(head.toString()))
                        flush()
                    }
                }
            } catch (_: Exception) {
                // 客户端提前断开等情况直接丢弃
            }
        }
    }

    fun stop() {
        server.close()
    }
}

fun httpResponse(
    status: String,
    body: ByteArray = ByteArray(0),
    extraHeaders: Map<String, String> = emptyMap(),
): ByteArray {
    val head = StringBuilder("HTTP/1.1 $status\r\n")
    head.append("Content-Length: ${body.size}\r\n")
    extraHeaders.forEach { (k, v) -> head.append("$k: $v\r\n") }
    head.append("Connection: close\r\n\r\n")
    return head.toString().toByteArray(Charsets.ISO_8859_1) + body
}
