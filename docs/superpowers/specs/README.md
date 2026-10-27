# 学习闭环设计规格（2026-07-28）

本目录存放「AI 学书 → 教学资产 → 教学状态机 → 同步兼容」契约设计，**先于实现**对齐语义。

| 文档 | 内容 |
| --- | --- |
| [01-domain-contracts](./2026-07-28-01-domain-contracts.md) | 领域对象、字段、生命周期、旧模型映射、迁移阶段 |
| [02-unit-analysis-pipeline](./2026-07-28-02-unit-analysis-pipeline.md) | Context Builder、两阶段分析、证据/题目校验、降级 |
| [03-teaching-state-machine](./2026-07-28-03-teaching-state-machine.md) | 状态/事件/守卫、目标级掌握、修复与子会话、问答中断 |
| [04-sync-and-compatibility](./2026-07-28-04-sync-and-compatibility.md) | 所有权、1.0/1.1 合约、追加事件、冲突与旧客户端 |

## 实现顺序（文档共识）

1. 钉契约（本四份）
2. DocumentBlock + 单单元资产管线
3. 教学修复闭环 + LearningEvidence
4. AnalysisJob 按需调度
5. 路径/UI 统一与 Android 同步升级

## 实现计划

- [单单元闭环计划](../plans/2026-07-28-unit-learning-loop.md)

## 已落地（后端第一刀，2026-07-28）

- ORM：`documents` / `document_revisions` / `document_blocks` / `analysis_jobs` / `unit_learning_assets` / `learning_attempts` / `learning_evidences`
- 模块：`backend/app/modules/learning_assets/`
- 教学 v2：`state_machine_v2.py`、`session_v2_service.py`、`router_v2.py`
- 路由挂载：`/api/v1/learning-assets/*`、`/api/v1/teaching/v2/*`
- 验证：`pytest app/modules/learning_assets/tests app/modules/teaching/tests/test_state_machine_v2.py` → 18 passed

## 已核对的项目事实摘要

- 无持久化 DocumentBlock；PDF 仅有解析期 page_map
- 单元分析写在 knowledge_units 列；TestQuestion 无稳定 id
- 迁移：后端 ADD COLUMN；Android Room v2
- 同步：SCHEMA_VERSION 1.0，覆盖 upsert
- LLM：json_object，非 strict JSON Schema

## 状态

契约定稿；后端单单元闭环主路径已可测；Web/Android/Sync 1.1 仍为 backlog。
