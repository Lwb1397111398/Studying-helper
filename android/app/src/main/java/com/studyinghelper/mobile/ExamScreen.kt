package com.studyinghelper.mobile

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.studyinghelper.mobile.data.repository.ExamQuestion
import com.studyinghelper.mobile.ui.StudyViewModel
import com.studyinghelper.mobile.ui.components.BookmarkRibbon
import com.studyinghelper.mobile.ui.components.GhostButton
import com.studyinghelper.mobile.ui.components.PaperButton
import com.studyinghelper.mobile.ui.theme.Amber
import com.studyinghelper.mobile.ui.theme.BookmarkGreen
import com.studyinghelper.mobile.ui.theme.CardBackground
import com.studyinghelper.mobile.ui.theme.CoffeeOrange
import com.studyinghelper.mobile.ui.theme.InkBrown
import com.studyinghelper.mobile.ui.theme.LightBrown
import com.studyinghelper.mobile.ui.theme.MediumBrown
import com.studyinghelper.mobile.ui.theme.PaleBrown
import com.studyinghelper.mobile.ui.theme.PaperWhite

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
            Column {
                TopAppBar(
                    title = { Text("考试模式") },
                    navigationIcon = { TextButton(onClick = ::leaveExam) { Text("返回") } },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = PaperWhite)
                )
                BookmarkRibbon(color = Amber)
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            val result = state?.result
            if (result != null) {
                item {
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = CardDefaults.cardColors(containerColor = CardBackground),
                        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                    ) {
                        Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Text("🎉 考试完成", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = InkBrown)
                            Text("得分：${result.score.toInt()} / 100", style = MaterialTheme.typography.titleMedium, color = BookmarkGreen)
                            Text("题目数：${result.total}", style = MaterialTheme.typography.bodyMedium, color = MediumBrown)
                            PaperButton(onClick = ::leaveExam, backgroundColor = BookmarkGreen) { Text("返回书籍") }
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
                        GhostButton(onClick = { viewModel.moveExam(-1) }, enabled = canMoveExamPrevious(currentIndex)) { Text("上一题") }
                        GhostButton(onClick = { viewModel.moveExam(1) }, enabled = canMoveExamNext(currentIndex, total)) { Text("下一题") }
                        PaperButton(onClick = { showFinishConfirm = true }, backgroundColor = CoffeeOrange) { Text("完成考试") }
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
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(
                "第 $index / $total 题",
                style = MaterialTheme.typography.labelLarge,
                color = BookmarkGreen
            )
            Text(
                question.prompt,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = InkBrown
            )
            OutlinedTextField(
                value = question.userAnswer,
                onValueChange = onAnswer,
                label = { Text("你的答案") },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = BookmarkGreen,
                    unfocusedBorderColor = LightBrown,
                    focusedLabelColor = BookmarkGreen,
                    cursorColor = BookmarkGreen,
                )
            )
            Text(
                "参考答案",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = CoffeeOrange
            )
            Text(question.referenceAnswer, style = MaterialTheme.typography.bodyMedium, color = MediumBrown)
            Text(
                "自评分",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = CoffeeOrange
            )
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(0, 40, 70, 100).forEach { score ->
                    val isSelected = question.selfScore == score
                    if (isSelected) {
                        PaperButton(onClick = { onScore(score) }, backgroundColor = BookmarkGreen, modifier = Modifier.height(36.dp)) { Text(score.toString()) }
                    } else {
                        GhostButton(onClick = { onScore(score) }, modifier = Modifier.height(36.dp)) { Text(score.toString()) }
                    }
                }
            }
            Text("当前分数：${question.selfScore}", style = MaterialTheme.typography.bodyMedium, color = InkBrown)
            Text(
                "${examAnswerHint(question.userAnswer)} · ${examScoreHint(question.selfScore)}",
                style = MaterialTheme.typography.bodySmall,
                color = PaleBrown
            )
        }
    }
}
