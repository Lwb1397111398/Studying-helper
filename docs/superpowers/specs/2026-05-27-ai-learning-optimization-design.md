# AI 分析模块优化设计

> 日期：2026-05-27
> 范围：`ai_learning`、`review`、`knowledge_graph` 三模块联动优化

---

## 一、现状诊断

### 核心流程（现在）

```
知识单元 → LLM 理解（摘要/要点/概念/难度）
        → LLM 自评（出题/答题/打分）
        → score < 80？→ 最多重学 3 轮
        → score ≥ 80 → 输出 LearnedUnit
```

### 问题清单

| 类别 | 问题 | 严重度 |
|------|------|--------|
| 学习科学 | LLM 自评打分无外部锚点，分数虚高 | 高 |
| 学习科学 | 学单元前不检查前置知识掌握度 | 高 |
| 学习科学 | 难度/重要度靠 LLM 拍脑袋，无用户数据校准 | 中 |
| 学习科学 | 迭代深化无方向性，prompt 不变，重学效果差 | 高 |
| LLM 效率 | 每单元 2-6 次 LLM 调用（理解+自评循环） | 高 |
| LLM 效率 | 自评是模拟考试，不如等用户真考 | 高 |
| LLM 效率 | 并发 3 但共享上下文加锁，并发优势被吃掉 | 中 |
| LLM 效率 | Token 预估拍脑袋（AVG_TOKENS_PER_UNIT = 2000） | 低 |
| 工程设计 | Router 全是 stub，没接 Service | 高 |
| 工程设计 | Service 和 Router 脱节，LLM client 未注入 | 高 |
| 工程设计 | 知识图谱和 AI 学习割裂，图谱不指导学习顺序 | 中 |
| 工程设计 | 掌握度评估（mastery_evaluator）和自评两套体系不互通 | 中 |
| 工程设计 | 答案匹配只做字符串包含，误判率高 | 中 |

---

## 二、优化方案

### 核心思路

**砍掉虚假自评，拥抱真实数据驱动。**

```
优化后：LLM 学 → 生成学习产物（摘要/要点/概念）
           ↓
      Teaching 模块讲解
           ↓
      Review 模块真实考试
           ↓
      Mastery 评估（5 维真实数据）
           ↓
      薄弱点反馈给下次学习排序
```

### 2.1 砍掉自评循环

**改什么：**

- 删除 `build_assess_prompt` 在 `learn_unit` 中的调用
- 删除 `SelfAssessment` 作为 `learn_unit` 返回的必需字段
- `learn_unit` 只做一次 LLM 理解调用，输出摘要/要点/概念/难度/重要度

**为什么：**

- LLM 自评 = 自己改自己作业，分数不可信
- 省 50%+ token 消耗
- 真实掌握度由 `review` 模块的用户答题数据评估，更准

**影响：**

- `LearnedUnit.self_assessment` 改为可选字段
- `learn_unit` 返回的 `needs_deepening` 标记由后续真实考试决定
- `max_iterations` 参数移除（不再需要迭代重学）

### 2.2 一次 Prompt 搞定理解

**现状：** 已经是 `build_understand_prompt` 一次调用产出摘要 + 要点 + 概念 + 难度。这块**保持不变**，已经是最佳实践。

### 2.3 知识图谱指导学习顺序

**改什么：**

- `AILearningService.learn_book` 学习前，先调 `KnowledgeGraphService` 获取拓扑排序
- 学单元 X 前，检查前置节点掌握度（从 `MasteryRecord` 查）
- 前置未掌握的，自动加入学习队列优先学

**新增方法：**

```python
async def get_learning_order(
    self,
    book_id: str,
    units: List[KnowledgeUnit],
) -> List[KnowledgeUnit]:
    """基于知识图谱拓扑排序 + 前置掌握度，返回优化后的学习顺序"""
```

**为什么：**

- 学习科学核心原则：先掌握前置，再学后续
- 知识图谱已经建了 `prerequisite` 关系，不用白不用
- 避免学生学到一半发现前置不会，体验断裂

### 2.4 真实用户数据校准

**改什么：**

- `LearnedUnit.difficulty_level` 初始值仍由 LLM 给（首次无数据）
- 用户每次复习/考试后，用 `mastery_evaluator.evaluate_mastery()` 的 5 维分数反向校准难度和重要度
- 校准公式：`adjusted_difficulty = llm_difficulty * 0.4 + actual_difficulty * 0.6`

**新增字段：**

```python
class LearnedUnit(BaseModel):
    # ... 现有字段 ...
    calibrated_difficulty: Optional[float] = None  # 用户数据校准后的难度
    calibration_count: int = 0  # 校准次数（用于加权）
```

**为什么：**

- LLM 给的难度是"通用难度"，实际难度因人而异
- 真实答题数据（正确率、速度、一致性）更能反映个体难度
- 校准次数越多，越准

### 2.5 Router 接真实 Service

**改什么：**

- 注入 `LLMClient` 到 Router（通过 `Depends(get_llm_client)`）
- `POST /{book_id}/learn` → 调 `AILearningService.learn_book`
- `GET /{book_id}/progress` → 查 `LearningRecord` + `MasteryRecord` 返回真实进度
- `GET /{book_id}/overview` → 调 `SelectiveLearningService.get_book_overview`

**影响：**

- 所有 stub 接口变成真实接口
- 需要处理异步学习任务的进度推送（SSE 或轮询）

### 2.6 并发模型优化

**现状：** `asyncio.Semaphore(3)` + `ctx_lock` 把并发优势吃掉

**改什么：**

- 移除 `ctx_lock` 对上下文读写的锁
- 改为无锁设计：每个单元独立构建上下文，学习完后再合并结果
- 上下文共享改为只读快照 + 追加式更新

```python
# 现在：锁保护读写
async with ctx_lock:
    context = self.optimizer.build_context(...)
result = await self.learn_unit(unit, context)
async with ctx_lock:
    previous_summary = result.summary  # 写共享状态

# 优化后：无锁，顺序依赖改为拓扑序保证
context = self.optimizer.build_context(unit, chapters, previous_summary_snapshot)
result = await self.learn_unit(unit, context)
previous_summary_snapshot = result.summary  # 单变量赋值是原子的
```

**注意：** `asyncio` 单线程内，简单变量赋值本身就是原子的，不需要锁。锁只保护多步复合操作。

### 2.7 Token 预估校准

**改什么：**

- 移除拍脑袋常量 `AVG_TOKENS_PER_UNIT = 2000`
- 改为基于实际内容长度计算：`estimated_tokens = len(prompt) / 4 + max_tokens * 0.3`
- 学习完成后记录实际 token 消耗，用于后续预估校准

**新增字段：**

```python
class CostEstimate:
    total_tokens: int
    estimated_cost_usd: float
    unit_count: int
    actual_tokens: Optional[int] = None  # 学习完成后回填
```

---

## 三、模块改动范围

### `ai_learning/service.py`

| 改动 | 类型 |
|------|------|
| 移除自评循环（`build_assess_prompt` 调用） | 删除 |
| `SelfAssessment` 从 `LearnedUnit` 必需改为可选 | 修改 |
| 新增 `get_learning_order()` 方法 | 新增 |
| 无锁并发重构 | 修改 |
| `calibrated_difficulty` 字段 | 新增 |

### `ai_learning/schemas.py`

| 改动 | 类型 |
|------|------|
| `LearnedUnit.self_assessment` 改为 `Optional` | 修改 |
| `LearnedUnit.calibrated_difficulty` / `calibration_count` | 新增 |

### `ai_learning/prompts.py`

| 改动 | 类型 |
|------|------|
| `build_assess_prompt` 函数标记为 deprecated | 保留但不用 |

### `ai_learning/token_optimizer.py`

| 改动 | 类型 |
|------|------|
| 移除拍脑袋常量，改为基于内容长度计算 | 修改 |
| `CostEstimate.actual_tokens` 字段 | 新增 |

### `ai_learning/router.py`

| 改动 | 类型 |
|------|------|
| 注入 `LLMClient` | 修改 |
| `POST /{book_id}/learn` 接真实 Service | 修改 |
| `GET /{book_id}/progress` 返回真实进度 | 修改 |
| `GET /{book_id}/overview` 接真实 Service | 修改 |

### `knowledge_graph/service.py`

| 改动 | 类型 |
|------|------|
| 新增拓扑排序方法 `get_topological_order()` | 新增 |

### `review/mastery_evaluator.py`

| 改动 | 类型 |
|------|------|
| 新增反向校准接口 `calibrate_unit_difficulty()` | 新增 |

---

## 四、数据流（优化后）

```
上传书籍
  ↓
document_parser: 解析 PDF/EPUB/TXT → 章节结构
  ↓
knowledge_splitter: 切块 → KnowledgeUnit[]
  ↓
knowledge_graph: 构建图谱 → 概念关系 + 前置依赖
  ↓
ai_learning (learn_book):
  1. 调 knowledge_graph.get_topological_order() 获取学习顺序
  2. 检查前置掌握度，未掌握的先学
  3. 一次 LLM 调用生成摘要/要点/概念
  4. 输出 LearnedUnit（无自评）
  ↓
teaching: 讲解（INTRO → CORE → CHECK → CONNECT）
  ↓
review: 真实考试（用户答题）
  ↓
mastery_evaluator: 5 维评估（正确率/速度/一致性/解释/应用）
  ↓
反向校准 ai_learning 的难度/重要度
  ↓
spaced_repetition: 安排下次复习时间
```

---

## 五、兼容性

- `build_assess_prompt` 保留但不调用，如果后续需要"快速自检"功能可以复用
- `SelfAssessment` 仍作为 schema 存在，只是 `LearnedUnit` 中改为可选
- Router 新增接口，旧 stub 接口标记 `deprecated`

---

## 六、成功标准

1. `learn_unit` LLM 调用从 2-6 次降为 1 次
2. 学习顺序由知识图谱拓扑排序决定，前置未掌握自动优先
3. 所有 Router 接口返回真实数据（非 stub）
4. 掌握度评估基于真实用户数据，非 LLM 自评
5. 所有现有测试通过（需更新 mock 和断言）
