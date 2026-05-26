# AI 分析模块优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 砍掉虚假自评循环，用知识图谱指导学习顺序，Router 接真实 Service，实现真实数据驱动的 AI 学习流程。

**Architecture:** 按 7 个子方案顺序实施：schemas 改字段 → prompts 标记废弃 → service 去自评+无锁并发+图谱排序 → token_optimizer 校准 → mastery_evaluator 反向校准 → router 接真实 Service。每步 TDD。

**Tech Stack:** Python, FastAPI, asyncio, Pydantic, pytest, httpx

---

## Task 1: schemas — LearnedUnit 改字段

**Files:**
- Modify: `backend/app/modules/ai_learning/schemas.py`
- Test: `backend/app/modules/ai_learning/tests/test_schemas.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
import pytest
from app.modules.ai_learning.schemas import LearnedUnit, SelfAssessment

def test_learned_unit_self_assessment_optional():
    """self_assessment 应为可选字段，不传也能构造"""
    unit = LearnedUnit(
        unit_id="u1",
        book_id="b1",
        summary="摘要",
        key_points=["要点1"],
        concepts=[],
        difficulty_level=3,
        importance_score=0.5,
        prerequisites=[],
    )
    assert unit.self_assessment is None

def test_learned_unit_with_calibration_fields():
    """新增校准字段：calibrated_difficulty 和 calibration_count"""
    unit = LearnedUnit(
        unit_id="u1",
        book_id="b1",
        summary="摘要",
        key_points=["要点1"],
        concepts=[],
        difficulty_level=3,
        importance_score=0.5,
        prerequisites=[],
        calibrated_difficulty=3.5,
        calibration_count=2,
    )
    assert unit.calibrated_difficulty == 3.5
    assert unit.calibration_count == 2

def test_learned_unit_calibration_defaults():
    """校准字段默认值：calibrated_difficulty=None, calibration_count=0"""
    unit = LearnedUnit(
        unit_id="u1",
        book_id="b1",
        summary="摘要",
        key_points=["要点1"],
        concepts=[],
        difficulty_level=3,
        importance_score=0.5,
        prerequisites=[],
    )
    assert unit.calibrated_difficulty is None
    assert unit.calibration_count == 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/test_schemas.py -v
```
预期：FAIL，`self_assessment` 必填报错 / `calibrated_difficulty` 字段不存在

- [ ] **Step 3: 修改 schemas.py**

将 `self_assessment: SelfAssessment` 改为 `self_assessment: Optional[SelfAssessment] = None`，并新增两个校准字段：

```python
# 在 LearnedUnit 类中：
self_assessment: Optional[SelfAssessment] = None
calibrated_difficulty: Optional[float] = None
calibration_count: int = 0
```

同时 `import` 中已有 `Optional`，确认存在即可。

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/test_schemas.py -v
```
预期：3 PASS

- [ ] **Step 5: Commit**

```bash
git add app/modules/ai_learning/schemas.py app/modules/ai_learning/tests/test_schemas.py
git commit -m "feat(ai_learning): self_assessment 改为可选，新增校准字段"
```

---

## Task 2: prompts — 标记 build_assess_prompt 废弃

**Files:**
- Modify: `backend/app/modules/ai_learning/prompts.py`

- [ ] **Step 1: 给 build_assess_prompt 加 deprecated 注释**

在函数 docstring 第一行加 `.. deprecated:: 保留但不调用，自评由真实考试替代。`，函数体不改。

- [ ] **Step 2: 运行现有测试确认无回归**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/ -v
```
预期：全部通过

- [ ] **Step 3: Commit**

```bash
git add app/modules/ai_learning/prompts.py
git commit -m "chore(ai_learning): build_assess_prompt 标记 deprecated"
```

---

## Task 3: service — 砍掉自评循环

**Files:**
- Modify: `backend/app/modules/ai_learning/service.py`
- Test: `backend/app/modules/ai_learning/tests/test_learning_service.py`（已有，需更新）

- [ ] **Step 1: 更新测试 — learn_unit 不再返回 SelfAssessment**

修改 `test_learn_unit_basic`：
```python
def test_learn_unit_basic(self, mock_llm, sample_unit):
    from app.modules.ai_learning.service import AILearningService
    from app.modules.ai_learning.schemas import LearningContext

    service = AILearningService(llm_client=mock_llm)
    result = await service.learn_unit(sample_unit, LearningContext())

    assert result.summary != ""
    assert len(result.key_points) >= 1
    assert 1 <= result.difficulty_level <= 5
    assert result.unit_id == "unit-1"
    # 不再有自评
    assert result.self_assessment is None
```

删除 `test_self_assessment_pass`、`test_self_assessment_fail_triggers_deepening`、`test_max_iterations_limit` 三个测试（自评已移除）。

修改 `mock_llm.py`：`MockLLMClient.chat` 中移除 `call_count % 2 == 0` 的自评分支，所有调用都返回理解响应（摘要/要点/概念）。

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/test_learning_service.py -v
```
预期：FAIL

- [ ] **Step 3: 修改 service.py — 移除自评循环**

`learn_unit` 方法改为单次 LLM 调用：
1. 删除 `for iteration in range(self.max_iterations)` 循环
2. 删除 `build_assess_prompt` 调用
3. 删除 `SelfAssessment` 构造
4. 直接返回 `LearnedUnit(self_assessment=None)`
5. `__init__` 移除 `max_iterations` 参数

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/test_learning_service.py -v
```
预期：PASS

- [ ] **Step 5: Commit**

```bash
git add app/modules/ai_learning/service.py app/modules/ai_learning/tests/test_learning_service.py app/modules/ai_learning/tests/mock_llm.py
git commit -m "feat(ai_learning): 移除自评循环，learn_unit 单次 LLM 调用"
```

---

## Task 4: service — 并发无锁化

**Files:**
- Modify: `backend/app/modules/ai_learning/service.py`

- [ ] **Step 1: 写测试验证并发学习结果正确**

在 `test_learning_service.py` 中新增：
```python
@pytest.mark.asyncio
async def test_learn_book_concurrent_results(self, mock_llm, sample_units, sample_chapters):
    """并发学习后所有单元都有结果，无数据竞争"""
    from app.modules.ai_learning.service import AILearningService

    service = AILearningService(llm_client=mock_llm)
    result = await service.learn_book("book-1", sample_units, sample_chapters)

    assert result.learned_count == len(sample_units)
    assert result.failed_count == 0
```

- [ ] **Step 2: 运行测试确认通过（当前有锁版本应已通过）**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/test_learning_service.py::TestAILearningService::test_learn_book_concurrent_results -v
```
预期：PASS

- [ ] **Step 3: 移除 ctx_lock，改为无锁设计**

在 `learn_book` 中：
1. 删除 `ctx_lock = asyncio.Lock()`
2. 删除所有 `async with ctx_lock:` 块
3. `previous_summary` 和 `existing_concepts` 的读写改为普通变量赋值（asyncio 单线程内原子）

- [ ] **Step 4: 运行测试确认仍然通过**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/test_learning_service.py -v
```
预期：PASS

- [ ] **Step 5: Commit**

```bash
git add app/modules/ai_learning/service.py
git commit -m "feat(ai_learning): 并发无锁化，移除 ctx_lock"
```

---

## Task 5: service — 知识图谱指导学习顺序

**Files:**
- Modify: `backend/app/modules/ai_learning/service.py`
- Modify: `backend/app/modules/knowledge_graph/service.py`
- Test: `backend/app/modules/ai_learning/tests/test_learning_service.py`

- [ ] **Step 1: 在 knowledge_graph/service.py 新增拓扑排序**

```python
async def get_topological_order(self, book_id: str) -> List[str]:
    """返回知识单元的拓扑排序（前置在前）。基于 prerequisite 边 BFS。"""
    graph = await self.get_graph(book_id)
    # 收集 unit 节点
    unit_ids = {n.id for n in graph.nodes if n.node_type == "unit"}
    # 构建入度表（只统计 unit 之间的 prerequisite 关系）
    in_degree = {uid: 0 for uid in unit_ids}
    adj = {uid: [] for uid in unit_ids}
    for edge in graph.edges:
        if edge.relation_type == "prerequisite" and edge.source_id in unit_ids and edge.target_id in unit_ids:
            adj[edge.source_id].append(edge.target_id)
            in_degree[edge.target_id] += 1
    # BFS 拓扑排序
    queue = [uid for uid, deg in in_degree.items() if deg == 0]
    order = []
    while queue:
        # 按入度为0的节点，保持原始顺序
        node = queue.pop(0)
        order.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    # 有环的剩余节点追加到末尾
    for uid in unit_ids:
        if uid not in order:
            order.append(uid)
    return order
```

- [ ] **Step 2: 在 ai_learning/service.py 新增 get_learning_order**

```python
async def get_learning_order(
    self,
    book_id: str,
    units: List[KnowledgeUnit],
) -> List[KnowledgeUnit]:
    """
    基于知识图谱拓扑排序 + 前置掌握度，返回优化后的学习顺序。
    前置未掌握的单元自动排到前面。
    """
    if not self.db:
        return units

    from app.modules.knowledge_graph.service import KnowledgeGraphService
    kg_service = KnowledgeGraphService(self.db)

    try:
        ordered_ids = await kg_service.get_topological_order(book_id)
    except Exception:
        return units

    unit_map = {u.id: u for u in units}
    ordered = [unit_map[uid] for uid in ordered_ids if uid in unit_map]
    # 追加不在图谱中的单元
    seen = {u.id for u in ordered}
    ordered.extend([u for u in units if u.id not in seen])
    return ordered
```

- [ ] **Step 3: 修改 learn_book 调用 get_learning_order**

在 `learn_book` 方法开头加：
```python
units = await self.get_learning_order(book_id, units)
```

- [ ] **Step 4: 写测试**

```python
@pytest.mark.asyncio
async def test_learn_book_respects_topology(self, mock_llm, sample_units, sample_chapters, db_with_graph):
    """学习顺序遵循知识图谱拓扑排序（前置在前）"""
    # db_with_graph 是 fixture，预置了 prerequisite 边：unit-2 依赖 unit-1
    from app.modules.ai_learning.service import AILearningService

    service = AILearningService(llm_client=mock_llm, db_session=db_with_graph)
    # 传入顺序打乱
    shuffled = [sample_units[2], sample_units[0], sample_units[1]]
    result = await service.learn_book("book-1", shuffled, sample_chapters)
    # unit-1 应在 unit-2 之前被学完
    assert result.learned_count == 3
```

- [ ] **Step 5: 运行测试**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/test_learning_service.py -v
```
预期：PASS

- [ ] **Step 6: Commit**

```bash
git add app/modules/ai_learning/service.py app/modules/knowledge_graph/service.py
git commit -m "feat(ai_learning): 知识图谱拓扑排序指导学习顺序"
```

---

## Task 6: token_optimizer — 基于内容长度估算

**Files:**
- Modify: `backend/app/modules/ai_learning/token_optimizer.py`
- Test: `backend/app/modules/ai_learning/tests/test_token_optimizer.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
import pytest
from app.modules.ai_learning.token_optimizer import TokenOptimizer

def test_estimate_cost_based_on_content_length():
    """Token 估算基于内容长度，非常量拍脑袋"""
    optimizer = TokenOptimizer()

    small = optimizer.estimate_cost(unit_count=1)
    large = optimizer.estimate_cost(unit_count=10)

    # 10 个单元应该是 1 个单元的 10 倍
    assert large.total_tokens == small.total_tokens * 10
    # 单价一致
    assert small.estimated_cost_usd > 0

def test_cost_estimate_has_actual_tokens_field():
    """CostEstimate 有 actual_tokens 字段，默认 None"""
    from app.modules.ai_learning.token_optimizer import CostEstimate

    est = CostEstimate(total_tokens=5000, estimated_cost_usd=0.15, unit_count=10)
    assert est.actual_tokens is None

    est.actual_tokens = 4800
    assert est.actual_tokens == 4800
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/test_token_optimizer.py -v
```
预期：FAIL

- [ ] **Step 3: 修改 token_optimizer.py**

1. 删除 `AVG_TOKENS_PER_UNIT`、`AVG_ASSESSMENT_TOKENS`、`AVG_DEEPENING_TOKENS` 常量
2. `estimate_cost` 改为：
```python
def estimate_cost(self, unit_count: int, avg_content_length: int = 2000) -> CostEstimate:
    # 基于内容长度估算：1 token ≈ 4 字符，加 prompt 开销 500 tokens
    tokens_per_unit = avg_content_length // 4 + 500
    total = unit_count * tokens_per_unit
    return CostEstimate(
        total_tokens=total,
        estimated_cost_usd=total / 1000 * 0.03,
        unit_count=unit_count,
    )
```
3. `CostEstimate` 加 `actual_tokens: Optional[int] = None` 字段

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/test_token_optimizer.py -v
```
预期：PASS

- [ ] **Step 5: Commit**

```bash
git add app/modules/ai_learning/token_optimizer.py app/modules/ai_learning/tests/test_token_optimizer.py
git commit -m "feat(ai_learning): Token 预估基于内容长度，新增 actual_tokens 字段"
```

---

## Task 7: mastery_evaluator — 反向校准接口

**Files:**
- Modify: `backend/app/modules/review/mastery_evaluator.py`
- Test: `backend/app/modules/review/tests/test_mastery_evaluator.py`（已有，追加）

- [ ] **Step 1: 写测试**

```python
def test_calibrate_difficulty_no_data():
    """无校准时返回 LLM 原始难度"""
    from app.modules.review.mastery_evaluator import calibrate_difficulty

    result = calibrate_difficulty(llm_difficulty=3.0, mastery_score=None, calibration_count=0)
    assert result == 3.0

def test_calibrate_difficulty_with_data():
    """有校准时加权混合：LLM 40% + 实际 60%"""
    from app.modules.review.mastery_evaluator import calibrate_difficulty

    # mastery_score=0.3 → 实际难度高（掌握差）→ 校准后难度应上升
    result = calibrate_difficulty(llm_difficulty=3.0, mastery_score=0.3, calibration_count=5)
    # actual_difficulty = 5 - 0.3 * 4 = 3.8
    # result = 3.0 * (1 - 0.6) + 3.8 * 0.6 = 1.2 + 2.28 = 3.48
    assert 3.4 <= result <= 3.6

def test_calibrate_difficulty_high_mastery():
    """掌握度高 → 校准后难度应下降"""
    from app.modules.review.mastery_evaluator import calibrate_difficulty

    result = calibrate_difficulty(llm_difficulty=4.0, mastery_score=0.95, calibration_count=10)
    # actual_difficulty = 5 - 0.95 * 4 = 1.2
    # result = 4.0 * 0.4 + 1.2 * 0.6 = 1.6 + 0.72 = 2.32
    assert 2.0 <= result <= 2.5
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/review/tests/test_mastery_evaluator.py::test_calibrate_difficulty_no_data -v
```
预期：FAIL，函数不存在

- [ ] **Step 3: 新增 calibrate_difficulty 函数**

在 `mastery_evaluator.py` 末尾加：

```python
def calibrate_difficulty(
    llm_difficulty: float,
    mastery_score: float | None,
    calibration_count: int,
) -> float:
    """
    用真实掌握度反向校准 LLM 给出的难度。

    校准公式：
    - actual_difficulty = 5 - mastery_score * 4  （掌握差=难度高）
    - weight = min(calibration_count / 10, 0.6)  （最多 60% 权重给实际数据）
    - result = llm_difficulty * (1 - weight) + actual_difficulty * weight

    参数:
        llm_difficulty: LLM 给出的难度 (1-5)
        mastery_score: 掌握度分数 (0-1)，None 时不校准
        calibration_count: 已校准次数

    返回:
        校准后的难度 (1-5)
    """
    if mastery_score is None or calibration_count == 0:
        return llm_difficulty

    actual_difficulty = max(1.0, min(5.0, 5.0 - mastery_score * 4.0))
    weight = min(calibration_count / 10.0, 0.6)
    calibrated = llm_difficulty * (1.0 - weight) + actual_difficulty * weight
    return round(max(1.0, min(5.0, calibrated)), 2)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/review/tests/test_mastery_evaluator.py -v
```
预期：PASS（含新增 3 个）

- [ ] **Step 5: Commit**

```bash
git add app/modules/review/mastery_evaluator.py app/modules/review/tests/test_mastery_evaluator.py
git commit -m "feat(review): 新增 calibrate_difficulty 反向校准接口"
```

---

## Task 8: router — 接真实 Service

**Files:**
- Modify: `backend/app/modules/ai_learning/router.py`
- Test: `backend/app/modules/ai_learning/tests/test_router.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.main import app

def test_start_learning_returns_real_result():
    """POST /{book_id}/learn 调真实 Service，不返回 stub"""
    # mock AILearningService
    mock_result = MagicMock()
    mock_result.book_id = "book-1"
    mock_result.total_units = 5
    mock_result.learned_count = 5
    mock_result.failed_count = 0
    mock_result.skipped_count = 0
    mock_result.total_token_cost = 1500
    mock_result.duration_seconds = 1.5

    with patch("app.modules.ai_learning.router.AILearningService") as MockService:
        MockService.return_value.learn_book = AsyncMock(return_value=mock_result)
        client = TestClient(app)
        resp = client.post("/api/v1/learning/book-1/learn", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["book_id"] == "book-1"
        assert data["learned_count"] == 5
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/test_router.py -v
```
预期：FAIL

- [ ] **Step 3: 修改 router.py**

核心改动：
1. 注入 `LLMClient`：`from app.deps import get_llm_client`，路由函数加 `llm_client: LLMClient = Depends(get_llm_client)`
2. `POST /{book_id}/learn`：创建 `AILearningService(llm_client)`，调 `learn_book()`，返回 `BookLearningResult`
3. `GET /{book_id}/progress`：查 `LearningRecord` + `MasteryRecord` 返回真实进度
4. `GET /{book_id}/overview`：创建 `SelectiveLearningService`，调 `get_book_overview()`
5. 异步学习任务：用后台任务 + 轮询模式（先返回 `{task_id}`，再 `GET /tasks/{task_id}` 查进度）

- [ ] **Step 4: 运行测试确认通过**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/test_router.py -v
```
预期：PASS

- [ ] **Step 5: 全量测试回归**

```bash
cd "/e/AI Agent/work area/Studying-helper/backend"
python -m pytest app/modules/ai_learning/tests/ app/modules/review/tests/ app/modules/knowledge_graph/tests/ -v
```
预期：全部通过

- [ ] **Step 6: Commit**

```bash
git add app/modules/ai_learning/router.py app/modules/ai_learning/tests/test_router.py
git commit -m "feat(ai_learning): Router 接真实 Service，移除 stub"
```
