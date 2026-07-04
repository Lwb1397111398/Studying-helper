# AID / 跨端教学设计交接

本文面向接手本项目的 AI。旧版文档把 AID 的 Android/Web 工作写成 M5/M6 待做；当前工作区里这些能力已经大部分落地。后续接手时应以代码现状为准。

## 1. 项目背景

Studying-helper 的主链路是：

```text
导入书籍 -> 解析/拆分 -> AI 学习 -> 知识图谱 -> AID 教学设计 -> 教学 -> 复习/考试 -> 同步
```

AID（Adaptive Instructional Design）解决的问题是：AI 学完书后不再只按章节机械教学，而是根据学习者意图和知识图谱重组教学路径。

## 2. AID 当前能力

### 后端

后端模块：`backend/app/modules/adaptive_design/`

已具备：

- 学习者画像：身份背景、目标深度、认知偏好、重组容忍度、时间预算。
- 宏观设计：跨章节模块化，保存在 `TeachingDesignModel.macro_design_json`。
- 微观设计：模块内 unit 顺序、认知标注、导言，保存在 `ModuleMicroPlanModel`。
- Replan：模块结束后根据薄弱点和掌握度调整下一模块。
- LLM + 规则化 fallback：没有 LLM key 时仍能生成可用设计。
- `KnowledgeUnitModel.ai_cognitive_hint` 写回：`memorize` / `understand` / `skip_if_mastered`。

API 前缀：`/api/v1/aid`

```text
GET  /{book_id}/profile
PUT  /{book_id}/profile
POST /{book_id}/profile/confirm
POST /{book_id}/macro
GET  /{book_id}/design
POST /{book_id}/micro/{module_index}
GET  /{book_id}/micro/{module_index}
POST /{book_id}/activate
POST /{book_id}/advance
POST /{book_id}/replan
POST /{book_id}/adjustment
GET  /{book_id}/active-units
```

### Web

已存在：

- `frontend/src/api/aid.ts`
- `frontend/src/pages/TeachingDesign.tsx`
- 路由：`/books/:bookId/design`
- 书籍页和教学页已有 AID 相关接入点。

### Android

已存在：

- `TeachingDesignScreen.kt`
- `AdaptiveDesignRepository.kt`
- `LearnerIntentProfileEntity`
- `TeachingDesignEntity`
- `ModuleMicroPlanEntity`
- `KnowledgeUnitEntity.aiCognitiveHint`
- `StudyDatabase.version = 2`
- `MIGRATION_1_2`
- 同步 DTO/Repository 中的 AID 三表和 `ai_cognitive_hint`

Android 主路径是离线优先：AID 数据可由后端生成后同步到端，也可由端侧界面消费本地 Room 数据。Android 教学有自己的 `TeachingRepository.kt`，不是完全复用后端 `/api/v1/teaching`。

## 3. 数据模型

### learner_intent_profiles

每本书一份学习者意图画像。

关键字段：

- `identity_background`
- `goal_depth`
- `cognitive_pref`
- `restructure_tolerance`
- `time_budget_minutes`
- `source`
- `status`
- `extra_json`

### teaching_designs

一本书的 AID 设计总账。

关键字段：

- `profile_id`
- `macro_design_json`
- `current_module_index`
- `generated_module_count`
- `adjustments_json`
- `status`
- `version`

### module_micro_plans

单个模块的微观编排。

关键字段：

- `design_id`
- `module_index`
- `module_title`
- `ordered_unit_ids_json`
- `unit_annotations_json`
- `module_intro`
- `module_status`
- `module_summary_json`
- `parent_design_version`

### knowledge_units.ai_cognitive_hint

AID 对知识单元的认知标注。改这个字段时要同步后端 schema、Android DTO/Entity 和 sync 测试。

## 4. 同步当前状态

后端 sync 已包含：

- `learner_intent_profiles`
- `teaching_designs`
- `module_micro_plans`
- `knowledge_units[].ai_cognitive_hint`

相关文件：

- `backend/app/modules/sync/schemas.py`
- `backend/app/modules/sync/service.py`
- `backend/app/modules/sync/tests/test_sync_contract.py`
- `android/app/src/main/java/com/studyinghelper/mobile/data/sync/SyncDtos.kt`
- `android/app/src/main/java/com/studyinghelper/mobile/data/sync/SyncPreview.kt`
- `android/app/src/main/java/com/studyinghelper/mobile/data/repository/SyncRepository.kt`

## 5. 接手时优先检查

1. 如果改 AID schema，先检查后端 ORM、Pydantic schema、sync、Web API、Android Entity/DTO、Room migration。
2. 如果改 macro/micro JSON 结构，要兼容旧记录。
3. 如果改教学入口，要同时检查 Web `/design`、后端 `/active-units` 和 Android `TeachingDesignScreen`。
4. 如果改同步字段，跑后端 sync contract 测试和 Android SyncDtosTest。

## 6. 验证命令

```bash
cd backend && python -m pytest app/modules/adaptive_design/tests/ -q
cd backend && python -m pytest app/modules/sync/tests/ -q

cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:GRADLE_USER_HOME=(Resolve-Path '..\.gradle-ascii').Path
$env:Path="$env:JAVA_HOME\bin;$env:Path"
.\gradlew.bat :app:testDebugUnitTest
```

## 7. 仍需注意的风险

- AID 逻辑横跨多端，最容易出现“一端字段已加，另一端同步丢失”。
- Android Room migration 必须手写，不能只改 Entity。
- 规则化 fallback 很重要，不要让 AID 变成无 LLM 不可用。
- 当前同步是覆盖式导入，不处理复杂冲突。
- 工作区可能存在未提交重构改动，接手时不要回滚无关文件。
