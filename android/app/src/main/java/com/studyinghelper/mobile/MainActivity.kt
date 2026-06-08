package com.studyinghelper.mobile

import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.FlowRowScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.studyinghelper.mobile.data.repository.AiConfig
import com.studyinghelper.mobile.data.repository.ExamQuestion
import com.studyinghelper.mobile.data.repository.TeachingRepository
import com.studyinghelper.mobile.data.repository.TeachingState
import com.studyinghelper.mobile.data.sync.SyncPreview
import com.studyinghelper.mobile.data.db.BookEntity
import com.studyinghelper.mobile.data.db.ChapterEntity
import com.studyinghelper.mobile.data.db.KnowledgeUnitEntity
import com.studyinghelper.mobile.data.db.MasteryRecordEntity
import com.studyinghelper.mobile.data.db.TeachingMessageEntity
import com.studyinghelper.mobile.ui.StudyViewModel
import kotlinx.coroutines.launch

private fun routeParam(value: String): String = Uri.encode(value)

fun canConfirmCreateBook(title: String): Boolean = title.isNotBlank()

fun canConfirmCreateText(first: String, second: String, requiresSecond: Boolean): Boolean {
    return first.isNotBlank() && (!requiresSecond || second.isNotBlank())
}

fun canSubmitTeachingQuestion(question: String): Boolean = question.isNotBlank()

fun teachingCompletedActionLabel(): String = "返回书籍"

fun teachingProgressUnitTitle(sessionStatus: String?, unitTitle: String?): String {
    return if (sessionStatus == "completed") "已完成" else unitTitle ?: "已完成"
}

fun canMoveExamPrevious(currentIndex: Int): Boolean = currentIndex > 0

fun canMoveExamNext(currentIndex: Int, total: Int): Boolean = currentIndex < total - 1

fun examAnswerHint(answer: String): String = if (answer.isBlank()) "尚未填写答案" else "已填写答案"

fun examScoreHint(score: Int): String = if (score == 0) "已选择 0 分" else "已自评分"

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            StudyingHelperApp()
        }
    }
}

@Composable
fun StudyingHelperApp(viewModel: StudyViewModel = viewModel()) {
    val navController = rememberNavController()
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val status by viewModel.status.collectAsState()

    LaunchedEffect(status) {
        val message = status ?: return@LaunchedEffect
        scope.launch { snackbarHostState.showSnackbar(message) }
        viewModel.clearStatus()
    }

    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Scaffold(snackbarHost = { SnackbarHost(snackbarHostState) }) { padding ->
                NavHost(
                    navController = navController,
                    startDestination = "books",
                    modifier = Modifier.padding(padding),
                ) {
                    composable("books") { BooksScreen(navController, viewModel) }
                    composable("books/{bookId}") { backStackEntry ->
                        BookDetailScreen(
                            navController = navController,
                            viewModel = viewModel,
                            bookId = backStackEntry.arguments?.getString("bookId").orEmpty(),
                        )
                    }
                    composable("units/{unitId}") { backStackEntry ->
                        UnitDetailScreen(
                            navController = navController,
                            viewModel = viewModel,
                            unitId = backStackEntry.arguments?.getString("unitId").orEmpty(),
                        )
                    }
                    composable("exam/{bookId}") { backStackEntry ->
                        ExamScreen(
                            navController = navController,
                            viewModel = viewModel,
                            bookId = backStackEntry.arguments?.getString("bookId").orEmpty(),
                        )
                    }
                    composable("teach/{bookId}") { backStackEntry ->
                        TeachingScreen(
                            navController = navController,
                            viewModel = viewModel,
                            bookId = backStackEntry.arguments?.getString("bookId").orEmpty(),
                        )
                    }
                    composable("report") {
                        ReportScreen(navController, viewModel)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun BooksScreen(navController: NavHostController, viewModel: StudyViewModel) {
    val books by viewModel.books.collectAsState()
    val aiConfig by viewModel.aiConfig.collectAsState()
    val syncPreview by viewModel.syncPreview.collectAsState()
    var showCreateBook by remember { mutableStateOf(false) }
    var showAiSettings by remember { mutableStateOf(false) }
    val importLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) viewModel.importFromUri(uri)
    }
    val txtImportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) viewModel.importTxtFromUri(uri)
    }
    val epubImportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) viewModel.importEpubFromUri(uri)
    }
    val pdfImportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) viewModel.importPdfFromUri(uri)
    }
    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
        if (uri != null) viewModel.exportToUri(uri)
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Studying Helper") }) },
    ) { padding ->
        Column(modifier = Modifier.padding(padding).padding(16.dp)) {
            HomeSummary(books)
            Spacer(Modifier.height(12.dp))
            ActionGroup("创建与导入") {
                Button(onClick = { showCreateBook = true }) { Text("新建书籍") }
                Button(onClick = { txtImportLauncher.launch(arrayOf("text/plain", "text/*")) }) { Text("导入 TXT") }
                Button(onClick = { epubImportLauncher.launch(arrayOf("application/epub+zip", "application/octet-stream")) }) { Text("导入 EPUB") }
                Button(onClick = { pdfImportLauncher.launch(arrayOf("application/pdf", "application/octet-stream")) }) { Text("导入 PDF") }
            }
            Spacer(Modifier.height(8.dp))
            ActionGroup("同步与设置") {
                Button(onClick = { importLauncher.launch(arrayOf("application/json")) }) { Text("导入同步包") }
                Button(onClick = { exportLauncher.launch("studying-helper-android-sync.json") }) { Text("导出同步包") }
                Button(onClick = { showAiSettings = true }) { Text("AI 设置") }
                Button(onClick = { navController.navigate("report") }) { Text("学习报告") }
            }
            Spacer(Modifier.height(16.dp))
            if (books.isEmpty()) {
                EmptyState()
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    items(books, key = { it.id }) { book ->
                        BookCard(book = book, onClick = { navController.navigate("books/${routeParam(book.id)}") })
                    }
                }
            }
        }
    }
    if (showCreateBook) {
        CreateBookDialog(
            onDismiss = { showCreateBook = false },
            onConfirm = { title, author ->
                viewModel.createBook(title, author)
                showCreateBook = false
            },
        )
    }
    if (showAiSettings) {
        AiSettingsDialog(
            config = aiConfig,
            onDismiss = { showAiSettings = false },
            onConfirm = { apiKey, baseUrl, model ->
                viewModel.saveAiConfig(apiKey, baseUrl, model)
                showAiSettings = false
            },
        )
    }
    syncPreview?.let { preview ->
        SyncPreviewDialog(
            preview = preview,
            onDismiss = viewModel::cancelSyncImport,
            onConfirm = viewModel::confirmSyncImport,
        )
    }
}

@Composable
fun HomeSummary(books: List<BookEntity>) {
    val totalUnits = books.sumOf { it.totalUnits ?: 0 }
    val learnedUnits = books.sumOf { it.learnedUnits ?: 0 }
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("今日学习从这里开始", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text("${books.size} 本书 · $learnedUnits / $totalUnits 个知识单元已学习")
            if (totalUnits > 0) {
                LinearProgressIndicator(progress = { learnedUnits.toFloat() / totalUnits.coerceAtLeast(1) }, modifier = Modifier.fillMaxWidth())
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ActionGroup(title: String, content: @Composable FlowRowScope.() -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                content()
            }
        }
    }
}

@Composable
fun SyncPreviewDialog(
    preview: SyncPreview,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("确认导入同步包") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("来源：${if (preview.source == "android") "Android" else "电脑端"}")
                Text("书籍：${preview.books} 本，知识单元：${preview.units} 个")
                Text("掌握记录：${preview.masteryRecords} 条")
                if (preview.overwrittenBooks > 0) {
                    Text("将覆盖本地 ${preview.overwrittenBooks} 本同 ID 书籍，请确认已备份。")
                } else {
                    Text("不会覆盖本地已有书籍。")
                }
            }
        },
        confirmButton = { TextButton(onClick = onConfirm) { Text("确认导入") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReportScreen(navController: NavHostController, viewModel: StudyViewModel) {
    val report by viewModel.report.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.refreshReport()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("学习报告") },
                navigationIcon = { TextButton(onClick = { navController.popBackStack() }) { Text("返回") } },
            )
        },
    ) { padding ->
        Column(modifier = Modifier.padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            val data = report
            if (data == null) {
                Text("正在统计学习数据...")
            } else {
                ReportCard("书籍", data.books.toString())
                ReportCard("知识单元", "${data.learnedUnits} / ${data.units} 已学习")
                ReportCard("复习记录", data.reviewSessions.toString())
                ReportCard("考试次数", data.examSessions.toString())
                ReportCard("累计学习时长", "${data.totalMinutes} 分钟")
            }
        }
    }
}

@Composable
fun ReportCard(label: String, value: String) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(label, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(value, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
fun EmptyState() {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("还没有学习数据", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text("你可以直接在手机端新建学习内容，也可以导入电脑端或其他手机端导出的同步包。", style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
fun AiSettingsDialog(
    config: AiConfig,
    onDismiss: () -> Unit,
    onConfirm: (String, String, String) -> Unit,
) {
    var apiKey by remember { mutableStateOf(config.apiKey) }
    var baseUrl by remember { mutableStateOf(config.baseUrl) }
    var model by remember { mutableStateOf(config.model) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("AI 设置") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(value = apiKey, onValueChange = { apiKey = it }, label = { Text("API Key") })
                OutlinedTextField(value = baseUrl, onValueChange = { baseUrl = it }, label = { Text("Base URL") })
                OutlinedTextField(value = model, onValueChange = { model = it }, label = { Text("模型") })
            }
        },
        confirmButton = { TextButton(onClick = { onConfirm(apiKey, baseUrl, model) }) { Text("保存") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
fun CreateBookDialog(onDismiss: () -> Unit, onConfirm: (String, String?) -> Unit) {
    var title by remember { mutableStateOf("") }
    var author by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("新建书籍") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("书名") },
                    supportingText = {
                        if (!canConfirmCreateBook(title)) Text("请输入书名。")
                    },
                )
                OutlinedTextField(value = author, onValueChange = { author = it }, label = { Text("作者（可选）") })
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(title, author) }, enabled = canConfirmCreateBook(title)) { Text("创建") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
fun ConfirmDialog(title: String, message: String, onDismiss: () -> Unit, onConfirm: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(message) },
        confirmButton = { TextButton(onClick = onConfirm) { Text("确认") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
fun CreateTextDialog(
    title: String,
    firstLabel: String,
    secondLabel: String? = null,
    onDismiss: () -> Unit,
    onConfirm: (String, String) -> Unit,
) {
    var first by remember { mutableStateOf("") }
    var second by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = first,
                    onValueChange = { first = it },
                    label = { Text(firstLabel) },
                    supportingText = {
                        if (first.isBlank()) Text("请输入$firstLabel。")
                    },
                )
                if (secondLabel != null) {
                    OutlinedTextField(
                        value = second,
                        onValueChange = { second = it },
                        label = { Text(secondLabel) },
                        supportingText = {
                            if (second.isBlank()) Text("请输入$secondLabel。")
                        },
                    )
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(first, second) },
                enabled = canConfirmCreateText(first, second, requiresSecond = secondLabel != null),
            ) { Text("保存") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
fun BookCard(book: BookEntity, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(book.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text("章节 ${book.totalChapters ?: 0} · 知识单元 ${book.totalUnits ?: 0} · 已学习 ${book.learnedUnits ?: 0}")
            val total = (book.totalUnits ?: 0).coerceAtLeast(1)
            val learned = (book.learnedUnits ?: 0).coerceAtMost(total)
            LinearProgressIndicator(progress = { learned.toFloat() / total }, modifier = Modifier.fillMaxWidth())
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun BookDetailScreen(navController: NavHostController, viewModel: StudyViewModel, bookId: String) {
    val bookFlow = remember(bookId) { viewModel.book(bookId) }
    val chaptersFlow = remember(bookId) { viewModel.chapters(bookId) }
    val unitsFlow = remember(bookId) { viewModel.units(bookId) }
    val dueUnitsFlow = remember(bookId) { viewModel.dueUnits(bookId) }
    val book by bookFlow.collectAsState()
    val chapters by chaptersFlow.collectAsState()
    val units by unitsFlow.collectAsState()
    val dueUnits by dueUnitsFlow.collectAsState()
    var showCreateChapter by remember { mutableStateOf(false) }
    var showCreateUnit by remember { mutableStateOf(false) }
    var showDeleteConfirm by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(book?.title ?: "书籍详情", maxLines = 1, overflow = TextOverflow.Ellipsis) },
                navigationIcon = { TextButton(onClick = { navController.popBackStack() }) { Text("返回") } },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { BookSummary(book, chapters, units) }
            item {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { showCreateChapter = true }) { Text("新建章节") }
                    Button(onClick = { showCreateUnit = true }) { Text("新建知识单元") }
                    Button(onClick = { navController.navigate("teach/${routeParam(bookId)}") }) { Text("AI 教学") }
                    Button(onClick = { navController.navigate("exam/${routeParam(bookId)}") }) { Text("考试模式") }
                    Button(onClick = { showDeleteConfirm = true }) { Text("删除书籍") }
                }
            }
            if (dueUnits.isNotEmpty()) {
                item { Text("待复习", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
                items(dueUnits, key = { "due-${it.id}" }) { unit ->
                    UnitCard(unit = unit, onClick = { navController.navigate("units/${routeParam(unit.id)}") })
                }
            }
            item { Text("全部知识单元", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
            items(units, key = { it.id }) { unit ->
                UnitCard(unit = unit, onClick = { navController.navigate("units/${routeParam(unit.id)}") })
            }
        }
    }
    if (showCreateChapter) {
        CreateTextDialog(
            title = "新建章节",
            firstLabel = "章节标题",
            onDismiss = { showCreateChapter = false },
            onConfirm = { title, _ ->
                viewModel.createChapter(bookId, title)
                showCreateChapter = false
            },
        )
    }
    if (showCreateUnit) {
        CreateTextDialog(
            title = "新建知识单元",
            firstLabel = "标题",
            secondLabel = "内容",
            onDismiss = { showCreateUnit = false },
            onConfirm = { title, content ->
                viewModel.createUnit(bookId, title, content)
                showCreateUnit = false
            },
        )
    }
    if (showDeleteConfirm) {
        ConfirmDialog(
            title = "删除书籍",
            message = "将删除这本书及其章节、知识单元、学习、复习、考试和教学记录。此操作不可撤销。",
            onDismiss = { showDeleteConfirm = false },
            onConfirm = {
                viewModel.deleteBook(bookId)
                showDeleteConfirm = false
                navController.popBackStack()
            },
        )
    }
}

@Composable
fun BookSummary(book: BookEntity?, chapters: List<ChapterEntity>, units: List<KnowledgeUnitEntity>) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(book?.title ?: "加载中", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("章节 ${chapters.size} · 知识单元 ${units.size}")
            if (!book?.readingMotivation.isNullOrBlank()) {
                Text(book?.readingMotivation.orEmpty())
            }
        }
    }
}

@Composable
fun UnitCard(unit: KnowledgeUnitEntity, onClick: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth().clickable(onClick = onClick)) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(unit.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(unit.summary ?: unit.content, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UnitDetailScreen(navController: NavHostController, viewModel: StudyViewModel, unitId: String) {
    val unitFlow = remember(unitId) { viewModel.unit(unitId) }
    val masteryFlow = remember(unitId) { viewModel.mastery(unitId) }
    val state by unitFlow.collectAsState()
    val mastery by masteryFlow.collectAsState()
    val unit = state.unit

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(unit?.title ?: "知识单元", maxLines = 1, overflow = TextOverflow.Ellipsis) },
                navigationIcon = { TextButton(onClick = { navController.popBackStack() }) { Text("返回") } },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (unit == null) {
                item { Text(if (state.isLoading) "正在加载知识单元..." else "未找到知识单元") }
            } else {
                item { UnitHeader(unit, mastery) }
                item { UnitActions(unit.id, viewModel) }
                item { TextSection("内容", unit.content) }
                if (!unit.summary.isNullOrBlank()) item { TextSection("摘要", unit.summary) }
                if (!unit.explanation.isNullOrBlank()) item { TextSection("AI 讲解", unit.explanation) }
                if (!unit.keyPoints.isNullOrBlank()) item { TextSection("要点", unit.keyPoints) }
                if (!unit.concepts.isNullOrBlank()) item { TextSection("概念", unit.concepts) }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TeachingScreen(navController: NavHostController, viewModel: StudyViewModel, bookId: String) {
    val state by viewModel.teachingState.collectAsState()
    val error by viewModel.teachingError.collectAsState()

    fun leaveTeaching() {
        viewModel.clearTeaching()
        navController.popBackStack()
    }

    LaunchedEffect(bookId) {
        viewModel.startTeaching(bookId)
    }

    BackHandler(onBack = ::leaveTeaching)

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("AI 教学") },
                navigationIcon = {
                    TextButton(onClick = ::leaveTeaching) { Text("返回") }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            val teachingState = state
            if (teachingState == null) {
                item {
                    LoadingOrError(
                        loadingText = "正在准备教学内容...",
                        error = error,
                        onBack = ::leaveTeaching,
                    )
                }
            } else {
                item { TeachingProgress(teachingState) }
                items(teachingState.messages, key = { it.id }) { message ->
                    TeachingMessageCard(message)
                }
                item { TeachingActions(teachingState, viewModel, navController) }
            }
        }
    }
}

@Composable
fun TeachingProgress(state: TeachingState) {
    val unit = state.units.getOrNull(state.session.currentUnitIndex ?: 0)
    val phaseTitle = TeachingRepository.TEACHING_PHASES
        .firstOrNull { it.key == state.session.currentPhase }
        ?.title
        ?: state.session.currentPhase.orEmpty()
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("当前单元：${teachingProgressUnitTitle(state.session.status, unit?.title)}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text("阶段：$phaseTitle")
            Text("所有阶段都需要手动点击继续，不会自动跳转。", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
fun TeachingMessageCard(message: TeachingMessageEntity) {
    val phaseTitle = TeachingRepository.TEACHING_PHASES
        .firstOrNull { it.key == message.phase }
        ?.title
        ?: message.phase
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(phaseTitle, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(message.content)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun TeachingActions(state: TeachingState, viewModel: StudyViewModel, navController: NavHostController) {
    var question by remember { mutableStateOf("") }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (state.session.status == "completed") {
            Button(onClick = {
                viewModel.clearTeaching()
                navController.popBackStack()
            }) { Text(teachingCompletedActionLabel()) }
        } else {
            OutlinedTextField(
                value = question,
                onValueChange = { question = it },
                label = { Text("向 AI 提问") },
                supportingText = {
                    if (!canSubmitTeachingQuestion(question)) Text("输入问题后才能提交。")
                },
                modifier = Modifier.fillMaxWidth(),
            )
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = {
                        viewModel.askTeachingQuestion(question)
                        question = ""
                    },
                    enabled = canSubmitTeachingQuestion(question),
                ) { Text("提交问题") }
                Button(onClick = viewModel::advanceTeaching) { Text("继续下一阶段") }
                Button(onClick = viewModel::finishTeaching) { Text("结束教学") }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ExamScreen(navController: NavHostController, viewModel: StudyViewModel, bookId: String) {
    val state by viewModel.examState.collectAsState()
    val error by viewModel.examError.collectAsState()
    val current = state?.questions?.getOrNull(state?.currentIndex ?: 0)
    var showFinishConfirm by remember { mutableStateOf(false) }

    fun leaveExam() {
        viewModel.clearExam()
        navController.popBackStack()
    }

    LaunchedEffect(bookId) {
        viewModel.startExam(bookId)
    }

    BackHandler(onBack = ::leaveExam)

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("考试模式") },
                navigationIcon = { TextButton(onClick = ::leaveExam) { Text("返回") } },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            val result = state?.result
            if (result != null) {
                item {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("考试完成", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                            Text("得分：${result.score.toInt()} / 100")
                            Text("题目数：${result.total}")
                            Button(onClick = ::leaveExam) { Text("返回书籍") }
                        }
                    }
                }
            } else if (current == null) {
                item {
                    LoadingOrError(
                        loadingText = "正在生成考试题目...",
                        error = error,
                        onBack = ::leaveExam,
                    )
                }
            } else {
                item {
                    ExamQuestionCard(
                        question = current,
                        index = (state?.currentIndex ?: 0) + 1,
                        total = state?.questions?.size ?: 0,
                        onAnswer = { viewModel.updateExamAnswer(current.id, it) },
                        onScore = { viewModel.updateExamScore(current.id, it) },
                    )
                }
                item {
                    val currentIndex = state?.currentIndex ?: 0
                    val total = state?.questions?.size ?: 0
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { viewModel.moveExam(-1) }, enabled = canMoveExamPrevious(currentIndex)) { Text("上一题") }
                        Button(onClick = { viewModel.moveExam(1) }, enabled = canMoveExamNext(currentIndex, total)) { Text("下一题") }
                        Button(onClick = { showFinishConfirm = true }) { Text("完成考试") }
                    }
                }
            }
        }
    }
    if (showFinishConfirm) {
        ConfirmDialog(
            title = "完成考试",
            message = "完成后会保存本次考试结果，并返回得分汇总。确认现在交卷吗？",
            onDismiss = { showFinishConfirm = false },
            onConfirm = {
                showFinishConfirm = false
                viewModel.finishExam()
            },
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun LoadingOrError(loadingText: String, error: String?, onBack: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(if (error == null) loadingText else "加载失败", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            if (error == null) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                Text("请稍候，正在处理当前任务。", style = MaterialTheme.typography.bodySmall)
            } else {
                Text(error)
                Button(onClick = onBack) { Text("返回") }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ExamQuestionCard(
    question: ExamQuestion,
    index: Int,
    total: Int,
    onAnswer: (String) -> Unit,
    onScore: (Int) -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("第 $index / $total 题", style = MaterialTheme.typography.labelLarge)
            Text(question.prompt, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            OutlinedTextField(
                value = question.userAnswer,
                onValueChange = onAnswer,
                label = { Text("你的答案") },
                modifier = Modifier.fillMaxWidth(),
            )
            Text("参考答案", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Text(question.referenceAnswer)
            Text("自评分", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(0, 40, 70, 100).forEach { score ->
                    Button(onClick = { onScore(score) }) { Text(score.toString()) }
                }
            }
            Text("当前分数：${question.selfScore}")
            Text("${examAnswerHint(question.userAnswer)} · ${examScoreHint(question.selfScore)}", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun UnitActions(unitId: String, viewModel: StudyViewModel) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("学习操作", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { viewModel.analyzeUnit(unitId) }) { Text("AI 分析") }
            }
            Text("复习反馈", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { viewModel.updateMastery(unitId, 0.2f) }) { Text("忘了") }
                Button(onClick = { viewModel.updateMastery(unitId, 0.45f) }) { Text("模糊") }
                Button(onClick = { viewModel.updateMastery(unitId, 0.7f) }) { Text("记得") }
                Button(onClick = { viewModel.updateMastery(unitId, 0.95f) }) { Text("熟练") }
            }
        }
    }
}

@Composable
fun UnitHeader(unit: KnowledgeUnitEntity, mastery: MasteryRecordEntity?) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(unit.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("难度 ${unit.difficultyLevel ?: "-"} · 重要度 ${unit.importanceScore ?: "-"}")
            if (mastery != null) {
                Text("掌握度 ${mastery.masteryLevel} · ${(mastery.masteryScore * 100).toInt()}%")
                LinearProgressIndicator(progress = { mastery.masteryScore.coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
                Text("下次复习：${mastery.nextReviewAt}")
            } else {
                Text("暂无掌握度记录")
            }
        }
    }
}

@Composable
fun TextSection(title: String, content: String) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(content)
        }
    }
}
