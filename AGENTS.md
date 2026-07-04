# Studying-helper AI 接手说明

本文是给下一个 AI/Agent 的项目级入口说明。目标不是介绍产品给普通用户，而是让没有上下文的新模型快速理解代码、改动边界和当前重构状态。

## 协作规则

- 始终中文沟通；代码标识符保持英文，必要注释用中文。
- 用户是编程小白，默认由 AI 自动理解、选择方案、修改、验证和收尾。
- 不把技术细节选择抛给用户；只有删除、大迁移、依赖/部署/Git 破坏性操作、数据库结构变更、密钥/账号/业务规则缺失时才确认。
- 没有验证证据，不得声称完成。
- 工作区可能已有大量用户改动；不要回滚、格式化或清理无关文件。
- 本项目当前处于大重构后的未完全收敛状态，文档应以当前工作区代码为准。

## 项目一句话

Studying-helper 是个人 AI 学习辅助系统。核心链路是：

```text
导入书籍
  -> 文档解析 PDF/TXT/EPUB
  -> 章节与知识单元拆分
  -> AI 分析知识单元
  -> 构建知识图谱
  -> AID 自适应教学设计
  -> 交互式教学
  -> 复习/考试/导出
  -> Web 与 Android 离线同步
```

## 三端结构

### 后端

- 路径：`backend/`
- 框架：FastAPI + SQLAlchemy 2.0 async + SQLite
- 入口：`backend/app/main.py`
- 数据库模型：`backend/app/db/models.py`
- 模块目录：`backend/app/modules/`
- 特点：所有业务 API 都挂到 `/api/v1/*`；单用户模式下大量逻辑默认使用 `user_id="anonymous"`。

### Web 前端

- 路径：`frontend/`
- 技术：React 18 + TypeScript + Vite + Tailwind + Axios
- 路由：`frontend/src/router/index.tsx`
- API 封装：`frontend/src/api/`
- 重要页面：`TeachingDesign.tsx`、`TeachingSession.tsx`、`SyncCenter.tsx`、`BookOverview.tsx`

### Android

- 路径：`android/`
- 技术：Kotlin + Jetpack Compose + Room + kotlinx.serialization
- 入口：`android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt`
- 数据库：`data/db/StudyDatabase.kt`、`Entities.kt`、`StudyDao.kt`、`Migrations.kt`
- 特点：Android 是离线优先客户端，不只是 Web 附属同步查看器；端侧可新建书籍/章节/知识单元、AI 分析、教学、考试、复习，并通过同步包与 Web 交换数据。

## 后端模块地图

| 模块 | 路径 | API 前缀 | 职责 |
| --- | --- | --- | --- |
| `user_storage` | `backend/app/modules/user_storage` | `/api/v1` | 用户、书籍、章节、学习记录、统计、文件存储 |
| `document_parser` | `backend/app/modules/document_parser` | `/api/v1/documents` | PDF/TXT/EPUB 解析、目录预览/确认 |
| `knowledge_splitter` | `backend/app/modules/knowledge_splitter` | `/api/v1/split` | 章节文本拆成可学习知识单元 |
| `ai_learning` | `backend/app/modules/ai_learning` | `/api/v1/learning` | LLM 摘要、讲解、要点、概念、难度/重要度分析 |
| `knowledge_graph` | `backend/app/modules/knowledge_graph` | `/api/v1/knowledge-graph` | 图谱节点/边、前置依赖、跨章节概念关系 |
| `adaptive_design` | `backend/app/modules/adaptive_design` | `/api/v1/aid` | AID 学习者画像、宏观模块设计、微观教学编排、replan |
| `teaching` | `backend/app/modules/teaching` | `/api/v1/teaching` | 教学会话、阶段推进、问答、测试、Cornell 笔记 |
| `review` | `backend/app/modules/review` | `/api/v1/review` | SM-2/FSRS 复习、考试、自由回忆、导出 |
| `learning_plan` | `backend/app/modules/learning_plan` | `/api/v1/plans` | 学习计划和学习风格分析 |
| `settings` | `backend/app/modules/settings` | `/api/v1/settings` | 用户偏好、LLM 配置、`.env` 热更新 |
| `sync` | `backend/app/modules/sync` | `/api/v1/sync` | Web/Android 离线同步包导入导出与预览 |
| `common` | `backend/app/common` | 无独立前缀 | 统一错误、LLM client、共享 schema、时间工具 |

详细模块说明见 `docs/modules/`。

## 当前关键设计

### AID 自适应教学设计

AID 插在“AI 学习”和“教学”之间，避免按章节机械教学。

- `LearnerIntentProfileModel`：每本书一份学习者意图画像，维度包括身份背景、目标深度、认知偏好、重组容忍度、时间预算。
- `TeachingDesignModel`：一本书的宏观教学设计总账，保存模块化设计、当前模块、调整审计和版本。
- `ModuleMicroPlanModel`：每个模块的微观编排，保存重排后的 `unit_ids`、单元标注、导言和模块状态。
- `KnowledgeUnitModel.ai_cognitive_hint`：AID 写回的单元认知标注，典型值为 `memorize`、`understand`、`skip_if_mastered`。

AID 有 LLM 路径，也有规则化 fallback。不要假设 LLM 必定可用。

### 同步

同步是离线包导入导出，不是云同步。

- 后端同步 schema 在 `backend/app/modules/sync/schemas.py`。
- 后端同步服务在 `backend/app/modules/sync/service.py`。
- Android DTO 在 `android/.../data/sync/SyncDtos.kt`。
- Android 本地导入导出在 `android/.../data/repository/SyncRepository.kt`。
- 当前同步包包含 AID 三表、教学记录、复习/考试、学习效率、图谱、注释、`ai_cognitive_hint` 和 FSRS 相关字段。
- 导入策略以覆盖式 upsert 为主，尚未做自动冲突合并。

### 复习算法

项目从 SM-2 扩展到 FSRS。

- 后端：`review/spaced_repetition.py`、`review/spaced_repetition_v2.py`、`review/fsrs.py`
- Android：`data/algorithm/FSRSAlgorithm.kt`
- 数据字段在 `MasteryRecordModel` / `MasteryRecordEntity` 中，包括 `stability`、`difficulty`、`lapses`、`reps`、`scheduled_days`、`algorithm`。
- 新逻辑要兼容旧 SM-2 字段：`ease_factor`、`interval_days`、`review_count`。

## 数据模型总览

核心关系：

```text
User
  -> Book
    -> Chapter
      -> KnowledgeUnit
        -> MasteryRecord
        -> Annotation
        -> TeachingMessage
    -> KGNode / KGEdge
    -> TeachingDesign
      -> ModuleMicroPlan
    -> ReviewSession
    -> TeachingSession
  -> DailyStats
```

后端模型集中在 `backend/app/db/models.py`。Android Room Entity 需要与后端同步字段逐字对齐，尤其是 snake_case 字段、AID 三表和 FSRS 字段。

## LLM 配置

配置优先级：

```text
模块级 LLM_* 覆盖
  -> 全局默认 LLM_DEFAULT_*
  -> 旧字段兼容 LLM_*
```

重要模块名包括：

- `teaching`
- `ai_analysis`
- `parser`
- `aid`

LLM 客户端通过 `backend/app/common/llm_client.py` 和 `backend/app/deps.py` 管理，支持并发信号量和关闭时等待在途请求。

## 常用命令

```bash
# 一键启动 Web + 后端
python start.py

# 后端（从仓库根目录）
cd backend && uvicorn app.main:app --reload --port 8000
cd backend && python -m pytest

# Web（从仓库根目录）
cd frontend && npm run dev
cd frontend && npm run build

# Android（从仓库根目录，PowerShell）
cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:GRADLE_USER_HOME=(Resolve-Path '..\.gradle-ascii').Path
$env:Path="$env:JAVA_HOME\bin;$env:Path"
.\gradlew.bat :app:testDebugUnitTest
.\gradlew.bat :app:assembleDebug

# CodeGraph
codegraph status .
codegraph sync .
```

Windows PowerShell 下使用 `.\gradlew.bat`。如果命令行找不到 `java`，先按上面的方式临时设置 Android Studio 自带 JDK。中文用户路径下 Gradle worker 启动异常时，使用上面的 `.gradle-ascii` 作为 `GRADLE_USER_HOME`。

## 重要路由

### Web

`frontend/src/router/index.tsx`：

- `/` 首页书籍列表
- `/upload` 上传
- `/books/:bookId` 书籍详情
- `/books/:bookId/toc` 目录确认
- `/books/:bookId/learn` AI 学习
- `/books/:bookId/design` AID 教学设计
- `/books/:bookId/teach` 教学会话
- `/books/:bookId/review` 复习
- `/books/:bookId/exam` 考试
- `/books/:bookId/export` 导出
- `/books/:bookId/plan` 学习计划
- `/books/:bookId/graph` 知识图谱
- `/sync` 同步中心
- `/settings` 设置

### Android

`MainActivity.kt` NavHost：

- `books`
- `books/{bookId}`
- `units/{unitId}`
- `design/{bookId}`
- `teach/{bookId}`
- `exam/{bookId}`
- `report`

## 修改时的高风险点

- 不要把 AID 当成单纯前端页面；它有后端三表、sync 合约、Android Room migration、teaching 接入。
- 不要只改后端 sync schema；Android `SyncDtos.kt`、`SyncPreview.kt`、`SyncRepository.kt` 也要对齐。
- 不要改 Room Entity 而忘记 `Migrations.kt` 和 `StudyDatabase.version`。
- 不要把 `/api/v1/graph` 写进新代码；当前知识图谱前缀是 `/api/v1/knowledge-graph`。
- 不要假设 Web 和 Android 教学共用同一路径；Android 有端侧离线教学仓库。
- 不要删除旧字段；同步和复习算法仍需兼容旧数据。
- 不要手工编辑 `.codegraph/codegraph.db`，只运行 `codegraph sync .`。

## 文档索引

- AI 快速入口：`README.md`
- 项目级规则：`AGENTS.md`、`CLAUDE.md`
- 模块文档：`docs/modules/`
- AID 交接：`docs/HANDOFF_AID_M5_M6.md`
- Android/跨端路线：`docs/mobile/roadmap.md`

## 接手建议

1. 先读 `README.md` 和本文。
2. 根据任务读 `docs/modules/<module>.md`。
3. 用 `codegraph context "<任务>"` 或 `rg` 查实际调用点。
4. 改动前确认后端 schema、Web 类型/API、Android DTO/Entity 是否需要一起改。
5. 改动后运行最小验证，并同步 CodeGraph。
