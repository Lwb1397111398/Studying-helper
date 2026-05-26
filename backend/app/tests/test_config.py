import pytest
from app.config import Settings


def test_get_llm_config_falls_back_to_default():
    """模块未配置时应回退到全局默认"""
    s = Settings(
        LLM_DEFAULT_API_KEY="sk-default",
        LLM_DEFAULT_MODEL="gpt-4o-mini",
        LLM_DEFAULT_BASE_URL="https://api.openai.com/v1",
    )
    cfg = s.get_llm_config("teaching")
    assert cfg["api_key"] == "sk-default"
    assert cfg["model"] == "gpt-4o-mini"
    assert cfg["base_url"] == "https://api.openai.com/v1"


def test_get_llm_config_module_override():
    """模块有配置时应使用模块级配置"""
    s = Settings(
        LLM_DEFAULT_API_KEY="sk-default",
        LLM_DEFAULT_MODEL="gpt-4o-mini",
        LLM_DEFAULT_BASE_URL="https://api.openai.com/v1",
        LLM_TEACHING_API_KEY="sk-teaching",
        LLM_TEACHING_MODEL="gpt-4",
        LLM_TEACHING_BASE_URL="https://custom.api.com/v1",
    )
    cfg = s.get_llm_config("teaching")
    assert cfg["api_key"] == "sk-teaching"
    assert cfg["model"] == "gpt-4"
    assert cfg["base_url"] == "https://custom.api.com/v1"


def test_get_llm_config_partial_override():
    """模块只覆盖部分字段，其余回退默认"""
    s = Settings(
        LLM_DEFAULT_API_KEY="sk-default",
        LLM_DEFAULT_MODEL="gpt-4o-mini",
        LLM_DEFAULT_BASE_URL="https://api.openai.com/v1",
        LLM_KG_MODEL="gpt-4",
    )
    cfg = s.get_llm_config("kg")
    assert cfg["api_key"] == "sk-default"
    assert cfg["model"] == "gpt-4"
    assert cfg["base_url"] == "https://api.openai.com/v1"
