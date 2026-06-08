"""AI学习提示词模板"""

# 最大内容长度（字符），防止超长输入
MAX_CONTENT_LENGTH = 8000

# 增量更新聚焦方向
FOCUS_DIRECTIONS = {
    "examples": {
        "label": "补充例子",
        "instruction": "为以下知识补充具体示例，特别是实际应用中的例子",
        "fields": ["concepts"],
    },
    "explanations": {
        "label": "深入解释",
        "instruction": "对以下知识给出更深入、更易懂的解释，补充原理细节",
        "fields": ["explanation"],
    },
    "connections": {
        "label": "关联拓展",
        "instruction": "补充以下知识与其他概念之间的关联和区别",
        "fields": ["concepts"],
    },
    "applications": {
        "label": "实践应用",
        "instruction": "补充这个知识在实际工作和生活中的应用场景和案例",
        "fields": ["explanation"],
    },
    "mistakes": {
        "label": "易错点",
        "instruction": "总结学习这个知识点时常见的错误理解，每条含标题和详细解释",
        "fields": ["key_points"],
    },
    "simplify": {
        "label": "简化总结",
        "instruction": "用更简洁通俗的语言重新总结这个知识点的核心要义",
        "fields": ["summary"],
    },
}

# 注入检测模式：用户内容中如果包含这些指令模式，进行清洗
_INJECTION_PATTERNS = [
    r'忽略(以上|之前|前面).*指令',
    r'ignore.*(previous|above|prior).*instructions?',
    r'你现在是.*不要.*遵守',
    r'你现在是.*忘记.*规则',
    r'system\s*:',
    r'<\|im_start\|>',
    r'<\|system\|>',
]


def _sanitize_content(content: str) -> str:
    """清洗用户上传内容，防止 prompt 注入"""
    import re
    cleaned = content
    for pattern in _INJECTION_PATTERNS:
        cleaned = re.sub(pattern, '[已过滤]', cleaned, flags=re.IGNORECASE)
    return cleaned


def build_understand_prompt(content: str, context_info: str) -> str:
    """构建理解 prompt（带注入防护）"""
    safe_content = _sanitize_content(content[:MAX_CONTENT_LENGTH])
    return f"""分析以下学习材料，返回JSON。

## 材料
{safe_content}

## 上下文
{context_info}

## 要求
1. summary: 200-500字核心概括
2. explanation: 用通俗易懂的语言讲解这个知识点，包括：① 核心思想是什么 ② 为什么重要 ③ 与现实的联系 ④ 举例说明。300-600字。像一位耐心的老师在给学生上课。
3. key_points: 3-7条结构化要点（每条含 title/explanation/examples）
4. concepts: 关键概念（含name/definition/examples/related_concepts）
5. difficulty_level: 1-5分（1=入门 5=高级），无法判断时返回 null
6. importance_score: 0-1分（在书中的重要性），无法判断时返回 null
7. prerequisites: 前置知识（优先unit_id，其次概念名）

返回纯JSON：
```json
{{"summary":"...","explanation":"...","key_points":[{{"title":"...","explanation":"...","examples":["..."]}}],"concepts":[{{"name":"...","definition":"...","examples":["..."],"related_concepts":["..."]}}],"difficulty_level":3,"importance_score":0.7,"prerequisites":["unit_id_1","概念A"]}}
```"""


def build_merge_prompt(
    unit_title: str,
    sub_results: list[dict],
    context_info: str,
) -> str:
    """构建整合 prompt —— 将多个子块的分析结果合并为整体。
    传入完整的 key_points 和 concepts 数据，避免整合时丢失细节。"""
    import json as _json
    parts = []
    for i, r in enumerate(sub_results):
        kp_list = r.get('key_points', [])
        kp_items = []
        for kp in kp_list[:7]:
            if isinstance(kp, dict):
                kp_items.append(_json.dumps(kp, ensure_ascii=False))
            else:
                kp_items.append(_json.dumps({"title": str(kp)}, ensure_ascii=False))
        kp_text = ", ".join(kp_items)

        concepts_list = r.get('concepts', [])
        c_items = []
        for c in concepts_list[:5]:
            if isinstance(c, dict):
                c_items.append(_json.dumps(c, ensure_ascii=False))
            else:
                c_items.append(_json.dumps({"name": str(c)}, ensure_ascii=False))
        concepts_text = ", ".join(c_items)

        explanation = r.get('explanation', '')[:400]
        parts.append(
            f"[子块{i+1}] 摘要: {r.get('summary', '')[:500]}\n"
            f"讲解: {explanation}\n"
            f"要点: [{kp_text}]\n"
            f"概念: [{concepts_text}]"
        )
    sub_text = "\n\n".join(parts)

    return f"""整合「{unit_title}」的各子块分析结果为统一整体，返回JSON。

## 子块结果
{sub_text}

## 上下文
{context_info}

## 要求
1. summary: 300-600字整体概括（非拼接）
2. explanation: 用通俗易懂的语言讲解这个知识点，包括：① 核心思想是什么 ② 为什么重要 ③ 与现实的联系 ④ 举例说明。300-600字。像一位耐心的老师在给学生上课。
3. key_points: 5-10条结构化要点（合并去重，每条含 title/explanation/examples）
4. concepts: 合并去重（含name/definition/examples/related_concepts）
5. difficulty_level: 1-5分（1=入门 5=高级），无法判断时返回 null
6. importance_score: 0-1分，无法判断时返回 null
7. prerequisites: 前置知识（优先unit_id，其次概念名）

返回纯JSON：
```json
{{"summary":"...","explanation":"...","key_points":[{{"title":"...","explanation":"...","examples":["..."]}}],"concepts":[{{"name":"...","definition":"...","examples":["..."],"related_concepts":["..."]}}],"difficulty_level":3,"importance_score":0.7,"prerequisites":[]}}
```"""


def build_enrich_prompt(
    title: str,
    content: str,
    existing_summary: str,
    existing_key_points: list,
    existing_concepts: list,
    instruction: str,
    focus: str | None = None,
) -> str:
    """构建增量更新 prompt — 在原有分析基础上补充细节，不覆盖。

    focus 有值时，prompt 只要求返回该方向对应的字段，LLM 输出更聚焦。
    focus 无值时，返回全部字段（通用补充模式）。
    """
    points_text = "\n".join(
        f"- {p.get('title', p) if isinstance(p, dict) else p}"
        for p in existing_key_points
    ) if existing_key_points else "（无）"
    concepts_text = "\n".join(
        f"- {c.get('name', c) if isinstance(c, dict) else c}"
        for c in existing_concepts
    ) if existing_concepts else "（无）"

    safe_content = _sanitize_content(content[:4000])

    # 聚焦模式：只请求特定字段
    if focus and focus in FOCUS_DIRECTIONS:
        focus_info = FOCUS_DIRECTIONS[focus]
        target_fields = focus_info["fields"]

        # 根据目标字段构建具体任务描述
        field_tasks = {
            "summary": "用更简洁通俗的语言重新总结这个知识点（200-500字）",
            "explanation": "用通俗易懂的语言深入讲解这个知识点（300-600字），包括核心思想、为什么重要、实际联系",
            "key_points": "总结 3-5 条新的结构化要点（每条含标题和详细解释），与已有要点不重复",
            "concepts": "补充或更新关键概念（含 name/definition/examples/related_concepts）",
        }
        task_text = "\n".join(f"- {field_tasks[f]}" for f in target_fields if f in field_tasks)

        # 构建聚焦的 JSON 示例
        field_examples = {
            "summary": '"summary": "..."',
            "explanation": '"explanation": "..."',
            "key_points": '"key_points": [{"title": "...", "explanation": "...", "examples": ["..."]}]',
            "concepts": '"concepts": [{"name": "...", "definition": "...", "examples": ["..."], "related_concepts": ["..."]}]',
        }
        json_fields = ", ".join(field_examples[f] for f in target_fields if f in field_examples)

        return f"""你是一位专业的知识分析专家。以下是一个知识单元的原文和已有分析结果。
请根据补充方向，只返回指定的字段内容。

## 知识单元：{title}

## 原文（节选）
{safe_content}

## 已有摘要
{existing_summary[:500] or "（无）"}

## 已有核心要点
{points_text}

## 已有概念
{concepts_text}

## 补充方向：{focus_info["label"]}
{instruction}

## 任务
{task_text}

注意：只返回指定的字段，不要返回其他字段。返回纯JSON：
```json
{{ {json_fields} }}
```"""

    # 通用模式：返回全部字段
    return f"""你是一位专业的知识分析专家。以下是一个知识单元的已有分析结果和原文。
请根据补充指令，在原有基础上增加细节。

## 知识单元：{title}

## 原文（节选）
{safe_content}

## 已有摘要
{existing_summary[:500] or "（无）"}

## 已有核心要点
{points_text}

## 已有概念
{concepts_text}

## 补充指令
{instruction}

## 任务
1. **补充摘要**：在原有摘要基础上补充缺失的细节（300-800字）
2. **补充讲解**：用通俗易懂的语言讲解这个知识点（300-600字），像一位耐心的老师在给学生上课
3. **补充要点**：新增 2-5 条原分析遗漏的核心要点
4. **补充概念**：新增概念或补充已有概念的定义/示例/关联

请以JSON格式返回：
```json
{{
  "summary": "...",
  "explanation": "...",
  "key_points": [{{"title": "...", "explanation": "...", "examples": ["..."]}}],
  "concepts": [{{"name": "...", "definition": "...", "examples": ["..."], "related_concepts": ["..."]}}],
  "difficulty_level": 3,
  "importance_score": 0.7,
  "prerequisites": []
}}
```"""


def build_assess_prompt(summary: str, key_points: str) -> str:
    """.. deprecated:: 保留但不调用，自评由真实考试替代。

    构建自评 prompt
    """
    return f"""你刚刚学习了以下内容，请测试自己的理解程度。

## 学习内容摘要
{summary[:1000]}

## 核心要点
{key_points[:500]}

## 任务
1. 生成3道测试题（覆盖核心要点，题型混合：选择题、填空题、简答题）
2. 自己回答这些测试题
3. 评估自己的回答质量（0-100分）
4. 指出理解薄弱点

请以JSON格式返回：
```json
{{
  "test_questions": [
    {{
      "question": "...",
      "question_type": "choice",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "correct_answer": "A",
      "explanation": "..."
    }}
  ],
  "self_answers": ["...", "...", "..."],
  "score": 85,
  "weak_points": ["对XX概念的理解不够深入"]
}}
```"""
