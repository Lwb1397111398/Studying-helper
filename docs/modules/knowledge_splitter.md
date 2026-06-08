# knowledge_splitter 模块

## 概述

将解析后的章节文本拆分为可学习的知识单元（KnowledgeUnit）。

## 文件结构

| 文件 | 职责 |
|------|------|
| `router.py` | API 路由（触发拆分、查询进度） |
| `schemas.py` | 请求/响应模型（SplitResult、KnowledgeUnit 等） |
| `service.py` | 拆分服务（协调拆分器、持久化到数据库） |
| `splitter.py` | 核心拆分算法 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/split/{book_id}` | 触发知识拆分 |
| GET | `/api/v1/split/{book_id}/progress` | 查询拆分进度 |

## 拆分算法

按优先级尝试切分：
1. **子标题切分**: 按章节内的子标题（h3/h4 等）拆分
2. **段落切分**: 按段落边界拆分，合并过短段落
3. **句子切分**: 按句号等标点拆分（最终 fallback）

切分后对每个单元生成：title、content、order_index、char_offset_start/end。

## 已知问题

| 严重度 | 问题 | 位置 |
|--------|------|------|
| 中等 | `text.find()` 偏移追踪 O(n*m) 复杂度，大文档性能差 | `splitter.py:~L86` |
| 中等 | `_split_by_sub_titles` 从未被传入实际 sub_titles，走的是死代码路径 | `splitter.py` |
| 低 | 拆分结果无质量校验（过长/过短单元无警告） | `service.py` |

## 优化建议

1. 偏移追踪改用预计算位置映射，O(1) 查找
2. 清理 `_split_by_sub_titles` 死代码或修复调用链
3. 添加单元长度校验（建议 min 50 字、max 5000 字）

## 测试覆盖

- `tests/test_splitter.py` — 存在
- `service.py` — 无独立测试
- `router.py` — 无测试
