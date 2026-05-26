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
