# ai_learning 模块

## 职责

对知识单元进行 LLM 分析，写回摘要、讲解、要点、概念、先修、难度和重要度。它是 AID、教学、复习和知识图谱质量的上游。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `router.py` | `/api/v1/learning` 路由、学习进度、笔记、统计 |
| `service.py` | LLM 分析、结果解析、持久化 |
| `schemas.py` | LearnedUnit、Concept、KeyPoint、LearningSession 等模型 |
| `prompts.py` | AI 分析 prompt |
| `token_optimizer.py` | 输入压缩和 token 控制 |
| `token_optimizer_v2.py` | 新版 token 优化实验/扩展 |
| `tests/mock_llm.py` | 测试 LLM |

## API 入口

前缀：`/api/v1/learning`

常用端点：

- `POST /{book_id}/learn`
- `POST /{book_id}/learn-selected`
- `GET /{book_id}/progress`
- `GET /{book_id}/learn-progress`
- `GET /{book_id}/overview`
- `GET /units/{unit_id}`
- `POST /units/{unit_id}/notes`
- `POST /units/{unit_id}/mark`
- `POST /units/{unit_id}/relearn`
- `PUT /units/{unit_id}/enrich`
- `POST /units/{unit_id}/restore`
- `GET /stats`
- `GET /report`

## 数据流

```text
KnowledgeUnitModel.content
  -> token optimizer
  -> LLM ai_analysis client
  -> JSON 解析
  -> KnowledgeUnitModel.summary/explanation/key_points/concepts/prerequisites/difficulty_level/importance_score
  -> 图谱/AID/教学/复习使用
```

## 依赖关系

- 上游：`knowledge_splitter` 生成知识单元。
- 可选：`knowledge_graph` 拓扑排序优化学习顺序。
- 下游：`adaptive_design`、`teaching`、`review`、Web/Android 展示。

## 验证入口

```bash
cd backend && python -m pytest app/modules/ai_learning/tests/ -q
```

## 已知风险

- LLM 返回不稳定，service 必须能处理非标准 JSON 或缺字段。
- 大单元 token 控制会影响成本和质量。
- 改 LearnedUnit 字段时要检查 teaching、review、Android 内容解析和 sync。
