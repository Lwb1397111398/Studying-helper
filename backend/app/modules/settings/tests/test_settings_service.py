import pytest
from pathlib import Path
from app.modules.settings.settings_service import read_env, write_env


def test_read_env_returns_dict(tmp_path, monkeypatch):
    """读取 .env 文件应返回键值对字典"""
    env_file = tmp_path / ".env"
    env_file.write_text('KEY1="value1"\nKEY2="value2"\n', encoding="utf-8")
    monkeypatch.setattr(
        "app.modules.settings.settings_service.ENV_FILE",
        env_file,
    )
    result = read_env()
    assert result["KEY1"] == "value1"
    assert result["KEY2"] == "value2"


def test_read_env_ignores_comments_and_blanks(tmp_path, monkeypatch):
    """应忽略注释行和空行"""
    env_file = tmp_path / ".env"
    env_file.write_text('# comment\n\nKEY="val"\n', encoding="utf-8")
    monkeypatch.setattr(
        "app.modules.settings.settings_service.ENV_FILE",
        env_file,
    )
    result = read_env()
    assert result == {"KEY": "val"}


@pytest.mark.asyncio
async def test_write_env_creates_file(tmp_path, monkeypatch):
    """写入应创建文件"""
    env_file = tmp_path / ".env"
    monkeypatch.setattr(
        "app.modules.settings.settings_service.ENV_FILE",
        env_file,
    )
    await write_env({"NEW_KEY": "new_val"})
    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8")
    assert 'NEW_KEY="new_val"' in content


@pytest.mark.asyncio
async def test_write_env_merges_with_existing(tmp_path, monkeypatch):
    """写入应合并到现有配置"""
    env_file = tmp_path / ".env"
    env_file.write_text('EXISTING="old"\n', encoding="utf-8")
    monkeypatch.setattr(
        "app.modules.settings.settings_service.ENV_FILE",
        env_file,
    )
    await write_env({"NEW_KEY": "new_val"})
    result = read_env()
    assert result["EXISTING"] == "old"
    assert result["NEW_KEY"] == "new_val"


@pytest.mark.asyncio
async def test_write_env_skip_none_values(tmp_path, monkeypatch):
    """None 值应跳过不写"""
    env_file = tmp_path / ".env"
    env_file.write_text('KEEP="yes"\n', encoding="utf-8")
    monkeypatch.setattr(
        "app.modules.settings.settings_service.ENV_FILE",
        env_file,
    )
    await write_env({"KEEP": None, "ADD": "new"})
    result = read_env()
    assert result["KEEP"] == "yes"
    assert result["ADD"] == "new"


# ── 路由端点测试 ──

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.db.database import get_db
from app.deps import get_current_user


# 创建内存数据库并 override get_db 依赖，同时 mock 用户认证
@pytest.fixture(autouse=True)
def _override_deps():
    """为路由测试提供内存 SQLite 数据库 session 和 mock 用户认证"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_db():
        async with factory() as session:
            yield session

    async def _get_current_user():
        return "test-user"

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = _get_current_user
    yield
    app.dependency_overrides.clear()


def test_get_preferences():
    """GET /api/v1/settings/preferences 应返回用户偏好"""
    with patch("app.modules.settings.router.read_env") as mock_read:
        mock_read.return_value = {
            "DAILY_GOAL_MINUTES": "45",
            "DAILY_GOAL_UNITS": "8",
            "REVIEW_REMINDER": "true",
            "REMINDER_TIME": "21:00",
        }
        client = TestClient(app)
        resp = client.get("/api/v1/settings/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["daily_goal_minutes"] == 45
        assert data["daily_goal_units"] == 8
        assert data["review_reminder"] is True
        assert data["reminder_time"] == "21:00"


def test_update_preferences():
    """PUT /api/v1/settings/preferences 应更新用户偏好"""
    with patch("app.modules.settings.router.read_env") as mock_read, \
         patch("app.modules.settings.router.write_env", new_callable=AsyncMock) as mock_write:
        mock_read.return_value = {
            "DAILY_GOAL_MINUTES": "60",
            "DAILY_GOAL_UNITS": "10",
            "REVIEW_REMINDER": "false",
            "REMINDER_TIME": "19:00",
        }
        client = TestClient(app)
        resp = client.put("/api/v1/settings/preferences", json={
            "daily_goal_minutes": 60,
            "daily_goal_units": 10,
            "review_reminder": False,
            "reminder_time": "19:00",
        })
        assert resp.status_code == 200
        mock_write.assert_called_once()


def test_update_preferences_validation():
    """无效输入应返回 422"""
    client = TestClient(app)
    resp = client.put("/api/v1/settings/preferences", json={
        "daily_goal_minutes": -1,
    })
    assert resp.status_code == 422


def test_get_ai_config():
    """GET /api/v1/settings/ai-config 应返回 AI 配置（只读）"""
    with patch("app.config.settings") as mock_settings:
        mock_settings.get_llm_config.return_value = {
            "api_key": "sk-test",
            "model": "gpt-4",
            "base_url": "https://api.openai.com/v1",
        }
        mock_settings.LLM_DEFAULT_MODEL = "gpt-4o-mini"
        mock_settings.LLM_DEFAULT_BASE_URL = "https://api.openai.com/v1"
        mock_settings.LLM_TEACHING_API_KEY = ""
        mock_settings.LLM_AI_ANALYSIS_API_KEY = ""
        mock_settings.LLM_PARSER_API_KEY = ""

        client = TestClient(app)
        resp = client.get("/api/v1/settings/ai-config")
        assert resp.status_code == 200
        data = resp.json()
        assert "default_model" in data
        assert "modules" in data
        assert len(data["modules"]) == 3  # teaching, ai_analysis, parser
