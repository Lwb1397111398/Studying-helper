package com.studyinghelper.mobile

import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
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
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import com.studyinghelper.mobile.data.db.LearnerIntentProfileEntity
import com.studyinghelper.mobile.data.db.ModuleMicroPlanEntity
import com.studyinghelper.mobile.ui.StudyViewModel
import com.studyinghelper.mobile.ui.components.BookmarkRibbon
import com.studyinghelper.mobile.ui.components.GhostButton
import com.studyinghelper.mobile.ui.components.NumberCircle
import com.studyinghelper.mobile.ui.components.PaperButton
import com.studyinghelper.mobile.ui.theme.BookmarkGreen
import com.studyinghelper.mobile.ui.theme.CardBackground
import com.studyinghelper.mobile.ui.theme.CoffeeOrange
import com.studyinghelper.mobile.ui.theme.InkBrown
import com.studyinghelper.mobile.ui.theme.MediumBrown
import com.studyinghelper.mobile.ui.theme.PaleBrown
import com.studyinghelper.mobile.ui.theme.PaperWhite
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray

private fun teachingRouteParam(value: String): String = Uri.encode(value)

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun TeachingDesignScreen(navController: NavHostController, viewModel: StudyViewModel, bookId: String) {
    val state by viewModel.aidDesignState.collectAsState()
    var identity by remember { mutableStateOf("unknown") }
    var goal by remember { mutableStateOf("apply_understand") }
    var pref by remember { mutableStateOf("rigorous_system") }
    var tolerance by remember { mutableStateOf("moderate") }
    var minutes by remember { mutableStateOf("30") }

    LaunchedEffect(bookId) {
        viewModel.loadAidDesign(bookId)
    }

    LaunchedEffect(state.profile?.id, state.profile?.updatedAt) {
        val profile = state.profile ?: return@LaunchedEffect
        identity = profile.identityBackground
        goal = profile.goalDepth
        pref = profile.cognitivePref
        tolerance = profile.restructureTolerance
        minutes = profile.timeBudgetMinutes?.toString() ?: ""
    }

    Scaffold(
        topBar = {
            Column {
                TopAppBar(
                    title = { Text("教学设计") },
                    navigationIcon = { TextButton(onClick = { navController.popBackStack() }) { Text("返回") } },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = PaperWhite)
                )
                BookmarkRibbon(color = BookmarkGreen)
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (state.error != null) {
                item {
                    Card(modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = CardBackground)) {
                        Text(state.error.orEmpty(), modifier = Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error)
                    }
                }
            }
            if (state.isLoading) {
                item {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }
            }
            item {
                ProfileFormCard(
                    profile = state.profile,
                    identity = identity,
                    goal = goal,
                    pref = pref,
                    tolerance = tolerance,
                    minutes = minutes,
                    onIdentity = { identity = it },
                    onGoal = { goal = it },
                    onPref = { pref = it },
                    onTolerance = { tolerance = it },
                    onMinutes = { minutes = it },
                    onInfer = { viewModel.inferAidProfile(bookId) },
                    onSave = {
                        viewModel.saveAidProfile(
                            bookId = bookId,
                            identityBackground = identity,
                            goalDepth = goal,
                            cognitivePref = pref,
                            restructureTolerance = tolerance,
                            timeBudgetMinutes = minutes.toIntOrNull(),
                        )
                    },
                    onConfirm = { viewModel.confirmAidProfile(bookId) },
                )
            }
            item {
                DesignActionCard(
                    designStatus = state.design?.status,
                    planCount = state.plans.size,
                    canGenerate = state.profile?.status == "confirmed",
                    onGenerate = { viewModel.generateAidDesign(bookId) },
                    onStart = {
                        viewModel.activateAidDesign(bookId)
                        navController.navigate("teach/${teachingRouteParam(bookId)}")
                    },
                )
            }
            if (state.plans.isNotEmpty()) {
                item {
                    Text("模块预览", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = InkBrown)
                }
                items(state.plans, key = { it.id }) { plan ->
                    ModulePlanCard(plan)
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ProfileFormCard(
    profile: LearnerIntentProfileEntity?,
    identity: String,
    goal: String,
    pref: String,
    tolerance: String,
    minutes: String,
    onIdentity: (String) -> Unit,
    onGoal: (String) -> Unit,
    onPref: (String) -> Unit,
    onTolerance: (String) -> Unit,
    onMinutes: (String) -> Unit,
    onInfer: () -> Unit,
    onSave: () -> Unit,
    onConfirm: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                Text("学习者画像", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = InkBrown)
                Text(profileStatusLabel(profile?.status), style = MaterialTheme.typography.bodySmall, color = BookmarkGreen)
            }
            OptionGroup("背景", identityOptions(), identity, onIdentity)
            OptionGroup("目标", goalOptions(), goal, onGoal)
            OptionGroup("认知偏好", prefOptions(), pref, onPref)
            OptionGroup("重组强度", toleranceOptions(), tolerance, onTolerance)
            OutlinedTextField(
                value = minutes,
                onValueChange = onMinutes,
                label = { Text("时间预算（分钟，可空）") },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
            )
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                GhostButton(onClick = onInfer) { Text("AI 推断") }
                GhostButton(onClick = onSave) { Text("保存画像") }
                PaperButton(onClick = onConfirm, backgroundColor = BookmarkGreen) { Text("确认画像") }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun OptionGroup(
    title: String,
    options: List<Pair<String, String>>,
    selected: String,
    onSelected: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(title, style = MaterialTheme.typography.titleSmall, color = InkBrown, fontWeight = FontWeight.SemiBold)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            options.forEach { (value, label) ->
                if (value == selected) {
                    PaperButton(onClick = { onSelected(value) }, backgroundColor = BookmarkGreen, modifier = Modifier.height(36.dp)) {
                        Text(label)
                    }
                } else {
                    GhostButton(onClick = { onSelected(value) }, modifier = Modifier.height(36.dp)) {
                        Text(label)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun DesignActionCard(
    designStatus: String?,
    planCount: Int,
    canGenerate: Boolean,
    onGenerate: () -> Unit,
    onStart: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("教学编排", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = InkBrown)
            Text("状态：${designStatus ?: "未生成"} · 模块：$planCount", style = MaterialTheme.typography.bodyMedium, color = MediumBrown)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                PaperButton(onClick = onGenerate, enabled = canGenerate, backgroundColor = CoffeeOrange) { Text("生成教学设计") }
                PaperButton(onClick = onStart, enabled = planCount > 0, backgroundColor = BookmarkGreen) { Text("开始教学") }
            }
            if (!canGenerate) {
                Text("先确认画像，再生成教学设计。", style = MaterialTheme.typography.bodySmall, color = PaleBrown)
            }
        }
    }
}

@Composable
fun ModulePlanCard(plan: ModuleMicroPlanEntity) {
    val unitCount = remember(plan.orderedUnitIdsJson) {
        runCatching { Json.parseToJsonElement(plan.orderedUnitIdsJson).jsonArray.size }.getOrDefault(0)
    }
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = CardBackground),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                NumberCircle(number = plan.moduleIndex + 1, backgroundColor = CoffeeOrange)
                Spacer(modifier = Modifier.width(10.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(plan.moduleTitle.ifBlank { "模块 ${plan.moduleIndex + 1}" }, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = InkBrown)
                    Text("$unitCount 个知识单元 · ${plan.moduleStatus}", style = MaterialTheme.typography.bodySmall, color = MediumBrown)
                }
            }
            if (!plan.moduleIntro.isNullOrBlank()) {
                Text(plan.moduleIntro, style = MaterialTheme.typography.bodyMedium, color = MediumBrown)
            }
        }
    }
}
