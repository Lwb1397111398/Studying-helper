# adaptive_design 模块

## 职责

AID（Adaptive Instructional Design，自适应教学设计）位于 AI 学习和教学之间。它根据学习者意图画像和知识图谱，把书本章节重组成更适合学习的模块，并为每个模块生成微观教学顺序和单元认知标注。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `router.py` | `/api/v1/aid` 路由 |
| `service.py` | 画像、macro、micro、activate、advance、replan 主逻辑 |
| `schemas.py` | LearnerIntentProfile、MacroDesign、MicroPlan、Replan 等模型 |
| `prompts.py` | AID LLM prompt |
| `profile_builder.py` | 规则化画像推断 |
| `kg_adapter.py` | 从知识图谱提取概念聚类输入 |
| `tests/` | AID 端到端、LLM fallback、sync roundtrip、cognitive hint 测试 |

## API 入口

前缀：`/api/v1/aid`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/{book_id}/profile` | 获取或创建学习者画像 |
| PUT | `/{book_id}/profile` | 更新画像 |
| POST | `/{book_id}/profile/confirm` | 确认画像 |
| POST | `/{book_id}/macro` | 生成宏观模块设计 |
| GET | `/{book_id}/design` | 获取当前教学设计 |
| POST | `/{book_id}/micro/{module_index}` | 生成模块微观编排 |
| GET | `/{book_id}/micro/{module_index}` | 获取模块微观编排 |
| POST | `/{book_id}/activate` | 激活当前模块 |
| POST | `/{book_id}/advance` | 完成当前模块并推进 |
| POST | `/{book_id}/replan` | 模块结束后重规划 |
| POST | `/{book_id}/adjustment` | 记录用户调整 |
| GET | `/{book_id}/active-units` | 获取当前 active module 的有序 unit ids |

## 数据模型

后端 ORM：

- `LearnerIntentProfileModel`
- `TeachingDesignModel`
- `ModuleMicroPlanModel`
- `KnowledgeUnitModel.ai_cognitive_hint`

Android Room 对应：

- `LearnerIntentProfileEntity`
- `TeachingDesignEntity`
- `ModuleMicroPlanEntity`
- `KnowledgeUnitEntity.aiCognitiveHint`

## 核心流程

```text
get_or_create_profile
  -> 用户或 AI/规则确认画像
  -> generate_macro_design
    -> 读取知识单元和知识图谱
    -> 按重组容忍度生成跨章节模块
  -> generate_micro_plan
    -> 模块内排序
    -> 写 UnitRetrofitAnnotation
    -> 写 KnowledgeUnit.ai_cognitive_hint
  -> activate_module
  -> teaching 读取 active-units
  -> advance/replan
```

## LLM 与 fallback

AID 可使用 `LLM_AID_*` 配置；若无 key 或 LLM 返回不可用，应走规则化路径。不要写成强依赖 LLM 成功。

## 跨端同步

AID 三表和 `ai_cognitive_hint` 已进入同步包。改字段时必须同步：

- 后端 ORM：`models.py`
- 后端 sync schema/service
- Android Entity/DAO/DTO/Repository/Preview
- Room migration
- Web `api/aid.ts` 和页面类型

## 验证入口

```bash
cd backend && python -m pytest app/modules/adaptive_design/tests/ -q
cd backend && python -m pytest app/modules/sync/tests/test_sync_contract.py -q
```

## 已知风险

- AID 是跨模块功能，不能只改单个页面或单个 service。
- macro/micro JSON 存在数据库文本字段中，改 schema 要考虑旧记录解析。
- `parent_design_version`、`module_index`、`design_id` 是同步和幂等逻辑的关键字段。
