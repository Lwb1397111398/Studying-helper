# 03 教学状态机（Teaching State Machine）

> 状态：设计完整版 v1（契约修正后）
> 依赖：`01-domain-contracts.md`、`02-unit-analysis-pipeline.md`
> 目标：服务端掌权的教学循环；LLM 生成内容/辅助评分，**不**决定状态跳转。
> 第一刀范围：**单单元**闭环（含前置子会话）。多单元 playlist 复用同一状态机实例序列。

---

## 0. 设计原则

1. **状态 + 事件 + 守卫** 三元组，禁止前端点 `continue` 就盲进。
2. **目标级通过**，禁止只用会话平均分。
3. **用户提问 = 中断**，不是长期状态。
4. **连续失败 ≠ 能力标签 blocked**；用 `paused` + `needs_support`。
5. 会话绑定 `asset_id`；全程题目与标准来自该版本。
6. 与旧阶段名兼容映射，便于渐进替换 UI。

---

## 1. 状态定义

| state | 职责 | 用户可见 |
| --- | --- | --- |
| `prepare` | 加载资产、校验 readiness、初始化 objective 追踪 | 准备中 |
| `diagnose` | 前置/必要目标的短诊断（1～3 题，由 prereq 与 required objectives 决定） | 课前小问 |
| `activate` | 激活旧知、说明为何现在学 | 导入 |
| `explain` | 按 unit_type 核心讲解 | 讲解 |
| `guided_practice` | 低风险引导练习 | 练习 |
| `assess` | 正式检查（无过多提示） | 检测 |
| `repair` | 按 error_type 修复教学 | 针对性复习 |
| `reassess` | 等价题再检 | 再测 |
| `prerequisite_intervention` | 父会话挂起，进入子会话 | 先补基础 |
| `reflect` | 收束、笔记、掌握摘要 | 总结 |
| `schedule_review` | 写 ReviewItem / 更新 mastery 投影 | 安排复习 |
| `completed` | 正常结束 | 完成 |
| `paused` | 暂停（可恢复） | 已暂停 |

**不是状态**：`ask`（中断处理）、`blocked`（调度用语，不用于用户能力）。

### 1.1 与旧 TeachingPhase 映射

| 旧 | 新 |
| --- | --- |
| activate | activate |
| intro / core / example | explain（可多 turn） |
| feynman | guided_practice 或 assess 的 explain 子活动 |
| retrieval / check | assess / reassess |
| reflect / connect | reflect |
| （无） | diagnose / repair / prerequisite_intervention / schedule_review |

旧客户端可继续显示旧 phase 字段（由新 state 投影）。

---

## 2. 事件定义

| event | 典型来源 |
| --- | --- |
| `SESSION_STARTED` | API start |
| `ASSET_READY` | prepare 内部 |
| `DIAGNOSIS_SUBMITTED` | 用户提交诊断 |
| `EXPLANATION_ACKNOWLEDGED` | 用户确认继续 / 系统自动若策略允许 |
| `PRACTICE_SUBMITTED` | 引导练习作答 |
| `ASSESSMENT_SUBMITTED` | 正式测 |
| `REPAIR_COMPLETED` | 修复段结束 |
| `REASSESSMENT_SUBMITTED` | 再测 |
| `PREREQ_CHILD_COMPLETED` | 子会话完成 |
| `PREREQ_CHILD_FAILED` | 子会话 needs_support |
| `USER_ASKED` | 随时提问 |
| `USER_PAUSED` | 退出/暂停 |
| `USER_RESUMED` | 继续 |
| `USER_SKIPPED` | 跳过检查（只记 visited） |
| `SESSION_TIMEOUT` | 超时 |
| `OBJECTIVE_TRACKER_UPDATED` | 内部 |

---

## 3. 会话级辅助结构（运行时，可持久化 JSON）

```text
ObjectiveTracker
- objective_id
- importance
- required_score
- best_score
- last_result
- status: unknown | passed | failed | unresolved_prereq
- evidence_ids[]

SessionFlags
- diagnosis_summary: strong | mixed | weak | already_mastered | missing_prereq
- repair_rounds
- assess_rounds
- degraded_asset: bool
```

---

## 4. 状态迁移表（主路径）

| from | event | guard | to |
| --- | --- | --- | --- |
| — | SESSION_STARTED | — | prepare |
| prepare | ASSET_READY | readiness ∈ {teachable, degraded_teachable} | diagnose |
| prepare | ASSET_READY | readiness ∈ {pending, stale} | prepare（等待/触发 AnalysisJob）或返回错误 |
| prepare | ASSET_READY | readiness = invalid | paused + completion_status 特殊错误 |
| diagnose | DIAGNOSIS_SUBMITTED | already_mastered | assess（挑战检）或建议跳过 |
| diagnose | DIAGNOSIS_SUBMITTED | missing_prereq & required | prerequisite_intervention |
| diagnose | DIAGNOSIS_SUBMITTED | strong | activate 或缩短后 explain |
| diagnose | DIAGNOSIS_SUBMITTED | mixed/weak | activate |
| activate | EXPLANATION_ACKNOWLEDGED | — | explain |
| explain | EXPLANATION_ACKNOWLEDGED | — | guided_practice |
| guided_practice | PRACTICE_SUBMITTED | — | assess（可多轮练习由 guard 次数控制） |
| assess | ASSESSMENT_SUBMITTED | all required objectives passed | reflect |
| assess | ASSESSMENT_SUBMITTED | missing_prereq detected | prerequisite_intervention |
| assess | ASSESSMENT_SUBMITTED | repairable gaps & repair_rounds < max | repair |
| assess | ASSESSMENT_SUBMITTED | repair_rounds ≥ max | paused + needs_support |
| repair | REPAIR_COMPLETED | — | reassess |
| reassess | REASSESSMENT_SUBMITTED | all required passed | reflect |
| reassess | REASSESSMENT_SUBMITTED | still gaps & repair_rounds < max | repair |
| reassess | REASSESSMENT_SUBMITTED | still gaps & max | paused + needs_support |
| prerequisite_intervention | PREREQ_CHILD_COMPLETED | — | reassess 或 diagnose（策略：回到触发点） |
| prerequisite_intervention | PREREQ_CHILD_FAILED | — | paused + needs_support |
| reflect | （内部完成） | — | schedule_review |
| schedule_review | （内部完成） | — | completed |
| * | USER_PAUSED | — | paused |
| paused | USER_RESUMED | — | 恢复 pause 前状态 |
| * | USER_SKIPPED | 跳过评估 | 可至 reflect 但 **不**标 mastered |
| * | SESSION_TIMEOUT | — | paused |

`max` 默认：`repair_rounds` 最多 2；`assess_rounds` 含 reassess 计入。

---

## 5. 守卫：目标级通过规则

```text
required_objectives_passed iff
  ∀ o in objectives where o.importance == required:
      tracker[o].best_score >= o.required_score
      AND tracker[o].status != unresolved_prereq

session_may_complete iff
  required_objectives_passed
  AND no unresolved required prerequisites
```

平均分仅用于 UI。
supporting 失败 → 生成 ReviewItem，不单独阻塞 `reflect`（可配置更严策略）。

---

## 6. 各状态输入 / 输出

### 6.1 prepare

**输入**：session 请求、unit_id
**动作**：解析 active/`asset_id`；若 pending 则 enqueue AnalysisJob priority=5
**输出**：ASSET_READY 或错误码

### 6.2 diagnose

**输入**：asset.prerequisites（required）、弱 objective
**出题数**：1～3，不固定 2
**输出**：LearningEvidence(source_type=diagnose) + diagnosis_summary

分支含义：

| summary | 后续 |
| --- | --- |
| strong | 缩短 activate/explain |
| mixed | 正常 |
| weak | 正常，pace 放慢 |
| missing_prereq | 子会话 |
| already_mastered | 挑战 assess 或跳过建议 |

### 6.3 activate / explain

**输入**：teaching_strategy、claims、examples
**输出**：TeachingTurn(turn_type=teaching)，content_origin 正确标记
**degraded_asset**：explain 以原文+模板为主，限制扩展

LLM **建议**下一阶段，服务端可采纳建议仅当事件合法；最终 transition 服务端做。

### 6.4 guided_practice

低风险：补全、判断、辨例。
每题写 evidence `source_type=practice`（可权重低于 assess）。
默认 1～3 轮，由策略与 diagnosis 决定。

### 6.5 assess / reassess

- 题来自 asset.retrieval_questions，绑定 objective
- reassess **禁止**同 id 原题；用 `equivalent_group_id` 或变体生成器
- 评分：规则优先，短答 hybrid；写 evidence `assessment|reassessment`
- 产出 error_type 分类（规则+LLM 辅助，服务端枚举校验）

### 6.6 repair

按 `error_type`：

| error_type | 策略 |
| --- | --- |
| memory | 再编码 + 增加检索线索 |
| confusion | 对比/反例 |
| missing_prereq | 转 prerequisite_intervention |
| inference | 拆推理链 |
| no_application | 新情境逐步练 |
| ambiguous_item | 换题，不惩罚用户 |
| evaluator_unreliable | 重评或换规则题 |

### 6.7 prerequisite_intervention

```text
Parent.state = prerequisite_intervention
Child TeachingSession:
  parent_session_id = parent.id
  intervention_type = prerequisite
  unit_id = prerequisite unit（若仅有 concept/external：微型讲解会话或外部说明 turn）
```

子会话完成后：

- 更新父 tracker 前置状态
- 进入 `reassess`（若从 assess 触发）或 `diagnose`（若从 diagnose 触发）
- **不**覆盖父 `asset_id` 与原 objectives

### 6.8 reflect / schedule_review / completed

reflect：生成掌握摘要、薄弱点、用户笔记钩子。
schedule_review：

- 失败/临界 objective → ReviewItem
- 更新 unit 级 mastery 投影（兼容旧表）
- FSRS 字段由证据事件计算（服务端权威；客户端离线临时值同步后重算）

completed：`completion_status=completed` 仅当 required 通过。
若用户 skip 评估：`completion_status` 可用 `abandoned` 或扩展 `visited_only`（实现时二选一写死，推荐 `visited_only` 进 completion_status 枚举）。

---

## 7. 随时问答中断（USER_ASKED）

```text
1. 持久化 interrupted_state = current state
2. TeachingTurn(user_question)
3. 相关性判断（规则+轻量 LLM）：current objectives / 本单元 claims
4. 相关：基于 asset + evidence 回答；引用 book 时带 EvidenceRef
5. 扩展：content_origin=external_knowledge，UI 标注
6. 回答 turn 后恢复 interrupted_state
7. 仅当用户明确要求改学习目标/换单元 → 发计划调整事件（非本状态机默认自动改 plan）
```

不把 `ask` 做成长期 state，避免与 assess 抢控制流。

---

## 8. 暂停、恢复、跳过、超时

| 情况 | completion_status | pause_reason | 掌握 |
| --- | --- | --- | --- |
| 用户退出 | in_progress | user_exit | 不改 mastered |
| 连续评估失败 | needs_support | repeated_assessment_failure | 保留已通过 objective 证据 |
| 超时 | in_progress | timeout | |
| 跳过检查 | visited_only（推荐） | — | **不得** mastered |
| 正常完成 | completed | — | 按证据 |

恢复：`USER_RESUMED` → 回到 paused 前 state；若 asset 已 superseded，**仍用原 asset_id** 直到会话结束。

---

## 9. 掌握证据生成规则

每次可评分作答创建 `LearningEvidence`：

- 必填：user/book/unit/objective/attempt_id/source_type/result/score/evaluator
- assess/reassess 权重最高
- diagnose 用于路径，不单独宣布 unit mastered
- practice 可提升信心但不替代 required assess（配置：practice 最高折算 0.5 * score 可选；第一版可 **不**计入 best_score，仅 assess 计）

**第一版推荐**：`best_score` 只取 assessment + reassessment，简单可证。

---

## 10. ReviewItem 生成

| 触发 | target |
| --- | --- |
| required 临界通过（0.8～0.9） | objective 短间隔复习 |
| supporting 失败 | objective/concept |
| confusion 类错误 | concept 对比卡 |
| 完成时全部 required 通过 | 标准 FSRS 对新 objective |

兼容：同步更新 `mastery_records` unit 行（聚合函数文档化）。

---

## 11. API 幂等与重复提交

| 接口 | 幂等键 |
| --- | --- |
| start session | user+unit+active 策略 |
| submit answer | attempt_id |
| continue/ack | client_event_id |
| ask | client_event_id |

重复 submit 同一 attempt_id：返回首次评分，不重复写 evidence，不重复推进状态。

---

## 12. LLM 边界

| 允许 LLM | 禁止 LLM 单独决定 |
| --- | --- |
| 讲解文本、例子 | 下一状态 |
| 短答初评 | 最终是否 mastered |
| error_type 建议 | 绕过 guard |
| 问答 | 静默换 asset |

服务端校验 LLM 输出枚举；非法则降级规则路径。

---

## 13. 单单元端到端验收剧本

1. 资产 teachable → start → prepare → diagnose
2. 诊断 mixed → activate → explain → practice → assess
3. 一 required 失败 confusion → repair → reassess 通过
4. reflect → schedule_review → completed
5. 库中 ≥2 条 LearningEvidence，ReviewItem 或 mastery 更新
6. 中途 USER_ASKED 外部知识，标注 origin，状态恢复
7. 另测：required prereq 缺失 → child session → 回父 reassess
8. 另测：连续失败 → paused + needs_support，非 completed

---

## 14. 与现有 teaching service 的接入策略

1. 保留旧 endpoint，增加 `engine=v2` 或 feature flag。
2. `current_phase` 投影自 v2 state。
3. `assessment_json` 逐步改为 evidence id 引用。
4. Android 端侧 TeachingRepository 长期应对齐同一状态枚举；第一刀可先 Web/后端。

---

## 15. OPEN

- `visited_only` 是否加入 completion_status 枚举（推荐是）
- practice 是否计入 best_score（推荐否）
- 诊断 already_mastered 默认挑战还是建议跳过（推荐：建议跳过 + 可选挑战）
- 子会话 unit 找不到时 external_knowledge 迷你课深度
