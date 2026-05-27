"""设置模块 REST 端点"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.modules.settings.settings_service import read_env, write_env
from app.config import settings
from app.deps import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── 用户偏好（可读写）──

class UserPreferences(BaseModel):
    daily_goal_minutes: int = Field(ge=1, le=1440, default=30)
    daily_goal_units: int = Field(ge=1, le=100, default=5)
    review_reminder: bool = True
    reminder_time: str = Field(pattern=r"^\d{2}:\d{2}$", default="20:00")


class UserPreferencesUpdate(BaseModel):
    daily_goal_minutes: int | None = Field(ge=1, le=1440, default=None)
    daily_goal_units: int | None = Field(ge=1, le=100, default=None)
    review_reminder: bool | None = None
    reminder_time: str | None = Field(pattern=r"^\d{2}:\d{2}$", default=None)


# 用户偏好 .env 键名映射
_PREF_ENV_KEYS = {
    "daily_goal_minutes": "DAILY_GOAL_MINUTES",
    "daily_goal_units": "DAILY_GOAL_UNITS",
    "review_reminder": "REVIEW_REMINDER",
    "reminder_time": "REMINDER_TIME",
}


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences(current_user: str = Depends(get_current_user)):
    """获取用户偏好"""
    if current_user == "anonymous":
        raise HTTPException(status_code=401, detail="请先登录")
    env = read_env()
    return UserPreferences(
        daily_goal_minutes=int(env.get("DAILY_GOAL_MINUTES", 30)),
        daily_goal_units=int(env.get("DAILY_GOAL_UNITS", 5)),
        review_reminder=env.get("REVIEW_REMINDER", "true").lower() == "true",
        reminder_time=env.get("REMINDER_TIME", "20:00"),
    )


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(
    body: UserPreferencesUpdate,
    current_user: str = Depends(get_current_user),
):
    """更新用户偏好"""
    if current_user == "anonymous":
        raise HTTPException(status_code=401, detail="请先登录")
    updates = {
        _PREF_ENV_KEYS[k]: str(v)
        for k, v in body.model_dump(exclude_none=True).items()
    }
    write_env(updates)
    env = read_env()
    return UserPreferences(
        daily_goal_minutes=int(env.get("DAILY_GOAL_MINUTES", 30)),
        daily_goal_units=int(env.get("DAILY_GOAL_UNITS", 5)),
        review_reminder=env.get("REVIEW_REMINDER", "true").lower() == "true",
        reminder_time=env.get("REMINDER_TIME", "20:00"),
    )


# ── AI 配置（只读）──

class LLMModuleConfig(BaseModel):
    module: str
    label: str
    description: str
    strength_hint: str
    model: str
    has_custom_key: bool
    base_url: str


class AIConfigResponse(BaseModel):
    default_model: str
    default_base_url: str
    modules: list[LLMModuleConfig]


# 模块元数据：实际调用 LLM 的模块
_MODULE_META = [
    {
        "key": "teaching",
        "label": "🎯 教学策略",
        "desc": "类比/举例/对比生成、问答、测试出题",
        "hint": "强",
    },
    {
        "key": "ai_analysis",
        "label": "🧠 AI 分析",
        "desc": "内容分析、出题、掌握度评估",
        "hint": "强",
    },
    {
        "key": "parser",
        "label": "📚 书本导入",
        "desc": "目录识别、章节标题优化（LLM fallback）",
        "hint": "弱",
    },
]


@router.get("/ai-config", response_model=AIConfigResponse)
async def get_ai_config(current_user: str = Depends(get_current_user)):
    """获取 AI 模型配置（只读，需改 .env 重启生效）"""
    if current_user == "anonymous":
        raise HTTPException(status_code=401, detail="请先登录")
    modules = []
    for m in _MODULE_META:
        cfg = settings.get_llm_config(m["key"])
        has_custom = bool(
            getattr(settings, f"LLM_{m['key'].upper()}_API_KEY", "")
        )
        modules.append(LLMModuleConfig(
            module=m["key"],
            label=m["label"],
            description=m["desc"],
            strength_hint=m["hint"],
            model=cfg["model"],
            has_custom_key=has_custom,
            base_url=cfg["base_url"],
        ))
    return AIConfigResponse(
        default_model=settings.LLM_DEFAULT_MODEL or settings.LLM_MODEL,
        default_base_url=settings.LLM_DEFAULT_BASE_URL or settings.LLM_BASE_URL,
        modules=modules,
    )
