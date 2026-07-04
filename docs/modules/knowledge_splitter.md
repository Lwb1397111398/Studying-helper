# knowledge_splitter 模块

## 职责

把 `ChapterModel` 中的章节文本拆成 `KnowledgeUnitModel`。知识单元是 AI 学习、知识图谱、教学、复习、同步的最小业务单位。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `router.py` | `/api/v1/split` 路由、拆分任务和进度 |
| `service.py` | 从章节读取文本、写入知识单元、更新书籍状态 |
| `splitter.py` | 拆分算法 |
| `schemas.py` | Chapter、Section、KnowledgeUnit、SplitResult 等模型 |
| `tests/test_splitter.py` | 拆分算法测试 |

## API 入口

前缀：`/api/v1/split`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/{book_id}` | 触发拆分 |
| GET | `/{book_id}/progress` | 查询拆分进度 |
| GET | `/{book_id}/result` | 查询拆分结果 |
| POST | `/{book_id}/sync` | 同步/修正拆分结果 |

## 拆分策略

优先级大致是：

```text
子标题
  -> 段落
  -> 句子
  -> 长文本硬切
```

目标是得到适合单次学习/复习的知识单元，而不是机械固定长度 chunk。

## 下游影响

`KnowledgeUnitModel` 会被这些模块使用：

- `ai_learning` 写摘要、讲解、概念、难度、重要度。
- `knowledge_graph` 建节点和边。
- `adaptive_design` 做模块重组并写 `ai_cognitive_hint`。
- `teaching` 按单元教学。
- `review` 生成复习/考试题。
- `sync` 和 Android 同步所有字段。

## 验证入口

```bash
cd backend && python -m pytest app/modules/knowledge_splitter/tests/ -q
```

## 已知风险

- 拆分粒度会直接影响 AI 成本、教学体验和复习题质量。
- 改 `KnowledgeUnit` schema 时必须检查后端 ORM、sync、Web 类型、Android Entity/DTO。
- 不要在 splitter 内引入强 LLM 依赖；拆分基础能力应离线可用。
