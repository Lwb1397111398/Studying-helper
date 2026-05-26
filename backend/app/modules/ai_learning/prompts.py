"""AI学习提示词模板"""

# 最大内容长度（字符），防止超长输入
MAX_CONTENT_LENGTH = 3000

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
    return f"""你是一位专业的知识分析专家。请仔细阅读以下学习材料，完成以下任务：

## 学习材料
{safe_content}

## 上下文
{context_info}

## 任务
1. **摘要**（200-500字）：概括本段内容的核心要义
2. **核心要点**（3-7条）：提取最重要的知识点，每条一句话
3. **核心概念**：提取关键概念，每个概念包含：
   - 名称
   - 一句话定义
   - 1-2个示例
   - 相关概念
4. **难度评估**（1-5分）：
   - 1=入门级，无需前置知识
   - 2=基础，需要少量背景
   - 3=中等，需要一定基础
   - 4=进阶，需要扎实基础
   - 5=高级，需要深入理解前置概念
5. **重要程度**（0-1分）：在整本书中的重要性
6. **前置知识**：学习本段内容前需要掌握的知识。
   格式：可以是 unit_id（如果你能推断出对应单元的ID）或概念名称字符串。
   优先输出 unit_id，无法确定时输出概念名称。

请以JSON格式返回：
```json
{{
  "summary": "...",
  "key_points": ["...", "..."],
  "concepts": [{{"name": "...", "definition": "...", "examples": ["..."], "related_concepts": ["..."]}}],
  "difficulty_level": 3,
  "importance_score": 0.7,
  "prerequisites": ["unit_id_1", "概念A"]
}}
```"""


def build_merge_prompt(
    unit_title: str,
    sub_results: list[dict],
    context_info: str,
) -> str:
    """构建整合 prompt —— 将多个子块的分析结果合并为整体"""
    # 拼合各子块结果
    parts = []
    for i, r in enumerate(sub_results):
        parts.append(f"## 子块 {i+1}\n摘要: {r.get('summary', '')}\n"
                      f"核心概念: {', '.join(c.get('name','') for c in r.get('concepts', []))}\n"
                      f"核心要点: {'; '.join(r.get('key_points', []))}")
    sub_text = "\n\n".join(parts)

    return f"""你是一位专业的知识分析专家。以下是对「{unit_title}」这个知识单元
按段落分块后各块的分析结果。请将这些分散的分析整合为一份统一的整体分析。

## 各子块分析结果
{sub_text}

## 上下文
{context_info}

## 整合任务
1. **综合摘要**（300-600字）：站在整体角度概括本单元核心要义，不是各子块摘要的拼接
2. **核心要点**（5-10条）：合并去重后的最重要知识点
3. **核心概念**：合并去重，每个概念包含名称、一句话定义、1-2个示例、相关概念
4. **难度评估**（1-5分）
5. **重要程度**（0-1分）
6. **前置知识**：学习本单元前需要掌握的知识（优先输出 unit_id，其次概念名称）

请以JSON格式返回：
```json
{{
  "summary": "...",
  "key_points": ["...", "..."],
  "concepts": [{{"name": "...", "definition": "...", "examples": ["..."], "related_concepts": ["..."]}}],
  "difficulty_level": 3,
  "importance_score": 0.7,
  "prerequisites": ["unit_id_1", "概念A"]
}}
```"""


def build_enrich_prompt(
    title: str,
    content: str,
    existing_summary: str,
    existing_key_points: list,
    existing_concepts: list,
    instruction: str,
) -> str:
    """构建增量更新 prompt — 在原有分析基础上补充细节，不覆盖"""
    points_text = "\n".join(f"- {p}" for p in existing_key_points) if existing_key_points else "（无）"
    concepts_text = "\n".join(
        f"- {c.get('name', c) if isinstance(c, dict) else c}"
        for c in existing_concepts
    ) if existing_concepts else "（无）"

    return f"""你是一位专业的知识分析专家。以下是一个知识单元的已有分析结果和原文。
请根据补充指令，在原有基础上增加细节。

## 知识单元：{title}

## 原文（节选）
{content[:2000]}

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
2. **补充要点**：新增 2-5 条原分析遗漏的核心要点
3. **补充概念**：新增概念或补充已有概念的定义/示例/关联

请以JSON格式返回：
```json
{{
  "summary": "...",
  "key_points": ["...", "..."],
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
