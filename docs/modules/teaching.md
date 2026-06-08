# teaching 模块

## 概述

交互式 AI 教学模块，基于教学策略提供个性化讲解、问答和测试。

## 文件结构

| 文件 | 职责 |
|------|------|
| `router.py` | API 路由（开始教学、发送消息、提交答案） |
| `schemas.py` | 请求/响应模型（TeachingStrategy、TeachingPhase 等） |
| `service.py` | 教学服务（会话管理、阶段推进、LLM 交互） |
| `strategies.py` | 教学策略选择（知识类型推断、认知层级、脚手架级别） |
| `prompts.py` | LLM prompt 模板 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/teaching/start` | 开始教学会话 |
| POST | `/api/v1/teaching/{session_id}/message` | 发送消息（通用交互） |
| POST | `/api/v1/teaching/{session_id}/answer` | 提交答案（检查阶段） |
| POST | `/api/v1/teaching/{session_id}/continue` | 手动推进到下一阶段 |
| POST | `/api/v1/teaching/{session_id}/question` | 提问（任意阶段） |
| POST | `/api/v1/teaching/{session_id}/test` | 生成测试题 |
| POST | `/api/v1/teaching/{session_id}/test/submit` | 提交测试答案 |
| POST | `/api/v1/teaching/{session_id}/complete` | 完成教学会话 |

## 教学阶段

```
ACTIVATE → INTRO → CORE → RETRIEVAL → CHECK → REFLECT → CONNECT
(激活旧知)  (引入)  (核心讲解) (检索练习) (检查理解) (反思) (知识连接)
```

- **RETRIEVAL**：在学习新内容前，从前置单元生成 2-3 个快速回忆问题，利用测试效应强化记忆
- 简单内容可跳过 INTRO、REFLECT、RETRIEVAL

## 教学策略

```python
@dataclass
class TeachingStrategy:
    explanation_style: str   # example_first / theory_first / analogy / problem_based
    visual_level: str        # high / medium / low
    interaction_frequency: str  # high / medium
    pace: str                # fast / normal / slow
    knowledge_type: str      # concept / procedure / principle / fact
    cognitive_level: str     # remember / understand / apply / analyze
    scaffold_level: str      # full / partial / minimal
    feedback_style: str      # immediate / guided / delayed
```

策略根据知识类型、难度、用户掌握度动态选择（见 `strategies.py`）。

## 已知问题

| 严重度 | 问题 | 位置 | 状态 |
|--------|------|------|------|
| **严重** | 阶段顺序错误：INTRO 在 CORE 之后，教学法上应在之前 | `strategies.py` | **已修复** |
| **严重** | `submit_answer` 传入 `should_advance=False` 时创建卡死状态，用户无法继续 | `service.py` | **已修复** |
| **严重** | `_advance_phase` 遇到未知阶段时抛出 ValueError 而非优雅处理 | `service.py:~L822` | **已修复** |
| 中等 | 掌握度等级不一致（4级 vs 5级） | `_score_to_level` | **已修复** |
| 中等 | 掌握度追踪使用 `max()`（只升不降） | `_schedule_reviews` | **已修复** |
| 中等 | God Object：1379 行、30+ 方法，职责过多 | `service.py` | 待重构 |
| 中等 | 掌握度追踪使用硬编码 `user_id="anonymous"` | `service.py` | 待修复 |

## 优化建议

1. ~~**修正阶段顺序**: `ACTIVATE → INTRO → CORE → CHECK → REFLECT → CONNECT`~~ ✅ 已完成
2. ~~`submit_answer` 移除自动推进，添加 `/continue` 端点供手动推进~~ ✅ 已完成
3. ~~`_advance_phase` 添加默认处理，未知阶段回退到第一个阶段~~ ✅ 已完成
4. ~~添加 RETRIEVAL 阶段（检索练习）~~ ✅ 已完成
5. ~~掌握度等级统一为5级，`max()` 改为加权移动平均~~ ✅ 已完成
6. 拆分 service.py：
   - `session_manager.py` — 会话 CRUD
   - `phase_handler.py` — 阶段推进逻辑
   - `content_generator.py` — LLM 内容生成
7. 掌握度追踪接入实际用户系统

## 测试覆盖

- `tests/test_teaching_service.py` — 存在
- **策略选择（strategies.py）— 无独立测试**
- **router.py — 无测试**
- 阶段推进逻辑 — 测试不足
