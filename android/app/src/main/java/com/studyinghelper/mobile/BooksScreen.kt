package com.studyinghelper.mobile

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.studyinghelper.mobile.data.db.BookEntity
import com.studyinghelper.mobile.data.repository.AiConfig
import com.studyinghelper.mobile.data.sync.SyncPreview
import com.studyinghelper.mobile.ui.StudyViewModel
import com.studyinghelper.mobile.ui.components.BookCardWithSpine
import com.studyinghelper.mobile.ui.components.BookmarkRibbon
import com.studyinghelper.mobile.ui.components.GhostButton
import com.studyinghelper.mobile.ui.components.InkProgressBar
import com.studyinghelper.mobile.ui.components.PaperButton
import com.studyinghelper.mobile.ui.theme.BookmarkGreen
import com.studyinghelper.mobile.ui.theme.CardBackground
import com.studyinghelper.mobile.ui.theme.CoffeeOrange
import com.studyinghelper.mobile.ui.theme.InkBrown
import com.studyinghelper.mobile.ui.theme.MediumBrown
import com.studyinghelper.mobile.ui.theme.PaperWhite

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
        topBar = {
            Column {
                TopAppBar(
                    title = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                "📚",
                                style = MaterialTheme.typography.headlineSmall
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                "Studying Helper",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = PaperWhite
                    )
                )
                BookmarkRibbon()
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { Spacer(modifier = Modifier.height(4.dp)) }
            item { WelcomeSummary(books) }
            item {
                ActionGroup("创建与导入") {
                    PaperButton(onClick = { showCreateBook = true }, backgroundColor = CoffeeOrange) { Text("📕 新建书籍") }
                    GhostButton(onClick = { txtImportLauncher.launch(arrayOf("text/plain", "text/*")) }) { Text("📄 导入 TXT") }
                    GhostButton(onClick = { epubImportLauncher.launch(arrayOf("application/epub+zip", "application/octet-stream")) }) { Text("📖 导入 EPUB") }
                    GhostButton(onClick = { pdfImportLauncher.launch(arrayOf("application/pdf", "application/octet-stream")) }) { Text("📑 导入 PDF") }
                }
            }
            item {
                ActionGroup("同步与设置") {
                    GhostButton(onClick = { importLauncher.launch(arrayOf("application/json")) }) { Text("📥 导入同步包") }
                    GhostButton(onClick = { exportLauncher.launch("studying-helper-android-sync.json") }) { Text("📤 导出同步包") }
                    GhostButton(onClick = { showAiSettings = true }) { Text("🤖 AI 设置") }
                    GhostButton(onClick = { navController.navigate("report") }) { Text("📊 学习报告") }
                }
            }
            if (books.isEmpty()) {
                item { EmptyState() }
            } else {
                item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("📚", style = MaterialTheme.typography.titleMedium)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("我的书籍", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = InkBrown)
                    }
                }
                items(books, key = { it.id }) { book ->
                    val total = (book.totalUnits ?: 0).coerceAtLeast(1)
                    val learned = (book.learnedUnits ?: 0).coerceAtMost(total)
                    val progress = learned.toFloat() / total
                    BookCardWithSpine(
                        title = book.title,
                        subtitle = "章节 ${book.totalChapters ?: 0} · 知识单元 ${book.totalUnits ?: 0} · 已学习 ${book.learnedUnits ?: 0}",
                        progress = progress,
                        onClick = { navController.navigate("books/${routeParam(book.id)}") }
                    )
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
fun WelcomeSummary(books: List<BookEntity>) {
    val totalUnits = books.sumOf { it.totalUnits ?: 0 }
    val learnedUnits = books.sumOf { it.learnedUnits ?: 0 }
    val progress = if (totalUnits > 0) learnedUnits.toFloat() / totalUnits else 0f

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = BookmarkGreen.copy(alpha = 0.1f))
    ) {
        Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(
                "今日学习从这里开始 ✨",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = BookmarkGreen
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    "${books.size} 本书",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MediumBrown
                )
                Text(
                    "$learnedUnits / $totalUnits 单元已学",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = BookmarkGreen
                )
            }
            InkProgressBar(progress = progress)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ActionGroup(title: String, content: @Composable FlowRowScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .width(4.dp)
                        .height(16.dp)
                        .background(
                            brush = Brush.verticalGradient(
                                colors = listOf(BookmarkGreen, BookmarkGreen.copy(alpha = 0.6f))
                            ),
                            shape = RoundedCornerShape(2.dp)
                        )
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    title,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = InkBrown
                )
            }
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
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
                Text("书籍：${preview.books} 本，章节：${preview.chapters} 个，知识单元：${preview.units} 个")
                Text("掌握记录：${preview.masteryRecords} 条")
                Text("复习/考试：${preview.reviewSessions} 条，教学会话：${preview.teachingSessions} 个，教学消息：${preview.teachingMessages} 条")
                if (preview.learnerIntentProfiles > 0 || preview.teachingDesigns > 0 || preview.moduleMicroPlans > 0) {
                    Text("AID：画像 ${preview.learnerIntentProfiles} 个，设计 ${preview.teachingDesigns} 个，模块 ${preview.moduleMicroPlans} 个")
                }
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

@Composable
fun EmptyState() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(
            modifier = Modifier.padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text("📭", style = MaterialTheme.typography.displayMedium)
            Text(
                "还没有学习数据",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = InkBrown
            )
            Text(
                "你可以直接在手机端新建学习内容，\n也可以导入电脑端或其他手机端导出的同步包。",
                style = MaterialTheme.typography.bodyMedium,
                color = MediumBrown,
                textAlign = TextAlign.Center
            )
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
fun BookCard(book: BookEntity, onClick: () -> Unit) {
    val total = (book.totalUnits ?: 0).coerceAtLeast(1)
    val learned = (book.learnedUnits ?: 0).coerceAtMost(total)
    val progress = learned.toFloat() / total

    BookCardWithSpine(
        title = book.title,
        subtitle = "章节 ${book.totalChapters ?: 0} · 知识单元 ${book.totalUnits ?: 0} · 已学习 ${book.learnedUnits ?: 0}",
        progress = progress,
        onClick = onClick
    )
}
