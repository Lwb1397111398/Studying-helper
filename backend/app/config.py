"""应用配置 — 支持模块级 LLM 配置覆盖 + 便携路径"""
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.paths import (
    ensure_data_dirs,
    get_backups_dir,
    get_env_file,
    get_files_dir,
    get_sqlite_url,
)


# 需要支持模块级覆盖的 LLM 模块列表
LLM_MODULES = ["teaching", "ai_analysis", "parser", "aid"]


def _env_file_tuple() -> tuple[str, ...]:
    """启动时解析 .env 位置（可能尚未创建）。"""
    try:
        p = get_env_file()
        return (str(p),) if p else ()
    except Exception:
        return ()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file_tuple() or None,
        env_file_encoding="utf-8",
        extra="allow",
    )

    # ── 全局默认 LLM 配置（保底）──
    LLM_DEFAULT_API_KEY: str = ""
    LLM_DEFAULT_MODEL: str = "gpt-4o-mini"
    LLM_DEFAULT_BASE_URL: str = "https://api.openai.com/v1"

    # ── 教学模块 LLM 配置 ──
    LLM_TEACHING_API_KEY: str = ""
    LLM_TEACHING_MODEL: str = ""
    LLM_TEACHING_BASE_URL: str = ""

    # ── AI 分析模块 LLM 配置 ──
    LLM_AI_ANALYSIS_API_KEY: str = ""
    LLM_AI_ANALYSIS_MODEL: str = ""
    LLM_AI_ANALYSIS_BASE_URL: str = ""

    # ── 文档解析模块 LLM 配置 ──
    LLM_PARSER_API_KEY: str = ""
    LLM_PARSER_MODEL: str = ""
    LLM_PARSER_BASE_URL: str = ""

    # ── 适应性教学设计（AID）模块 LLM 配置 ──
    LLM_AID_API_KEY: str = ""
    LLM_AID_MODEL: str = ""
    LLM_AID_BASE_URL: str = ""

    # ── 并发控制 ──
    LLM_MAX_CONCURRENT: int = 4

    # ── 原有配置（相对路径默认值会在 validator 中解析为绝对）──
    DB_URL: str = "sqlite+aiosqlite:///./data/learning.db"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    FILE_STORAGE_DIR: str = "./data/files"
    BACKUP_DIR: str = "./data/backups"
    JWT_SECRET_KEY: str = ""
    JWT_EXPIRE_HOURS: int = 72
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:8765,http://127.0.0.1:8765,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )
    # 生产静态目录（也可通过环境变量 APP_STATIC_DIR 设置，见 paths.get_static_dir）
    APP_STATIC_DIR: str = ""

    @model_validator(mode="after")
    def _resolve_portable_paths(self) -> "Settings":
        """把相对默认路径解析到 paths 数据根；显式绝对/环境覆盖保留。"""
        ensure_data_dirs()

        # DB：默认相对路径或空 → 统一绝对 URL
        db = (self.DB_URL or "").strip()
        if (
            not db
            or db == "sqlite+aiosqlite:///./data/learning.db"
            or db.startswith("sqlite+aiosqlite:///./")
        ):
            self.DB_URL = get_sqlite_url()

        # 文件存储
        fs = (self.FILE_STORAGE_DIR or "").strip()
        if not fs or fs in ("./data/files", "data/files"):
            self.FILE_STORAGE_DIR = str(get_files_dir())
        else:
            p = Path(fs).expanduser()
            if not p.is_absolute():
                p = (get_files_dir().parent / p).resolve()
            self.FILE_STORAGE_DIR = str(p)
            p.mkdir(parents=True, exist_ok=True)

        # 备份
        bk = (self.BACKUP_DIR or "").strip()
        if not bk or bk in ("./data/backups", "data/backups"):
            self.BACKUP_DIR = str(get_backups_dir())
        else:
            p = Path(bk).expanduser()
            if not p.is_absolute():
                p = (get_backups_dir().parent / p).resolve()
            self.BACKUP_DIR = str(p)
            p.mkdir(parents=True, exist_ok=True)

        return self

    def get_llm_config(self, module: str) -> dict:
        """获取指定模块的 LLM 配置，未配置则回退到全局默认。"""
        prefix = f"LLM_{module.upper()}"
        api_key = (
            getattr(self, f"{prefix}_API_KEY", "")
            or self.LLM_DEFAULT_API_KEY
            or self.LLM_API_KEY
        )
        model = (
            getattr(self, f"{prefix}_MODEL", "")
            or self.LLM_DEFAULT_MODEL
            or self.LLM_MODEL
        )
        base_url = (
            getattr(self, f"{prefix}_BASE_URL", "")
            or self.LLM_DEFAULT_BASE_URL
            or self.LLM_BASE_URL
        )
        return {"api_key": api_key, "model": model, "base_url": base_url}


# 注意：import 时会 ensure_data_dirs；测试若需隔离请设 APP_DATA_DIR
settings = Settings()
