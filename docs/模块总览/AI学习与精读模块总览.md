# AI 学习与精读模块总览

> 最后更新：2026-10-28 夜（round2 C1：ai_learning 与 learning_assets 共 8 条未用导入清理，职能面无变化；上轮 B4 为 f-string 清理）

## 模块职责（一句话）

对知识单元做 AI 深度分析产出「单元学习资产」（目标/断言/测试题/概念），无 LLM 时走规则化降级管线，为教学 v2 提供唯一内容源。

## 运作流程（真实数据流）

用户在「AI 学习」页对某个知识单元触发分析后，数据按以下顺序流动：

### 触发与旧版分析（ai_learning）

1. `router.py`（前缀 `/api/v1/learning`）收分析请求，`service.py` 编排 LLM 调用：摘要、讲解、要点、概念、难度/重要度。
2. 大单元走 map-reduce（`service.py` 内 reduce 整合 + 质量校验重试：`_validate_parsed_result` 不过则 `logger.warning` 后重试一次，温度 0.2）。
3. 产出写回 `KnowledgeUnitModel`（summary/key_points/concepts/difficulty/importance 等），并供 `book_overview.py` 出书籍总览。

### 新版学习资产（learning_assets，v2 教学前置）

1. **入口**：`router.py`（前缀 `/api/v1/learning-assets`）的 `POST /api/v1/learning-assets/units/{unit_id}/analyze`——无请求体，**同步执行**，2xx 返回 `AnalyzeResponse{asset_id, unit_id, version, status, readiness_status, quality_score, analysis_job_id}`；404=unit 不存在。
2. **管线**：`pipeline.py:300 analyze_unit` 主流程——`context_builder.py` 组装单元上下文（blocks 全文、章节归属）→ LLM 可用时走 `mapreduce.py` 的 map-reduce 精读；LLM 不可用时走**规则化理解**（`understanding.py`：用单元全文作唯一 required claim，quote 截前 40 字符，`find_quote_offsets` 在块内定位偏移）。
3. **证据校验**：`evidence_validator.py` 校验每条 claim 的引用是否真实存在于原文（validation_status：valid/offset_mismatch/missing_block/invalid_offsets/offset_out_of_range 等）；`assessment_validator.py` 校验测试题质量。
4. **概念采集**：`concept_harvest.py` 从 claims/讲解里提取概念（供知识图谱联动）。
5. **readiness 判级**：`readiness.py` 对 required claims 逐条算 `ok`（support_status=="supported" 且 evidence_ref_ids 全部有效，坏状态 offset_mismatch/missing_block 直接否决），汇总出 `readiness_status ∈ {teachable, degraded_teachable, pending, invalid}`。
6. **落库**：`service.py:24 analyze_unit_job` 把 payload_json/status 写 `UnitLearningAssetModel`（status=active）；`dual_write.py` 兼容旧字段双写。
7. **消费**：教学 v2 开课读该资产（见教学模块总览）；`GET /api/v1/learning-assets/units/{unit_id}/asset` 与 `GET /api/v1/learning-assets/assets/{asset_id}` 查询；`concept_mastery.py` 跟踪概念级掌握。

## 入口文件清单

- `backend/app/modules/ai_learning/router.py`（前缀 `/api/v1/learning`）
- `backend/app/modules/ai_learning/service.py`（LLM 分析编排 + map-reduce + 重试）
- `backend/app/modules/ai_learning/prompts.py`、`token_optimizer.py`、`book_overview.py`
- `backend/app/modules/learning_assets/router.py`（前缀 `/api/v1/learning-assets`）
- `backend/app/modules/learning_assets/pipeline.py`（analyze_unit 主流程 + 规则化理解）
- `backend/app/modules/learning_assets/service.py`（analyze_unit_job 落库）
- `backend/app/modules/learning_assets/{context_builder,mapreduce,understanding,evidence_validator,assessment_validator,readiness,concept_harvest,concept_mastery,dual_write}.py`

## 对外接口 / 被谁调用

- HTTP：`/api/v1/learning/*`（AI 学习页）、`/api/v1/learning-assets/*`（精读资产）
- 被 `teaching` 的 `start_session_v2` 硬依赖（active+teachable 资产才能开 v2 课）
- 被 `sync` 搬运资产表；`knowledge_graph` 的概念联动

## 依赖的上游模块

`user_storage`（单元/块归属）、`document_parser`（blocks 原文）、`common`（LLM client、parse_llm_json）

## 关键数据结构

- `UnitLearningAssetModel`：`payload_json`（UnitLearningAssetPayload：learning_objectives/claims/assessment_items）、`status`、`readiness_status`、`freshness_status`、`quality_score`
- `AnalyzeResponse`：同步返回的资产句柄
- claim：id/text/evidence_ref_ids/support_status

## 已知坑与约束

1. 无 LLM 也能产出 active/degraded_teachable 资产（规则化管线，P4 冒烟实测 claims=1 items=2），不要把"教学 v2 开不了课"都归咎于 LLM 配置。
2. quote 偏移校验对中文全文的边界敏感（offset_mismatch/offset_out_of_range 会直接把 readiness 压到非可教）。
3. `ai_learning/service.py` 的 map-reduce 每次分析是多次串行 LLM 调用（map 若干 + reduce + 质量不合格重试一次），成本与耗时按单元大小线性涨。

## 验证命令

```bash
cd backend && python -m pytest app/modules/ai_learning/ app/modules/learning_assets/ -q
```

（测试入口：`app/modules/ai_learning/tests/test_router.py`、learning_assets 的 `tests/test_pipeline_mock.py`——规则路径产出 active/teachable 的证明；端到端 `python backend/scripts/smoke_backend.py`）
