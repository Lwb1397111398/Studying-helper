# 04 同步与兼容契约（Sync and Compatibility）

> 状态：设计完整版 v1
> 依赖：`01-domain-contracts.md`（及 02/03 产生的对象）
> 目标：规定 Web / 后端 / Android 对学习资产与证据的**所有权、缓存、合并、冲突、版本兼容**。
> 背景：当前同步是 **JSON 离线包**（`SCHEMA_VERSION = "1.0"`），导入以**覆盖式 upsert** 为主，不是实时 CRDT 云同步。

---

## 0. 现状基线（已核对）

| 项 | 现状 |
| --- | --- |
| 合约 | `backend/app/modules/sync/schemas.py`，`SCHEMA_VERSION="1.0"` |
| 集合 | books/chapters/units/mastery/annotations/kg/daily_stats/learning_records/review_sessions/teaching_sessions/messages/user_questions/session_tests/learning_efficiency/AID 三表 |
| 导入 | 覆盖 upsert；无细粒度事件合并 |
| Android | `SyncDtos.kt` / `SyncRepository.kt`，Room v2 |
| 单元字段 | 同步 summary/explanation/key_points/concepts/prerequisites/difficulty/importance/ai_cognitive_hint |
| 题目 | session_tests 整包 JSON；题目无稳定全局 id 合约 |
| 增量 | 存在 `incremental_sync.py` 探索，完整事件模型未成为主路径 |

本设计在 **不破坏 1.0 可读** 的前提下定义 **1.1+** 扩展。

---

## 1. 设计原则

1. **服务端权威材料 vs 多端事件**
   理解/资产/标准答案以服务端（或导出时的权威快照）为准；学习证据与会话事件可多端产生。
2. **追加事件优先于覆盖最终状态**
   尤其 `LearningEvidence`、`TeachingTurn`。
3. **FSRS 最终调度可重算**
   客户端离线临时 due/stability；同步后服务端按证据重算或选主。
4. **旧客户端可降级**
   未知字段忽略；未知集合忽略；不可教新状态映射到旧 phase。
5. **不默认同步“全书全部资产”**
   按当前模块 + 预热窗口缓存。

---

## 2. 数据所有权矩阵

| 数据 | 权威写 | 客户端可写 | 同步方向 | 冲突策略 |
| --- | --- | --- | --- | --- |
| Book/Chapter 元数据 | 两端都可（现有） | 是 | 双向 | 较新 updated_at；标题冲突预览提示 |
| DocumentBlock | 解析端/后端 | 只读缓存 | 权威→客户端 | 按 source_revision 整批替换 |
| Book/Chapter Understanding | 分析端（通常后端） | 只读缓存 | 权威→客户端 | 高版本 active 胜 |
| UnitLearningAsset | 分析端 | 只读缓存 | 权威→客户端 | 同 unit 高 version active 胜；会话钉住 id |
| RetrievalQuestion 标准答案/rubric | 随资产 | 只读 | 随资产 | 同资产 |
| AnalysisJob | 后端 | Android 可建本地 job 但导出时标记 device | 可选同步 | 不做跨端抢执行；只同步结果资产 |
| LearningPlan / AID 设计 | 两端 | 是 | 双向 | 设计 version + updated_at；预览冲突 |
| TeachingSession | 多端 | 是 | 双向 | 同 id 按 updated_at；状态机用事件回放更佳 |
| TeachingTurn | 多端 | 是 | **追加** | id 幂等；禁止静默改历史 content |
| LearningEvidence | 多端 | 是 | **追加** | attempt_id/id 幂等 |
| Review 作答事件 | 多端 | 是 | 追加 | 同证据 |
| mastery_records 投影 | 可派生 | 离线可写临时 | 双向 | **证据重算优先**于裸覆盖 stability |
| annotations / notes | 多端 | 是 | 双向 | id 幂等；更新用 updated_at |
| 用户答案明细 | 多端 | 是 | 随 evidence/tests | 不覆盖他人 attempt |

---

## 3. 离线缓存范围（Android）

### 3.1 必须可离线

- 当前书的章节树与当前模块 unit 原文
- 当前 + 后续 2～3 单元的 **active/degraded** 资产（若已生成）
- 进行中 TeachingSession + Turns
- 本地产生的 Evidence（未同步）
- 到期 Review 队列所需题目（不含未使用全书题库）

### 3.2 可按需拉取/导入

- 全书 DocumentBlock
- 非当前模块资产
- 完整 Understanding

### 3.3 不要默认塞进日常同步包

- Prompt 全文
- 模型原始 completion 日志
- 失败 job 调试堆栈（可另导出诊断包）

---

## 4. Schema 版本策略

```text
1.0  当前生产合约
1.1  增加可选集合：document_blocks, unit_learning_assets, learning_evidences, review_items_v2（名可议）
     增加 teaching_sessions 可选字段：asset_id, parent_session_id, completion_status, pause_reason, state_v2
1.2  事件日志集合（teaching_turns 规范化、evidence 为主路径）
```

规则：

- 导出写入 `schema_version`
- 导入：
  - 主版本差 > 0 且不支持 → 明确错误
  - 同主版本新次版本：忽略未知字段/集合，已知集合照常
- Android 旧版：忽略 1.1 新集合，仍能导入 books/units/mastery；**不得崩溃**

---

## 5. 集合级合约（1.1 草案）

在现有 `SYNC_COLLECTION_CONTRACT` 上**追加**（保持旧字段稳定）：

| package_field | preview_count | import_count | 所有权 |
| --- | --- | --- | --- |
| document_blocks | document_blocks_count | document_blocks_imported | 权威材料 |
| unit_learning_assets | unit_learning_assets_count | unit_learning_assets_imported | 权威材料 |
| learning_evidences | learning_evidences_count | learning_evidences_imported | 追加事件 |
| teaching_turns | teaching_turns_count | teaching_turns_imported | 追加事件（若从 messages 规范化） |
| analysis_jobs | 可选 | 可选 | 非必须同步 |

预览与导入计数测试必须扩展 `test_sync_contract.py` 与 Android `SyncDtosTest`。

---

## 6. ID 与幂等

| 实体 | ID 生成 |
| --- | --- |
| Evidence | 客户端 UUID；`attempt_id` 另立 |
| Turn | 客户端 UUID |
| Session | 客户端或服务端 UUID，创建后不可变 |
| Asset | 分析端 UUID；version 单调 |
| Block | 解析端稳定算法或 UUID；**revision 变更即新集** |

导入幂等：

- 同 `id` 的 evidence/turn：**不覆盖** content，仅补 `server_received_at`
- 同 `attempt_id` 已存在：跳过
- asset 同 `id`：以 payload 为准（权威快照）

---

## 7. 增量同步游标（演进）

短期仍可全量包；1.2 目标：

```text
SyncCursor
- device_id
- last_export_at
- last_seq by collection
```

事件表带 `server_seq` / `client_created_at`。
第一版完整设计允许先全量导出 evidences 子集（按 book_id + since）。

---

## 8. 冲突处理细则

### 8.1 权威材料（Asset / Block / Understanding）

```text
if incoming.version > local.version: replace
if equal version and different hash: 标记 conflict_preview，默认不覆盖 active 教学中 session 钉住的 asset
if incoming.source_revision 与本地书不一致: 整书材料需要重导入解析
```

### 8.2 TeachingSession

优先：

1. 同 id 合并：取并集 turns/evidences（靠追加集合）
2. 状态字段：用 `updated_at` 较新，但 **completed 不被 in_progress 覆盖**（单调状态保护）
3. 若两端都 completed 且 asset_id 不同：保留两条？不允许同 id；导出前应避免——冲突预览让用户选

### 8.3 mastery_records vs evidences

```text
推荐导入顺序：
1. learning_evidences 追加
2. 由服务端/导入器重算 mastery 投影
3. 若包内 mastery 与重算差异大：以重算为准，旧 mastery 作 fallback 当无 evidence 时
```

禁止：仅按 mastery.updated_at 覆盖从而丢失另一端 evidence。

### 8.4 删除语义

| 类型 | 语义 |
| --- | --- |
| 书删除 | 软删或 tombstone 同步（现状若硬删需在预览警告） |
| 资产 superseded | 保留历史 id 供会话回放；可在包中带 status |
| evidence | **默认不可删**；GDPR/用户清除走专用 tombstone |

---

## 9. 资产缓存与失效

Android 本地：

```text
cached asset 若 unit.source_revision 变化 → stale，不可开新课
进行中 session 仍用 session.asset_id 对应缓存快照
```

导入新资产 active 时：旧 active 标 superseded，不删文件式缓存直至 LRU。

---

## 10. 旧客户端 / 旧后端行为

| 场景 | 行为 |
| --- | --- |
| 旧 Android 导入 1.1 包 | 读 1.0 集合；跳过新集合；教学仍用 unit 旧列投影 |
| 新后端导出给旧客户端 | 仍填充 knowledge_units 双写列 |
| 新 Android 导入 1.0 包 | 正常；assets 缺失则 readiness=pending，触发本地或提示需分析 |
| 旧 phase 字符串 | 新 state 投影表（见 03） |

---

## 11. 安全与隐私

- 同步包可含用户作答全文：导出提示
- 不把 API Key 写入同步包
- 书本原文 blocks 体积大：允许按 book 导出与“学习进度包”分离（进度包可只含 evidence/session + asset ids，缺资产则需材料包）

推荐产品层两种包：

1. **材料包**：blocks + assets + understandings
2. **进度包**：sessions + turns + evidences + mastery + plan

第一版可仍单包，但字段上可分组，便于后续拆分。

---

## 12. 测试契约要求

必须自动化：

1. `SYNC_COLLECTION_CONTRACT` 字段三角一致（package/preview/import）
2. 1.0 包在 1.1 导入器可导入
3. 1.1 包在“旧导入器模拟”（忽略未知）不抛
4. evidence 重复 id 不加倍
5. completed session 不被旧 in_progress 覆盖
6. Android DTO 序列化往返
7. 双写：有 asset 时旧 unit.summary 非空（过渡期）

---

## 13. 实施阶段与领域对象同步节奏

| 阶段 | 同步影响 |
| --- | --- |
| M0 DocumentBlock | 可先不同步；仅后端 |
| M1 UnitLearningAsset | 启动 1.1 可选集合 + unit 双写 |
| M2 LearningEvidence | 追加导入逻辑；mastery 重算 |
| M3 Teaching state_v2 字段 | sessions 扩展列 |
| M4 拆材料包/进度包 | 产品层 |

---

## 14. 明确非目标（本阶段）

- 实时多用户协作编辑同一单元
- 自动语义合并两段不同讲解文案
- 跨用户共享证据
- 无预览的静默毁灭性覆盖全书

---

## 15. 验收标准

- [ ] 所有权矩阵中每类数据有唯一冲突策略
- [ ] schema 1.0 / 1.1 兼容路径可测
- [ ] Evidence 追加幂等
- [ ] 资产版本与会话 pin 在同步后仍一致
- [ ] 旧 Android 不因新字段崩溃
- [ ] 文档回答：谁产生、谁可改、何时可驱动教学（与 01 一致）

---

## 16. OPEN

- 是否第一版就拆“材料包/进度包”两个文件（推荐设计支持，产品默认同包）
- Android 是否允许离线生成 degraded 资产（若允许，导出时 `model_provider=on_device`）
- incremental_sync 与全量包双轨时间表
