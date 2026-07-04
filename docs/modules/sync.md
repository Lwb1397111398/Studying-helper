# sync 模块

## 职责

负责 Web/后端与 Android 之间的离线同步包导入导出、导入前预览和覆盖式导入。它不是云同步，也不是实时冲突合并。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `router.py` | `/api/v1/sync` 路由 |
| `schemas.py` | SyncPackage、各表 Sync DTO、预览/导入结果 |
| `service.py` | 导出、预览、导入、scope 校验、删除旧书数据 |
| `incremental_sync.py` | 增量同步实验/扩展 |
| `tests/test_sync_service.py` | 同步服务测试 |
| `tests/test_sync_contract.py` | 同步字段合约测试 |

## API 入口

前缀：`/api/v1/sync`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/export` | 导出全部同步包 |
| GET | `/books/{book_id}/export` | 导出单本书同步包 |
| POST | `/preview` | 导入前预览 |
| POST | `/import` | 导入同步包 |

## 同步包内容

`SyncPackage` 当前包含：

- `books`
- `chapters`
- `knowledge_units`
- `kg_nodes`
- `kg_edges`
- `mastery_records`
- `annotations`
- `learning_records`
- `daily_stats`
- `review_sessions`
- `teaching_sessions`
- `teaching_messages`
- `user_questions`
- `session_tests`
- `learning_efficiency`
- `learner_intent_profiles`
- `teaching_designs`
- `module_micro_plans`

其中 `knowledge_units` 包含 `ai_cognitive_hint`，`mastery_records` 包含 FSRS 字段。

## Android 对齐文件

- `android/app/src/main/java/com/studyinghelper/mobile/data/sync/SyncDtos.kt`
- `android/app/src/main/java/com/studyinghelper/mobile/data/sync/SyncPreview.kt`
- `android/app/src/main/java/com/studyinghelper/mobile/data/repository/SyncRepository.kt`
- `android/app/src/main/java/com/studyinghelper/mobile/data/db/Entities.kt`
- `android/app/src/main/java/com/studyinghelper/mobile/data/db/StudyDao.kt`

## 导入策略

- 通过 package 内 `user_id` 和 book scope 做基础校验。
- 同 ID 书籍采用覆盖式导入。
- 单书导出不应错误覆盖与该书无关的全局统计。
- 当前不做自动冲突合并。

## 验证入口

```bash
cd backend && python -m pytest app/modules/sync/tests/ -q

cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:GRADLE_USER_HOME=(Resolve-Path '..\.gradle-ascii').Path
$env:Path="$env:JAVA_HOME\bin;$env:Path"
.\gradlew.bat :app:testDebugUnitTest
```

## 已知风险

- 字段顺序/名称必须与后端 ORM 和 Android DTO 对齐，尤其 snake_case。
- 新增表时要同步 preview count、import count、contract tuple 和 Android 计数字段。
- 不要让同步包吞掉未知字段后静默丢数据。
