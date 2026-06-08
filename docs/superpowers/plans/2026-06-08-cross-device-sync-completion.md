# Cross-Device Sync Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成电脑端 Web/FastAPI 与 Android APP 的离线同步闭环，让两端都能独立学习并通过 JSON 同步包双向转移进度。

**Architecture:** 后端 `backend/app/modules/sync/` 继续作为同步契约权威实现；Web `SyncCenter` 只负责调用同步 API 和展示导入/覆盖影响；Android `SyncDtos.kt` 与 `SyncRepository` 跟随后端契约，Room 作为本地离线数据源。先增强同步结果可观测性和跨端契约测试，再补 Android 导入/导出反馈，最后跑后端、Web、Android 验证与代码审查。

**Tech Stack:** FastAPI、Pydantic v2、SQLAlchemy async、React 18、TypeScript、Vite、Android Kotlin、Room、kotlinx.serialization、Jetpack Compose。

---

## File Structure

- Modify: `backend/app/modules/sync/schemas.py`
  - 负责同步包、预览结果、导入结果的数据契约。
- Modify: `backend/app/modules/sync/service.py`
  - 负责导出、预览、覆盖式导入和导入统计。
- Modify: `backend/app/modules/sync/tests/test_sync_service.py`
  - 覆盖 Web 包与 Android 包的预览/导入统计。
- Modify: `frontend/src/api/sync.ts`
  - 让前端类型与后端导入/预览统计对齐。
- Modify: `frontend/src/pages/SyncCenter.tsx`
  - 显示更完整的同步包统计、覆盖风险和导入结果。
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/data/repository/SyncRepository.kt`
  - Android 本地导入/导出统计、空包保护和覆盖列表。
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/ui/StudyViewModel.kt`
  - Android 同步状态提示展示完整导入/导出结果。
- Modify: `android/app/build.gradle`
  - 增加 JVM 单元测试依赖。
- Create: `android/app/src/test/java/com/studyinghelper/mobile/data/sync/SyncDtosTest.kt`
  - 验证 Android DTO 能解析 Web 风格同步包并输出 Android 来源同步包。
- Modify: `docs/mobile/roadmap.md`
  - 更新本轮同步闭环状态和剩余限制。

> 注意：本会话不自动提交 commit，除非用户明确要求。计划中的每个任务完成后用 `git diff --check`、测试命令和审查结果作为检查点。

---

### Task 1: 后端同步统计契约补全

**Files:**
- Modify: `backend/app/modules/sync/schemas.py`
- Modify: `backend/app/modules/sync/service.py`
- Modify: `backend/app/modules/sync/tests/test_sync_service.py`

- [ ] **Step 1: 写入失败测试，要求预览返回完整统计**

在 `backend/app/modules/sync/tests/test_sync_service.py` 的 `test_preview_package_marks_overwritten_books` 中追加这些断言：

```python
    assert preview.chapters_count == 1
    assert preview.units_count == 1
    assert preview.mastery_records_count == 1
    assert preview.annotations_count == 1
    assert preview.kg_nodes_count == 2
    assert preview.kg_edges_count == 1
    assert preview.daily_stats_count == 1
    assert preview.teaching_sessions_count == 1
    assert preview.teaching_messages_count == 1
```

- [ ] **Step 2: 写入失败测试，要求导入结果返回完整统计**

在 `test_import_package_replaces_existing_book` 的断言区追加：

```python
    assert result.books_imported == 1
    assert result.chapters_imported == 1
    assert result.units_imported == 1
    assert result.mastery_records_imported == 1
    assert result.annotations_imported == 1
    assert result.kg_nodes_imported == 2
    assert result.kg_edges_imported == 1
    assert result.learning_records_imported == 0
    assert result.daily_stats_imported == 1
    assert result.review_sessions_imported == 0
    assert result.teaching_sessions_imported == 1
    assert result.teaching_messages_imported == 1
    assert result.user_questions_imported == 0
    assert result.session_tests_imported == 0
    assert result.learning_efficiency_imported == 1
```

- [ ] **Step 3: 运行后端同步测试，确认新增断言失败**

Run:

```bash
cd backend && PYTHONPATH=. pytest app/modules/sync/tests/test_sync_service.py -q
```

Expected: FAIL，错误包含 `SyncPreviewResult` 或 `SyncImportResult` 没有新增字段。

- [ ] **Step 4: 扩展后端同步结果模型**

在 `backend/app/modules/sync/schemas.py` 中，把 `SyncPreviewResult` 和 `SyncImportResult` 修改为：

```python
class SyncPreviewResult(BaseModel):
    schema_version: str
    source: Literal["web", "android"]
    exported_at: datetime
    books_count: int
    chapters_count: int
    units_count: int
    mastery_records_count: int
    annotations_count: int = 0
    kg_nodes_count: int = 0
    kg_edges_count: int = 0
    daily_stats_count: int = 0
    teaching_sessions_count: int = 0
    teaching_messages_count: int = 0
    books: list[SyncPreviewBook]


class SyncImportResult(BaseModel):
    books_imported: int
    chapters_imported: int
    units_imported: int
    mastery_records_imported: int
    overwritten_books: list[str] = Field(default_factory=list)
    annotations_imported: int = 0
    kg_nodes_imported: int = 0
    kg_edges_imported: int = 0
    learning_records_imported: int = 0
    daily_stats_imported: int = 0
    review_sessions_imported: int = 0
    teaching_sessions_imported: int = 0
    teaching_messages_imported: int = 0
    user_questions_imported: int = 0
    session_tests_imported: int = 0
    learning_efficiency_imported: int = 0
```

- [ ] **Step 5: 扩展后端服务返回值**

在 `backend/app/modules/sync/service.py` 的 `preview_package()` 中，把 `SyncPreviewResult(...)` 参数扩展为：

```python
        return SyncPreviewResult(
            schema_version=package.schema_version,
            source=package.source,
            exported_at=package.exported_at,
            books_count=len(package.books),
            chapters_count=len(package.chapters),
            units_count=len(package.knowledge_units),
            mastery_records_count=len(package.mastery_records),
            annotations_count=len(package.annotations),
            kg_nodes_count=len(package.kg_nodes),
            kg_edges_count=len(package.kg_edges),
            daily_stats_count=len(package.daily_stats),
            teaching_sessions_count=len(package.teaching_sessions),
            teaching_messages_count=len(package.teaching_messages),
            books=[
                SyncPreviewBook(
                    id=book.id,
                    title=book.title,
                    source_updated_at=book.updated_at,
                    will_overwrite=book.id in local_books,
                    local_title=local_books[book.id].title if book.id in local_books else None,
                )
                for book in package.books
            ],
        )
```

在 `import_package()` 的 `SyncImportResult(...)` 返回值中扩展为：

```python
        return SyncImportResult(
            books_imported=len(package.books),
            chapters_imported=len(package.chapters),
            units_imported=len(package.knowledge_units),
            mastery_records_imported=len(package.mastery_records),
            overwritten_books=overwritten_books,
            annotations_imported=len(package.annotations),
            kg_nodes_imported=len(package.kg_nodes),
            kg_edges_imported=len(package.kg_edges),
            learning_records_imported=len(package.learning_records),
            daily_stats_imported=len(package.daily_stats),
            review_sessions_imported=len(package.review_sessions),
            teaching_sessions_imported=len(package.teaching_sessions),
            teaching_messages_imported=len(package.teaching_messages),
            user_questions_imported=len(package.user_questions),
            session_tests_imported=len(package.session_tests),
            learning_efficiency_imported=len(package.learning_efficiency),
        )
```

- [ ] **Step 6: 运行后端同步测试，确认通过**

Run:

```bash
cd backend && PYTHONPATH=. pytest app/modules/sync/tests/test_sync_service.py -q
```

Expected: PASS。

- [ ] **Step 7: 检查格式**

Run:

```bash
git diff --check -- backend/app/modules/sync/schemas.py backend/app/modules/sync/service.py backend/app/modules/sync/tests/test_sync_service.py
```

Expected: no output。

---

### Task 2: Web 同步中心展示完整预览和导入结果

**Files:**
- Modify: `frontend/src/api/sync.ts`
- Modify: `frontend/src/pages/SyncCenter.tsx`

- [ ] **Step 1: 更新前端同步类型**

在 `frontend/src/api/sync.ts` 中扩展 `SyncPreviewResult`：

```typescript
export interface SyncPreviewResult {
  schema_version: string;
  source: 'web' | 'android';
  exported_at: string;
  books_count: number;
  chapters_count: number;
  units_count: number;
  mastery_records_count: number;
  annotations_count: number;
  kg_nodes_count: number;
  kg_edges_count: number;
  daily_stats_count: number;
  teaching_sessions_count: number;
  teaching_messages_count: number;
  books: SyncPreviewBook[];
}
```

扩展 `SyncImportResult`：

```typescript
export interface SyncImportResult {
  books_imported: number;
  chapters_imported: number;
  units_imported: number;
  mastery_records_imported: number;
  overwritten_books: string[];
  annotations_imported: number;
  kg_nodes_imported: number;
  kg_edges_imported: number;
  learning_records_imported: number;
  daily_stats_imported: number;
  review_sessions_imported: number;
  teaching_sessions_imported: number;
  teaching_messages_imported: number;
  user_questions_imported: number;
  session_tests_imported: number;
  learning_efficiency_imported: number;
}
```

- [ ] **Step 2: 在 SyncCenter 增加统计渲染辅助函数**

在 `downloadJson()` 后、`export default function SyncCenter()` 前加入：

```tsx
function StatPill({ label, value }: { label: string; value: number }) {
  return (
    <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-gray-600 border border-gray-100">
      {label}：{value}
    </span>
  );
}
```

- [ ] **Step 3: 扩展同步包预览区域**

在 `frontend/src/pages/SyncCenter.tsx` 的预览卡片中，紧跟来源说明 `<p className="text-sm text-gray-500 mt-1">...</p>` 后加入：

```tsx
              <div className="flex flex-wrap gap-2 mt-3">
                <StatPill label="章节" value={preview.chapters_count} />
                <StatPill label="知识单元" value={preview.units_count} />
                <StatPill label="掌握记录" value={preview.mastery_records_count} />
                <StatPill label="注释" value={preview.annotations_count} />
                <StatPill label="图谱节点" value={preview.kg_nodes_count} />
                <StatPill label="图谱关系" value={preview.kg_edges_count} />
                <StatPill label="每日统计" value={preview.daily_stats_count} />
                <StatPill label="教学会话" value={preview.teaching_sessions_count} />
              </div>
```

- [ ] **Step 4: 扩展导入完成区域**

把导入完成卡片中的单段结果文字替换为：

```tsx
          <div className="flex flex-wrap gap-2 mt-3">
            <StatPill label="书籍" value={importResult.books_imported} />
            <StatPill label="章节" value={importResult.chapters_imported} />
            <StatPill label="知识单元" value={importResult.units_imported} />
            <StatPill label="掌握记录" value={importResult.mastery_records_imported} />
            <StatPill label="注释" value={importResult.annotations_imported} />
            <StatPill label="学习记录" value={importResult.learning_records_imported} />
            <StatPill label="复习/考试" value={importResult.review_sessions_imported} />
            <StatPill label="教学会话" value={importResult.teaching_sessions_imported} />
            <StatPill label="教学消息" value={importResult.teaching_messages_imported} />
            <StatPill label="效率记录" value={importResult.learning_efficiency_imported} />
          </div>
```

保留覆盖书籍提示。

- [ ] **Step 5: 运行前端构建**

Run:

```bash
cd frontend && npm run build
```

Expected: TypeScript 和 Vite 构建成功。

- [ ] **Step 6: 检查格式**

Run:

```bash
git diff --check -- frontend/src/api/sync.ts frontend/src/pages/SyncCenter.tsx
```

Expected: no output。

---

### Task 3: Android 导入/导出反馈与空包保护

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/data/repository/SyncRepository.kt`
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/ui/StudyViewModel.kt`

- [ ] **Step 1: 扩展 Android ImportResult**

把 `SyncRepository.kt` 末尾的 `ImportResult` 替换为：

```kotlin
data class ImportResult(
    val books: Int,
    val chapters: Int,
    val units: Int,
    val masteryRecords: Int,
    val annotations: Int,
    val learningRecords: Int,
    val reviewSessions: Int,
    val teachingSessions: Int,
    val teachingMessages: Int,
    val overwrittenBooks: List<String>,
)
```

- [ ] **Step 2: 记录 Android 导入覆盖书籍**

在 `importPackage()` 中，`val bookIds = packageData.books.map { it.id }` 后加入：

```kotlin
        val localBookIds = dao.getBooks().map { it.id }.toSet()
        val overwrittenBooks = bookIds.filter { it in localBookIds }
```

- [ ] **Step 3: 返回完整 Android 导入结果**

把 `importPackage()` 的返回值替换为：

```kotlin
        return ImportResult(
            books = packageData.books.size,
            chapters = packageData.chapters.size,
            units = packageData.knowledgeUnits.size,
            masteryRecords = packageData.masteryRecords.size,
            annotations = packageData.annotations.size,
            learningRecords = packageData.learningRecords.size,
            reviewSessions = packageData.reviewSessions.size,
            teachingSessions = packageData.teachingSessions.size,
            teachingMessages = packageData.teachingMessages.size,
            overwrittenBooks = overwrittenBooks,
        )
```

- [ ] **Step 4: Android 导出空包保护**

在 `exportPackage()` 中，先读取书籍并拒绝空库导出：

```kotlin
    suspend fun exportPackage(): String {
        val books = dao.getBooks()
        require(books.isNotEmpty()) { "没有可导出的书籍" }
        val packageData = SyncPackage(
            exportedAt = OffsetDateTime.now().toString(),
            source = "android",
            books = books.map { it.toSync() },
            chapters = dao.getChapters().map { it.toSync() },
            knowledgeUnits = dao.getKnowledgeUnits().map { it.toSync() },
            kgNodes = dao.getKgNodes().map { it.toSync() },
            kgEdges = dao.getKgEdges().map { it.toSync() },
            masteryRecords = dao.getMasteryRecords().map { it.toSync() },
            annotations = dao.getAnnotations().map { it.toSync() },
            learningRecords = dao.getLearningRecords().map { it.toSync() },
            dailyStats = dao.getDailyStats().map { it.toSync() },
            reviewSessions = dao.getReviewSessions().map { it.toSync() },
            teachingSessions = dao.getTeachingSessions().map { it.toSync() },
            teachingMessages = dao.getTeachingMessages().map { it.toSync() },
            userQuestions = dao.getUserQuestions().map { it.toSync() },
            sessionTests = dao.getSessionTests().map { it.toSync() },
            learningEfficiency = dao.getLearningEfficiency().map { it.toSync() },
        )
        return json.encodeToString(packageData)
    }
```

- [ ] **Step 5: 扩展 ViewModel 导入状态提示**

在 `StudyViewModel.kt` 的 `importFromUri()` 成功分支中，把状态文字替换为：

```kotlin
            }.onSuccess { result ->
                val overwriteText = if (result.overwrittenBooks.isEmpty()) {
                    "无覆盖"
                } else {
                    "覆盖 ${result.overwrittenBooks.size} 本"
                }
                _status.value = "导入完成：${result.books} 本书，${result.units} 个知识单元，${result.masteryRecords} 条掌握记录，$overwriteText"
            }.onFailure { error ->
```

- [ ] **Step 6: 扩展 ViewModel 导出状态提示**

在 `exportToUri()` 成功分支中，把 `_status.value = "导出完成"` 保持为：

```kotlin
            }.onSuccess {
                _status.value = "导出完成：可在电脑端同步中心导入"
            }.onFailure { error ->
```

- [ ] **Step 7: 运行 Android 构建或记录环境阻塞**

Run:

```bash
cd android && ./gradlew assembleDebug
```

Expected: 构建成功。如果失败是 JDK/Android SDK 环境问题，记录完整错误输出，后续仍需运行 `git diff --check`。

- [ ] **Step 8: 检查格式**

Run:

```bash
git diff --check -- android/app/src/main/java/com/studyinghelper/mobile/data/repository/SyncRepository.kt android/app/src/main/java/com/studyinghelper/mobile/ui/StudyViewModel.kt
```

Expected: no output。

---

### Task 4: Android 同步 DTO JVM 兼容性测试

**Files:**
- Modify: `android/app/build.gradle`
- Create: `android/app/src/test/java/com/studyinghelper/mobile/data/sync/SyncDtosTest.kt`

- [ ] **Step 1: 增加 JUnit 依赖**

在 `android/app/build.gradle` 的 `dependencies` 中加入：

```gradle
    testImplementation 'junit:junit:4.13.2'
```

- [ ] **Step 2: 创建 Android DTO 测试文件**

创建 `android/app/src/test/java/com/studyinghelper/mobile/data/sync/SyncDtosTest.kt`：

```kotlin
package com.studyinghelper.mobile.data.sync

import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SyncDtosTest {
    private val json = Json { ignoreUnknownKeys = true; prettyPrint = true }

    @Test
    fun parsesWebSyncPackage() {
        val raw = """
            {
              "schema_version": "1.0",
              "exported_at": "2026-06-08T00:00:00Z",
              "source": "web",
              "user_id": "anonymous",
              "books": [
                {
                  "id": "book-1",
                  "user_id": "anonymous",
                  "title": "跨端测试",
                  "author": null,
                  "file_path": "test.txt",
                  "file_type": "txt",
                  "file_size_bytes": 10,
                  "parse_status": "completed",
                  "split_status": "completed",
                  "learn_status": "learning",
                  "total_chapters": 1,
                  "total_units": 1,
                  "learned_units": 0,
                  "reading_motivation": null,
                  "created_at": "2026-06-08T00:00:00Z",
                  "updated_at": "2026-06-08T00:00:00Z"
                }
              ],
              "chapters": [],
              "knowledge_units": [],
              "kg_nodes": [],
              "kg_edges": [],
              "mastery_records": [],
              "annotations": [],
              "learning_records": [],
              "daily_stats": [],
              "review_sessions": [],
              "teaching_sessions": [],
              "teaching_messages": [],
              "user_questions": [],
              "session_tests": [],
              "learning_efficiency": []
            }
        """.trimIndent()

        val packageData = json.decodeFromString<SyncPackage>(raw)

        assertEquals(SYNC_SCHEMA_VERSION, packageData.schemaVersion)
        assertEquals("web", packageData.source)
        assertEquals("book-1", packageData.books.single().id)
        assertEquals("跨端测试", packageData.books.single().title)
    }

    @Test
    fun encodesAndroidSyncPackageWithSnakeCaseFields() {
        val packageData = SyncPackage(
            exportedAt = "2026-06-08T00:00:00Z",
            source = "android",
            books = emptyList(),
        )

        val encoded = json.encodeToString(packageData)

        assertTrue(encoded.contains("\"schema_version\""))
        assertTrue(encoded.contains("\"exported_at\""))
        assertTrue(encoded.contains("\"knowledge_units\""))
        assertTrue(encoded.contains("\"mastery_records\""))
        assertTrue(encoded.contains("\"source\": \"android\""))
    }
}
```

- [ ] **Step 3: 运行 Android JVM 测试**

Run:

```bash
cd android && ./gradlew testDebugUnitTest
```

Expected: `SyncDtosTest` 通过。如果本地 JDK/Gradle 环境失败，记录具体错误，不要声称测试通过。

- [ ] **Step 4: 检查格式**

Run:

```bash
git diff --check -- android/app/build.gradle android/app/src/test/java/com/studyinghelper/mobile/data/sync/SyncDtosTest.kt
```

Expected: no output。

---

### Task 5: 文档更新、全量验证和代码审查

**Files:**
- Modify: `docs/mobile/roadmap.md`

- [ ] **Step 1: 更新移动端路线图**

在 `docs/mobile/roadmap.md` 的“验证清单”后追加：

```markdown

## 2026-06-08 同步闭环收敛

- Web 同步中心展示完整预览统计和导入结果统计。
- 后端同步导入结果返回注释、图谱、学习记录、教学记录和效率记录数量。
- Android 导入同步包后展示覆盖数量和核心记录数量。
- Android 导出空库时给出明确提示，避免生成无法导入的空同步包。
- Android DTO 增加 JVM 测试，覆盖 Web 包解析和 Android 包 snake_case 字段输出。
- 单书同步包不携带每日统计，避免覆盖同一天其他书籍产生的全局累计数据。
```

- [ ] **Step 2: 后端同步测试**

Run:

```bash
cd backend && PYTHONPATH=. pytest app/modules/sync/tests/test_sync_service.py -q
```

Expected: PASS。

- [ ] **Step 3: 后端相关回归**

Run:

```bash
cd backend && PYTHONPATH=. pytest app/modules/sync/tests app/tests/test_integration.py -q
```

Expected: PASS。如果 `test_integration.py` 因现有未提交改动失败，记录失败测试名和错误。

- [ ] **Step 4: 前端构建**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS。

- [ ] **Step 5: Android 验证**

Run:

```bash
cd android && ./gradlew testDebugUnitTest assembleDebug
```

Expected: PASS。如果 Android SDK/JDK 环境失败，记录错误输出和缺失环境。

- [ ] **Step 6: 全部改动格式检查**

Run:

```bash
git diff --check
```

Expected: no output。

- [ ] **Step 7: 调用代码审查技能**

Invoke:

```text
/code-review high
```

Review scope: 当前 diff 中与同步闭环相关的后端、Web、Android 改动。重点检查跨端字段一致性、覆盖删除完整性、UI 风险提示和无关重构。

- [ ] **Step 8: 修复审查发现的高置信问题**

如果审查提出必须修复的问题，按问题逐个修改，并重新运行对应测试命令。没有新鲜验证证据时，不得声称修复完成。

---

## Self-Review

- Spec coverage: 本计划覆盖同步契约完整性、Web 同步中心、Android 本地导入/导出反馈、Android DTO 兼容测试、文档更新、验证和代码审查。
- Scope control: 不实现云同步、账号体系、自动冲突合并或大规模 UI 重构。
- Type consistency: 后端新增字段使用 snake_case；前端接口使用相同字段名；Android DTO 测试验证 snake_case 序列化。
- Placeholders: 无 TBD、TODO、待定或未说明的“适当处理”。
- Commit policy: 由于当前会话未获得显式 commit 授权，计划不自动提交，只使用测试、构建、diff check 和审查作为检查点。
