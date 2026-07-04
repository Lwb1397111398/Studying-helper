package com.studyinghelper.mobile
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.TopAppBarDefaults
import com.studyinghelper.mobile.ui.theme.StudyingHelperTheme
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.studyinghelper.mobile.data.db.BookEntity
import com.studyinghelper.mobile.data.db.ChapterEntity
import com.studyinghelper.mobile.data.db.KnowledgeUnitEntity
import com.studyinghelper.mobile.data.db.MasteryRecordEntity
import com.studyinghelper.mobile.data.repository.Concept
import com.studyinghelper.mobile.data.repository.KeyPoint
import com.studyinghelper.mobile.ui.components.*
import com.studyinghelper.mobile.ui.parseConcepts
import com.studyinghelper.mobile.ui.parseKeyPoints
import com.studyinghelper.mobile.ui.theme.*
import com.studyinghelper.mobile.ui.StudyViewModel
import kotlinx.coroutines.launch

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

    StudyingHelperTheme {
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
                    composable("design/{bookId}") { backStackEntry ->
                        TeachingDesignScreen(
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReportScreen(navController: NavHostController, viewModel: StudyViewModel) {
    val report by viewModel.report.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.refreshReport()
    }

    Scaffold(
        topBar = {
            Column {
                TopAppBar(
                    title = { Text("学习报告") },
                    navigationIcon = { TextButton(onClick = { navController.popBackStack() }) { Text("返回") } },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = PaperWhite)
                )
                BookmarkRibbon()
            }
        },
    ) { padding ->
        Column(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            val data = report
            if (data == null) {
                Text("正在统计学习数据...")
            } else {
                ReportCard("📚 书籍", data.books.toString())
                ReportCard("📖 知识单元", "${data.learnedUnits} / ${data.units} 已学习")
                ReportCard("🔄 复习记录", data.reviewSessions.toString())
                ReportCard("📝 考试次数", data.examSessions.toString())
                ReportCard("⏱️ 累计学习时长", "${data.totalMinutes} 分钟")
            }
        }
    }
}

@Composable
fun ReportCard(label: String, value: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                label,
                style = MaterialTheme.typography.bodyMedium,
                color = MediumBrown
            )
            Text(
                value,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = BookmarkGreen
            )
        }
    }
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
            Column {
                TopAppBar(
                    title = { Text(book?.title ?: "书籍详情", maxLines = 1, overflow = TextOverflow.Ellipsis) },
                    navigationIcon = { TextButton(onClick = { navController.popBackStack() }) { Text("返回") } },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = PaperWhite)
                )
                BookmarkRibbon()
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { BookSummary(book, chapters, units) }
            item {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    PaperButton(onClick = { showCreateChapter = true }, backgroundColor = CoffeeOrange) { Text("新建章节") }
                    PaperButton(onClick = { showCreateUnit = true }, backgroundColor = CoffeeOrange) { Text("新建知识单元") }
                    GhostButton(onClick = { navController.navigate("design/${routeParam(bookId)}") }) { Text("教学设计") }
                    GhostButton(onClick = { navController.navigate("exam/${routeParam(bookId)}") }) { Text("考试模式") }
                    GhostButton(onClick = { showDeleteConfirm = true }) { Text("删除书籍") }
                }
            }
            if (dueUnits.isNotEmpty()) {
                item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("📝", style = MaterialTheme.typography.titleMedium)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("待复习", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = InkBrown)
                    }
                }
                items(dueUnits, key = { "due-${it.id}" }) { unit ->
                    UnitCard(unit = unit, onClick = { navController.navigate("units/${routeParam(unit.id)}") })
                }
            }
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("📚", style = MaterialTheme.typography.titleMedium)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("全部知识单元", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = InkBrown)
                }
            }
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
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                book?.title ?: "加载中",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = InkBrown
            )
            Text(
                "章节 ${chapters.size} · 知识单元 ${units.size}",
                style = MaterialTheme.typography.bodyMedium,
                color = MediumBrown
            )
            if (!book?.readingMotivation.isNullOrBlank()) {
                Text(
                    book?.readingMotivation.orEmpty(),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MediumBrown
                )
            }
        }
    }
}

@Composable
fun UnitCard(unit: KnowledgeUnitEntity, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                unit.title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = InkBrown
            )
            Text(
                unit.summary ?: unit.content,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                style = MaterialTheme.typography.bodyMedium,
                color = MediumBrown
            )
        }
    }
}

@Composable
fun KeyPointsSection(keyPoints: List<KeyPoint>) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("🔑", style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    "要点",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = InkBrown
                )
            }
            keyPoints.forEachIndexed { index, kp ->
                KeyPointCard(
                    number = index + 1,
                    title = kp.title,
                    explanation = kp.explanation,
                    examples = kp.examples
                )
            }
        }
    }
}

@Composable
fun ConceptsSection(concepts: List<Concept>) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("💡", style = MaterialTheme.typography.titleMedium)
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    "核心概念",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = InkBrown
                )
            }
            concepts.forEach { concept ->
                ConceptCard(
                    name = concept.name,
                    definition = concept.definition,
                    examples = concept.examples
                )
            }
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
            Column {
                TopAppBar(
                    title = { Text(unit?.title ?: "知识单元", maxLines = 1, overflow = TextOverflow.Ellipsis) },
                    navigationIcon = { TextButton(onClick = { navController.popBackStack() }) { Text("返回") } },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = PaperWhite
                    )
                )
                BookmarkRibbon()
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
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
                if (!unit.keyPoints.isNullOrBlank()) {
                    val keyPoints = parseKeyPoints(unit.keyPoints)
                    if (keyPoints.isNotEmpty()) item { KeyPointsSection(keyPoints) }
                }
                if (!unit.concepts.isNullOrBlank()) {
                    val concepts = parseConcepts(unit.concepts)
                    if (concepts.isNotEmpty()) item { ConceptsSection(concepts) }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun UnitActions(unitId: String, viewModel: StudyViewModel) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("学习操作", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = InkBrown)
            PaperButton(onClick = { viewModel.analyzeUnit(unitId) }, backgroundColor = BookmarkGreen) { Text("✨ AI 分析") }
            Text("复习反馈", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold, color = InkBrown)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                GhostButton(onClick = { viewModel.updateMastery(unitId, 0.2f) }) { Text("忘了") }
                GhostButton(onClick = { viewModel.updateMastery(unitId, 0.45f) }) { Text("模糊") }
                GhostButton(onClick = { viewModel.updateMastery(unitId, 0.7f) }) { Text("记得") }
                GhostButton(onClick = { viewModel.updateMastery(unitId, 0.95f) }) { Text("熟练") }
            }
        }
    }
}

@Composable
fun UnitHeader(unit: KnowledgeUnitEntity, mastery: MasteryRecordEntity?) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                unit.title,
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = InkBrown
            )
            Text(
                "难度 ${unit.difficultyLevel ?: "-"} · 重要度 ${unit.importanceScore ?: "-"}",
                style = MaterialTheme.typography.bodyMedium,
                color = MediumBrown
            )
            if (mastery != null) {
                Text(
                    "掌握度 ${mastery.masteryLevel} · ${(mastery.masteryScore * 100).toInt()}%",
                    style = MaterialTheme.typography.bodyMedium,
                    color = BookmarkGreen
                )
                InkProgressBar(progress = mastery.masteryScore.coerceIn(0f, 1f))
                Text(
                    "下次复习：${mastery.nextReviewAt}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MediumBrown
                )
            } else {
                Text(
                    "暂无掌握度记录",
                    style = MaterialTheme.typography.bodyMedium,
                    color = PaleBrown
                )
            }
        }
    }
}

@Composable
fun TextSection(title: String, content: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = InkBrown
            )
            Text(
                content,
                style = MaterialTheme.typography.bodyMedium,
                color = MediumBrown
            )
        }
    }
}
