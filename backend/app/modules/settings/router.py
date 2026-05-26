"""设置模块的REST端点"""
from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path
import os

router = APIRouter(prefix="/api/settings", tags=["settings"])

ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"


class SettingsResponse(BaseModel):
    llm_provider: str = "openai"
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4"
    daily_goal_minutes: int = 30
    daily_goal_units: int = 5
    review_reminder: bool = True
    reminder_time: str = "20:00"


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_api_base: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    daily_goal_minutes: int | None = None
    daily_goal_units: int | None = None
    review_reminder: bool | None = None
    reminder_time: str | None = None


def _read_env() -> dict[str, str]:
    """读取.env文件"""
    result = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _write_env(updates: dict[str, str | None]):
    """更新.env文件"""
    existing = _read_env()
    existing.update({k: v for k, v in updates.items() if v is not None})
    lines = [f'{k}="{v}"' for k, v in existing.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _to_str(v) -> str | None:
    if v is None:
        return None
    return str(v)


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """获取当前设置"""
    env = _read_env()
    return SettingsResponse(
        llm_provider=env.get("LLM_PROVIDER", "openai"),
        llm_api_base=env.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        llm_api_key=env.get("LLM_API_KEY", ""),
        llm_model=env.get("LLM_MODEL", "gpt-4"),
        daily_goal_minutes=int(env.get("DAILY_GOAL_MINUTES", 30)),
        daily_goal_units=int(env.get("DAILY_GOAL_UNITS", 5)),
        review_reminder=env.get("REVIEW_REMINDER", "true").lower() == "true",
        reminder_time=env.get("REMINDER_TIME", "20:00"),
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(body: SettingsUpdate):
    """更新设置"""
    updates = {
        "LLM_PROVIDER": body.llm_provider,
        "LLM_BASE_URL": body.llm_api_base,
        "LLM_API_KEY": body.llm_api_key,
        "LLM_MODEL": body.llm_model,
        "DAILY_GOAL_MINUTES": _to_str(body.daily_goal_minutes),
        "DAILY_GOAL_UNITS": _to_str(body.daily_goal_units),
        "REVIEW_REMINDER": _to_str(body.review_reminder),
        "REMINDER_TIME": body.reminder_time,
    }
    _write_env(updates)
    os.environ.update({k: v for k, v in updates.items() if v})

    env = _read_env()
    return SettingsResponse(
        llm_provider=env.get("LLM_PROVIDER", "openai"),
        llm_api_base=env.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        llm_api_key=env.get("LLM_API_KEY", ""),
        llm_model=env.get("LLM_MODEL", "gpt-4"),
        daily_goal_minutes=int(env.get("DAILY_GOAL_MINUTES", 30)),
        daily_goal_units=int(env.get("DAILY_GOAL_UNITS", 5)),
        review_reminder=env.get("REVIEW_REMINDER", "true").lower() == "true",
        reminder_time=env.get("REMINDER_TIME", "20:00"),
    )
