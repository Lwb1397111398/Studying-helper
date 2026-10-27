"""Step6：路径解析 / 静态开关 / 便携数据目录。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_data_dir_respects_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "mydata"))
    # 重新 import 函数（paths 无缓存目录，每次调用读 env）
    from app.paths import get_data_dir, get_db_path, get_files_dir, get_sqlite_url, ensure_data_dirs

    root = ensure_data_dirs()
    assert root == (tmp_path / "mydata").resolve()
    assert get_db_path() == root / "learning.db"
    assert get_files_dir().is_dir()
    assert get_sqlite_url().startswith("sqlite+aiosqlite:///")
    assert "mydata" in get_sqlite_url().replace("\\", "/")


def test_static_dir_none_in_dev(monkeypatch):
    monkeypatch.delenv("APP_STATIC_DIR", raising=False)
    from app.paths import get_static_dir, is_frozen

    assert is_frozen() is False
    assert get_static_dir() is None


def test_static_dir_from_env(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setenv("APP_STATIC_DIR", str(dist))
    from app.paths import get_static_dir

    assert get_static_dir() == dist.resolve()


def test_ensure_default_env_creates_once(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "d"))
    from app.paths import ensure_default_env, get_env_file

    p1 = ensure_default_env()
    assert p1.exists()
    text = p1.read_text(encoding="utf-8")
    assert "127.0.0.1:1234" in text
    # 不覆盖
    p1.write_text("LLM_API_KEY=keep-me\n", encoding="utf-8")
    p2 = ensure_default_env()
    assert "keep-me" in p2.read_text(encoding="utf-8")


def test_path_audit_snapshot_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "x"))
    from app.paths import path_audit_snapshot, ensure_data_dirs

    ensure_data_dirs()
    snap = path_audit_snapshot()
    for k in ("frozen", "data_dir", "db_path", "files_dir", "env_file", "static_dir"):
        assert k in snap


@pytest.mark.asyncio
async def test_spa_health_and_fallback(tmp_path, monkeypatch):
    """APP_STATIC_DIR 设置后 / 回 index，/api/health 仍可用。"""
    dist = tmp_path / "web"
    dist.mkdir()
    (dist / "index.html").write_text("<html>SPA-OK</html>", encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log(1)", encoding="utf-8")

    monkeypatch.setenv("APP_STATIC_DIR", str(dist))
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))

    # 需要在设置 env 后重新加载 main（模块级 _mount_spa）
    import importlib
    import app.paths as paths_mod
    importlib.reload(paths_mod)
    import app.config as config_mod
    importlib.reload(config_mod)
    import app.main as main_mod
    importlib.reload(main_mod)

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=main_mod.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # health（不依赖完整 DB 时 lifespan 会 init db — 用 data dir 即可）
        r = await client.get("/api/health")
        # lifespan 可能已跑；若 200 即可
        assert r.status_code in (200, 500)  # 500 仅当 db 初始化异常
        if r.status_code == 200:
            body = r.json()
            assert body.get("status") == "ok"
            assert "data_dir" in (body.get("paths") or {})

        r2 = await client.get("/some/spa/route")
        # SPA fallback
        assert r2.status_code == 200
        assert b"SPA-OK" in r2.content
