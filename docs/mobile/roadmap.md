# Studying-helper 跨端与 Android 路线图

本文面向接手项目的 AI，用来快速判断 Android 和跨端同步当前状态。

## 总目标

Web 和 Android 都是一等客户端。Web 更适合导入、总览、复杂配置和教学设计；Android 更适合离线学习、复习、考试和轻量教学。两端通过同步包交换数据。

## 当前跨端架构

```text
后端 FastAPI + SQLite
  -> Web React
  -> 同步包 JSON
  -> Android Room
```

同步不是云同步。当前策略以导出、预览、覆盖式导入为主。

## 已完成能力

### 后端

- 全量同步包导出。
- 单本书同步包导出。
- 导入前预览。
- 覆盖式导入。
- 同步范围包含书籍、章节、知识单元、图谱、掌握度、注释、学习记录、教学记录、复习/考试、学习效率。
- 已加入 AID 三表和 `ai_cognitive_hint`。
- 掌握度同步包含 FSRS 字段。

### Web

- `/sync` 同步中心。
- 导出全部、导出单本、预览同步包、确认导入。
- `/books/:bookId/design` AID 教学设计页面。
- `/books/:bookId/teach` 教学会话。
- 书籍页提供学习、教学、复习、考试、图谱、导出等入口。

### Android

- Compose 单 Activity 导航。
- Room 本地数据库，当前 `version = 2`。
- `MIGRATION_1_2` 已加入 AID 三表和 `knowledge_units.ai_cognitive_hint`。
- 本地书籍、章节、知识单元管理。
- TXT/EPUB/PDF 基础导入。
- 本地 AI 配置，支持 OpenAI 兼容接口。
- 知识单元 AI 分析。
- AID 教学设计界面。
- 端侧教学页面和教学消息记录。
- 复习反馈和 FSRS 算法。
- 考试模式。
- 同步包导入导出。

## Android 关键文件

| 目标 | 文件 |
| --- | --- |
| 导航入口 | `android/app/src/main/java/com/studyinghelper/mobile/MainActivity.kt` |
| 书籍列表 | `BooksScreen.kt` |
| 教学设计 | `TeachingDesignScreen.kt` |
| 教学 | `TeachingScreen.kt` |
| 考试 | `ExamScreen.kt` |
| ViewModel | `ui/StudyViewModel.kt` |
| Room Entity | `data/db/Entities.kt` |
| DAO | `data/db/StudyDao.kt` |
| 数据库和版本 | `data/db/StudyDatabase.kt` |
| 迁移 | `data/db/Migrations.kt` |
| 同步 DTO | `data/sync/SyncDtos.kt` |
| 同步仓库 | `data/repository/SyncRepository.kt` |
| AID 仓库 | `data/repository/AdaptiveDesignRepository.kt` |
| AI 分析 | `data/repository/AiRepository.kt` |
| 教学 | `data/repository/TeachingRepository.kt` |
| 复习 | `data/repository/ReviewRepository.kt` |
| FSRS | `data/algorithm/FSRSAlgorithm.kt` |

## 后续优先级

### 1. 同步稳定性

- 加强后端 sync contract 和 Android DTO 对齐测试。
- 覆盖 AID 三表、FSRS 字段、`ai_cognitive_hint` 的端到端导入导出。
- 明确单书同步对全局统计的处理规则。

### 2. Android 教学体验

- 优化 AID design -> teach 的路径。
- 明确端侧教学使用 AID active module 的顺序。
- 改善教学阶段自动/手动推进体验。

### 3. Android 文档导入质量

- TXT/EPUB/PDF 已有基础版。
- PDF 扫描件仍需要 OCR 或 AI 解析。
- EPUB 复杂目录和脚注清理仍可优化。

### 4. 冲突合并

- 当前是覆盖式导入。
- 自动合并需要为书籍、知识单元、掌握度、AID 设计、教学记录分别定义规则。
- 不应在没有测试数据前贸然引入。

### 5. 云同步

- 需要账号、设备标识、服务端同步状态和冲突策略。
- 应在离线同步稳定后再做。

## 验证清单

```bash
# 后端同步
cd backend && python -m pytest app/modules/sync/tests/ -q

# AID 后端
cd backend && python -m pytest app/modules/adaptive_design/tests/ -q

# Android 单元测试
cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
$env:GRADLE_USER_HOME=(Resolve-Path '..\.gradle-ascii').Path
$env:Path="$env:JAVA_HOME\bin;$env:Path"
.\gradlew.bat :app:testDebugUnitTest
```

手动链路：

1. Web 导出全部同步包。
2. Android 导入 Web 包。
3. Android 新建/修改书籍、章节、知识单元、掌握度。
4. Android 导出同步包。
5. Web 预览并导入 Android 包。
6. 检查 AID 三表、`ai_cognitive_hint`、FSRS 字段是否保留。

## 坑位

- 改 Room Entity 必须改 migration。
- 改同步字段必须改后端 schema/service、Android DTO/Entity/Repository/Preview。
- Android 教学不等于 Web 教学页面的简单移植。
- AID 是跨端功能，不是单个页面功能。
- 不要把未完成的云同步设想写成当前能力。
