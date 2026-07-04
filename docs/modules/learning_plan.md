# learning_plan 模块

## 职责

生成学习计划和学习会话，基于书籍、知识单元、用户目标和学习风格安排学习节奏。它偏“计划层”，不同于 AID 的“教学设计层”。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `router.py` | `/api/v1/plans` 路由 |
| `service.py` | 计划生成、当前会话、会话完成 |
| `schemas.py` | 学习计划和会话模型 |
| `style_analyzer.py` | 学习风格分析 |
| `style_analyzer_v2.py` | 新版学习风格分析扩展 |
| `tests/` | service/router 测试 |

## API 入口

前缀：`/api/v1/plans`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/{book_id}/generate` | 生成学习计划 |
| GET | `/{book_id}/current-session` | 获取当前学习会话 |
| POST | `/{book_id}/sessions/{session_id}/complete` | 完成学习会话 |

## 与 AID 的区别

- `learning_plan` 回答“什么时候学、学多少、当前 session 是什么”。
- `adaptive_design` 回答“这本书应该如何重组、先讲什么、单元以什么认知模式讲”。
- 两者可以共存，不要把 AID 逻辑塞进 learning_plan。

## 验证入口

```bash
cd backend && python -m pytest app/modules/learning_plan/tests/ -q
```

## 已知风险

- 计划依赖学习进度和掌握度，改 user_storage/review 字段时要回看本模块。
- 学习风格分析 v1/v2 并存，改调用前先查实际引用。
