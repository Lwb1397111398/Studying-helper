package com.studyinghelper.mobile.data.repository

import android.content.Context
import androidx.room.withTransaction
import com.studyinghelper.mobile.data.db.BookEntity
import com.studyinghelper.mobile.data.db.ChapterEntity
import com.studyinghelper.mobile.data.db.KnowledgeUnitEntity
import com.studyinghelper.mobile.data.db.StudyDatabase
import com.tom_roush.pdfbox.android.PDFBoxResourceLoader
import com.tom_roush.pdfbox.pdmodel.PDDocument
import com.tom_roush.pdfbox.text.PDFTextStripper
import java.io.ByteArrayInputStream
import java.net.URLDecoder
import java.nio.charset.StandardCharsets
import java.time.OffsetDateTime
import java.util.UUID
import java.util.zip.ZipInputStream

class DocumentRepository(
    private val database: StudyDatabase,
    private val context: Context,
) {
    private val dao = database.studyDao()

    suspend fun importTxt(title: String, content: String): DocumentImportResult {
        val normalized = content.replace("\r\n", "\n").replace("\r", "\n").trim()
        require(normalized.isNotEmpty()) { "TXT 文件内容为空" }
        return saveBook(
            title = title.trim().ifEmpty { "TXT 导入书籍" },
            fileType = "txt",
            fileSizeBytes = normalized.encodeToByteArray().size,
            sections = splitTxtSections(normalized),
        )
    }

    suspend fun importPdf(title: String, bytes: ByteArray): DocumentImportResult {
        PDFBoxResourceLoader.init(context.applicationContext)
        val text = PDDocument.load(ByteArrayInputStream(bytes)).use { document ->
            PDFTextStripper().getText(document)
        }.replace("\r\n", "\n").replace("\r", "\n").trim()
        require(text.isNotEmpty()) { "PDF 中没有可导入的文本，扫描版 PDF 需要后续 OCR 支持" }
        return saveBook(
            title = title.trim().ifEmpty { "PDF 导入书籍" },
            fileType = "pdf",
            fileSizeBytes = bytes.size,
            sections = splitTxtSections(text),
        )
    }

    suspend fun importEpub(title: String, bytes: ByteArray): DocumentImportResult {
        val entries = readZipEntries(bytes)
        val container = entries["META-INF/container.xml"]?.decodeToString() ?: error("EPUB 缺少 container.xml")
        val opfPath = Regex("full-path=[\"']([^\"']+)[\"']").find(container)?.groupValues?.get(1)
            ?: error("EPUB 缺少 OPF 路径")
        val opf = entries[opfPath]?.decodeToString() ?: error("EPUB 缺少 OPF 文件")
        val baseDir = opfPath.substringBeforeLast('/', missingDelimiterValue = "")
        val manifest = parseManifest(opf)
        val spine = Regex("<itemref\\b[^>]*idref=[\"']([^\"']+)[\"'][^>]*/?>")
            .findAll(opf)
            .map { it.groupValues[1] }
            .toList()
        val sections = spine.mapNotNull { idref ->
            val href = manifest[idref] ?: return@mapNotNull null
            val path = resolvePath(baseDir, href)
            val html = entries[path]?.decodeToString() ?: return@mapNotNull null
            val text = htmlToText(html)
            if (text.isBlank()) return@mapNotNull null
            TxtSection(extractTitle(html, text), text)
        }
        require(sections.isNotEmpty()) { "EPUB 中没有可导入的章节文本" }
        return saveBook(
            title = title.trim().ifEmpty { extractBookTitle(opf) ?: "EPUB 导入书籍" },
            fileType = "epub",
            fileSizeBytes = bytes.size,
            sections = sections,
        )
    }

    private suspend fun saveBook(
        title: String,
        fileType: String,
        fileSizeBytes: Int,
        sections: List<TxtSection>,
    ): DocumentImportResult {
        val bookId = "android-book-${UUID.randomUUID()}"
        val now = OffsetDateTime.now().toString()
        val chapters = sections.mapIndexed { index, section ->
            ChapterEntity(
                id = "android-chapter-${UUID.randomUUID()}",
                bookId = bookId,
                title = section.title,
                chapterNumber = index + 1,
                parentId = null,
                level = 0,
                orderIndex = index,
                summary = null,
            )
        }
        var nextOrder = 0
        val units = chapters.flatMapIndexed { chapterIndex, chapter ->
            splitUnits(sections[chapterIndex].content).mapIndexed { unitIndex, unitChunk ->
                KnowledgeUnitEntity(
                    id = "android-unit-${UUID.randomUUID()}",
                    bookId = bookId,
                    chapterId = chapter.id,
                    sectionId = null,
                    title = buildUnitTitle(chapter.title, unitIndex),
                    content = unitChunk.content,
                    orderIndex = nextOrder++,
                    charOffsetStart = unitChunk.start,
                    charOffsetEnd = unitChunk.end,
                    summary = null,
                    explanation = null,
                    keyPoints = null,
                    concepts = null,
                    prerequisites = null,
                    difficultyLevel = 1,
                    importanceScore = 0.5f,
                )
            }
        }

        database.withTransaction {
            dao.insertBooks(
                listOf(
                    BookEntity(
                        id = bookId,
                        userId = "anonymous",
                        title = title,
                        author = null,
                        filePath = "android://$fileType/$bookId",
                        fileType = fileType,
                        fileSizeBytes = fileSizeBytes,
                        parseStatus = "completed",
                        splitStatus = "completed",
                        learnStatus = "pending",
                        totalChapters = chapters.size,
                        totalUnits = units.size,
                        learnedUnits = 0,
                        readingMotivation = null,
                        createdAt = now,
                        updatedAt = now,
                    )
                )
            )
            dao.insertChapters(chapters)
            dao.insertUnits(units)
        }

        return DocumentImportResult(books = 1, chapters = chapters.size, units = units.size)
    }

    private fun splitTxtSections(content: String): List<TxtSection> {
        val lines = content.lines()
        val headingPattern = Regex("^\\s*(第[一二三四五六七八九十百千万0-9]+[章节篇部]|[0-9]+[.、]\\s+).+")
        val sections = mutableListOf<TxtSection>()
        var currentTitle = "正文"
        val buffer = StringBuilder()

        for (line in lines) {
            val trimmed = line.trim()
            if (trimmed.isNotEmpty() && headingPattern.matches(trimmed) && buffer.isNotBlank()) {
                sections += TxtSection(currentTitle, buffer.toString().trim())
                currentTitle = trimmed
                buffer.clear()
            } else {
                if (trimmed.isNotEmpty() && headingPattern.matches(trimmed) && buffer.isBlank()) {
                    currentTitle = trimmed
                } else {
                    buffer.appendLine(line)
                }
            }
        }
        if (buffer.isNotBlank()) sections += TxtSection(currentTitle, buffer.toString().trim())
        return sections.ifEmpty { listOf(TxtSection("正文", content)) }
    }

    private fun splitUnits(content: String): List<UnitChunk> {
        val paragraphRegex = Regex("\\S[\\s\\S]*?(?=\\n\\s*\\n+|$)")
        val paragraphs = paragraphRegex.findAll(content)
            .map { match -> UnitChunk(match.value.trim(), match.range.first, match.range.last + 1) }
            .filter { it.content.isNotEmpty() }
            .toList()
        if (paragraphs.isEmpty()) return listOf(UnitChunk(content.trim(), 0, content.length))

        val units = mutableListOf<UnitChunk>()
        val buffer = StringBuilder()
        var start = paragraphs.first().start
        var end = paragraphs.first().end
        for (paragraph in paragraphs) {
            if (buffer.length + paragraph.content.length > 1200 && buffer.isNotBlank()) {
                units += UnitChunk(buffer.toString().trim(), start, end)
                buffer.clear()
                start = paragraph.start
            }
            if (buffer.isNotEmpty()) buffer.append("\n\n")
            buffer.append(paragraph.content)
            end = paragraph.end
        }
        if (buffer.isNotBlank()) units += UnitChunk(buffer.toString().trim(), start, end)
        return units
    }

    private fun readZipEntries(bytes: ByteArray): Map<String, ByteArray> {
        val entries = mutableMapOf<String, ByteArray>()
        ZipInputStream(ByteArrayInputStream(bytes)).use { zip ->
            generateSequence { zip.nextEntry }.forEach { entry ->
                if (!entry.isDirectory) entries[entry.name] = zip.readBytes()
                zip.closeEntry()
            }
        }
        return entries
    }

    private fun parseManifest(opf: String): Map<String, String> {
        return Regex("<item\\b[^>]*/?>")
            .findAll(opf)
            .mapNotNull { match ->
                val tag = match.value
                val id = attr(tag, "id") ?: return@mapNotNull null
                val href = attr(tag, "href") ?: return@mapNotNull null
                id to href
            }
            .toMap()
    }

    private fun attr(tag: String, name: String): String? {
        return Regex("$name=[\"']([^\"']+)[\"']").find(tag)?.groupValues?.get(1)
    }

    private fun resolvePath(baseDir: String, href: String): String {
        val cleanHref = URLDecoder.decode(
            href.substringBefore('#').substringBefore('?'),
            StandardCharsets.UTF_8.name(),
        )
        val raw = if (baseDir.isBlank()) cleanHref else "$baseDir/$cleanHref"
        val parts = mutableListOf<String>()
        raw.split('/').forEach { part ->
            when (part) {
                "", "." -> Unit
                ".." -> if (parts.isNotEmpty()) parts.removeAt(parts.lastIndex)
                else -> parts += part
            }
        }
        return parts.joinToString("/")
    }

    private fun htmlToText(html: String): String {
        return html
            .replace(Regex("<script[\\s\\S]*?</script>", RegexOption.IGNORE_CASE), " ")
            .replace(Regex("<style[\\s\\S]*?</style>", RegexOption.IGNORE_CASE), " ")
            .replace(Regex("</?(p|div|section|article|h[1-6]|li|br)[^>]*>", RegexOption.IGNORE_CASE), "\n\n")
            .replace(Regex("<[^>]+>"), " ")
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", "\"")
            .replace("&#39;", "'")
            .lines()
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .joinToString("\n\n")
    }

    private fun extractTitle(html: String, text: String): String {
        val heading = Regex("<h[1-3][^>]*>([\\s\\S]*?)</h[1-3]>", RegexOption.IGNORE_CASE)
            .find(html)
            ?.groupValues
            ?.get(1)
            ?.let { htmlToText(it) }
            ?.lineSequence()
            ?.firstOrNull { it.isNotBlank() }
        return heading ?: text.lineSequence().firstOrNull { it.isNotBlank() }?.take(40) ?: "章节"
    }

    private fun extractBookTitle(opf: String): String? {
        return Regex("<dc:title[^>]*>([\\s\\S]*?)</dc:title>", RegexOption.IGNORE_CASE)
            .find(opf)
            ?.groupValues
            ?.get(1)
            ?.trim()
            ?.takeIf { it.isNotEmpty() }
    }

    private fun buildUnitTitle(chapterTitle: String, index: Int): String {
        return if (index == 0) chapterTitle else "$chapterTitle - ${index + 1}"
    }
}

data class DocumentImportResult(val books: Int, val chapters: Int, val units: Int)

private data class TxtSection(val title: String, val content: String)

private data class UnitChunk(val content: String, val start: Int, val end: Int)
