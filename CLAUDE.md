# Studying-helper - AI 智能学习辅助系统

## 项目概述

基于 AI 的个人学习辅助系统，支持导入 PDF/TXT/EPUB 书籍，自动拆分知识单元，构建知识图谱，提供 AI 驱动的教学、复习和考试功能。

## 技术栈

### 后端
- **框架**: FastAPI + Uvicorn
- **数据库**: SQLAlchemy 2.0 (异步) + aiosqlite (SQLite)
- **数据验证**: Pydantic v2 + pydantic-settings
- **HTTP 客户端**: httpx (调用 LLM API)
- **文档解析**: pdfplumber (PDF), ebooklib (EPUB), chardet (编码检测)
- **认证**: PyJWT

### 前端
- **框架**: React 18 + TypeScript
- **构建工具**: Vite 5
- **样式**: Tailwind CSS 3
- **路由**: React Router v6
- **HTTP 客户端**: Axios

## 项目结构

```
├── backend/
│   ├── app/
│   │   ├── common/              # 共享组件
│   │   │   ├── errors.py        # ErrorCode 枚举 + ServiceError 异常
│   │   │   ├── llm_client.py    # LLM 客户端抽象 (OpenAI 兼容)
│   │   │   ├── schemas.py       # 共享 Pydantic 模型
│   │   │   └── time_utils.py    # 时间工具
│   │   ├── db/                  # 数据库层
│   │   │   ├── models.py        # SQLAlchemy ORM 模型
│   │   │   └── database.py      # 异步引擎和会话管理
│   │   ├── modules/             # 功能模块 (详见下方)
│   │   ├── config.py            # 全局配置 (Settings 类)
│   │   ├── deps.py              # FastAPI 依赖注入
│   │   └── main.py              # FastAPI 应用入口
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                 # API 调用封装
│   │   ├── components/          # 通用组件
│   │   ├── contexts/            # React Context (AppContext)
│   │   ├── pages/               # 页面组件
│   │   ├── router/              # 路由配置
│   │   └── types/               # TypeScript 类型定义
│   └── package.json
└── start.py                     # 一键启动脚本
```

## 模块详细文档

每个模块的详细分析（文件结构、已知问题、优化建议、测试覆盖）见 `docs/modules/` 目录：

| 模块 | 文档 | 核心职责 |
|------|------|---------|
| common | [common.md](docs/modules/common.md) | LLM 客户端、错误处理、共享模型 |
| document_parser | [document_parser.md](docs/modules/document_parser.md) | PDF/TXT/EPUB 文档解析 |
| knowledge_splitter | [knowledge_splitter.md](docs/modules/knowledge_splitter.md) | 章节文本拆分为知识单元 |
| knowledge_graph | [knowledge_graph.md](docs/modules/knowledge_graph.md) | 知识图谱构建与管理 |
| ai_learning | [ai_learning.md](docs/modules/ai_learning.md) | LLM 驱动的知识分析 |
| learning_plan | [learning_plan.md](docs/modules/learning_plan.md) | 个性化学习计划生成 |
| teaching | [teaching.md](docs/modules/teaching.md) | 交互式 AI 教学 |
| review | [review.md](docs/modules/review.md) | 间隔重复复习与考试 |
| settings | [settings.md](docs/modules/settings.md) | 用户偏好与 AI 配置 |
| user_storage | [user_storage.md](docs/modules/user_storage.md) | 书籍管理与学习统计 |

## 核心模块

每个模块遵循 `router.py` → `service.py` → `schemas.py` 的分层结构。

### 1. document_parser (文档解析)
- **职责**: 解析 PDF/TXT/EPUB 文件，提取章节结构和文本
- **解析器**: PDFParser, TXTParser, EPUBParser
- **API**: `/api/v1/documents`

### 2. knowledge_splitter (知识拆分)
- **职责**: 将章节文本拆分为可学习的知识单元 (KnowledgeUnit)
- **算法**: 按子标题 > 段落 > 句子的优先级切分
- **API**: `/api/v1/split`
- **关键类型**: KnowledgeUnit, Chapter, Section, SplitResult

### 3. knowledge_graph (知识图谱)
- **职责**: 构建和管理知识单元间的关系图谱
- **功能**: 拓扑排序、前置依赖分析、手动边管理
- **API**: `/api/v1/graph`
- **持久化**: KGNodeModel, KGEdgeModel

### 4. ai_learning (AI 学习)
- **职责**: LLM 驱动的知识分析 (摘要、要点、概念、难度评估)
- **特性**: 分层并发学习、拓扑排序优化学习顺序
- **API**: `/api/v1/learning`
- **依赖**: LLMClient, KnowledgeGraphService

### 5. teaching (教学)
- **职责**: 交互式 AI 教学会话
- **教学阶段**: 引入 → 讲解 → 类比 → 示例 → 检查 → 反思
- **策略**: 根据内容复杂度和用户掌握度动态选择
- **API**: `/api/v1/teaching`

### 6. learning_plan (学习计划)
- **职责**: 生成个性化学习方案和会话
- **特性**: 学习风格分析、自适应计划调整
- **API**: `/api/v1/plans`

### 7. review (复习)
- **职责**: 间隔重复复习、掌握度评估、考试模式
- **算法**: SM-2 间隔重复算法
- **导出**: Markdown, 思维导图
- **API**: `/api/v1/review`

### 8. settings (设置)
- **职责**: 用户偏好和 AI 配置管理
- **配置层级**: 模块级 > 全局默认 > 旧字段兼容
- **API**: `/api/v1/settings`
- **热更新**: LLM 配置变更后清除客户端缓存立即生效

### 9. user_storage (用户存储)
- **职责**: 书籍管理、学习进度、每日统计
- **API**: `/api/v1/books`, `/api/v1/mastery`, `/api/v1/stats`

## 数据库模型

```
User ─┬─< Book ─┬─< Chapter ─< KnowledgeUnit
      │         │                    │
      │         ├─< KGNode           ├─< MasteryRecord
      │         └─< KGEdge           │
      │                              └─< TeachingSession ─< TeachingMessage
      ├─< MasteryRecord
      └─< DailyStats
```

### 核心模型
- **BookModel**: 书籍元数据、解析/拆分/学习状态
- **ChapterModel**: 多级章节 (支持 编>章>节 层级)
- **KnowledgeUnitModel**: 知识单元 (最小可学习单位)
- **MasteryRecordModel**: 掌握度记录 (SM-2 算法参数)
- **KGNodeModel/KGEdgeModel**: 知识图谱节点和边

## LLM 配置

### 配置层级 (优先级从高到低)
1. **模块级**: `LLM_TEACHING_API_KEY`, `LLM_AI_ANALYSIS_MODEL`, etc.
2. **全局默认**: `LLM_DEFAULT_API_KEY`, `LLM_DEFAULT_MODEL`, `LLM_DEFAULT_BASE_URL`
3. **旧字段兼容**: `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`

### LLM 模块
- `teaching` - 教学策略 (类比/举例/对比生成、问答、测试)
- `ai_analysis` - AI 分析 (内容分析、出题、掌握度评估)
- `parser` - 文档解析 (目录识别、标题优化，LLM fallback)

### 并发控制
- `LLM_MAX_CONCURRENT`: 信号量控制并发请求数 (默认 4)
- 支持优雅关闭：拒绝新请求，等待在途请求完成

## 前端路由

```typescript
/                           # 首页 (书籍列表)
/upload                     # 上传书籍
/profile                    # 个人资料
/books/:bookId              # 书籍概览 (章节树、掌握度)
/books/:bookId/toc          # 目录确认
/books/:bookId/learn        # AI 学习会话
/books/:bookId/teach        # 交互式教学
/books/:bookId/review       # 复习会话
/books/:bookId/exam         # 考试模式
/books/:bookId/export       # 导出 (Markdown/思维导图)
/books/:bookId/plan         # 学习计划
/books/:bookId/graph        # 知识图谱可视化
/report                     # 学习报告
/settings                   # 设置 (用户偏好 + AI 配置)
```

## API 端点汇总

| 模块 | 前缀 | 主要端点 |
|------|------|---------|
| documents | `/api/v1/documents` | POST /upload, GET /{id}/status |
| split | `/api/v1/split` | POST /{book_id}, GET /{book_id}/progress |
| learning | `/api/v1/learning` | POST /{book_id}/learn, GET /{book_id}/progress |
| plans | `/api/v1/plans` | POST /{book_id}/generate, GET /{book_id}/current-session |
| teaching | `/api/v1/teaching` | POST /start, POST /{id}/message, POST /{id}/answer |
| review | `/api/v1/review` | GET /{book_id}/session, POST /{id}/answer |
| graph | `/api/v1/graph` | GET /{book_id}, POST /{book_id}/build, POST /{book_id}/edges |
| settings | `/api/v1/settings` | GET/PUT /preferences, GET/PUT /ai-config |
| books | `/api/v1/books` | GET /, GET /{id}, DELETE /{id} |
| mastery | `/api/v1/mastery` | GET /{book_id} |

## 错误处理

使用统一的 `ServiceError` 异常和 `ErrorCode` 枚举：

```python
class ErrorCode(str, Enum):
    NOT_FOUND = "NOT_FOUND"           # 404
    VALIDATION_ERROR = "VALIDATION_ERROR"  # 400
    PROCESSING_ERROR = "PROCESSING_ERROR"  # 500
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"  # 502
    RATE_LIMITED = "RATE_LIMITED"     # 429
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"  # 422
    DATABASE_ERROR = "DATABASE_ERROR" # 500
```

Router 层捕获 `ServiceError` 并转换为对应的 HTTP 状态码。

## 开发命令

### 启动项目
```bash
# 一键启动 (自动检测端口)
python start.py

# 或分别启动
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

### 测试
```bash
# 后端测试
cd backend && pytest

# 前端构建检查
cd frontend && npm run build
```

### 数据库
- 数据库文件: `backend/data/learning.db`
- 自动创建表 (启动时)
- 无需手动迁移

## 状态管理

### 前端 (AppContext)
```typescript
interface AppContextType {
  userId: string;              // 固定为 'anonymous'
  settings: UserSettings;      // 用户偏好
  settingsLoaded: boolean;     // 偏好是否已加载
  aiConfig: AIConfigResponse;  // AI 配置 (只读展示)
  refreshSettings: () => Promise<void>;
  saveSettings: (patch: Partial<UserSettings>) => Promise<void>;
  refreshAIConfig: () => Promise<void>;
  saveAIConfig: (config: AIConfigUpdate) => Promise<void>;
}
```

### 后端 (配置热更新)
- 用户偏好: 写入 `.env` 文件，立即生效
- AI 配置: 写入 `.env` + 更新内存 `settings` 对象 + 清除 LLM 客户端缓存

## 关键设计决策

1. **单用户模式**: 所有端点使用 `user_id="anonymous"`，无需认证
2. **模块级 LLM 配置**: 不同功能可使用不同的模型/密钥
3. **异步优先**: 全链路 async/await，包括数据库和 HTTP 调用
4. **拓扑排序学习**: 基于知识图谱的前置依赖优化学习顺序
5. **间隔重复**: SM-2 算法管理复习计划
6. **优雅关闭**: LLM 客户端支持拒绝新请求 + 等待在途请求

## 测试结构

```
backend/app/modules/
├── ai_learning/tests/
│   ├── test_learning_service.py
│   ├── test_schemas.py
│   ├── test_token_optimizer.py
│   └── mock_llm.py
├── document_parser/tests/
│   ├── test_pdf_parser.py
│   ├── test_txt_parser.py
│   ├── test_service.py
│   └── test_toc_detector_enhanced.py
├── knowledge_splitter/tests/
│   └── test_splitter.py
├── knowledge_graph/tests/
│   ├── test_graph_builder.py
│   ├── test_service.py
│   ├── test_router.py
│   └── test_relation_detector.py
├── learning_plan/tests/
│   └── test_plan_service.py
├── teaching/tests/
│   └── test_teaching_service.py
├── review/tests/
│   ├── test_spaced_repetition.py
│   ├── test_mastery_evaluator.py
│   ├── test_exporters.py
│   ├── test_exam_mode.py
│   └── test_service.py
├── settings/tests/
│   └── test_settings_service.py
└── user_storage/tests/
    ├── test_user_service.py
    ├── test_streak_service.py
    └── test_auth.py
```

## 环境变量 (.env)

```bash
# LLM 配置
LLM_DEFAULT_API_KEY=sk-xxx
LLM_DEFAULT_MODEL=gpt-4o-mini
LLM_DEFAULT_BASE_URL=https://api.openai.com/v1

# 模块级覆盖 (可选)
LLM_TEACHING_API_KEY=
LLM_TEACHING_MODEL=
LLM_AI_ANALYSIS_API_KEY=
LLM_PARSER_API_KEY=

# 并发控制
LLM_MAX_CONCURRENT=4

# 数据库
DB_URL=sqlite+aiosqlite:///./data/learning.db

# 文件存储
FILE_STORAGE_DIR=./data/files
BACKUP_DIR=./data/backups

# 用户偏好 (通过 Settings 页面管理)
DAILY_GOAL_MINUTES=30
DAILY_GOAL_UNITS=5
REVIEW_REMINDER=true
REMINDER_TIME=20:00
```
