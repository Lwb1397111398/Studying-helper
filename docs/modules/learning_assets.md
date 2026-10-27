# learning_assets 模块

## 职责

单单元学习闭环的**教学资产层**：文档定位块、分析任务、不可变 `UnitLearningAsset`、引用/题目校验、旧 unit 列双写。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `block_builder.py` | 从 `KnowledgeUnit.content` 回填 Document/Revision/Block |
| `context_builder.py` | 阶段 0 分析上下文（分层、token 预算） |
| `evidence_validator.py` | EvidenceRef 半开区间 + unicode code point 校验 |
| `assessment_validator.py` | 题目/目标 hard·soft 校验 |
| `models_domain.py` | 资产 payload Pydantic |
| `readiness.py` | teachable / degraded / invalid 判定 |
| `pipeline.py` | 可注入 stage1/stage2 的分析发布管线 |
| `service.py` | AnalysisJob 编排门面 |
| `dual_write.py` | 投影 summary/explanation 等到旧列 |
| `router.py` | `/api/v1/learning-assets/*` |

## API

- `POST /api/v1/learning-assets/books/{book_id}/document-blocks/ensure`
- `POST /api/v1/learning-assets/units/{unit_id}/analyze`
- `GET /api/v1/learning-assets/units/{unit_id}/asset`
- `GET /api/v1/learning-assets/assets/{asset_id}`
- `GET /api/v1/learning-assets/jobs/{job_id}`

## 教学 v2

- 状态机：`teaching/state_machine_v2.py`
- 会话：`teaching/session_v2_service.py`
- 路由：`teaching/router_v2.py` → `/api/v1/teaching/v2/*`
- 兼容入口：`POST /api/v1/teaching/sessions/start` 传 `engine=v2`

## 验证

```bash
cd backend && python -m pytest app/modules/learning_assets/tests app/modules/teaching/tests/test_state_machine_v2.py app/modules/teaching/tests/test_session_v2_skip.py app/tests/test_database_migrations.py -q
```

## 注意

- Chapter **无** content 列；回填只用 unit 原文。
- 新 Session 固定 `asset_id`；skip 不写 mastered。
- 同步 1.1 与 Android 明确不在本模块第一刀（见 plan backlog）。
