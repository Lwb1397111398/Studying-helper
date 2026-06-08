# Android Exam Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Android 端具备离线考试模式：从书籍知识单元生成题目、答题、评分、记录结果，并通过现有同步包回传电脑端。

**Architecture:** 第一版不新增数据库表，复用已有 `review_sessions` 表保存考试记录，`review_type="exam"`，`questions_json` 保存题目、答案和用户作答。新增 `ExamRepository` 负责题目生成、评分和保存；`StudyViewModel` 负责启动考试、提交答案、完成考试；`MainActivity` 增加考试页面路由和入口。

**Tech Stack:** Android Kotlin、Room、kotlinx.serialization、Jetpack Compose、现有 SyncPackage/ReviewSessionEntity。

---

### Task 1: 新增考试业务模型与仓库

**Files:**
- Create: `android/app/src/main/java/com/studyinghelper/mobile/data/repository/ExamRepository.kt`

- [ ] **Step 1: 定义序列化题目模型**

```kotlin
@Serializable
data class ExamQuestion(
    val id: String,
    val unitId: String,
    val prompt: String,
    val referenceAnswer: String,
    val userAnswer: String = "",
    val selfScore: Int = 0,
)
```

- [ ] **Step 2: 实现 generateExam(bookId, limit)**

从 `dao.getUnits(bookId)` 读取知识单元，优先选择低掌握度/未掌握单元，生成自由回忆题。

- [ ] **Step 3: 实现 saveExamResult(bookId, questions)**

计算平均分，保存 `ReviewSessionEntity(review_type="exam")`，并更新 `daily_stats.tests_taken` 和 `avg_test_score`。

### Task 2: DAO 支持按书籍读取单元和统计累加

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/data/db/StudyDao.kt`

- [ ] **Step 1: 新增 getUnits(bookId)**

```kotlin
@Query("SELECT * FROM knowledge_units WHERE book_id = :bookId ORDER BY order_index")
suspend fun getUnits(bookId: String): List<KnowledgeUnitEntity>
```

### Task 3: ViewModel 接入考试状态

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/ui/StudyViewModel.kt`

- [ ] **Step 1: 初始化 ExamRepository**

- [ ] **Step 2: 新增 examState: StateFlow<ExamState?>**

- [ ] **Step 3: 新增 startExam(bookId)、answerExamQuestion、finishExam**

考试状态只存在内存中，完成后保存到 review_sessions。

### Task 4: Compose 接入考试页面

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt`

- [ ] **Step 1: 增加 `exam/{bookId}` 路由**

- [ ] **Step 2: 书籍详情页增加“考试模式”按钮**

- [ ] **Step 3: 新增 ExamScreen**

展示题目、输入答案、自评分按钮、完成考试按钮。

### Task 5: 审查与验证

**Files:**
- Modify: `docs/mobile/roadmap.md`

- [ ] **Step 1: 静态检查**

Run:
```bash
git diff --check -- android/app/src/main/java/com/studyinghelper/mobile docs/mobile/roadmap.md
```

- [ ] **Step 2: Android 构建尝试**

当前 shell 预期因缺 Java 失败；Android Studio/JDK 环境需补测。

- [ ] **Step 3: 后端/前端回归**

Run:
```bash
cd backend && PYTHONPATH=. pytest app/modules/sync/tests
npm run build --prefix frontend
```

- [ ] **Step 4: 调用代码审查技能**

使用 `code-review --effort high` 审查并修复必须项。
