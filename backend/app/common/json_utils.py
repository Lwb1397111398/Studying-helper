"""LLM JSON 解析工具"""

import json
import re
from typing import Any


def extract_json_object(text: str) -> str:
    match = re.search(r"```(?:json)?\s*\n?(.*?)(?:\n?```|$)", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"无法从文本中提取 JSON 对象: {text[:200]}")

    return text[start:end + 1]


def parse_llm_json(text: str) -> dict[str, Any]:
    if isinstance(text, dict):
        return text

    json_text = extract_json_object(text)
    try:
        result = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"无法解析 JSON: {json_text[:200]}") from exc

    if not isinstance(result, dict):
        raise ValueError("LLM 响应 JSON 必须是对象")
    return result
