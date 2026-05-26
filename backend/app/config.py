"""应用配置 — 支持模块级 LLM 配置覆盖"""
from pydantic_settings import BaseSettings


# 需要支持模块级覆盖的 LLM 模块列表
LLM_MODULES = ["teaching", "ai_analysis", "parser"]


class Settings(BaseSettings):
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

    # ── 原有配置 ──
    DB_URL: str = "sqlite+aiosqlite:///./data/learning.db"
    LLM_API_KEY: str = ""          # 向后兼容，映射到 DEFAULT
    LLM_MODEL: str = "gpt-4"       # 向后兼容，映射到 DEFAULT
    LLM_BASE_URL: str = "https://api.openai.com/v1"  # 向后兼容
    FILE_STORAGE_DIR: str = "./data/files"
    BACKUP_DIR: str = "./data/backups"
    JWT_SECRET_KEY: str = "dev-only-key-replace-in-production-env"
    JWT_EXPIRE_HOURS: int = 72

    def get_llm_config(self, module: str) -> dict:
        """获取指定模块的 LLM 配置，未配置则回退到全局默认。

        Args:
            module: 模块名，如 "teaching"、"ai_analysis"、"parser"

        Returns:
            dict: {"api_key": str, "model": str, "base_url": str}
        """
        prefix = f"LLM_{module.upper()}"
        # 模块级配置为空时回退到 DEFAULT，DEFAULT 也为空时回退到旧字段
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

    class Config:
        env_file = ".env"
        extra = "allow"


settings = Settings()
