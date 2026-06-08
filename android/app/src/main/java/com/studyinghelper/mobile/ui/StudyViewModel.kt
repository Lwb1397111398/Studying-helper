package com.studyinghelper.mobile.ui

import android.app.Application
import android.net.Uri
import android.provider.OpenableColumns
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.room.withTransaction
import com.studyinghelper.mobile.data.db.BookEntity
import com.studyinghelper.mobile.data.db.ChapterEntity
import com.studyinghelper.mobile.data.db.DailyStatsEntity
import com.studyinghelper.mobile.data.db.KnowledgeUnitEntity
import com.studyinghelper.mobile.data.db.MasteryRecordEntity
import com.studyinghelper.mobile.data.db.StudyDatabase
import com.studyinghelper.mobile.data.repository.AiConfig
import com.studyinghelper.mobile.data.repository.AiConfigRepository
import com.studyinghelper.mobile.data.repository.AiRepository
import com.studyinghelper.mobile.data.repository.DocumentRepository
import com.studyinghelper.mobile.data.repository.ExamQuestion
import com.studyinghelper.mobile.data.repository.ExamRepository
import com.studyinghelper.mobile.data.repository.ExamState
import com.studyinghelper.mobile.data.repository.SyncRepository
import com.studyinghelper.mobile.data.repository.TeachingRepository
import com.studyinghelper.mobile.data.repository.TeachingState
import com.studyinghelper.mobile.data.sync.SyncPreview
import java.nio.charset.Charset
import java.time.LocalDate
import java.time.OffsetDateTime
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

class StudyViewModel(application: Application) : AndroidViewModel(application) {
    private val database = StudyDatabase.getInstance(application)
    private val dao = database.studyDao()
    private val syncRepository = SyncRepository(database)
    private val documentRepository = DocumentRepository(database, application)
    private val examRepository = ExamRepository(database)
    private val aiConfigRepository = AiConfigRepository(application)
    private val aiRepository = AiRepository(aiConfigRepository)
    private val teachingRepository = TeachingRepository(database, aiRepository)
    private val json = Json { prettyPrint = false }
    private val analyzingUnitIds = mutableSetOf<String>()

    // 手动序列化 KeyPoint 列表为 JSON 字符串
    private fun serializeKeyPoints(keyPoints: List<com.studyinghelper.mobile.data.repository.KeyPoint>): String {
        val elements = keyPoints.map { kp ->
            buildString {
                append("""{"title":${json.encodeToString(kp.title)}""")
                if (kp.explanation != null) append(""","explanation":${json.encodeToString(kp.explanation)}""")
                if (kp.examples.isNotEmpty()) append(""","examples":${json.encodeToString(kp.examples)}""")
                append("}")
            }
        }
        return "[${elements.joinToString(",")}]"
    }

    // 手动序列化 Concept 列表为 JSON 字符串
    private fun serializeConcepts(concepts: List<com.studyinghelper.mobile.data.repository.Concept>): String {
        val elements = concepts.map { c ->
            buildString {
                append("""{"name":${json.encodeToString(c.name)}""")
                if (c.definition != null) append(""","definition":${json.encodeToString(c.definition)}""")
                if (c.examples.isNotEmpty()) append(""","examples":${json.encodeToString(c.examples)}""")
                append("}")
            }
        }
        return "[${elements.joinToString(",")}]"
    }
    private var teachingBusy = false
    private var examSaving = false
    private var examRequestId = 0
    private var teachingRequestId = 0
    private var reportRequestId = 0
    private var syncRequestId = 0
    private var pendingSyncContent: String? = null
    private var syncImporting = false

    val books: StateFlow<List<BookEntity>> = dao.observeBooks().stateIn(
        viewModelScope,
        SharingStarted.WhileSubscribed(5_000),
        emptyList(),
    )

    private val _status = MutableStateFlow<String?>(null)
    val status: StateFlow<String?> = _status

    private val _aiConfig = MutableStateFlow(aiConfigRepository.getConfig())
    val aiConfig: StateFlow<AiConfig> = _aiConfig

    private val _examState = MutableStateFlow<ExamState?>(null)
    val examState: StateFlow<ExamState?> = _examState

    private val _teachingState = MutableStateFlow<TeachingState?>(null)
    val teachingState: StateFlow<TeachingState?> = _teachingState

    private val _examError = MutableStateFlow<String?>(null)
    val examError: StateFlow<String?> = _examError

    private val _teachingError = MutableStateFlow<String?>(null)
    val teachingError: StateFlow<String?> = _teachingError

    private val _syncPreview = MutableStateFlow<SyncPreview?>(null)
    val syncPreview: StateFlow<SyncPreview?> = _syncPreview

    private val _report = MutableStateFlow<ReportState?>(null)
    val report: StateFlow<ReportState?> = _report

    fun book(bookId: String): StateFlow<BookEntity?> = dao.observeBook(bookId).stateIn(
        viewModelScope,
        SharingStarted.WhileSubscribed(5_000),
        null,
    )

    fun chapters(bookId: String): StateFlow<List<ChapterEntity>> = dao.observeChapters(bookId).stateIn(
        viewModelScope,
        SharingStarted.WhileSubscribed(5_000),
        emptyList(),
    )

    fun units(bookId: String): StateFlow<List<KnowledgeUnitEntity>> = dao.observeUnits(bookId).stateIn(
        viewModelScope,
        SharingStarted.WhileSubscribed(5_000),
        emptyList(),
    )

    fun unit(unitId: String): StateFlow<UnitDetailState> = dao.observeUnit(unitId).map { unit ->
        UnitDetailState(unit = unit, isLoading = false)
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), UnitDetailState())

    fun mastery(unitId: String): StateFlow<MasteryRecordEntity?> = dao.observeMastery(unitId).stateIn(
        viewModelScope,
        SharingStarted.WhileSubscribed(5_000),
        null,
    )

    fun dueUnits(bookId: String): StateFlow<List<KnowledgeUnitEntity>> = dao.observeDueUnits(
        bookId,
        OffsetDateTime.now().toString(),
    ).stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    fun refreshReport() {
        val requestId = ++reportRequestId
        _report.value = null
        viewModelScope.launch(Dispatchers.IO) {
            val report = ReportState(
                books = dao.countBooks(),
                units = dao.countAllUnits(),
                learnedUnits = dao.countAllLearnedUnits(),
                reviewSessions = dao.countReviewSessions(),
                examSessions = dao.countExamSessions(),
                totalMinutes = dao.sumStudyMinutes() ?: 0,
            )
            if (reportRequestId == requestId) {
                _report.value = report
            }
        }
    }

    fun saveAiConfig(apiKey: String, baseUrl: String, model: String) {
        aiConfigRepository.saveConfig(apiKey, baseUrl, model)
        _aiConfig.value = aiConfigRepository.getConfig()
        _status.value = "AI 配置已保存"
    }

    fun startExam(bookId: String) {
        val requestId = ++examRequestId
        examSaving = false
        _examState.value = null
        _examError.value = null
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                examRepository.generateExam(bookId)
            }.onSuccess { questions ->
                if (examRequestId == requestId) {
                    _examState.value = ExamState(bookId = bookId, questions = questions)
                    _status.value = "考试已开始"
                }
            }.onFailure { error ->
                if (examRequestId == requestId) {
                    val message = error.message ?: "未知错误"
                    _examError.value = message
                    _status.value = "无法开始考试：$message"
                }
            }
        }
    }

    fun updateExamAnswer(questionId: String, answer: String) {
        updateExamQuestion(questionId) { it.copy(userAnswer = answer) }
    }

    fun updateExamScore(questionId: String, score: Int) {
        updateExamQuestion(questionId) { it.copy(selfScore = score.coerceIn(0, 100)) }
    }

    fun moveExam(offset: Int) {
        val state = _examState.value ?: return
        val nextIndex = (state.currentIndex + offset).coerceIn(0, state.questions.lastIndex)
        _examState.value = state.copy(currentIndex = nextIndex)
    }

    fun finishExam() {
        if (examSaving) return
        val state = _examState.value ?: return
        if (state.result != null) return
        examSaving = true
        val requestId = examRequestId
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                examRepository.saveExamResult(state.bookId, state.questions)
            }.onSuccess { result ->
                if (examRequestId == requestId) {
                    _examState.value = state.copy(result = result)
                    _status.value = "考试完成：${result.score.toInt()} 分"
                }
            }.onFailure { error ->
                if (examRequestId == requestId) {
                    _status.value = "考试保存失败：${error.message ?: "未知错误"}"
                }
            }
            if (examRequestId == requestId) examSaving = false
        }
    }

    fun clearExam() {
        examRequestId++
        examSaving = false
        _examState.value = null
        _examError.value = null
    }

    fun startTeaching(bookId: String) {
        if (teachingBusy) return
        val requestId = ++teachingRequestId
        teachingBusy = true
        _teachingState.value = null
        _teachingError.value = null
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                teachingRepository.start(bookId)
            }.onSuccess { state ->
                if (teachingRequestId == requestId) {
                    _teachingState.value = state
                    _status.value = "教学已开始"
                }
            }.onFailure { error ->
                if (teachingRequestId == requestId) {
                    val message = error.message ?: "未知错误"
                    _teachingError.value = message
                    _status.value = "无法开始教学：$message"
                }
            }
            if (teachingRequestId == requestId) teachingBusy = false
        }
    }

    fun advanceTeaching() {
        if (teachingBusy) return
        val state = _teachingState.value ?: return
        if (state.session.status == "completed") return
        teachingBusy = true
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                teachingRepository.advance(state)
            }.onSuccess { next ->
                _teachingState.value = next
                _status.value = if (next.session.status == "completed") "教学已完成" else "已进入下一阶段"
            }.onFailure { error ->
                _status.value = "教学推进失败：${error.message ?: "未知错误"}"
            }
            teachingBusy = false
        }
    }

    fun finishTeaching() {
        if (teachingBusy) return
        val state = _teachingState.value ?: return
        teachingBusy = true
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                teachingRepository.finish(state)
            }.onSuccess { next ->
                _teachingState.value = next
                _status.value = "教学已结束"
            }.onFailure { error ->
                _status.value = "教学结束失败：${error.message ?: "未知错误"}"
            }
            teachingBusy = false
        }
    }

    fun askTeachingQuestion(question: String) {
        if (teachingBusy) return
        val state = _teachingState.value ?: return
        teachingBusy = true
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                teachingRepository.answerQuestion(state, question)
            }.onSuccess { next ->
                _teachingState.value = next
                _status.value = "已回答问题"
            }.onFailure { error ->
                _status.value = "回答问题失败：${error.message ?: "未知错误"}"
            }
            teachingBusy = false
        }
    }

    fun clearTeaching() {
        teachingRequestId++
        teachingBusy = false
        _teachingState.value = null
        _teachingError.value = null
    }

    private fun updateExamQuestion(questionId: String, transform: (ExamQuestion) -> ExamQuestion) {
        val state = _examState.value ?: return
        _examState.value = state.copy(
            questions = state.questions.map { question ->
                if (question.id == questionId) transform(question) else question
            },
        )
    }

    fun deleteBook(bookId: String) {
        if (_examState.value?.bookId == bookId) clearExam()
        if (_teachingState.value?.session?.bookId == bookId) clearTeaching()
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                database.withTransaction {
                    val unitIds = dao.getUnitIds(listOf(bookId))
                    val nodeIds = dao.getNodeIds(listOf(bookId))
                    val sessionIds = dao.getTeachingSessionIds(listOf(bookId))
                    if (unitIds.isNotEmpty()) dao.deleteAnnotations(unitIds)
                    if (nodeIds.isNotEmpty()) dao.deleteKgEdges(nodeIds)
                    if (sessionIds.isNotEmpty()) {
                        dao.deleteTeachingMessages(sessionIds)
                        dao.deleteUserQuestions(sessionIds)
                        dao.deleteSessionTests(sessionIds)
                        dao.deleteLearningEfficiency(sessionIds)
                    }
                    dao.deleteMastery(listOf(bookId))
                    dao.deleteLearningRecords(listOf(bookId))
                    dao.deleteReviewSessions(listOf(bookId))
                    dao.deleteTeachingSessions(listOf(bookId))
                    dao.deleteKgNodes(listOf(bookId))
                    dao.deleteUnits(listOf(bookId))
                    dao.deleteChapters(listOf(bookId))
                    dao.deleteBooks(listOf(bookId))
                }
            }.onSuccess {
                _status.value = "已删除书籍"
            }.onFailure { error ->
                _status.value = "删除书籍失败：${error.message ?: "未知错误"}"
            }
        }
    }

    fun createBook(title: String, author: String?) {
        val trimmedTitle = title.trim()
        if (trimmedTitle.isEmpty()) {
            _status.value = "书名不能为空"
            return
        }
        viewModelScope.launch {
            val now = OffsetDateTime.now().toString()
            val bookId = "android-book-${UUID.randomUUID()}"
            val chapterId = "android-chapter-${UUID.randomUUID()}"
            dao.insertBooks(
                listOf(
                    BookEntity(
                        id = bookId,
                        userId = "anonymous",
                        title = trimmedTitle,
                        author = author?.trim()?.takeIf { it.isNotEmpty() },
                        filePath = "android://manual/$bookId",
                        fileType = "manual",
                        fileSizeBytes = 0,
                        parseStatus = "completed",
                        splitStatus = "completed",
                        learnStatus = "pending",
                        totalChapters = 1,
                        totalUnits = 0,
                        learnedUnits = 0,
                        readingMotivation = null,
                        createdAt = now,
                        updatedAt = now,
                    )
                )
            )
            dao.insertChapters(
                listOf(
                    ChapterEntity(
                        id = chapterId,
                        bookId = bookId,
                        title = "默认章节",
                        chapterNumber = 1,
                        parentId = null,
                        level = 0,
                        orderIndex = 0,
                        summary = null,
                    )
                )
            )
            _status.value = "已创建书籍"
        }
    }

    fun createChapter(bookId: String, title: String) {
        val trimmedTitle = title.trim()
        if (trimmedTitle.isEmpty()) {
            _status.value = "章节标题不能为空"
            return
        }
        viewModelScope.launch {
            val order = dao.countChapters(bookId)
            dao.insertChapters(
                listOf(
                    ChapterEntity(
                        id = "android-chapter-${UUID.randomUUID()}",
                        bookId = bookId,
                        title = trimmedTitle,
                        chapterNumber = order + 1,
                        parentId = null,
                        level = 0,
                        orderIndex = order,
                        summary = null,
                    )
                )
            )
            refreshBookCounts(bookId)
            _status.value = "已创建章节"
        }
    }

    fun createUnit(bookId: String, title: String, content: String) {
        val trimmedTitle = title.trim()
        val trimmedContent = content.trim()
        if (trimmedTitle.isEmpty() || trimmedContent.isEmpty()) {
            _status.value = "知识单元标题和内容不能为空"
            return
        }
        viewModelScope.launch {
            val chapter = dao.getFirstChapter(bookId) ?: ChapterEntity(
                id = "android-chapter-${UUID.randomUUID()}",
                bookId = bookId,
                title = "默认章节",
                chapterNumber = 1,
                parentId = null,
                level = 0,
                orderIndex = 0,
                summary = null,
            ).also { dao.insertChapters(listOf(it)) }
            val order = dao.countUnits(bookId)
            dao.insertUnits(
                listOf(
                    KnowledgeUnitEntity(
                        id = "android-unit-${UUID.randomUUID()}",
                        bookId = bookId,
                        chapterId = chapter.id,
                        sectionId = null,
                        title = trimmedTitle,
                        content = trimmedContent,
                        orderIndex = order,
                        charOffsetStart = 0,
                        charOffsetEnd = trimmedContent.length,
                        summary = null,
                        explanation = null,
                        keyPoints = null,
                        concepts = null,
                        prerequisites = null,
                        difficultyLevel = 1,
                        importanceScore = 0.5f,
                    )
                )
            )
            refreshBookCounts(bookId)
            _status.value = "已创建知识单元"
        }
    }

    fun analyzeUnit(unitId: String) {
        synchronized(analyzingUnitIds) {
            if (!analyzingUnitIds.add(unitId)) {
                _status.value = "该知识单元正在分析中"
                return
            }
        }
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                val unit = dao.getUnit(unitId) ?: error("未找到知识单元")
                val result = aiRepository.analyzeUnit(unit)
                // 序列化结构化数据为 JSON 字符串
                val keyPointsJson = serializeKeyPoints(result.keyPoints)
                val conceptsJson = serializeConcepts(result.concepts)
                dao.updateUnitAnalysis(
                    unitId = unitId,
                    summary = result.summary,
                    explanation = result.explanation,
                    keyPoints = keyPointsJson,
                    concepts = conceptsJson,
                )
            }.onSuccess {
                _status.value = "AI 分析已完成"
            }.onFailure { error ->
                _status.value = "AI 分析失败：${error.message ?: "未知错误"}"
            }
            synchronized(analyzingUnitIds) {
                analyzingUnitIds.remove(unitId)
            }
        }
    }

    fun updateMastery(unitId: String, score: Float) {
        viewModelScope.launch(Dispatchers.IO) {
            val unit = dao.getUnit(unitId) ?: return@launch
            val now = OffsetDateTime.now()
            val clampedScore = score.coerceIn(0f, 1f)
            val old = dao.getMastery(unitId)
            val reviewCount = (old?.reviewCount ?: 0) + 1
            val intervalDays = when {
                clampedScore >= 0.85f -> 7
                clampedScore >= 0.6f -> 3
                else -> 1
            }
            val mastery = MasteryRecordEntity(
                id = old?.id ?: "android-mastery-${UUID.randomUUID()}",
                userId = "anonymous",
                knowledgeUnitId = unit.id,
                bookId = unit.bookId,
                masteryScore = clampedScore,
                masteryLevel = when {
                    clampedScore >= 0.85f -> "mastered"
                    clampedScore >= 0.6f -> "familiar"
                    clampedScore > 0f -> "learning"
                    else -> "new"
                },
                lastReviewedAt = now.toString(),
                nextReviewAt = now.plusDays(intervalDays.toLong()).toString(),
                reviewCount = reviewCount,
                easeFactor = old?.easeFactor ?: 2.5f,
                intervalDays = intervalDays,
            )
            dao.insertMastery(listOf(mastery))

            val today = LocalDate.now().toString()
            val oldStats = dao.getDailyStats("anonymous", today)
            val newlyLearned = (old?.masteryScore ?: 0f) < 0.6f && clampedScore >= 0.6f
            dao.insertDailyStats(
                listOf(
                    DailyStatsEntity(
                        userId = "anonymous",
                        date = today,
                        totalMinutes = oldStats?.totalMinutes ?: 0,
                        unitsLearned = (oldStats?.unitsLearned ?: 0) + if (newlyLearned) 1 else 0,
                        unitsReviewed = (oldStats?.unitsReviewed ?: 0) + 1,
                        testsTaken = oldStats?.testsTaken ?: 0,
                        avgTestScore = oldStats?.avgTestScore ?: 0f,
                        streakDay = oldStats?.streakDay ?: 1,
                    )
                )
            )
            refreshBookCounts(unit.bookId)
            _status.value = "已更新掌握度"
        }
    }

    private suspend fun refreshBookCounts(bookId: String) {
        val chapters = dao.countChapters(bookId)
        val units = dao.countUnits(bookId)
        val learned = dao.countLearnedUnits(bookId)
        val learnStatus = if (units > 0 && learned >= units) "completed" else if (learned > 0) "learning" else "pending"
        dao.updateBookCounts(bookId, chapters, units, learned, learnStatus, OffsetDateTime.now().toString())
    }

    fun importPdfFromUri(uri: Uri) {
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                val resolver = getApplication<Application>().contentResolver
                val bytes = resolver.openInputStream(uri)?.use { it.readBytes() }
                    ?: error("无法读取 PDF 文件")
                val title = getDisplayName(uri)
                    ?.substringBeforeLast('.')
                    ?.takeIf { it.isNotBlank() }
                    ?: uri.lastPathSegment?.substringAfterLast('/')?.substringBeforeLast('.')?.takeIf { it.isNotBlank() }
                    ?: "PDF 导入书籍"
                documentRepository.importPdf(title, bytes)
            }.onSuccess { result ->
                _status.value = "PDF 导入完成：${result.chapters} 个章节，${result.units} 个知识单元"
            }.onFailure { error ->
                _status.value = "PDF 导入失败：${error.message ?: "未知错误"}"
            }
        }
    }

    fun importEpubFromUri(uri: Uri) {
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                val resolver = getApplication<Application>().contentResolver
                val bytes = resolver.openInputStream(uri)?.use { it.readBytes() }
                    ?: error("无法读取 EPUB 文件")
                val title = getDisplayName(uri)
                    ?.substringBeforeLast('.')
                    ?.takeIf { it.isNotBlank() }
                    ?: uri.lastPathSegment?.substringAfterLast('/')?.substringBeforeLast('.')?.takeIf { it.isNotBlank() }
                    ?: "EPUB 导入书籍"
                documentRepository.importEpub(title, bytes)
            }.onSuccess { result ->
                _status.value = "EPUB 导入完成：${result.chapters} 个章节，${result.units} 个知识单元"
            }.onFailure { error ->
                _status.value = "EPUB 导入失败：${error.message ?: "未知错误"}"
            }
        }
    }

    fun importTxtFromUri(uri: Uri) {
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                val resolver = getApplication<Application>().contentResolver
                val bytes = resolver.openInputStream(uri)?.use { it.readBytes() }
                    ?: error("无法读取 TXT 文件")
                val content = decodeText(bytes)
                val title = getDisplayName(uri)
                    ?.substringBeforeLast('.')
                    ?.takeIf { it.isNotBlank() }
                    ?: uri.lastPathSegment?.substringAfterLast('/')?.substringBeforeLast('.')?.takeIf { it.isNotBlank() }
                    ?: "TXT 导入书籍"
                documentRepository.importTxt(title, content)
            }.onSuccess { result ->
                _status.value = "TXT 导入完成：${result.chapters} 个章节，${result.units} 个知识单元"
            }.onFailure { error ->
                _status.value = "TXT 导入失败：${error.message ?: "未知错误"}"
            }
        }
    }

    fun importFromUri(uri: Uri) {
        if (syncImporting) return
        val requestId = ++syncRequestId
        syncImporting = true
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                val resolver = getApplication<Application>().contentResolver
                val content = resolver.openInputStream(uri)?.bufferedReader()?.use { it.readText() }
                    ?: error("无法读取文件")
                val preview = syncRepository.previewPackage(content)
                content to preview
            }.onSuccess { (content, preview) ->
                if (syncRequestId == requestId) {
                    pendingSyncContent = content
                    _syncPreview.value = preview
                    _status.value = "同步包预览完成，请确认后导入"
                }
            }.onFailure { error ->
                if (syncRequestId == requestId) {
                    pendingSyncContent = null
                    _syncPreview.value = null
                    _status.value = "同步包预览失败：${error.message ?: "未知错误"}"
                }
            }
            if (syncRequestId == requestId) syncImporting = false
        }
    }

    fun cancelSyncImport() {
        syncRequestId++
        syncImporting = false
        pendingSyncContent = null
        _syncPreview.value = null
    }

    fun confirmSyncImport() {
        val content = pendingSyncContent ?: return
        if (syncImporting) return
        val requestId = ++syncRequestId
        syncImporting = true
        pendingSyncContent = null
        _syncPreview.value = null
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                syncRepository.importPackage(content)
            }.onSuccess { result ->
                if (syncRequestId == requestId) {
                    val overwriteText = if (result.overwrittenBooks.isEmpty()) {
                        "无覆盖"
                    } else {
                        "覆盖 ${result.overwrittenBooks.size} 本"
                    }
                    _status.value = "导入完成：${result.books} 本书，${result.units} 个知识单元，${result.masteryRecords} 条掌握记录，$overwriteText"
                }
            }.onFailure { error ->
                if (syncRequestId == requestId) {
                    _status.value = "导入失败：${error.message ?: "未知错误"}"
                }
            }
            if (syncRequestId == requestId) syncImporting = false
        }
    }

    fun exportToUri(uri: Uri) {
        viewModelScope.launch(Dispatchers.IO) {
            runCatching {
                val content = syncRepository.exportPackage()
                val resolver = getApplication<Application>().contentResolver
                resolver.openOutputStream(uri)?.bufferedWriter()?.use { it.write(content) }
                    ?: error("无法写入文件")
            }.onSuccess {
                _status.value = "导出完成：可在电脑端同步中心导入"
            }.onFailure { error ->
                _status.value = "导出失败：${error.message ?: "未知错误"}"
            }
        }
    }

    private fun decodeText(bytes: ByteArray): String {
        val utf8 = bytes.toString(Charsets.UTF_8)
        return if (utf8.contains('�')) {
            bytes.toString(Charset.forName("GB18030"))
        } else {
            utf8
        }
    }

    private fun getDisplayName(uri: Uri): String? {
        val resolver = getApplication<Application>().contentResolver
        return resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (nameIndex >= 0 && cursor.moveToFirst()) cursor.getString(nameIndex) else null
        }
    }

    fun clearStatus() {
        _status.value = null
    }
}

data class UnitDetailState(
    val unit: KnowledgeUnitEntity? = null,
    val isLoading: Boolean = true,
)

data class ReportState(
    val books: Int,
    val units: Int,
    val learnedUnits: Int,
    val reviewSessions: Int,
    val examSessions: Int,
    val totalMinutes: Int,
)
