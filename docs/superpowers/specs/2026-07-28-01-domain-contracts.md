# 01 领域契约（Domain Contracts）

> 状态：设计完整版 v1（已按契约修正轮次定稿，待用户确认后进入实现）  
> 目标：回答三件事——**谁产生这条数据？谁有权修改？什么条件下它才可以驱动教学？**  
> 范围：领域对象、字段、生命周期、不变量、版本策略、旧模型映射。不含 UI 与具体 Prompt 正文。

---

## 0. 设计原则

1. **语义拆分优先于表拆分**  
   现有 `LearningRecord` / `TeachingSession` / `KnowledgeUnit` 字段混用分析与学习语义。契约先钉死概念；物理表可分阶段迁移。

2. **权威数据 vs 用户数据**  
   - 服务端权威：书籍理解、章节理解、单元教学资产、题目标准答案、评分量表、分析任务。  
   - 用户侧可写：教学会话状态、教学轮次、学习证据、笔记、复习作答事件。  
   - 可派生：FSRS 调度结果可由证据事件重算。

3. **版本不可变**  
   教学会话绑定**特定资产版本**。分析结果更新只能发布新版本，不能静默覆盖正在使用的资产。

4. **证据驱动掌握**  
   “学会”只能由 `LearningEvidence` 证明，不能由“看完讲解”或“点了完成”证明。

5. **兼容优先**  
   旧字段不删除；新语义以新对象/新表或 JSON 扩展落地，旧客户端可读降级。

---

## 1. 项目事实基线（已核对代码）

| 项 | 现状 | 对契约影响 |
| --- | --- | --- |
| 文本定位 | PDF 解析有临时 `page_map(page_number, start/end_offset)`；TXT/EPUB 无页码。**无持久化 `DocumentBlock` 表**。`KnowledgeUnit` 有 `content` + `char_offset_start/end`，`Chapter` **无 content 列** | 必须先引入 `DocumentBlock`，否则 `EvidenceRef` 无法稳定 |
| 单元分析产物 | 写在 `knowledge_units.summary/explanation/key_points/concepts/prerequisites/...` | 逐步迁到 `UnitLearningAsset`，旧列作兼容投影 |
| 题目 | `TestQuestion` **无稳定 id**；`session_tests.questions_json` 是 blob | 新资产内题目必须有 id |
| 教学阶段 | `activate/intro/core/example/feynman/retrieval/check/reflect/connect` | 新状态机映射并扩展 repair/reassess |
| 掌握 | `mastery_records` 按 **unit** 粒度，含 SM-2 + FSRS | 新证据落到 objective；unit 级 mastery 由证据派生 |
| 同步 | `SCHEMA_VERSION="1.0"`，全量包 + 覆盖 upsert | 新对象进 v1.1+ 合约；事件追加优于覆盖 |
| 迁移 | 后端 `_run_migrations` 增量 `ADD COLUMN`；Android Room v2 | 允许加表/加列，避免破坏性改名 |
| LLM | OpenAI 兼容；`chat_json` 用 `response_format=json_object`，**非严格 JSON Schema** | Prompt + Pydantic 校验；不假设原生 schema 强制 |

### 待确认（完整版中标为 OPEN，不写死实现假设）

| ID | 问题 | 默认假设（可推翻） |
| --- | --- | --- |
| OPEN-1 | 第一版主攻书型 | 通用教材/技术书；`unit_type` 分支教学，不绑死考试书 |
| OPEN-2 | 是否允许 AI 补充书外知识 | **允许**，但必须 `content_origin != book` 并在 UI 标注 |
| OPEN-3 | 用户主目标 | 默认“理解 + 可检索”；画像可切换 exam/application |
| OPEN-4 | 是否已有失败样本集 | 无则实现期建立 golden fixtures |

---

## 2. 领域边界

### 2.1 属于本契约

- 文档块与引用锚点  
- 分析任务与理解产物（书/章/单元）  
- 教学资产与评价标准  
- 教学会话、轮次、中断问答  
- 学习证据与复习项  
- 用户学习计划（个性化路径）

### 2.2 不属于本契约（保持现有模块）

- PDF/TXT/EPUB 原始解析算法细节（只要求产出 `DocumentBlock`）  
- 知识图谱可视化布局  
- LLM provider 配置 UI  
- 同步传输层实现细节（见 `04-sync-and-compatibility.md`）

### 2.3 明确禁止混用

| 禁止 | 原因 |
| --- | --- |
| 把 `LearningRecord` 当分析任务 | 它是用户学习时长/覆盖记录 |
| 把 `UnitLearningAsset` 当用户计划 | 资产是书的教学材料，计划是用户路径 |
| 把会话平均分当掌握判定 | 必须目标级证据 |
| 把 AI 自创例子写成 `EvidenceRef(source_kind=book)` | 伪造原文依据 |
| 教学中静默替换 `asset_id` | 破坏题目与标准一致性 |

---

## 3. 对象总览与职责

```text
DocumentBlock          原文最小可定位块（解析层产出，服务端权威）
EvidenceRef            指向 DocumentBlock 的引用（可校验）
SourceClaim            一条可教学结论 + 其证据
BookUnderstanding      AI 对书的理解（非用户计划）
ChapterUnderstanding   AI 对章的理解
UnitLearningAsset      可教学的单元资产（不可变版本）
LearningObjective      学习目标
AssessmentCriterion    目标的可观察通过标准
RetrievalQuestion      带稳定 ID 的检查题
Prerequisite           前置关系（可 unit/concept/external）
AnalysisJob            分析任务调度实体
LearningPlan           用户个性化路径（可对标现有 AID design）
TeachingSession        一次教学会话（绑定 asset 版本）
TeachingTurn           会话内一轮交互
LearningEvidence       一次可审计的掌握证据（独立表）
ReviewItem             复习调度目标（可由证据生成）
```

关系简图：

```text
DocumentBlock 1..* <- EvidenceRef
SourceClaim *..* EvidenceRef
UnitLearningAsset
  -> SourceClaim[]
  -> LearningObjective[]
       -> AssessmentCriterion[]
  -> RetrievalQuestion[] (objective_id)
  -> Prerequisite[]
TeachingSession.asset_id -> UnitLearningAsset.id
LearningEvidence.session_id -> TeachingSession
LearningEvidence.objective_id -> LearningObjective
ReviewItem.source_evidence_id -> LearningEvidence
LearningPlan 使用 BookUnderstanding/AID，但不等于 Understanding
AnalysisJob 产出 Understanding / Asset
```

---

## 4. 完整字段表

### 4.1 DocumentBlock（**实现前置**）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | 稳定 ID，建议 `blk_{bookId}_{seq}` 或 UUID |
| book_id | string | |
| chapter_id | string \| null | 目录确认后可填 |
| seq | int | 全书顺序 |
| block_type | enum | `paragraph` \| `heading` \| `list_item` \| `code` \| `other` |
| text | string | 清洗后文本 |
| char_start | int | 在清洗后全书/章坐标系中的起点 |
| char_end | int | 终点（半开或闭区间需全局统一，推荐半开） |
| page_start | int \| null | PDF 展示用 |
| page_end | int \| null | |
| source_revision | string | 清洗/解析版本哈希 |
| created_at | datetime | |

**谁产生**：document_parser / splitter 管线。  
**谁可改**：仅解析重跑可生成新 revision；旧 block 标记 `superseded`，不原地改 text。  
**驱动教学条件**：存在且 `source_revision` 与当前书一致。

### 4.2 EvidenceRef

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | |
| document_id | string | 通常 = book_id 或 file id |
| chapter_id | string \| null | |
| block_start_id | string | |
| block_end_id | string | |
| start_offset | int | 相对 block_start 文本 |
| end_offset | int | |
| quote | string | 短引文，用于失效检测 |
| page_start | int \| null | 展示 |
| page_end | int \| null | |
| source_kind | enum | `book` \| `external` |
| validation_status | enum | `valid` \| `offset_mismatch` \| `missing_block` \| `unchecked` |

**不变量**：`source_kind=book` 时必须能在 DocumentBlock 上复现 quote（允许空白归一化）。

### 4.3 SourceClaim

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | |
| claim_type | enum | `definition` \| `fact` \| `author_view` \| `principle` \| `procedure` \| `other` |
| text | string | 结论文本 |
| importance | enum | `required` \| `supporting` |
| evidence_ref_ids | string[] | |
| support_status | enum | `supported` \| `partially_supported` \| `unsupported` |
| content_origin | enum | `book` \| `ai_inference`（推断不得伪装成书中事实） |

### 4.4 BookUnderstanding

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | |
| book_id | string | |
| source_revision | string | |
| core_questions | string[] | |
| target_audience | string \| null | |
| book_type | string \| null | theory/skill/exam/method/narrative… |
| themes | string[] | |
| module_outline | object[] | 粗模块，**不是**用户 LearningPlan |
| concept_candidates | string[] | |
| version | int | |
| status | enum | `draft` \| `active` \| `superseded` \| `invalid` |
| model_provider / model_name | string | |
| prompt_version / schema_version | string | |
| created_at | datetime | |

**注意**：用户“怎么学这本书”属于 `LearningPlan` / 现有 AID `TeachingDesign`，不写入本对象。

### 4.5 ChapterUnderstanding

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | |
| chapter_id / book_id | string | |
| source_revision | string | |
| chapter_role | string | |
| central_questions | string[] | |
| learning_objectives | object[] | 章级目标（可粗） |
| key_claims | SourceClaim[] 或 id 引用 | |
| terminology | object[] | |
| prerequisite_candidates | Prerequisite[] | |
| chapter_summary | string | |
| evidence_refs | EvidenceRef[] | |
| version / status / 模型元数据 | 同书级 | |

### 4.6 UnitLearningAsset（核心）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | **会话绑定这个 id，不是 unit_id** |
| unit_id | string | |
| version | int | 单调递增 |
| status | enum | `draft` \| `active` \| `superseded` \| `invalid` |
| readiness_status | enum | 见下 |
| quality_score | float 0~1 | **辅助**，不单独决定可教 |
| unit_type | enum | `concept` \| `principle` \| `procedure` \| `argument` \| `example` \| `comparison` \| `application` \| `evidence` |
| central_question | string | |
| claims | SourceClaim[] | |
| learning_objectives | LearningObjective[] | |
| assessment_criteria | AssessmentCriterion[] | |
| key_points | object[] | |
| concepts | object[] | |
| misconceptions | object[] | |
| prerequisites | Prerequisite[] | |
| teaching_strategy | object | 类型化讲解策略 |
| retrieval_questions | RetrievalQuestion[] | |
| repair_strategy_map | object | error_type → 策略 |
| source_revision | string | 原文版本 |
| prompt_version / schema_version | string | |
| model_provider / model_name | string | |
| analysis_job_id | string \| null | |
| created_at | datetime | |

#### readiness_status

| 值 | 含义 | 可否进入正式教学 |
| --- | --- | --- |
| `pending` | 未生成 | 否 |
| `understanding_ready` | 内容理解完成，教学资产未完成 | 否（可展示原文） |
| `teachable` | 通过教学质量门槛 | 是 |
| `degraded_teachable` | 模板教学可用 | 是（受限） |
| `invalid` | 不可教学 | 否 |
| `stale` | 原文/Prompt/模型版本变化 | 否（需重生） |

**教学入口只认** `teachable` 与 `degraded_teachable`。

### 4.7 LearningObjective

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | 稳定 |
| description | string | 具体可检验 |
| ability | enum | `recognize` \| `recall` \| `explain` \| `apply` \| `differentiate` \| `transfer` |
| importance | enum | `required` \| `supporting` |
| required_score | float | 默认 0.8 |
| source_claim_ids | string[] | |

### 4.8 AssessmentCriterion

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | |
| objective_id | string | |
| observable_behavior | string | 可观察行为 |
| scoring_rubric | object/string | |
| pass_threshold | float | |

### 4.9 RetrievalQuestion

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | **必须稳定** |
| objective_id | string | 每题绑定目标 |
| question_type | enum | choice/fill_blank/short_answer/… |
| stem | string | |
| options | string[] \| null | |
| correct_answer | string \| object | |
| rubric | object \| null | 简答量表 |
| explanation | string | |
| difficulty | float \| null | |
| equivalent_group_id | string \| null | reassess 抽等价题 |
| content_origin | enum | `book_grounded` \| `ai_generated` |
| answer_evidence_ref_ids | string[] | 书内可追溯时填写 |

### 4.10 Prerequisite

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | |
| target_type | enum | `unit` \| `concept` \| `external_knowledge` |
| target_id | string \| null | |
| label | string | 无 id 时的可读名 |
| necessity | enum | `required` \| `recommended` |
| relation_type | enum | `understand_before` \| `practice_before` \| `recall_before` |
| source | enum | `explicit` \| `inferred` \| `graph` |
| confidence | float | **仅关系推断可信度**，不决定资产可教 |

### 4.11 AnalysisJob

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | |
| scope_type | enum | `book` \| `chapter` \| `unit` \| `graph` \| `blocks` |
| scope_id | string | |
| status | enum | `queued` \| `running` \| `waiting_dependency` \| `retry_scheduled` \| `succeeded` \| `degraded` \| `failed` \| `cancelled` |
| blocked_reason | enum \| null | `missing_source` \| `toc_unconfirmed` \| `dependency_not_ready` \| `quota_exceeded` \| `manual_review_required` |
| priority | int 0~5 | 当前单元=5 |
| attempt_count / max_attempts | int | |
| next_retry_at | datetime \| null | |
| idempotency_key | string | 防重复 |
| lease_expires_at | datetime \| null | 崩溃恢复 |
| depends_on_job_ids | string[] | |
| input_version / output_version | string | |
| quality_result | object | 可检查指标 |
| error | object \| null | |
| created_at / updated_at | datetime | |

**禁止**用含糊的 `blocked` 作为唯一状态；阻塞原因进 `blocked_reason` + `waiting_dependency` / `failed`。

### 4.12 LearningPlan（用户路径）

可映射/演进自现有 AID：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | |
| user_id / book_id | string | |
| goal_profile | object | 意图画像快照 |
| module_sequence | object[] | |
| current_module_id | string \| null | |
| plan_version | int | |
| generated_from_book_version | string | BookUnderstanding 版本 |
| status | enum | active/archived |

与 `TeachingDesignModel` 关系：第一阶段可把 LearningPlan 视为 AID 设计的领域视图；物理上可先复用 AID 表，契约上必须与 `BookUnderstanding` 分离。

### 4.13 TeachingSession

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | |
| user_id / book_id / unit_id | string | 单单元闭环时 unit_id 必填 |
| parent_session_id | string \| null | 前置补习子会话 |
| intervention_type | enum \| null | `prerequisite` \| null |
| state | enum | 见状态机文档 |
| completion_status | enum | `in_progress` \| `completed` \| `needs_support` \| `abandoned` |
| pause_reason | enum \| null | `user_exit` \| `repeated_assessment_failure` \| `timeout` \| … |
| asset_id | string | **具体资产版本 id** |
| plan_snapshot | object | 开始时计划快照 |
| started_at / completed_at / paused_at | datetime | |
| device_id | string \| null | 同步用 |

**不包含** `learning_evidence[]` 嵌入数组。

### 4.14 TeachingTurn

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | |
| session_id | string | |
| state_at_turn | string | 产生时会话状态 |
| turn_type | enum | `system_instruction` \| `teaching` \| `user_question` \| `answer` \| `assessment` \| `repair` |
| content | string | |
| objective_ids | string[] | |
| content_origin | enum | `book` \| `ai_generated_example` \| `external_knowledge` \| `system` |
| created_at | datetime | |
| client_created_at / device_id | 同步字段 | |

用户提问是**中断**，不新增长期 `ask` 状态：保存 state → 回答 → 恢复 state。

### 4.15 LearningEvidence（独立）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | 全局唯一，客户端可预生成 |
| user_id / book_id / unit_id | string | |
| objective_id | string | |
| criterion_id | string \| null | |
| session_id | string \| null | |
| source_type | enum | `diagnose` \| `practice` \| `assessment` \| `reassessment` \| `review` \| `exam` |
| question_id | string \| null | |
| attempt_id | string | 同一次提交幂等 |
| ability | enum | 同 objective |
| result | enum | `correct` \| `partial` \| `incorrect` |
| score | float 0~1 | |
| error_type | enum \| null | `memory` \| `confusion` \| `missing_prereq` \| `inference` \| `no_application` \| `ambiguous_item` \| `evaluator_unreliable` \| `other` |
| hints_used | int | |
| response_time_ms | int \| null | |
| evaluator | enum | `rule` \| `llm` \| `hybrid` \| `user_self` |
| raw_response | string \| null | 可选 |
| device_id / client_created_at / server_received_at | 同步 | |
| schema_version | string | |

### 4.16 ReviewItem

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | string | |
| user_id | string | |
| target_type | enum | `objective` \| `concept` \| `question` |
| target_id | string | |
| unit_id / book_id | string \| null | 冗余便于查询 |
| due_at | datetime | |
| stability / difficulty | float | FSRS 兼容 |
| source_evidence_id | string \| null | |
| algorithm | string | sm2/fsrs |
| status | enum | active/suspended |

**兼容**：现有 `mastery_records`（unit 级）保留；可由 objective 证据聚合更新 unit 级分数，作为过渡投影。

---

## 5. 生命周期与不变量

### 5.1 资产发布

```text
AnalysisJob queued → running
  → draft UnitLearningAsset
  → validators
  → status=active + readiness_status=teachable|degraded_teachable
  → 旧 active 同 unit 变为 superseded
```

### 5.2 会话绑定

- `SESSION_STARTED` 时冻结 `asset_id`。  
- 若资产变 stale，进行中会话仍用旧 asset；新会话取新 active。

### 5.3 掌握判定不变量

```text
unit mastered 仅当：
  所有 required objectives 在有效时间窗内达到 required_score
  且不存在 unresolved missing_prereq
supporting objectives 失败不单独阻止完成，但可生成 ReviewItem
```

### 5.4 引用不变量

- required claim 的 `support_status` 必须为 `supported` 才可 `teachable`。  
- AI 例子：`content_origin=ai_generated_example`，**无**伪造 book EvidenceRef。

---

## 6. 旧模型映射

| 旧 | 新 | 策略 |
| --- | --- | --- |
| `knowledge_units.summary/explanation/...` | `UnitLearningAsset` 投影 | 双写过渡；读优先新资产 |
| `LearningRecordModel` | 仍表示学习时长会话 | **不**改成 AnalysisJob |
| `TeachingSessionModel.current_phase` | `TeachingSession.state` | 枚举扩展 + 映射表 |
| `TeachingMessageModel` | `TeachingTurn` 超集 | 可先加列 |
| `SessionTestModel.questions_json` | Evidence + Question id | 保留 blob，同时写 evidence |
| `MasteryRecordModel` | unit 投影 + ReviewItem | 不删；证据驱动更新 |
| `TestQuestion` 无 id | `RetrievalQuestion.id` | 生成时强制 id |
| AID `TeachingDesign` | `LearningPlan` 视图 | 逻辑分离，物理可暂共用 |
| 无 DocumentBlock | 新表 | **阶段 0 必做** |

---

## 7. 数据库迁移阶段（后端 SQLite + Android Room）

### 阶段 M0：DocumentBlock

- 新表 `document_blocks`  
- 解析/拆分后回填  
- 旧书：后台 job 从 unit content 近似切块（质量低于原生解析）

### 阶段 M1：分析与资产表

- `analysis_jobs`  
- `book_understandings` / `chapter_understandings`  
- `unit_learning_assets`（大 JSON 可先单表 + 校验后的结构化列）

### 阶段 M2：证据与复习

- `learning_evidences`  
- `review_items`（或扩展 mastery）  
- `teaching_sessions` 加 `asset_id/parent_session_id/completion_status/pause_reason`

### 阶段 M3：同步合约 v1.1

- 见 04 文档  
- Android Entity + Migration + DTO 同步

**迁移工具约束**：后端继续 `_add_column_if_missing` + `create_all`；新表用 ORM 创建。Android 升 `version` 并写 `Migration`。禁止破坏性 rename 无双写期。

---

## 8. API 序列化约束

1. 对外返回 `readiness_status` 枚举字符串，不只返回 `quality_score`。  
2. 教学开始接口若资产不可教，返回可操作错误码：`ASSET_PENDING` / `ASSET_INVALID` / `ASSET_STALE`。  
3. 证据提交必须带 `attempt_id`，重复提交幂等返回首次结果。  
4. 资产 GET 默认 `status=active`；会话回放按 `asset_id` 取历史版本。  
5. 所有时间 UTC；Android 本地临时时间在同步时带 `client_created_at`。

---

## 9. 明确“不属于该对象”

| 对象 | 不要塞进去 |
| --- | --- |
| BookUnderstanding | 用户进度、FSRS、个性化顺序 |
| UnitLearningAsset | 用户答案、会话状态、掌握分 |
| TeachingSession | 证据数组、完整题库副本（只存 asset_id） |
| LearningEvidence | 下一题生成逻辑、完整资产 |
| AnalysisJob | 教学阶段、用户作答 |

---

## 10. 第一版纵向闭环最小集合

只为“一个单元端到端”必需要落地的对象：

1. `DocumentBlock`（当前章/单元范围即可）  
2. `UnitLearningAsset` + Objective/Criterion/Question/Claim/EvidenceRef  
3. `AnalysisJob`（unit scope）  
4. `TeachingSession` + `TeachingTurn`  
5. `LearningEvidence`  
6. `ReviewItem`（可先写入现有 mastery 投影）

书/章 Understanding 与完整 LearningPlan 可第二刀，但字段预留，避免再混进 Unit 资产。

---

## 11. 开放问题清单（实现前确认）

1. OPEN-1 书型默认是否接受“通用 + unit_type 分支”？  
2. OPEN-2 书外知识默认允许并标注？  
3. DocumentBlock 坐标系：全书偏移 vs 章内偏移，选一并写死。  
4. `LearningPlan` 第一版是新建表还是 AID 视图适配器？  
5. 证据时间窗（多久的 assessment 仍算有效掌握）默认 14 天？  

---

## 12. 验收标准（契约层）

- [ ] 任何“可教学”判定只依赖 `readiness_status`，不依赖 LLM confidence。  
- [ ] 任一 required claim 可追溯到可校验 EvidenceRef。  
- [ ] TeachingSession 能指出唯一 `asset_id`。  
- [ ] LearningEvidence 独立可查询，且绑定 objective_id。  
- [ ] 旧 LearningRecord / MasteryRecord 仍可读，语义文档化。  
- [ ] 同步文档 04 能指出每个新字段的所有权。  
