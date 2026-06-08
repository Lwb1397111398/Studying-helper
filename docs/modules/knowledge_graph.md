# knowledge_graph 模块

## 概述

构建和管理知识单元间的关系图谱，支持拓扑排序、路径查找、手动边管理。

## 文件结构

| 文件 | 职责 |
|------|------|
| `router.py` | API 路由（图谱构建、查询、边管理） |
| `schemas.py` | 请求/响应模型 |
| `service.py` | 图谱服务（CRUD、拓扑排序、路径查找） |
| `graph_builder.py` | 图谱构建器（从知识单元生成节点和边） |
| `relation_detector.py` | 关系检测器（自动发现单元间依赖） |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/graph/{book_id}` | 获取图谱 |
| POST | `/api/v1/graph/{book_id}/build` | 构建图谱 |
| POST | `/api/v1/graph/{book_id}/edges` | 添加手动边 |
| DELETE | `/api/v1/graph/{book_id}/edges/{id}` | 删除边 |
| GET | `/api/v1/graph/{book_id}/topo` | 拓扑排序 |
| GET | `/api/v1/graph/{book_id}/path` | 路径查找 |

## 关系类型

| 类型 | 语义 | 方向 |
|------|------|------|
| `depends_on` | A 依赖 B（学 A 前需先学 B） | A → B |
| `related_to` | A 与 B 相关 | 双向 |
| `part_of` | A 是 B 的一部分 | A → B |

## 已知问题

| 严重度 | 问题 | 位置 | 状态 |
|--------|------|------|------|
| **严重** | 拓扑排序使用错误的关系类型 `"prerequisite"` 而非 `"depends_on"`，导致排序完全失效 | `service.py:~L559,583` | **已修复** |
| **严重** | 拓扑排序边方向语义错误：`depends_on` 表示 A→B（A 依赖 B），但排序时反转了方向 | `service.py:~L559-560` | **已修复** |
| **严重** | `find_path` 未遵循有向边语义，双向遍历导致路径可能违反依赖顺序 | `service.py:~L208-210` | **已修复** |
| 中等 | `update_unit_graph` 更新单元时丢失已有概念 | `service.py:~L455-461` | 待修复 |
| 中等 | `update_unit_graph` 删除共享概念边范围过大，可能误删其他单元的边 | `service.py:~L376-381` | 待修复 |

## 优化建议

1. ~~**紧急修复**: 拓扑排序中 `"prerequisite"` → `"depends_on"`，并修正边方向~~ ✅ 已完成
2. ~~`find_path` 添加方向感知，只沿 `depends_on` 方向遍历~~ ✅ 已完成
3. `update_unit_graph` 改为增量更新而非全量替换
4. 添加图谱一致性校验（循环依赖检测、孤立节点检测）

## 测试覆盖

- `tests/test_graph_builder.py` — 存在
- `tests/test_service.py` — 存在
- `tests/test_router.py` — 存在
- `tests/test_relation_detector.py` — 存在
- **拓扑排序和路径查找的测试未覆盖方向性 bug**
