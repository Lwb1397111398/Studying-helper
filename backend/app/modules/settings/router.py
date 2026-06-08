"""设置模块 REST 端点"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.modules.settings.settings_service import read_env, write_env
from app.config import settings

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


# ── 用户偏好（可读写）──

class UserPreferences(BaseModel):
    daily_goal_minutes: int = Field(ge=1, le=1440, default=30)
    daily_goal_units: int = Field(ge=1, le=100, default=5)
    review_reminder: bool = True
    reminder_time: str = Field(pattern=r"^\d{2}:\d{2}$", default="20:00")
    llm_max_concurrent: int = Field(ge=1, le=20, default=3)


class UserPreferencesUpdate(BaseModel):
    daily_goal_minutes: int | None = Field(ge=1, le=1440, default=None)
    daily_goal_units: int | None = Field(ge=1, le=100, default=None)
    review_reminder: bool | None = None
    reminder_time: str | None = Field(pattern=r"^\d{2}:\d{2}$", default=None)
    llm_max_concurrent: int | None = Field(ge=1, le=20, default=None)


# 用户偏好 .env 键名映射
_PREF_ENV_KEYS = {
    "daily_goal_minutes": "DAILY_GOAL_MINUTES",
    "daily_goal_units": "DAILY_GOAL_UNITS",
    "review_reminder": "REVIEW_REMINDER",
    "reminder_time": "REMINDER_TIME",
    "llm_max_concurrent": "LLM_MAX_CONCURRENT",
}


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences():
    """获取用户偏好"""
    env = read_env()
    return UserPreferences(
        daily_goal_minutes=int(env.get("DAILY_GOAL_MINUTES", 30)),
        daily_goal_units=int(env.get("DAILY_GOAL_UNITS", 5)),
        review_reminder=env.get("REVIEW_REMINDER", "true").lower() == "true",
        reminder_time=env.get("REMINDER_TIME", "20:00"),
        llm_max_concurrent=int(env.get("LLM_MAX_CONCURRENT", 3)),
    )


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(body: UserPreferencesUpdate):
    """更新用户偏好"""
    updates = {
        _PREF_ENV_KEYS[k]: str(v)
        for k, v in body.model_dump(exclude_none=True).items()
    }
    await write_env(updates)
    # 如果更新了并发数，热更新信号量
    if "llm_max_concurrent" in body.model_dump(exclude_none=True):
        from app.common.llm_client import init_semaphore
        init_semaphore(body.llm_max_concurrent)
    env = read_env()
    return UserPreferences(
        daily_goal_minutes=int(env.get("DAILY_GOAL_MINUTES", 30)),
        daily_goal_units=int(env.get("DAILY_GOAL_UNITS", 5)),
        review_reminder=env.get("REVIEW_REMINDER", "true").lower() == "true",
        reminder_time=env.get("REMINDER_TIME", "20:00"),
        llm_max_concurrent=int(env.get("LLM_MAX_CONCURRENT", 3)),
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
async def get_ai_config():
    """获取 AI 模型配置（只读，需改 .env 重启生效）"""
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


# ── AI 配置（可编辑）──

class LLMModuleUpdate(BaseModel):
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None


class AIConfigUpdate(BaseModel):
    default_model: str | None = None
    default_api_key: str | None = None
    default_base_url: str | None = None
    modules: dict[str, LLMModuleUpdate] | None = None


@router.put("/ai-config", response_model=AIConfigResponse)
async def update_ai_config(body: AIConfigUpdate):
    """更新 AI 模型配置，保存后立即生效"""
    updates: dict[str, str] = {}

    # 全局默认配置
    if body.default_model is not None:
        updates["LLM_DEFAULT_MODEL"] = body.default_model
    if body.default_api_key is not None:
        updates["LLM_DEFAULT_API_KEY"] = body.default_api_key
    if body.default_base_url is not None:
        updates["LLM_DEFAULT_BASE_URL"] = body.default_base_url

    # 模块级配置
    valid_modules = {m["key"] for m in _MODULE_META}
    if body.modules:
        for module_name, mod_update in body.modules.items():
            if module_name not in valid_modules:
                continue
            prefix = f"LLM_{module_name.upper()}"
            if mod_update.model is not None:
                updates[f"{prefix}_MODEL"] = mod_update.model
            if mod_update.api_key is not None:
                updates[f"{prefix}_API_KEY"] = mod_update.api_key
            if mod_update.base_url is not None:
                updates[f"{prefix}_BASE_URL"] = mod_update.base_url

    if updates:
        await write_env(updates)
        # 同步更新内存中的 settings 对象，使其立即生效
        for key, value in updates.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        # 清除受影响的 LLM 客户端缓存，下次请求时用新配置重建
        from app.deps import clear_llm_client_cache
        if body.modules:
            for module_name in body.modules:
                if module_name in valid_modules:
                    await clear_llm_client_cache(module_name)
        # 全局默认变了，清除所有未单独配置的模块
        if any(k.startswith("LLM_DEFAULT_") for k in updates):
            await clear_llm_client_cache()

    # 返回更新后的配置
    return await get_ai_config()
