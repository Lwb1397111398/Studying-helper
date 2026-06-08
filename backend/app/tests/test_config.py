import pytest
import os
from app.config import Settings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """清除 LLM 相关环境变量，避免 .env 文件干扰测试"""
    for key in list(os.environ.keys()):
        if key.startswith("LLM_"):
            monkeypatch.delenv(key, raising=False)


def test_get_llm_config_falls_back_to_default():
    """模块未配置时应回退到全局默认"""
    s = Settings(
        _env_file=None,
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
        _env_file=None,
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
        _env_file=None,
        LLM_DEFAULT_API_KEY="sk-default",
        LLM_DEFAULT_MODEL="gpt-4o-mini",
        LLM_DEFAULT_BASE_URL="https://api.openai.com/v1",
        LLM_KG_MODEL="gpt-4",
    )
    cfg = s.get_llm_config("kg")
    assert cfg["api_key"] == "sk-default"
    assert cfg["model"] == "gpt-4"
    assert cfg["base_url"] == "https://api.openai.com/v1"


import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_llm_client_returns_cached_instance():
    """相同 module 应返回同一实例"""
    from app.deps import get_llm_client
    import app.deps as deps_mod
    deps_mod._module_clients.clear()

    with patch("app.deps.OpenAIClient") as mock_cls:
        mock_instance = AsyncMock()
        mock_cls.return_value = mock_instance

        client1 = await get_llm_client("teaching")
        client2 = await get_llm_client("teaching")
        assert client1 is client2
        mock_cls.assert_called_once()


@pytest.mark.asyncio
async def test_get_llm_client_different_modules():
    """不同 module 应创建不同实例"""
    from app.deps import get_llm_client
    import app.deps as deps_mod
    deps_mod._module_clients.clear()

    with patch("app.deps.OpenAIClient") as mock_cls:
        mock_cls.side_effect = lambda **kw: AsyncMock(**kw)

        client1 = await get_llm_client("teaching")
        client2 = await get_llm_client("parser")
        assert client1 is not client2
        assert mock_cls.call_count == 2


@pytest.mark.asyncio
async def test_module_llm_dependency_helpers_return_configured_clients():
    """模块级 LLM 依赖函数应返回对应模块的客户端实例"""
    from app.deps import (
        get_ai_analysis_llm_client,
        get_default_llm_client,
        get_parser_llm_client,
        get_teaching_llm_client,
    )
    import app.deps as deps_mod
    deps_mod._module_clients.clear()

    with patch("app.deps.OpenAIClient") as mock_cls:
        mock_cls.side_effect = lambda **kw: AsyncMock(**kw)

        default_client = await get_default_llm_client()
        teaching_client = await get_teaching_llm_client()
        ai_analysis_client = await get_ai_analysis_llm_client()
        parser_client = await get_parser_llm_client()

        assert default_client is deps_mod._module_clients["default"]
        assert teaching_client is deps_mod._module_clients["teaching"]
        assert ai_analysis_client is deps_mod._module_clients["ai_analysis"]
        assert parser_client is deps_mod._module_clients["parser"]
        assert mock_cls.call_count == 4
