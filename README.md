# Studying-helper AI 快速接手入口

这份 README 面向接手项目的 AI，不面向普通用户。读完后应能知道项目是什么、从哪里查代码、哪些文件一起改、哪些坑不能踩。

## 0. 先记住这句话

Studying-helper 是一个三端学习系统：FastAPI 后端负责书籍解析、AI 分析、知识图谱、AID 教学设计、复习考试和同步；React Web 是主要桌面界面；Android 是离线优先客户端，通过同步包与 Web/后端交换数据。

## 1. 当前主链路

```text
书籍导入
  -> document_parser 解析章节
  -> knowledge_splitter 拆知识单元
  -> ai_learning 调 LLM 生成摘要/讲解/概念/难度
  -> knowledge_graph 建依赖和跨章节关系
  -> adaptive_design 生成学习者画像、宏观模块、微观顺序
  -> teaching 按 AID 顺序或普通顺序教学
  -> review 做间隔重复、考试、导出
  -> sync 在 Web 与 Android 间搬运数据
```

## 2. 入口文件

| 目标 | 先看 |
| --- | --- |
| 后端应用启动和路由注册 | `backend/app/main.py` |
| 后端数据库模型 | `backend/app/db/models.py` |
| 后端模块说明 | `docs/modules/*.md` |
| Web 路由 | `frontend/src/router/index.tsx` |
| Web API 封装 | `frontend/src/api/` |
| Android 导航 | `android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt` |
| Android Room 表 | `android/app/src/main/java/com/studyinghelper/mobile/data/db/Entities.kt` |
| Android 数据库版本/迁移 | `android/app/src/main/java/com/studyinghelper/mobile/data/db/StudyDatabase.kt`、`Migrations.kt` |
| Android 同步 DTO | `android/app/src/main/java/com/studyinghelper/mobile/data/sync/SyncDtos.kt` |

## 3. 后端模块速查

| 模块 | API | 核心职责 |
| --- | --- | --- |
| `user_storage` | `/api/v1` | 书籍、章节、用户、统计、文件 |
| `document_parser` | `/api/v1/documents` | PDF/TXT/EPUB 解析、目录确认 |
| `knowledge_splitter` | `/api/v1/split` | 文本拆知识单元 |
| `ai_learning` | `/api/v1/learning` | LLM 知识分析与学习状态 |
| `knowledge_graph` | `/api/v1/knowledge-graph` | 知识图谱、依赖、跨章节关系 |
| `adaptive_design` | `/api/v1/aid` | AID 画像、宏观/微观设计、replan |
| `teaching` | `/api/v1/teaching` | 教学会话、阶段、问答、测试 |
| `review` | `/api/v1/review` | SM-2/FSRS、考试、自由回忆、导出 |
| `learning_plan` | `/api/v1/plans` | 学习计划 |
| `settings` | `/api/v1/settings` | 用户偏好和 LLM 配置 |
| `sync` | `/api/v1/sync` | 离线同步包 |

## 4. AID 是当前最重要的新结构

AID 全称 Adaptive Instructional Design。它不是一个孤立页面，而是一条横跨后端、Web、Android、同步、教学的链。

核心表：

- `learner_intent_profiles`：学习者意图画像。
- `teaching_designs`：一本书的教学设计总账。
- `module_micro_plans`：模块内微观编排。
- `knowledge_units.ai_cognitive_hint`：AID 对单元的认知标注。

相关文件：

- 后端：`backend/app/modules/adaptive_design/`
- 后端模型：`backend/app/db/models.py`
- 后端同步：`backend/app/modules/sync/schemas.py`、`service.py`
- Web：`frontend/src/api/aid.ts`、`frontend/src/pages/TeachingDesign.tsx`
- Android：`TeachingDesignScreen.kt`、`AdaptiveDesignRepository.kt`、Room 三张 AID Entity
- 教学接入：`backend/app/modules/teaching/router.py`、`strategies.py`

改 AID 时要同时检查 sync 合约和 Android Room migration。

## 5. 同步模型

同步不是实时云同步，而是 JSON 包导入导出。

后端端点：

- `GET /api/v1/sync/export`
- `GET /api/v1/sync/books/{book_id}/export`
- `POST /api/v1/sync/preview`
- `POST /api/v1/sync/import`

同步包当前包含：

- books / chapters / knowledge_units
- mastery_records，含 SM-2 和 FSRS 字段
- annotations / kg_nodes / kg_edges
- review_sessions / teaching_sessions / teaching_messages
- user_questions / session_tests / learning_efficiency
- learner_intent_profiles / teaching_designs / module_micro_plans

不要只改一端字段。后端 Pydantic、后端 ORM、Android DTO、Android Entity、Android DAO、预览计数都可能要一起改。

## 6. Android 当前状态

Android 已是离线优先学习端，主要能力包括：

- 书籍、章节、知识单元本地管理。
- TXT/EPUB/PDF 基础导入。
- 本地 AI 配置与 OpenAI 兼容接口调用。
- 知识单元 AI 分析。
- 教学设计预览与教学页面。
- 复习反馈、FSRS 算法、考试模式。
- 同步包导入导出。

数据库当前是 Room `version = 2`，已有 `MIGRATION_1_2`。改 Entity 前必须写 migration。

## 7. Web 当前状态

关键页面：

- `Home.tsx`：书籍入口。
- `BookOverview.tsx`：书籍详情和学习入口。
- `TeachingDesign.tsx`：AID 画像/宏观设计界面。
- `TeachingSession.tsx`：教学会话。
- `SyncCenter.tsx`：同步中心。
- `Settings.tsx`：偏好和 AI 配置。

Web API 封装在 `frontend/src/api/`。新增后端端点时优先在这里加薄封装，再让页面调用。

## 8. 常用验证

```bash
# 文档/索引
codegraph status .
codegraph sync .

# 后端（从仓库根目录）
cd backend && python -m pytest
cd backend && python -m pytest app/modules/adaptive_design/tests/ -q
cd backend && python -m pytest app/modules/sync/tests/ -q

# Web（从仓库根目录）
cd frontend && npm run build

# Android（从仓库根目录，PowerShell）
cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:GRADLE_USER_HOME=(Resolve-Path '..\.gradle-ascii').Path
$env:Path="$env:JAVA_HOME\bin;$env:Path"
.\gradlew.bat :app:testDebugUnitTest
.\gradlew.bat :app:assembleDebug
```

只改文档时，不需要跑全量测试；但必须核对文档里的路径、端点和命令是否真实存在。

## 9. 常见坑位

- 当前知识图谱 API 是 `/api/v1/knowledge-graph`，不是 `/api/v1/graph`。
- Android 教学有端侧离线路径，不等同于 Web 调后端教学接口。
- AID 有规则化 fallback，不要让代码强依赖 LLM 成功。
- `ai_cognitive_hint` 要能跨平台同步。
- FSRS 字段要兼容旧 SM-2 字段。
- Room 新字段必须配 migration。
- 不要手工编辑 `.codegraph/codegraph.db`。
- 工作区可能有很多未提交改动，不要回滚无关文件。

## 10. 接任务时的默认动作

1. 读本 README、`AGENTS.md` 或 `CLAUDE.md`。
2. 读相关 `docs/modules/<module>.md`。
3. 用 `rg` 或 `codegraph context` 找真实调用点。
4. 判断是否跨后端/Web/Android/sync。
5. 精准改动，避免顺手重构。
6. 跑最小验证。
7. 如改了代码结构或文档，运行 `codegraph sync .`。
