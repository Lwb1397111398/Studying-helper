package com.studyinghelper.mobile

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
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
import com.studyinghelper.mobile.data.db.TeachingMessageEntity
import com.studyinghelper.mobile.data.repository.TeachingRepository
import com.studyinghelper.mobile.data.repository.TeachingState
import com.studyinghelper.mobile.ui.StudyViewModel
import com.studyinghelper.mobile.ui.components.BookmarkRibbon
import com.studyinghelper.mobile.ui.components.GhostButton
import com.studyinghelper.mobile.ui.components.PaperButton
import com.studyinghelper.mobile.ui.theme.BookmarkGreen
import com.studyinghelper.mobile.ui.theme.CardBackground
import com.studyinghelper.mobile.ui.theme.CoffeeOrange
import com.studyinghelper.mobile.ui.theme.InkBrown
import com.studyinghelper.mobile.ui.theme.LightBrown
import com.studyinghelper.mobile.ui.theme.MediumBrown
import com.studyinghelper.mobile.ui.theme.PaleBrown
import com.studyinghelper.mobile.ui.theme.PaperWhite

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
            Column {
                TopAppBar(
                    title = { Text("AI 教学") },
                    navigationIcon = {
                        TextButton(onClick = ::leaveTeaching) { Text("返回") }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = PaperWhite)
                )
                BookmarkRibbon(color = CoffeeOrange)
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
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
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                "当前单元：${teachingProgressUnitTitle(state.session.status, unit?.title)}",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = InkBrown
            )
            Text("阶段：$phaseTitle", style = MaterialTheme.typography.bodyMedium, color = CoffeeOrange)
            Text(
                "所有阶段都需要手动点击继续，不会自动跳转。",
                style = MaterialTheme.typography.bodySmall,
                color = PaleBrown
            )
        }
    }
}

@Composable
fun TeachingMessageCard(message: TeachingMessageEntity) {
    val phaseTitle = TeachingRepository.TEACHING_PHASES
        .firstOrNull { it.key == message.phase }
        ?.title
        ?: message.phase
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                phaseTitle,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = BookmarkGreen
            )
            Text(message.content, style = MaterialTheme.typography.bodyMedium, color = MediumBrown)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun TeachingActions(state: TeachingState, viewModel: StudyViewModel, navController: NavHostController) {
    var question by remember { mutableStateOf("") }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (state.session.status == "completed") {
            PaperButton(onClick = {
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
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = BookmarkGreen,
                    unfocusedBorderColor = LightBrown,
                    focusedLabelColor = BookmarkGreen,
                    cursorColor = BookmarkGreen,
                )
            )
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                PaperButton(
                    onClick = {
                        viewModel.askTeachingQuestion(question)
                        question = ""
                    },
                    enabled = canSubmitTeachingQuestion(question),
                    backgroundColor = BookmarkGreen
                ) { Text("提交问题") }
                GhostButton(onClick = viewModel::advanceTeaching) { Text("继续下一阶段") }
                GhostButton(onClick = viewModel::finishTeaching) { Text("结束教学") }
            }
        }
    }
}
