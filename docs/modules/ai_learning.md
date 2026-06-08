# ai_learning 模块

## 概述

LLM 驱动的知识分析模块，负责对知识单元进行摘要、要点提取、概念识别、难度评估。

## 文件结构

| 文件 | 职责 |
|------|------|
| `router.py` | API 路由（触发学习、查询进度） |
| `schemas.py` | 请求/响应模型（LearnedUnit、Concept、KeyPoint 等） |
| `service.py` | 学习服务（LLM 调用、结果解析、持久化） |
| `prompts.py` | LLM prompt 模板 |
| `token_optimizer.py` | Token 优化器（控制 LLM 输入长度） |
| `tests/mock_llm.py` | 测试用 LLM mock |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/learning/{book_id}/learn` | 触发全书学习 |
| GET | `/api/v1/learning/{book_id}/progress` | 查询学习进度 |

## 学习流程

```
获取知识单元 → 拓扑排序（可选）
  → 逐单元调用 LLM 分析
    → 解析 LLM 返回的 JSON（摘要/要点/概念/难度/重要性）
      → 更新 KnowledgeUnitModel
```

## 并发机制

- 按拓扑层级分批，同层单元可并发
- 信号量控制 LLM 并发数（`LLM_MAX_CONCURRENT`）

## 已知问题

| 严重度 | 问题 | 位置 |
|--------|------|------|------|
| 中等 | 魔法哨兵值：`difficulty=3` 和 `importance=0.5` 被视为"未返回"，与实际值冲突 | `service.py:~L1003` | **已修复** |
| 中等 | `token_cost` 对大单元始终返回 0，无法统计实际消耗 | `service.py:~L326` | **已修复** |
| 中等 | 连续学习天数查询存在 N+1 问题 | `router.py:~L273-288` | **已修复** |
| 低 | LLM 返回非 JSON 时解析失败，无重试 | `service.py` | 待修复 |

## 优化建议

1. ~~用 `None` 替代魔法哨兵值（`difficulty=None` 表示未返回）~~ ✅ 已完成
2. ~~修复 token_cost 计算：大单元通过 `_last_large_unit_tokens` 累计追踪~~ ✅ 已完成
3. ~~连续天数改用 `StreakService` 单条查询~~ ✅ 已完成
4. LLM 返回解析失败时添加一次重试（换 prompt 格式）

## 测试覆盖

- `tests/test_learning_service.py` — 存在
- `tests/test_schemas.py` — 存在
- `tests/test_token_optimizer.py` — 存在
- `tests/mock_llm.py` — 测试辅助
- **router.py — 测试不足**（N+1 问题未被发现）
