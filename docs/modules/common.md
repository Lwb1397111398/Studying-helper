# common / db 基础层

## 职责

`backend/app/common` 和 `backend/app/db` 是后端所有模块共享的底座。接手任何后端任务前，先理解这里的错误模型、LLM 调用方式、时间格式和数据库会话生命周期。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `backend/app/common/errors.py` | `ErrorCode`、`ServiceError`、HTTP 状态码映射 |
| `backend/app/common/llm_client.py` | OpenAI 兼容 LLM 客户端、并发信号量、优雅关闭 |
| `backend/app/common/schemas.py` | 共享 Pydantic 模型 |
| `backend/app/common/time_utils.py` | 时间工具 |
| `backend/app/common/json_utils.py` | JSON 兼容解析/序列化辅助 |
| `backend/app/common/mastery.py` | 掌握度等级/分数辅助 |
| `backend/app/db/database.py` | SQLAlchemy async engine、session、初始化 |
| `backend/app/db/models.py` | 全部 ORM 表模型 |
| `backend/app/config.py` | `.env` 配置、模块级 LLM 配置 |
| `backend/app/deps.py` | FastAPI 依赖注入、模块级 LLM client 缓存 |

## 当前核心约定

- 后端使用 FastAPI + SQLAlchemy 2.0 async + SQLite。
- 大多数路由通过 `get_db` 获取 `AsyncSession`。
- 单用户模式大量默认使用 `user_id="anonymous"`，认证能力存在但不是主路径。
- Router 层应把 `ServiceError` 交给全局异常处理，不要随意返回不一致的错误结构。
- LLM client 支持 OpenAI 兼容接口，配置按模块覆盖。

## LLM 配置

模块列表在 `backend/app/config.py`：

```python
LLM_MODULES = ["teaching", "ai_analysis", "parser", "aid"]
```

优先级：

```text
LLM_<MODULE>_*
  -> LLM_DEFAULT_*
  -> 旧字段 LLM_*
```

`LLM_MAX_CONCURRENT` 控制全局并发。应用关闭时 `main.py` 会拒绝新请求、等待在途请求，并关闭模块级 client。

## 数据模型提示

`models.py` 已不只是旧的 11 张表。当前包含：

- 基础学习表：users、books、chapters、knowledge_units、mastery_records、daily_stats。
- 图谱表：kg_nodes、kg_edges。
- 教学表：teaching_sessions、teaching_messages、user_questions、session_tests、learning_efficiency。
- 复习/记录表：review_sessions、annotations、learning_records。
- AID 表：learner_intent_profiles、teaching_designs、module_micro_plans。
- 兼容字段：`KnowledgeUnitModel.ai_cognitive_hint`、MasteryRecord 的 FSRS 字段。

## 验证入口

```bash
cd backend && python -m pytest app/tests/test_database_migrations.py -q
cd backend && python -m pytest app/modules/settings/tests/test_settings_service.py -q
```

## 已知风险

- 改 ORM 字段时要同步 sync schema、Android Entity/DTO 和迁移。
- LLM 配置热更新会影响已缓存 client，改 settings 逻辑时要检查 `deps.py` 的缓存清理。
- SQLite 自动建表不是正式迁移系统；生产式迁移能力有限。
