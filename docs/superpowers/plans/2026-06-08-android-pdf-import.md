# Android PDF Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Android 端支持导入 PDF，抽取文本并生成书籍、章节和知识单元，进入现有学习/复习/同步闭环。

**Architecture:** 复用 `DocumentRepository` 的“章节列表 → Room 数据”保存路径。PDF 文本抽取使用 Android 适配的 PDFBox 依赖，不引入云服务；PDF 抽出的文本继续复用 TXT 拆分规则。

**Tech Stack:** Android Kotlin、Room、Jetpack Compose、tom-roush/pdfbox-android。

---

### Task 1: 增加 PDFBox Android 依赖

**Files:**
- Modify: `android/app/build.gradle`

- [ ] **Step 1: 修改 Gradle 依赖**

```groovy
implementation 'com.tom-roush:pdfbox-android:2.0.27.0'
```

- [ ] **Step 2: 验证**

Run:
```bash
"E:/AI Agent/work area/Studying-helper/android/gradlew" -p "E:/AI Agent/work area/Studying-helper/android" assembleDebug
```

Expected in this environment: fails with `java: not found` until JDK is installed. In Android Studio/JDK environment: Gradle sync should resolve dependency from Maven Central.

### Task 2: 在 DocumentRepository 中实现 PDF 导入

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/data/repository/DocumentRepository.kt`

- [ ] **Step 1: 注入 Context**

`DocumentRepository` 构造函数增加 `Context`，用于初始化 PDFBox Android 资源加载器。

- [ ] **Step 2: 实现 importPdf**

```kotlin
suspend fun importPdf(title: String, bytes: ByteArray): DocumentImportResult
```

行为：
- 初始化 `PDFBoxResourceLoader`。
- 用 `PDDocument.load(ByteArrayInputStream(bytes))` 读取 PDF。
- 用 `PDFTextStripper().getText(document)` 抽取文本。
- 文本为空时抛出 `PDF 中没有可导入的文本`。
- 复用 `splitTxtSections` 和 `saveBook(fileType = "pdf")`。

### Task 3: ViewModel 接入 PDF URI

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/ui/StudyViewModel.kt`

- [ ] **Step 1: 初始化 DocumentRepository(database, application)**

- [ ] **Step 2: 新增 importPdfFromUri(uri)**

读取 URI bytes，提取显示名作为标题，调用 `documentRepository.importPdf`，成功后显示导入章节/单元数量。

### Task 4: 首页增加 PDF 导入按钮

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt`

- [ ] **Step 1: 新增 PDF 文件选择 launcher**

MIME：`application/pdf`。

- [ ] **Step 2: 增加“导入 PDF”按钮**

按钮和 TXT/EPUB 同组，调用 `viewModel.importPdfFromUri(uri)`。

### Task 5: 审查与验证

**Files:**
- Modify: `docs/mobile/roadmap.md`

- [ ] **Step 1: 静态检查**

Run:
```bash
git diff --check -- android/app/build.gradle android/app/src/main/java/com/studyinghelper/mobile/data/repository/DocumentRepository.kt android/app/src/main/java/com/studyinghelper/mobile/ui/StudyViewModel.kt android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt
```

Expected: no output.

- [ ] **Step 2: Android 构建尝试**

Run:
```bash
"E:/AI Agent/work area/Studying-helper/android/gradlew" -p "E:/AI Agent/work area/Studying-helper/android" assembleDebug
```

Expected in this shell: `java: not found`。这不是代码验证通过，只说明当前环境无法构建；需要 Android Studio/JDK 环境补测。

- [ ] **Step 3: 调用代码审查技能**

使用 `/code-review` 或 `code-review` skill 审查当前 diff。

- [ ] **Step 4: 更新路线图**

将 PDF 标记为基础版完成，并记录风险：扫描件 PDF 需要 OCR/AI 后续处理。
