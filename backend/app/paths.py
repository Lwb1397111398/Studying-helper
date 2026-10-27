"""运行时路径解析（开发 / frozen exe 统一入口）。

规则：
- 可写数据（db / 上传 / 日志 / .env）→ 数据根目录，**绝不**放进 sys._MEIPASS
- 只读资源（前端 dist）→ APP_STATIC_DIR 或 _MEIPASS/frontend_dist
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


DEFAULT_ENV_CONTENT = """# Studying-helper 默认配置（可在 Web 设置页修改）
# 本地 LM Studio 默认；不配也能全 fallback 跑通主流程
LLM_DEFAULT_BASE_URL=http://127.0.0.1:1234/v1
LLM_DEFAULT_API_KEY=lm-studio
LLM_DEFAULT_MODEL=local-model
LLM_BASE_URL=http://127.0.0.1:1234/v1
LLM_API_KEY=lm-studio
LLM_MODEL=local-model
LLM_MAX_CONCURRENT=2
"""


def is_frozen() -> bool:
    """PyInstaller --onefile / --onedir 打包后为 True。"""
    return bool(getattr(sys, "frozen", False))


def meipass_dir() -> Path | None:
    """onefile 解压只读临时目录；不存在则 None。"""
    mp = getattr(sys, "_MEIPASS", None)
    return Path(mp) if mp else None


def executable_dir() -> Path:
    """exe 所在目录（frozen）或当前工作目录（开发）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def backend_dir() -> Path:
    """源码模式下 backend 包根目录（含 app/）。"""
    return Path(__file__).resolve().parent.parent


def get_data_dir() -> Path:
    """可写数据根目录。

    优先级：APP_DATA_DIR > exe 同级 data/（frozen）> cwd/data（开发）。
    """
    env = (os.environ.get("APP_DATA_DIR") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    if is_frozen():
        return (executable_dir() / "data").resolve()
    return (Path.cwd() / "data").resolve()


def get_db_path() -> Path:
    return get_data_dir() / "learning.db"


def get_sqlite_url() -> str:
    """生成 aiosqlite URL（绝对路径，跨盘符安全）。"""
    path = get_db_path().resolve()
    # SQLAlchemy: sqlite+aiosqlite:///absolute/path
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def get_files_dir() -> Path:
    return get_data_dir() / "files"


def get_backups_dir() -> Path:
    return get_data_dir() / "backups"


def get_logs_dir() -> Path:
    return get_data_dir() / "logs"


def get_env_file() -> Path:
    """配置文件位置。

    frozen / 显式 APP_DATA_DIR → data/.env（便携）
    开发 → 优先 backend/.env（兼容现有），否则 data/.env
    """
    data_env = get_data_dir() / ".env"
    if is_frozen() or (os.environ.get("APP_DATA_DIR") or "").strip():
        return data_env
    legacy = backend_dir() / ".env"
    if legacy.exists():
        return legacy
    return data_env


def get_static_dir() -> Path | None:
    """前端静态资源目录；None 表示不托管（纯 API 开发模式）。"""
    env = (os.environ.get("APP_STATIC_DIR") or "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        return p if p.is_dir() else None
    if is_frozen():
        mp = meipass_dir()
        if mp:
            p = mp / "frontend_dist"
            if p.is_dir():
                return p
        # onedir 兜底：exe 旁 resources
        p2 = executable_dir() / "frontend_dist"
        if p2.is_dir():
            return p2
    return None


def ensure_data_dirs() -> Path:
    """创建数据目录结构，返回 data 根。"""
    root = get_data_dir()
    for d in (root, get_files_dir(), get_backups_dir(), get_logs_dir()):
        d.mkdir(parents=True, exist_ok=True)
    return root


def ensure_default_env() -> Path:
    """若 .env 不存在则写入默认（指向 LM Studio）。返回 env 路径。"""
    ensure_data_dirs()
    env_path = get_env_file()
    if not env_path.exists():
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text(DEFAULT_ENV_CONTENT, encoding="utf-8")
    return env_path


def path_audit_snapshot() -> dict:
    """调试/回报用：当前解析到的关键路径。"""
    return {
        "frozen": is_frozen(),
        "executable_dir": str(executable_dir()),
        "meipass": str(meipass_dir()) if meipass_dir() else None,
        "data_dir": str(get_data_dir()),
        "db_path": str(get_db_path()),
        "db_url": get_sqlite_url(),
        "files_dir": str(get_files_dir()),
        "backups_dir": str(get_backups_dir()),
        "logs_dir": str(get_logs_dir()),
        "env_file": str(get_env_file()),
        "static_dir": str(get_static_dir()) if get_static_dir() else None,
        "cwd": str(Path.cwd()),
    }
