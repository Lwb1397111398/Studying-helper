"""AID 三层 + 画像推断 Prompt 模板

务实保守风格：单次 LLM 调用，结构化 JSON 输出，注入画像+概念图摘要+审计。
所有 LLM 调用都有规则化回退（见 service.py）。
"""

# ── 画像推断 ──
PROFILE_INFER_PROMPT = """你是学习顾问。根据用户的学习动机文本，推断其学习画像。

## 用户学习动机
{motivation}

## 单元难度均值（1-5，越高越难）
{avg_difficulty}

## 输出要求（严格 JSON）
{{
  "identity_background": "expert|related|unrelated|unknown",
  "goal_depth": "exam_memorize|apply_understand|general_interest",
  "cognitive_pref": "vivid_analogy|rigorous_system|problem_driven",
  "restructure_tolerance": "keep_book_order|moderate|aggressive",
  "reason": "简短推断理由"
}}

## 维度说明
- identity_background: 专业相关度。expert=本专业师生/从业者；related=相关专业；unrelated=跨领域纯兴趣
- goal_depth: exam_memorize=应试需记忆术语；apply_understand=应用重在理解；general_interest=通识兴趣弱化术语
- cognitive_pref: 讲解风格偏好
- restructure_tolerance: 跨章节重组强度。专家型倾向 keep_book_order 保留书结构；新手兴趣型倾向 aggressive 大胆重组；高难度(>3.5)新手也应 moderate 防过载

只返回 JSON，不要多余文字。"""


# ── 宏观设计：跨章节聚类成 Module ──
MACRO_DESIGN_PROMPT = """你是资深教学设计师。把这本书的知识单元组织成若干「学习模块」(Module)，不机械按章节切分。

## 学习者画像
- 身份背景: {identity_background}
- 目标深度: {goal_depth}
- 认知偏好: {cognitive_pref}
- 重组强度: {restructure_tolerance}

## 全书策略（已据画像推导，供参考）
{global_strategy}

## 单元列表（含概念与章节）
{units_brief}

## 概念共现关系（跨章节同现的概念，可据此聚类）
{concept_relations}

## 用户已明确调整（避免与之冲突）
{adjustments_summary}

## 任务
把单元聚成 3-8 个 Module。规则：
1. {restructure_rule}
2. 同构/对比概念不论章节远近可归一组（如不同章的同类定律对比学）
3. 每模块 unit_ids 必须来自上面列表，不得臆造
4. 不得违反前置依赖：模块 i 的单元不能依赖模块 i+1 的单元

## 输出（严格 JSON）
{{
  "modules": [
    {{
      "title": "模块标题",
      "unit_ids": ["unit-x", ...],
      "concept_ids": ["相关概念名"],
      "strategy_tags": ["deep_dive|rapid_survey|concept_merge_overview|comparison_group|defer_hard_point"],
      "rationale": "为何这么分"
    }}
  ]
}}

{restructure_rule_detail}
只返回 JSON。"""


# ── 微观编排：模块内教授计划 ──
MICRO_PLAN_PROMPT = """你是教学设计师。为下面这个学习模块内的单元设计教授顺序与重构标注。

## 学习者画像
- 身份背景: {identity_background}
- 目标深度: {goal_depth}
- 认知偏好: {cognitive_pref}

## 当前模块
标题: {module_title}
策略标签: {module_strategy}

## 模块内单元（含难度、重要性、概念、前置）
{units_detail}

## 上一模块反馈（若有，用于查漏）
{prev_summary}

## 用户已明确调整
{adjustments_summary}

## 任务
1. 重排单元顺序（ordered_unit_ids），遵循前置依赖，允许画像覆盖默认偏好
2. 为每个单元给标注：
   - cognitive_mode: memorize(术语需记忆)/understand(原理重在理解)/skip_if_mastered(已掌握可跳过)
   - merge_group: 若多单元表述重叠可合并讲解，给同组名；否则 null
   - defer_to_module: 难度高且依赖未学可推迟到第 N 模块；否则 null
   - emphasis: 该单元教学侧重什么（可选）
3. 写一段 module_intro 地图提示：说明本模块学什么、为何这样组织、对应书里哪几章

## 输出（严格 JSON）
{{
  "ordered_unit_ids": ["unit-x", ...],
  "unit_annotations": [
    {{"unit_id":"unit-x","cognitive_mode":"understand","merge_group":null,"defer_to_module":null,"emphasis":"..."}}
  ],
  "module_intro": "地图提示文本"
}}

被 defer 的单元仍出现在 unit_annotations 中，但不要放进 ordered_unit_ids。
只返回 JSON。"""


# ── 动态再规划：模块结束查漏 ──
REPLAN_PROMPT = """你是教学顾问。某学习模块刚结束，根据反馈对下一模块做保守调整。

## 刚结束模块反馈
- 薄弱点: {weak_points}
- 用户反馈: {user_feedback}
- 用时(分钟): {time_spent}

## 下一模块骨架
{next_module_skeleton}

## 学习者画像
- 目标深度: {goal_depth}

## 任务（保守原则）
1. revisit_unit_ids: 本模块薄弱点对应的旧单元，需在下一模块开头回访精讲（最多2个）
2. skip_unit_ids: 下一模块中已被本模块高分掌握前置的单元可跳过（仅当确有把握）
3. rationale: 调整理由

## 输出（严格 JSON）
{{
  "revisit_unit_ids": ["unit-x"],
  "skip_unit_ids": ["unit-y"],
  "rationale": "..."
}}

只返回 JSON。"""
