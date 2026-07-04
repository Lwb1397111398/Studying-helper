# knowledge_graph 模块

## 职责

构建和管理知识单元之间的图谱关系，用于学习顺序、前置依赖、跨章节概念聚类、复习干扰项和 AID 宏观重组。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `router.py` | `/api/v1/knowledge-graph` 路由 |
| `service.py` | 图谱持久化、查询、手动边管理 |
| `graph_builder.py` | 从知识单元构建节点和边 |
| `relation_detector.py` | 关系检测，包括前置、相似、对比等 |
| `schemas.py` | 图谱节点/边/可视化模型 |

## API 入口

前缀：`/api/v1/knowledge-graph`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/{book_id}/build` | 构建图谱 |
| GET | `/{book_id}` | 获取图谱 |
| GET | `/{book_id}/neighbors/{node_id}` | 邻居节点 |
| GET | `/{book_id}/path` | 路径查询 |
| GET | `/{book_id}/visualization` | 可视化数据 |
| POST | `/{book_id}/edges` | 新增手动边 |
| DELETE | `/{book_id}/edges/{edge_id}` | 删除边 |
| POST | `/{book_id}/units/{unit_id}` | 单元级图谱更新 |

## 重要说明

- 当前 API 前缀是 `/api/v1/knowledge-graph`，不是旧文档里可能出现的 `/api/v1/graph`。
- 图谱数据表是 `KGNodeModel`、`KGEdgeModel`。
- AID 的 `kg_adapter.py` 会读取图谱，把跨章节相关概念聚成学习模块。

## 数据流

```text
KnowledgeUnitModel
  -> relation_detector 识别关系
  -> graph_builder 生成 KGNode/KGEdge
  -> service 持久化
  -> ai_learning / adaptive_design / review / Web graph 使用
```

## 验证入口

```bash
cd backend && python -m pytest app/modules/knowledge_graph/tests/ -q
```

## 已知风险

- 关系类型会影响 AID 重组和复习题干扰项，改枚举或权重时要看下游。
- 手动边和自动边可能共存，删除逻辑不要误删用户编辑关系。
- 跨章节 `similar_to` / `contrasts_with` 对新教学体验很重要。
