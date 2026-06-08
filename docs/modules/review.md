# review 模块

## 概述

间隔重复复习模块，基于 SM-2 算法管理复习计划，支持多种题型、校准测试、关联概念复习和考试模式。

## 文件结构

| 文件 | 职责 |
|------|------|
| `router.py` | API 路由（复习会话、答题、考试、导出） |
| `schemas.py` | 请求/响应模型（含 QuestionType 枚举） |
| `service.py` | 复习服务（SM-2 算法、掌握度评估、会话管理） |
| `helpers.py` | 答案检查（支持6种题型）、掌握度变化计算、校准调整 |
| `question_generator.py` | 多题型生成器（不依赖 LLM） |
| `spaced_repetition.py` | SM-2 间隔重复算法实现 |
| `mastery_evaluator.py` | 掌握度评估器（5级体系） |
| `exporters/markdown_exporter.py` | Markdown 导出 |
| `exporters/mindmap_exporter.py` | 思维导图导出 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/review/{book_id}/session` | 获取复习会话 |
| POST | `/api/v1/review/{session_id}/answer` | 提交复习答案 |
| POST | `/api/v1/review/{book_id}/exam` | 开始考试 |
| POST | `/api/v1/review/{session_id}/exam/submit` | 提交考试答案 |
| GET | `/api/v1/review/{book_id}/export/markdown` | 导出 Markdown |
| GET | `/api/v1/review/{book_id}/export/mindmap` | 导出思维导图 |

## SM-2 算法

```python
# 核心参数
ease_factor: float    # 难度因子（初始 2.5）
interval_days: int    # 复习间隔天数
review_count: int     # 复习次数

# 质量评分 (quality)
# 0: 完全忘记
# 1: 错误，但看到答案后记起
# 2: 错误，但答案很熟悉
# 3: 正确，但很费力
# 4: 正确，略有犹豫
# 5: 完美回答
```

## 题型支持

| 题型 | question_type | 判分方式 | 说明 |
|------|--------------|---------|------|
| 简答题 | `short_answer` | 关键词匹配（50% 命中率） | 原有题型 |
| 单选题 | `choice` | 精确匹配 | 4选项，干扰项来自关联单元 |
| 填空题 | `fill_blank` | 关键词模糊匹配 | 从 key_points 提取关键词 |
| 判断题 | `true_false` | 精确匹配 | 基于 key_points 生成正确陈述 |
| 排序题 | `ordering` | JSON 数组比较 | 将 key_points 按正确顺序排列 |
| 配对题 | `matching` | JSON 对象比较 | 概念与描述配对 |

## 校准测试

回答前可选择信心等级（1-3），系统根据信心与正确性差异调整掌握度变化：
- 高信心+错误 → 掌握度变化 ×1.5（过度自信，惩罚更大）
- 低信心+正确 → 掌握度变化 ×1.3（低估自己，奖励更大）

## 掌握度等级（5级体系）

| 等级 | 分数范围 | 含义 |
|------|----------|------|
| beginner | 0.00-0.20 | 刚接触 |
| learning | 0.20-0.40 | 学习中 |
| familiar | 0.40-0.65 | 熟悉 |
| proficient | 0.65-0.85 | 熟练 |
| mastered | 0.85-1.00 | 掌握 |

## 关联概念复习

复习时自动从知识图谱加载 `similar_to` 和 `contrasts_with` 关联单元，用于生成选择题干扰项，强化概念辨别能力。

## 已知问题

| 严重度 | 问题 | 位置 | 状态 |
|--------|------|------|------|
| **严重** | `mastery_level` 从未被更新：`_upsert_mastery` 只更新 `mastery_score`，`mastery_level` 始终为初始值 | `service.py:~L80` | **已修复** |
| 中等 | 全模块使用 `datetime.now()` 而非 UTC，跨时区场景会出错 | 全模块 | **已修复** |
| 中等 | 掌握度等级不一致（3套不同阈值） | 多处 | **已修复** |
| 中等 | 考试模式中 `quality_from_correctness` 使用硬编码 `response_time=0` | `service.py:~L327` | 待修复 |
| 低 | 导出功能无缓存，每次重新生成 | `exporters/` | 待修复 |

## 优化建议

1. ~~**紧急修复**: `_upsert_mastery` 中根据 `mastery_score` 同步更新 `mastery_level`~~ ✅ 已完成
2. ~~统一使用 `datetime.now(timezone.utc)`~~ ✅ 已完成
3. ~~统一掌握度等级为5级体系~~ ✅ 已完成
4. ~~丰富复习题型（单选/填空/判断/排序/配对）~~ ✅ 已完成
5. ~~校准测试：信心等级与正确性差异调整掌握度~~ ✅ 已完成
6. ~~关联概念复习：从知识图谱加载关联单元~~ ✅ 已完成
7. 考试模式记录实际响应时间
8. 导出结果添加缓存（基于书籍内容 hash）

## 测试覆盖

- `tests/test_spaced_repetition.py` — 存在
- `tests/test_mastery_evaluator.py` — 存在
- `tests/test_exporters.py` — 存在
- `tests/test_exam_mode.py` — 存在
- `tests/test_service.py` — 存在
- **mastery_level 更新 bug 未被测试发现**
