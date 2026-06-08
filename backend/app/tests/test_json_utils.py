"""LLM JSON 工具测试"""

import pytest

from app.common.json_utils import extract_json_object, parse_llm_json


def test_parse_llm_json_accepts_plain_json():
    assert parse_llm_json('{"summary": "摘要"}') == {"summary": "摘要"}


def test_parse_llm_json_accepts_markdown_json_fence():
    text = "```json\n{\"summary\": \"摘要\"}\n```"
    assert parse_llm_json(text) == {"summary": "摘要"}


def test_extract_json_object_ignores_surrounding_text():
    text = "下面是结果：\n{\"summary\": \"摘要\", \"score\": 3}\n请查收"
    assert extract_json_object(text) == '{"summary": "摘要", "score": 3}'


def test_parse_llm_json_rejects_invalid_json():
    with pytest.raises(ValueError):
        parse_llm_json("不是 JSON")
