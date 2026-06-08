# Android UX Polish Round 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提升 Android 端考试、教学和加载过程中的状态反馈与误操作防护，不改变核心架构或数据模型。

**Architecture:** 本轮只修改 `MainActivity.kt` 中已有 Jetpack Compose UI 组件，复用现有 `StudyViewModel` 状态与方法。不新增数据库表、仓库、同步协议或导航结构；所有改动都是表现层的按钮可用性、确认弹窗、提示文案和加载进度。

**Tech Stack:** Android Kotlin、Jetpack Compose、Material 3、现有 ViewModel StateFlow。

---

## File Structure

- Modify: `android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt`
  - `TeachingActions`: 空问题时禁用“提交问题”，防止空请求。
  - `ExamScreen`: 完成考试前增加确认弹窗，并根据题目位置禁用上一题/下一题按钮。
  - `ExamQuestionCard`: 显示答案/评分完成度提示，让用户知道哪些题还未填写或未评分。
  - `LoadingOrError`: 加载态增加进度条，提高等待反馈。

---

### Task 1: 改善加载状态反馈

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt:732-744`

- [ ] **Step 1: 修改 LoadingOrError 加载态**

将 `LoadingOrError` 中的内容替换为：

```kotlin
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
```

- [ ] **Step 2: 运行格式/空白检查**

Run:
```bash
git diff --check -- android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt
```
Expected: no output and exit code 0.

---

### Task 2: 改善教学提问误操作防护

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt:646-672`

- [ ] **Step 1: 修改 TeachingActions 空问题状态**

在 `TeachingActions` 的 `else` 分支中，将提交按钮区域替换为：

```kotlin
OutlinedTextField(
    value = question,
    onValueChange = { question = it },
    label = { Text("向 AI 提问") },
    supportingText = {
        if (question.isBlank()) Text("输入问题后才能提交。")
    },
    modifier = Modifier.fillMaxWidth(),
)
FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
    Button(
        onClick = {
            viewModel.askTeachingQuestion(question)
            question = ""
        },
        enabled = question.isNotBlank(),
    ) { Text("提交问题") }
    Button(onClick = viewModel::advanceTeaching) { Text("继续下一阶段") }
    Button(onClick = viewModel::finishTeaching) { Text("结束教学") }
}
```

- [ ] **Step 2: 运行格式/空白检查**

Run:
```bash
git diff --check -- android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt
```
Expected: no output and exit code 0.

---

### Task 3: 改善考试页完成前确认与导航状态

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt:675-730`

- [ ] **Step 1: 增加完成确认状态**

在 `ExamScreen` 中 `current` 后面增加：

```kotlin
var showFinishConfirm by remember { mutableStateOf(false) }
```

- [ ] **Step 2: 修改考试操作按钮**

将考试答题分支中的 `FlowRow` 替换为：

```kotlin
val currentIndex = state?.currentIndex ?: 0
val total = state?.questions?.size ?: 0
FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
    Button(onClick = { viewModel.moveExam(-1) }, enabled = currentIndex > 0) { Text("上一题") }
    Button(onClick = { viewModel.moveExam(1) }, enabled = currentIndex < total - 1) { Text("下一题") }
    Button(onClick = { showFinishConfirm = true }) { Text("完成考试") }
}
```

- [ ] **Step 3: 增加确认弹窗**

在 `Scaffold` 之后、`ExamScreen` 结束前增加：

```kotlin
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
```

- [ ] **Step 4: 运行格式/空白检查**

Run:
```bash
git diff --check -- android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt
```
Expected: no output and exit code 0.

---

### Task 4: 改善考试题目完成度提示

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt:746-776`

- [ ] **Step 1: 修改 ExamQuestionCard 提示文案**

在 `ExamQuestionCard` 的 `Column` 内，保持原有题干、输入框、参考答案和评分按钮，在当前分数下方增加：

```kotlin
val answerHint = if (question.userAnswer.isBlank()) "尚未填写答案" else "已填写答案"
val scoreHint = if (question.selfScore <= 0) "尚未自评分" else "已自评分"
Text("$answerHint · $scoreHint", style = MaterialTheme.typography.bodySmall)
```

完整函数应保持签名不变：

```kotlin
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
            val answerHint = if (question.userAnswer.isBlank()) "尚未填写答案" else "已填写答案"
            val scoreHint = if (question.selfScore <= 0) "尚未自评分" else "已自评分"
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
            Text("$answerHint · $scoreHint", style = MaterialTheme.typography.bodySmall)
        }
    }
}
```

- [ ] **Step 2: 运行格式/空白检查**

Run:
```bash
git diff --check -- android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt
```
Expected: no output and exit code 0.

---

### Task 5: 构建验证

**Files:**
- Verify: `android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt`

- [ ] **Step 1: 运行 Android 构建**

Run:
```bash
cd android && ./gradlew :app:assembleDebug
```
Expected: `BUILD SUCCESSFUL`.

- [ ] **Step 2: 如构建失败，记录原始错误并只修复本轮改动导致的问题**

如果错误指向本轮新增代码，例如 Compose 参数或 Kotlin 语法错误，回到对应任务修复并重跑构建。

- [ ] **Step 3: 不提交代码**

本会话不执行 `git commit`，除非用户明确要求。
