# Android AI Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Android 端能独立配置 OpenAI 兼容 LLM，并对知识单元生成摘要、讲解、要点和概念，结果保存到 Room 并通过同步包回传电脑端。

**Architecture:** 使用本地 SharedPreferences 保存 AI 配置；新增轻量 `AiRepository` 负责 OpenAI 兼容 Chat Completions 请求；`StudyViewModel` 提供 `analyzeUnit(unitId)` 用例；`UnitDetailScreen` 增加“AI 分析”按钮和配置入口。先实现知识单元分析，不实现完整多轮教学。

**Tech Stack:** Android Kotlin、SharedPreferences、HttpURLConnection、kotlinx.serialization、Room、Jetpack Compose。

---

### Task 1: 网络权限与 AI 配置存储

**Files:**
- Modify: `android/app/src/main/AndroidManifest.xml`
- Create: `android/app/src/main/java/com/studyinghelper/mobile/data/repository/AiConfigRepository.kt`

- [ ] **Step 1: Manifest 加网络权限**

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

- [ ] **Step 2: 新增 AiConfigRepository**

保存字段：`apiKey`、`baseUrl`、`model`。默认 `baseUrl=https://api.openai.com/v1`，默认 `model=gpt-4o-mini`。

### Task 2: OpenAI 兼容 LLM 请求

**Files:**
- Create: `android/app/src/main/java/com/studyinghelper/mobile/data/repository/AiRepository.kt`

- [ ] **Step 1: 实现 analyzeUnit(unit)**

请求：`POST {baseUrl}/chat/completions`。

输出要求模型返回 JSON：

```json
{
  "summary": "...",
  "explanation": "...",
  "key_points": ["..."],
  "concepts": ["..."]
}
```

- [ ] **Step 2: 错误处理**

无 API Key 时抛出 `请先配置 API Key`；HTTP 非 2xx 时返回响应摘要。

### Task 3: DAO 更新知识单元 AI 字段

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/data/db/StudyDao.kt`

- [ ] **Step 1: 增加 updateUnitAnalysis**

更新 `summary`、`explanation`、`key_points`、`concepts`。

### Task 4: ViewModel 接入 AI 分析和配置保存

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/ui/StudyViewModel.kt`

- [ ] **Step 1: 初始化 AiConfigRepository 和 AiRepository**

- [ ] **Step 2: 新增 saveAiConfig(apiKey, baseUrl, model)**

- [ ] **Step 3: 新增 analyzeUnit(unitId)**

在 `Dispatchers.IO` 中读取 unit，调用 AI，保存结果。

### Task 5: UI 增加 AI 设置与分析按钮

**Files:**
- Modify: `android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt`

- [ ] **Step 1: 首页增加 AI 设置按钮和弹窗**

- [ ] **Step 2: 知识单元详情增加“AI 分析”按钮**

### Task 6: 审查与验证

**Files:**
- Modify: `docs/mobile/roadmap.md`

- [ ] **Step 1: 静态检查**

Run:
```bash
git diff --check -- android/app/src/main AndroidManifest.xml android/app/src/main/java/com/studyinghelper/mobile
```

- [ ] **Step 2: Android 构建尝试**

当前 shell 预期因缺 Java 失败；Android Studio/JDK 环境需补测。

- [ ] **Step 3: 后端/前端回归**

Run:
```bash
cd backend && PYTHONPATH=. pytest app/modules/sync/tests
npm run build --prefix frontend
```

- [ ] **Step 4: 代码审查**

调用 `code-review` skill，修复必须项。
