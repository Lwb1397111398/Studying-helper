# Android 端侧数据模块总览

> 最后更新：2026-10-28（R1b 补建；覆盖 data/db + data/repository + data/sync + data/algorithm 四子域）

## 模块职责（一句话）

Android 离线优先客户端的数据底座：Room 本地库存全部学习数据，仓库层调度业务与算法，同步模块用 JSON 包与 Web 双向搬数据，FSRS 算法在端侧独立算复习调度（不依赖后端）。

## 运作流程（真实数据流）

以「同步一次 + 复习一次」为例，数据这样流动：

1. **同步导入**：`data/sync/SyncDtos.kt` 用 kotlinx.serialization 把同步包 JSON 反序列化成 `Sync*` DTO（`Json { ignoreUnknownKeys = true }`，旧版包多出的/缺少的字段都安全）。`data/repository/SyncRepository.kt:importPackage` 先删该书既有数据（`dao.deleteTeachingSessions(bookIds)` 等 delete+add 重放语义），再把 DTO 经 `toEntity()` 扩展函数转成 Room Entity 插库。Android 端所有记录的 `user_id` 一律改写为 `"anonymous"`（单用户）。
2. **本地存储**：`data/db/Entities.kt` 定义 18 张 Room 表（books/chapters/knowledge_units/mastery_records/kg_nodes/kg_edges/teaching_sessions/teaching_messages/…）。`StudyDatabase.kt` 是唯一入口（version 4，`addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4)`），`StudyDao.kt` 暴露查询，`Migrations.kt` 存 ALTER TABLE 迁移语句。
3. **业务调度**：`data/repository/` 各仓库（BookRepository/TeachingRepository/ReviewRepository/SyncRepository/AiRepository 等）组合 DAO、LLM 配置和算法，离线完成建书、AI 分析、教学、考试。
4. **复习计算**：`data/algorithm/FSRSAlgorithm.kt` 是纯算法（FSRS v4，17 参数）。`ReviewRepository.kt:47` 用**已有实体**构造 `FSRSState`（直通存量 stability/difficulty/lastReview，与后端 R4 修复后语义一致）；`nextReview(state, grade, now)` 返回 `FSRSResult`，仓库把结果回写实体（`lapses = result.lapses`、`stability = result.stability` 等）。
5. **同步导出**：`SyncRepository.kt:exportAll` 把全库 Entity 经 `toSync()` 扩展转回 `Sync*` DTO，序列化成 JSON 包（`schema_version: "1.0"`，source=`android`）。

## Android ↔ 后端 sync 字段对齐清单（v2 教学会话三字段，R1a/R1b 补齐）

| 后端 DB 列（TeachingSessionModel） | 后端 sync DTO（SyncTeachingSession） | Android DTO（SyncTeachingSession） | Android Room 列（TeachingSessionEntity） | 迁移语句 |
| --- | --- | --- | --- | --- |
| `state_v2`（String, nullable） | `state_v2: str \| None = None` | `@SerialName("state_v2") stateV2: String? = null` | `@ColumnInfo("state_v2") stateV2: String? = null` | `ALTER TABLE teaching_sessions ADD COLUMN state_v2 TEXT` |
| `asset_id`（String, nullable） | `asset_id: str \| None = None` | `@SerialName("asset_id") assetId: String? = null` | `@ColumnInfo("asset_id") assetId: String? = null` | `ALTER TABLE teaching_sessions ADD COLUMN asset_id TEXT` |
| `completion_status`（String, nullable） | `completion_status: str \| None = None` | `@SerialName("completion_status") completionStatus: String? = null` | `@ColumnInfo("completion_status") completionStatus: String? = null` | `ALTER TABLE teaching_sessions ADD COLUMN completion_status TEXT` |

v1 教学会话三字段为 null/None，双向同步时按 null 透传；后端导入为 delete+add 重放，默认 None 保证旧包零破坏。

## 入口文件清单

- `data/db/StudyDatabase.kt`（Room 入口，version 4）
- `data/db/Entities.kt`（18 张表定义）
- `data/db/StudyDao.kt`（全部查询）
- `data/db/Migrations.kt`（MIGRATION_1_2/2_3/3_4）
- `data/sync/SyncDtos.kt`（同步包 DTO 全集）
- `data/repository/SyncRepository.kt`（导入导出 + toEntity/toSync 映射）
- `data/repository/ReviewRepository.kt`（端侧复习 + FSRS 状态读写）
- `data/algorithm/FSRSAlgorithm.kt`（FSRS v4 纯算法 + FSRSState/FSRSResult）

## 对外接口 / 被谁调用

- `ui/` 各 ViewModel 调仓库层；`MainActivity.kt` 导航的 6 个页面全部读写本模块。
- 同步 JSON 包的另一半在 Web 后端 `backend/app/modules/sync/`（契约：后端 `SyncTeachingSession` pydantic ↔ 本端 `SyncTeachingSession` kotlinx，字段 snake_case 对齐）。

## 依赖的上游模块

无后端依赖（离线优先）；`data/update`（应用自更新，另有独立总览）与本模块平行。

## 关键数据结构

- `SyncPackage`（kotlinx DTO 根）：schema_version/exported_at/source + books/chapters/units/mastery/teaching_sessions/…
- `FSRSState`：stability/difficulty/elapsedDays/scheduledDays/reps/lapses/lastReview
- `FSRSResult`：nextReview/stability/difficulty/scheduledDays/retrievability/lapses

## 已知坑与约束

1. **同步是 delete+add 重放，不是增量合并**：导入会先删该书全部既有数据再插包内容；包里没有的数据会丢（两端一致语义，见 `docs/modules/sync.md`）。
2. **改 Room Entity 必须三件套**：Entities.kt 加列 + Migrations.kt 加 ALTER + StudyDatabase.version+1 并在 addMigrations 注册；漏迁移会在真机升级时崩（Room 不会自动补救，本项目未用 fallbackToDestructiveMigration）。v2 三字段迁移已做 SQL 实执行验证（`docs/superpowers/plans/logs/r1b_migration_sql_evidence.txt`）。
3. **两端 FSRS 默认参数一致性靠人工对齐**：后端 `review/fsrs.py DEFAULT_PARAMETERS` 与 Android `FSRSAlgorithm.DEFAULT_PARAMETERS` 是两份手抄数组，改一边必须同步另一边，否则两端调度结果分叉。
4. **两端 FSRS quality→grade 映射不同层**：后端把 quality 0-5 映射成 grade（`_quality_to_grade`），Android 的 `calculateQuality` 直接产出 grade——改映射口径时两端都要动。
5. Android 测试基建：Robolectric（`SyncRepositoryPersistenceTest`）+ 纯 JUnit；无 room-testing 依赖，迁移语句用字符串断言（`SyncDtosTest`）+ SQL 实执行证据护航。

## 验证命令

```powershell
# Windows PowerShell（仓库根）
cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:GRADLE_USER_HOME=(Resolve-Path '..\.gradle-ascii').Path
.\gradlew.bat :app:testDebugUnitTest --rerun-tasks
```

（测试入口：`SyncDtosTest`、`SyncRepositoryPersistenceTest`、`FSRSAlgorithmTest`）
