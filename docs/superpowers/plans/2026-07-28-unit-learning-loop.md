# 单单元学习闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通「原文定位 → 单元教学资产 → 质量门槛 → 教学修复闭环 → 掌握证据 → 复习投影」的**单单元纵向闭环**（先后端可测，再 Web 最小接入；Android 同步放后续阶段）。

**Architecture:** 在现有 FastAPI + SQLAlchemy SQLite 上新增不可变文档修订/块、分析任务、教学资产、作答与证据表；分析管线两阶段（理解→教学设计）+ 程序校验；教学 v2 状态机服务端掌权，Session 固定 `asset_id`；旧 `knowledge_units` 列双写兼容。不一次重写全部 teaching service。

**Tech Stack:** Python 3 + FastAPI + SQLAlchemy 2 async + SQLite + pytest；沿用 `app.common.llm_client.chat_json`；迁移用现有 `_run_migrations` + `create_all`。

**Spec 来源:**
- `docs/superpowers/specs/2026-07-28-01-domain-contracts.md`
- `docs/superpowers/specs/2026-07-28-02-unit-analysis-pipeline.md`
- `docs/superpowers/specs/2026-07-28-03-teaching-state-machine.md`
- `docs/superpowers/specs/2026-07-28-04-sync-and-compatibility.md`（本计划仅预留字段，不实现 1.1 全量同步）

---

## 范围边界（YAGNI）

**本计划做：**
1. Document / DocumentRevision / DocumentBlock + 从 KnowledgeUnit 回填
2. AnalysisJob + UnitLearningAsset（含 objectives/criteria/items/claims JSON payload）
3. 两阶段分析管线（可 mock LLM）+ Evidence/Assessment 校验器
4. LearningAttempt + LearningEvidence
5. Teaching Session v2 最小状态机（prepare→…→completed，含 repair/reassess 主路径）
6. 旧 unit 列双写；教学入口 feature flag `engine=v2`
7. 后端单元/集成测试

**本计划不做：**
- Android Room / Sync 1.1 全集合
- 完整 Book/Chapter Understanding LLM 生产
- 跨单元 LearningPlan 表
- Web 全面 UI 重做（可加最小 API 消费）
- 严格 JSON Schema 提供商能力假设

---

## 文件结构（将创建/修改）

| 路径 | 职责 |
| --- | --- |
| `backend/app/db/models.py` | 新 ORM 表 |
| `backend/app/db/database.py` | `init_db` 导入新模型；必要 ADD COLUMN |
| `backend/app/modules/learning_assets/` | **新模块**：文档块、资产、分析、校验 |
| `.../learning_assets/models_domain.py` | Pydantic 领域 schema（与 DB JSON 对齐） |
| `.../learning_assets/block_builder.py` | DocumentBlock 回填 |
| `.../learning_assets/evidence_validator.py` | 引用校验 |
| `.../learning_assets/assessment_validator.py` | 题目/目标校验 |
| `.../learning_assets/context_builder.py` | 分析上下文 |
| `.../learning_assets/pipeline.py` | 两阶段管线 + publish |
| `.../learning_assets/service.py` | AnalysisJob 编排 |
| `.../learning_assets/router.py` | API：建块、分析单元、取资产 |
| `.../learning_assets/dual_write.py` | 投影到 knowledge_units 旧列 |
| `backend/app/modules/teaching/state_machine_v2.py` | 状态+事件+守卫 |
| `backend/app/modules/teaching/evidence_service.py` | Attempt/Evidence 写入与 mastery 投影 |
| `backend/app/modules/teaching/router.py` | 可选 v2 端点或 query flag |
| `backend/app/main.py` | 挂载 learning_assets router |
| `backend/app/modules/learning_assets/tests/` | 管线与校验测试 |
| `backend/app/modules/teaching/tests/test_state_machine_v2.py` | 状态机测试 |
| `backend/app/tests/test_database_migrations.py` | 新表存在性 |

---

## 执行状态（2026-07-28）

- [x] Task 1–3 Phase A（Document/Block/EvidenceRef）
- [x] Task 4–8 Phase B（Asset/Job/Pipeline/API；含 assessment_validator、context_builder、service）
- [x] Task 9–12 Phase C（状态机、session v2、E2E、skip≠mastery）
- [x] Task 13 文档 + 相关 pytest
- [ ] Task 14 backlog（Sync 1.1 / Android / 真 LLM / Web UI）— **刻意不做**

验证：`23 passed`（learning_assets + state_machine_v2 + session_v2_skip + migrations）

---

## Phase A — 文档定位基础

### Task 1: ORM — Document / Revision / Block

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/db/database.py`（`init_db` import 列表）
- Test: `backend/app/tests/test_database_migrations.py` 或新 `backend/app/modules/learning_assets/tests/test_document_models.py`

- [ ] **Step 1: 写失败测试 — 表可创建且 block 绑定 revision**

```python
# backend/app/modules/learning_assets/tests/test_document_models.py
import pytest
from sqlalchemy import select
from app.db.models import DocumentModel, DocumentRevisionModel, DocumentBlockModel

@pytest.mark.asyncio
async def test_document_block_belongs_to_revision(db_session, sample_book):
    doc = DocumentModel(id="doc_1", book_id=sample_book.id, source_type="txt", source_uri=sample_book.file_path, status="active")
    rev = DocumentRevisionModel(id="rev_1", document_id="doc_1", revision_no=1, source_hash="sha256:abc", parser_version="test", normalization_version="v1", status="active")
    blk = DocumentBlockModel(id="blk_1", document_revision_id="rev_1", chapter_id=None, block_type="paragraph", ordinal=0, text="Hello", text_hash="h1")
    db_session.add_all([doc, rev, blk])
    await db_session.commit()
    rows = (await db_session.execute(select(DocumentBlockModel).where(DocumentBlockModel.document_revision_id == "rev_1"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].text == "Hello"
```

- [ ] **Step 2: 实现三张 ORM 表**（字段对齐 01 契约；无 `DocumentBlock.source_revision` 列）

```python
class DocumentModel(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True)
    book_id = Column(String, ForeignKey("books.id"), nullable=False, index=True)
    source_type = Column(String(20), nullable=False)
    source_uri = Column(String(500), nullable=False)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, nullable=False, default=_utc_now)

class DocumentRevisionModel(Base):
    __tablename__ = "document_revisions"
    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False, index=True)
    revision_no = Column(Integer, nullable=False)
    source_hash = Column(String(128), nullable=False)
    parser_version = Column(String(50), nullable=False)
    normalization_version = Column(String(50), nullable=False)
    status = Column(String(20), default="processing")
    created_at = Column(DateTime, nullable=False, default=_utc_now)

class DocumentBlockModel(Base):
    __tablename__ = "document_blocks"
    id = Column(String, primary_key=True)
    document_revision_id = Column(String, ForeignKey("document_revisions.id"), nullable=False, index=True)
    chapter_id = Column(String, ForeignKey("chapters.id"), nullable=True, index=True)
    parent_block_id = Column(String, nullable=True)
    block_type = Column(String(30), nullable=False, default="paragraph")
    ordinal = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    text_hash = Column(String(128), nullable=False)
    page_index = Column(Integer, nullable=True)
    page_label = Column(String(50), nullable=True)
    metadata_json = Column(Text, default="{}")  # 避免与 SQLAlchemy metadata 冲突
```

- [ ] **Step 3: `init_db` 导入新模型，跑测试 PASS**
- [ ] **Step 4: Commit** `feat(db): add Document/Revision/Block tables`

### Task 2: Block backfill from KnowledgeUnit

**Files:**
- Create: `backend/app/modules/learning_assets/__init__.py`
- Create: `backend/app/modules/learning_assets/block_builder.py`
- Test: `backend/app/modules/learning_assets/tests/test_block_builder.py`

- [ ] **Step 1: 失败测试**

```python
@pytest.mark.asyncio
async def test_backfill_blocks_from_units(db_session, book_with_units):
    from app.modules.learning_assets.block_builder import ensure_document_blocks_for_book
    rev_id = await ensure_document_blocks_for_book(db_session, book_with_units.id)
    blocks = (await db_session.execute(
        select(DocumentBlockModel).where(DocumentBlockModel.document_revision_id == rev_id).order_by(DocumentBlockModel.ordinal)
    )).scalars().all()
    assert len(blocks) >= 1
    assert all(b.text for b in blocks)
    # 幂等
    rev_id2 = await ensure_document_blocks_for_book(db_session, book_with_units.id)
    assert rev_id2 == rev_id
```

- [ ] **Step 2: 实现** `ensure_document_blocks_for_book(session, book_id) -> revision_id`
  - 若已有 active Document+Revision 且 source_hash 匹配（对 units content 拼接 hash）→ 返回现 revision
  - 否则创建 Document / 新 Revision，按 unit.order_index 为每个 unit 建 1+ 个 paragraph block（简单：整段 unit.content 一块；metadata 含 unit_id, char_offset_start/end）
  - **不**依赖不存在的 `chapter.content` 列
- [ ] **Step 3: 测试 PASS + Commit** `feat(learning_assets): backfill DocumentBlocks from units`

### Task 3: EvidenceRef quote validator

**Files:**
- Create: `backend/app/modules/learning_assets/models_domain.py`（EvidenceRef pydantic）
- Create: `backend/app/modules/learning_assets/evidence_validator.py`
- Test: `backend/app/modules/learning_assets/tests/test_evidence_validator.py`

- [ ] **Step 1: 测试**

```python
def test_quote_must_match_block_slice():
    block_text = "定义：光合作用是植物利用光能的过程。"
    ok = validate_evidence_ref(
        block_text=block_text,
        start_offset=3,
        end_offset=5,
        quote="光合",
        offset_encoding="unicode_code_point",
    )
    assert ok.valid is True

    bad = validate_evidence_ref(block_text=block_text, start_offset=0, end_offset=2, quote="错")
    assert bad.valid is False
    assert bad.code == "offset_mismatch"
```

- [ ] **Step 2: 实现半开区间 `[start,end)` + unicode code point 切片**（Python `str` 索引即可作为服务端权威）
- [ ] **Step 3: Commit** `feat(learning_assets): EvidenceRef quote validator`

---

## Phase B — 资产与分析任务

### Task 4: ORM — AnalysisJob + UnitLearningAsset + Attempt/Evidence

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/db/database.py`

表（最小列 + JSON payload）：

```python
class AnalysisJobModel(Base):
    __tablename__ = "analysis_jobs"
    id = Column(String, primary_key=True)
    scope_type = Column(String(20), nullable=False)  # unit|chapter|book|blocks
    scope_id = Column(String, nullable=False, index=True)
    status = Column(String(30), nullable=False, default="queued")
    wait_reason = Column(String(50), nullable=True)
    priority = Column(Integer, default=0)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    next_retry_at = Column(DateTime, nullable=True)
    idempotency_key = Column(String(200), nullable=False, unique=True)
    lease_expires_at = Column(DateTime, nullable=True)
    depends_on_job_ids_json = Column(Text, default="[]")
    quality_result_json = Column(Text, default="{}")
    error_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

class UnitLearningAssetModel(Base):
    __tablename__ = "unit_learning_assets"
    id = Column(String, primary_key=True)
    unit_id = Column(String, ForeignKey("knowledge_units.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="draft")  # draft|validating|active|superseded|invalid
    readiness_status = Column(String(30), nullable=False, default="pending")
    freshness_status = Column(String(30), nullable=False, default="current")
    quality_score = Column(Float, nullable=True)
    quality_profile = Column(String(80), nullable=True)
    document_revision_id = Column(String, nullable=True, index=True)
    payload_json = Column(Text, nullable=False, default="{}")  # objectives/items/claims/...
    schema_version = Column(String(40), default="unit-asset-v1")
    prompt_version = Column(String(40), nullable=True)
    model_name = Column(String(80), nullable=True)
    analysis_job_id = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    published_at = Column(DateTime, nullable=True)
    __table_args__ = (Index("ix_ula_unit_status", "unit_id", "status"),)

class LearningAttemptModel(Base):
    __tablename__ = "learning_attempts"
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=True, index=True)
    assessment_item_id = Column(String, nullable=False)
    attempt_no = Column(Integer, default=1)
    response_json = Column(Text, nullable=False)
    submitted_at = Column(DateTime, nullable=False, default=_utc_now)
    device_id = Column(String, nullable=True)
    idempotency_key = Column(String(200), nullable=False)
    client_created_at = Column(DateTime, nullable=True)
    server_received_at = Column(DateTime, nullable=False, default=_utc_now)
    status = Column(String(30), default="submitted")
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", name="uq_attempt_idem"),)

class LearningEvidenceModel(Base):
    __tablename__ = "learning_evidences"
    id = Column(String, primary_key=True)
    attempt_id = Column(String, ForeignKey("learning_attempts.id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    book_id = Column(String, nullable=False)
    unit_id = Column(String, nullable=False, index=True)
    objective_id = Column(String, nullable=False)
    criterion_id = Column(String, nullable=True)
    session_id = Column(String, nullable=True, index=True)
    source_type = Column(String(30), nullable=False)
    question_id = Column(String, nullable=True)  # assessment_item_id
    ability = Column(String(30), nullable=True)
    result = Column(String(20), nullable=False)
    score = Column(Float, nullable=False)
    error_type = Column(String(40), nullable=True)
    evaluator_type = Column(String(20), nullable=False)
    evaluator_version = Column(String(40), nullable=True)
    evaluation_revision = Column(Integer, default=1)
    supersedes_evidence_id = Column(String, nullable=True)
    status = Column(String(20), default="active")  # active|superseded|invalidated
    hints_used = Column(Integer, default=0)
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
```

- [ ] 测试：create + unique idempotency
- [ ] Commit `feat(db): analysis jobs, assets, attempts, evidences`

### Task 5: Domain Pydantic schemas

**Files:**
- Create/expand: `backend/app/modules/learning_assets/models_domain.py`

定义：`SourceClaim`, `EvidenceRef`, `LearningObjective`, `AssessmentCriterion`, `AssessmentItem`, `Prerequisite`, `UnitLearningAssetPayload`, `readiness` 枚举。

- [ ] 用 pydantic 校验样例 JSON 的测试
- [ ] Commit

### Task 6: Assessment validator + readiness decision

**Files:**
- Create: `backend/app/modules/learning_assets/assessment_validator.py`
- Create: `backend/app/modules/learning_assets/readiness.py`
- Test: `.../tests/test_readiness.py`

规则（对齐 02）：

```text
teachable: required claims 100% supported + 每 required objective ≥1 item + hard checks
degraded_teachable: required 仍 100%；缺高阶题可降级
invalid: required 无证据或 block 失效
```

- [ ] 表驱动单元测试覆盖三种结局
- [ ] Commit

### Task 7: Analysis pipeline (mockable LLM)

**Files:**
- Create: `backend/app/modules/learning_assets/context_builder.py`
- Create: `backend/app/modules/learning_assets/pipeline.py`
- Create: `backend/app/modules/learning_assets/dual_write.py`
- Create: `backend/app/modules/learning_assets/service.py`
- Test: `.../tests/test_pipeline_mock.py`

流程：

```text
ensure blocks → job queued → context → stage1 (injectable fn) → evidence validate
→ optional repair → stage2 → assessment validate → publish asset (active) → dual_write unit columns
```

Mock stage1/stage2 返回固定 claims/items，验证 publish 后：

- 同 unit 仅一 active
- dual_write 写入 summary/explanation 非空
- job status succeeded|degraded

- [ ] Commit `feat(learning_assets): mockable unit analysis pipeline`

### Task 8: HTTP API

**Files:**
- Create: `backend/app/modules/learning_assets/router.py`
- Modify: `backend/app/main.py` include_router `/api/v1/learning-assets`

端点最小集：

```text
POST /books/{book_id}/document-blocks/ensure
POST /units/{unit_id}/analyze
GET  /units/{unit_id}/asset          # active asset
GET  /assets/{asset_id}
GET  /jobs/{job_id}
```

- [ ] API 测试（httpx/AsyncClient 或现有 conftest 模式）
- [ ] Commit

---

## Phase C — 教学状态机 v2 + 证据

### Task 9: state_machine_v2 pure functions

**Files:**
- Create: `backend/app/modules/teaching/state_machine_v2.py`
- Test: `backend/app/modules/teaching/tests/test_state_machine_v2.py`

```python
@dataclass
class TransitionResult:
    next_state: str
    completion_status: str | None
    side_effects: list[str]

def transition(state: str, event: str, guards: dict) -> TransitionResult:
    ...
```

覆盖主路径与：

- assess 全 required 通过 → reflect
- 可修复失败 → repair → reassess
- missing_prereq → prerequisite_intervention
- USER_SKIPPED assessment → visited_only，非 mastered
- 连续失败 → paused + needs_support

- [ ] 纯函数测试，无 DB
- [ ] Commit

### Task 10: TeachingSession 列扩展 + v2 session service

**Files:**
- Modify: `TeachingSessionModel` ADD（via migration helper）:
  - `asset_id`, `parent_session_id`, `state_v2`, `completion_status`, `pause_reason`, `plan_snapshot_json`, `unit_id`（可选冗余）
- Create: `backend/app/modules/teaching/session_v2_service.py`
- Test: integration start → submit attempt → evidence → complete

规则：

- start 时 require asset readiness in teachable|degraded_teachable
- pin asset_id
- submit 用 idempotency_key
- best_score 仅 assessment/reassessment
- dual update mastery_records 投影（简单：required 全过 → mastery_score 提升）

- [ ] Commit

### Task 11: v2 router endpoints

```text
POST /api/v1/teaching/v2/sessions/start
POST /api/v1/teaching/v2/sessions/{id}/event   # body: event, payload
POST /api/v1/teaching/v2/sessions/{id}/attempts
GET  /api/v1/teaching/v2/sessions/{id}
```

不破坏旧 `/teaching` 路由。

- [ ] Commit

### Task 12: 端到端单单元测试（mock LLM）

**Files:**
- Create: `backend/app/modules/learning_assets/tests/test_unit_loop_e2e.py`

剧本：

1. 建书+unit 文本
2. ensure blocks
3. analyze（mock）→ teachable asset
4. start v2 session
5. diagnose/practice/assess（规则评分选择题）
6. 一题错 → repair → reassess 对
7. completed_mastered
8. LearningEvidence ≥ 2；mastery 投影更新

- [ ] Commit `test: unit learning loop e2e with mocks`

---

## Phase D — 收尾

### Task 13: 文档与 CodeGraph

- 更新 `docs/modules/` 增加 `learning_assets.md` 短文
- `docs/superpowers/specs/README.md` 链到 plan
- 跑：`cd backend && python -m pytest app/modules/learning_assets app/modules/teaching/tests/test_state_machine_v2.py -q`
- 可选 `codegraph sync .`

### Task 14: 明确后续 backlog（不实现）

- Sync 1.1 collections
- Android Entity
- 真 LLM prompt 调优
- Web TeachingSession 接 v2
- Book/Chapter Understanding 生产管线
- Prerequisite 子会话完整 UI

---

## 执行顺序与依赖

```text
Task1 → Task2 → Task3
Task4 → Task5 → Task6 → Task7 → Task8
Task9 → Task10 → Task11 → Task12
Task13
```

## 风险

| 风险 | 缓解 |
| --- | --- |
| models.py 已很大 | 新表仍放 models.py 以符合项目惯例；逻辑放 learning_assets |
| teaching service 巨大 | v2 平行模块，不重构整类 |
| 无 chapter.content | 只用 unit.content 回填 |
| LLM 不稳 | 测试全 mock；生产 pipeline 注入真实 client |

## Spec 覆盖自检

| Spec 要求 | Task |
| --- | --- |
| DocumentBlock 前置 | 1–2 |
| EvidenceRef 校验 | 3 |
| UnitLearningAsset 版本/readiness | 4–6 |
| 两阶段分析+降级 | 7 |
| Attempt/Evidence 分离 | 4,10 |
| 状态机事件守卫 | 9–11 |
| skip≠mastered | 9,12 |
| 双写兼容 | 7 |
| Sync 1.1 | backlog only |

---

**Plan complete.** 执行时从 Task 1 开始，TDD，小步提交。
