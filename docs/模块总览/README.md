# 模块总览索引

> 给老板（和接手的 AI）看的模块地图：每个模块一句话职责。想细看某个模块，先看这里定位，再进对应文件。

## 后端（backend/，FastAPI）

| 模块 | 职责 |
| --- | --- |
| user_storage | 用户、书籍、章节、知识单元的学习数据总仓 |
| document_parser | PDF/TXT/EPUB 解析成章节文本 |
| knowledge_splitter | 把章节文本拆成可学习的知识单元 |
| ai_learning | 调 LLM 做摘要、讲解、要点、概念、难度分析 |
| knowledge_graph | 知识图谱节点/边与前置依赖 |
| adaptive_design（AID） | 学习者画像 + 宏观教学设计 + 微观模块编排 |
| teaching | 交互式教学会话（阶段推进、问答、测试、笔记） |
| review | SM-2/FSRS 复习、考试、自由回忆、导出 |
| learning_plan | 学习计划和学习风格分析 |
| settings | 用户偏好、LLM 配置、.env 热更新 |
| sync | Web 与 Android 的离线同步包导入导出 |
| common | 统一错误、LLM client、共享 schema、时间工具 |

后端细节文档在 `docs/modules/`。

## Web 前端（frontend/，React + TypeScript）

| 页面/模块 | 职责 |
| --- | --- |
| router | 全部页面路由（书籍、上传、教学、复习、考试、同步、设置） |
| api/ | Axios 封装的后端接口层 |
| SyncCenter | 同步中心页（导入导出预览） |
| TeachingDesign / TeachingSession | AID 教学设计与教学会话页 |

## Android（android/，Kotlin + Compose）

| 模块 | 职责 |
| --- | --- |
| data/db | Room 本地库（Entities/DAO/Migrations） |
| data/repository | 端侧业务仓库（离线优先） |
| data/sync | 同步包 DTO 与导入导出 |
| data/algorithm | FSRS 复习算法 |
| data/update | **应用自更新**（检查/下载/安装），详见 `Android应用自更新模块总览.md` |
| ui/ | Compose 界面与 ViewModel |
| MainActivity | 导航入口（books/units/design/teach/exam/report） |

## 云端发版（.github/workflows/）

| 工作流 | 职责 |
| --- | --- |
| build-release.yml | 推代码自动构建 Release APK → 覆盖更新 latest Release，配合应用自更新模块 |
