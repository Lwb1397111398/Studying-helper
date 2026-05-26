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


def test_write_env_creates_file(tmp_path, monkeypatch):
    """写入应创建文件"""
    env_file = tmp_path / ".env"
    monkeypatch.setattr(
        "app.modules.settings.settings_service.ENV_FILE",
        env_file,
    )
    write_env({"NEW_KEY": "new_val"})
    assert env_file.exists()
    content = env_file.read_text(encoding="utf-8")
    assert 'NEW_KEY="new_val"' in content


def test_write_env_merges_with_existing(tmp_path, monkeypatch):
    """写入应合并到现有配置"""
    env_file = tmp_path / ".env"
    env_file.write_text('EXISTING="old"\n', encoding="utf-8")
    monkeypatch.setattr(
        "app.modules.settings.settings_service.ENV_FILE",
        env_file,
    )
    write_env({"NEW_KEY": "new_val"})
    result = read_env()
    assert result["EXISTING"] == "old"
    assert result["NEW_KEY"] == "new_val"


def test_write_env_skip_none_values(tmp_path, monkeypatch):
    """None 值应跳过不写"""
    env_file = tmp_path / ".env"
    env_file.write_text('KEEP="yes"\n', encoding="utf-8")
    monkeypatch.setattr(
        "app.modules.settings.settings_service.ENV_FILE",
        env_file,
    )
    write_env({"KEEP": None, "ADD": "new"})
    result = read_env()
    assert result["KEEP"] == "yes"
    assert result["ADD"] == "new"
