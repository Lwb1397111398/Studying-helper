# review 模块

## 职责

负责复习、考试、自由回忆、掌握度评估、间隔重复调度和导出。当前同时保留 SM-2 兼容字段，并引入 FSRS 相关实现。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `router.py` | `/api/v1/review` 路由 |
| `service.py` | 复习/考试/自由回忆主流程 |
| `schemas.py` | 复习题、考试、掌握度、导出模型 |
| `spaced_repetition.py` | SM-2 算法 |
| `spaced_repetition_v2.py` | 新版间隔重复扩展 |
| `fsrs.py` | FSRS 调度实现 |
| `mastery_evaluator.py` | 掌握度评估 |
| `question_generator.py` | 多题型生成 |
| `exam_mode.py` | 考试模式 |
| `helpers.py` | 答案检查和分数变化 |
| `exporters/` | Markdown、思维导图、Anki、Cornell、错题导出 |

## API 入口

前缀：`/api/v1/review`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/due` | 待复习项目 |
| POST | `/start` | 开始复习 |
| POST | `/answer` | 提交复习答案 |
| POST | `/free-recall/start` | 开始自由回忆 |
| POST | `/free-recall/answer` | 提交自由回忆 |
| GET | `/mastery/{unit_id}` | 查询单元掌握度 |
| POST | `/exam/start` | 开始考试 |
| POST | `/exam/submit` | 提交考试 |
| GET | `/export/{book_id}` | 导出 |

## 数据字段

`MasteryRecordModel` / Android `MasteryRecordEntity` 同时包含：

- SM-2：`ease_factor`、`interval_days`、`review_count`
- FSRS：`stability`、`difficulty`、`lapses`、`reps`、`last_elapsed_days`、`scheduled_days`、`algorithm`

改算法时必须保持旧数据可读。

## 与其他模块关系

- 使用 `KnowledgeUnitModel` 的 AI 分析结果生成题目。
- 可利用 knowledge graph 的关联概念生成干扰项。
- 教学完成时可能更新掌握度和复习计划。
- sync 会跨端同步 review session、mastery record、exam/session test 等数据。

## 验证入口

```bash
cd backend && python -m pytest app/modules/review/tests/ -q
```

## 已知风险

- 算法字段跨 Web/Android/后端同步，任何字段改动都要多端对齐。
- 考试、复习、自由回忆共享部分评分逻辑，改 helper 要跑相关测试。
- 导出器较多，改 schema 时要检查所有 exporter。
