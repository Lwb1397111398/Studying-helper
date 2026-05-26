# 设置模块优化实施计划

> **For agentic workers:** REQUIRED SUBILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构设置模块：支持模块级 LLM 配置（不同模块用不同 AI 模型）、前端去掉自动保存、加输入校验、抽 service 层。

**Architecture:**
- 后端：config.py 加 `get_llm_config(module)` 支持模块级覆盖+回退全局默认；deps.py 的 `get_llm_client()` 支持 module 参数缓存多实例；抽 settings_service.py 封装 .env 读写；router.py 拆分端点加校验
- 前端：去掉输入框自动保存只保留保存按钮；AI 配置只读展示区；API 路径从 `/settings` 改为 `/settings/preferences`
- 实际调用 LLM 的只有 3 个模块：teaching、ai_learning、document_parser(toc_detector)，其余模块不改

**Tech Stack:** Python FastAPI + pydantic_settings, React + TypeScript

---

## 文件改动总览

| 文件 | 类型 | 说明 |
|------|------|------|
| `backend/app/config.py` | 修改 | 加模块级 LLM 配置字段 + `get_llm_config()` |
| `backend/app/deps.py` | 修改 | `get_llm_client()` 支持 module 参数 + 多实例缓存 |
| `backend/app/modules/settings/settings_service.py` | **新增** | 封装 .env 读写逻辑 |
| `backend/app/modules/settings/router.py` | 修改 | 拆分端点 + 校验 + 只读 AI 配置 |
| `backend/app/modules/teaching/router.py` | 修改 | 传 `"teaching"` 模块名 |
| `backend/app/modules/ai_learning/router.py` | 修改 | 传 `"ai_analysis"` 模块名 |
| `backend/app/modules/document_parser/toc_detector.py` | 修改 | 接收 llm_client 参数（从 router 传入） |
| `backend/app/modules/document_parser/router.py` | 修改 | 传 `"parser"` 模块名给 toc_detector |
| `backend/.env` | 修改 | 加模块级配置项 |
| `frontend/src/api/settings.ts` | 修改 | 拆分 API 函数 |
| `frontend/src/contexts/AppContext.tsx` | 修改 | AI 配置独立状态 |
| `frontend/src/pages/Settings.tsx` | 修改 | 去掉自动保存 + 加 AI 配置展示区 |
| `frontend/src/types/index.ts` | 修改 | UserSettings 去掉 LLM 字段 + 加 AIConfig 类型 |

---

### Task 1: config.py — 加模块级 LLM 配置

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/app/tests/test_config.py`：

```python
import pytest
from unittest.mock import patch
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && python -m pytest app/tests/test_config.py -v
```
Expected: FAIL (test_config.py 不存在或 Settings 无 get_llm_config)

- [ ] **Step 3: 修改 config.py**

```python
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


settings = Settings()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && python -m pytest app/tests/test_config.py -v
```
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/config.py app/tests/test_config.py
git commit -m "feat(config): add module-level LLM config with fallback to global default"
```

---

### Task 2: deps.py — 支持 module 参数的多实例 LLM 客户端

**Files:**
- Modify: `backend/app/deps.py`

- [ ] **Step 1: 写失败测试**

在 `backend/app/tests/test_config.py` 追加：

```python
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_llm_client_returns_cached_instance():
    """相同 module 应返回同一实例"""
    from app.deps import get_llm_client
    # 清空缓存
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && python -m pytest app/tests/test_config.py::test_get_llm_client_returns_cached_instance -v
```
Expected: FAIL

- [ ] **Step 3: 修改 deps.py**

```python
"""FastAPI依赖注入"""
import asyncio
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.config import settings
from app.common.llm_client import OpenAIClient
from app.modules.user_storage.services import (
    UserService, BookService, LearningRecordService, CacheService, FileStorage,
)
from app.modules.user_storage.auth import get_current_user_id

# 模块级 LLM 客户端缓存 {module_name: OpenAIClient}
_module_clients: dict[str, OpenAIClient] = {}
_llm_lock = asyncio.Lock()


async def get_llm_client(module: str = "default") -> OpenAIClient:
    """获取指定模块的 LLM 客户端。

    相同 module 复用同一实例，不同 module 使用各自的配置和实例。
    module="default" 时向后兼容原有行为。
    """
    if module in _module_clients:
        return _module_clients[module]

    async with _llm_lock:
        if module in _module_clients:
            return _module_clients[module]
        cfg = settings.get_llm_config(module)
        client = OpenAIClient(
            api_key=cfg["api_key"],
            model=cfg["model"],
            base_url=cfg["base_url"],
        )
        _module_clients[module] = client
        return client


async def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


async def get_book_service(db: AsyncSession = Depends(get_db)) -> BookService:
    return BookService(db)


async def get_record_service(db: AsyncSession = Depends(get_db)) -> LearningRecordService:
    return LearningRecordService(db)


async def get_cache_service(db: AsyncSession = Depends(get_db)) -> CacheService:
    return CacheService(db)


async def get_file_storage() -> FileStorage:
    return FileStorage(settings.FILE_STORAGE_DIR)


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> str:
    """
    验证 user_id 对应的用户存在，返回 user_id。
    anonymous 直接放行（向后兼容）。
    """
    if user_id == "anonymous":
        return user_id
    from app.modules.user_storage.services.user_service import UserService
    await UserService(db).get_user(user_id)
    return user_id
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && python -m pytest app/tests/test_config.py -v
```
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/deps.py app/tests/test_config.py
git commit -m "feat(deps): support module-level LLM client with multi-instance cache"
```

---

### Task 3: 抽 settings_service.py

**Files:**
- Create: `backend/app/modules/settings/settings_service.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/app/modules/settings/tests/test_settings_service.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && python -m pytest app/modules/settings/tests/test_settings_service.py -v
```
Expected: FAIL

- [ ] **Step 3: 创建 settings_service.py**

```python
"""设置服务层 — 封装 .env 文件读写逻辑"""
from pathlib import Path
import os

ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"


def read_env() -> dict[str, str]:
    """读取 .env 文件，返回键值对字典"""
    result: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def write_env(updates: dict[str, str | None]):
    """更新 .env 文件，合并现有配置，跳过 None 值。

    写入后同步更新 os.environ，使当前进程生效。
    """
    existing = read_env()
    existing.update({k: v for k, v in updates.items() if v is not None})
    lines = [f'{k}="{v}"' for k, v in sorted(existing.items())]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 同步到环境变量，使当前进程生效
    os.environ.update({k: v for k, v in updates.items() if v is not None})
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && python -m pytest app/modules/settings/tests/test_settings_service.py -v
```
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/modules/settings/settings_service.py app/modules/settings/tests/test_settings_service.py
git commit -m "feat(settings): extract settings_service for .env read/write"
```

---

### Task 4: router.py — 拆分端点 + 校验 + 只读 AI 配置

**Files:**
- Modify: `backend/app/modules/settings/router.py`

- [ ] **Step 1: 写失败测试**

在 `backend/app/modules/settings/tests/test_settings_service.py` 追加：

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app


def test_get_preferences():
    """GET /api/settings/preferences 应返回用户偏好"""
    with patch("app.modules.settings.router.read_env") as mock_read:
        mock_read.return_value = {
            "DAILY_GOAL_MINUTES": "45",
            "DAILY_GOAL_UNITS": "8",
            "REVIEW_REMINDER": "true",
            "REMINDER_TIME": "21:00",
        }
        client = TestClient(app)
        resp = client.get("/api/settings/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert data["daily_goal_minutes"] == 45
        assert data["daily_goal_units"] == 8
        assert data["review_reminder"] is True
        assert data["reminder_time"] == "21:00"


def test_update_preferences():
    """PUT /api/settings/preferences 应更新用户偏好"""
    with patch("app.modules.settings.router.read_env") as mock_read, \
         patch("app.modules.settings.router.write_env") as mock_write:
        mock_read.return_value = {
            "DAILY_GOAL_MINUTES": "60",
            "DAILY_GOAL_UNITS": "10",
            "REVIEW_REMINDER": "false",
            "REMINDER_TIME": "19:00",
        }
        client = TestClient(app)
        resp = client.put("/api/settings/preferences", json={
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
    resp = client.put("/api/settings/preferences", json={
        "daily_goal_minutes": -1,
    })
    assert resp.status_code == 422


def test_get_ai_config():
    """GET /api/settings/ai-config 应返回 AI 配置（只读）"""
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
        resp = client.get("/api/settings/ai-config")
        assert resp.status_code == 200
        data = resp.json()
        assert "default_model" in data
        assert "modules" in data
        assert len(data["modules"]) == 3  # teaching, ai_analysis, parser
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && python -m pytest app/modules/settings/tests/test_settings_service.py::test_get_preferences -v
```
Expected: FAIL

- [ ] **Step 3: 重写 router.py**

```python
"""设置模块 REST 端点"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.modules.settings.settings_service import read_env, write_env
from app.config import settings

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
async def get_preferences():
    """获取用户偏好"""
    env = read_env()
    return UserPreferences(
        daily_goal_minutes=int(env.get("DAILY_GOAL_MINUTES", 30)),
        daily_goal_units=int(env.get("DAILY_GOAL_UNITS", 5)),
        review_reminder=env.get("REVIEW_REMINDER", "true").lower() == "true",
        reminder_time=env.get("REMINDER_TIME", "20:00"),
    )


@router.put("/preferences", response_model=UserPreferences)
async def update_preferences(body: UserPreferencesUpdate):
    """更新用户偏好"""
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && python -m pytest app/modules/settings/tests/test_settings_service.py -v
```
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/modules/settings/router.py app/modules/settings/tests/test_settings_service.py
git commit -m "feat(settings): split endpoints, add validation, read-only AI config"
```

---

### Task 5: teaching router — 传模块名

**Files:**
- Modify: `backend/app/modules/teaching/router.py:81-85`

- [ ] **Step 1: 修改 _get_service**

将：
```python
def _get_service(
    db: AsyncSession = Depends(get_db),
    llm_client=Depends(get_llm_client),
) -> TeachingService:
    return TeachingService(llm_client=llm_client, db=db)
```

改为：
```python
def _get_service(
    db: AsyncSession = Depends(get_db),
    llm_client=Depends(lambda: get_llm_client("teaching")),
) -> TeachingService:
    return TeachingService(llm_client=llm_client, db=db)
```

- [ ] **Step 2: 运行 teaching 测试确认没挂**

```bash
cd backend && python -m pytest app/modules/teaching/tests/ -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/modules/teaching/router.py
git commit -m "feat(teaching): use module-specific LLM client"
```

---

### Task 6: ai_learning router — 传模块名

**Files:**
- Modify: `backend/app/modules/ai_learning/router.py:233,291`

- [ ] **Step 1: 修改两处 llm_client 注入**

将两处：
```python
llm_client: LLMClient = Depends(get_llm_client),
```

改为：
```python
llm_client: LLMClient = Depends(lambda: get_llm_client("ai_analysis")),
```

- [ ] **Step 2: 运行 ai_learning 测试确认没挂**

```bash
cd backend && python -m pytest app/modules/ai_learning/tests/ -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/modules/ai_learning/router.py
git commit -m "feat(ai_learning): use module-specific LLM client"
```

---

### Task 7: document_parser — 传模块名给 toc_detector

**Files:**
- Modify: `backend/app/modules/document_parser/router.py`
- Modify: `backend/app/modules/document_parser/toc_detector.py`

- [ ] **Step 1: 查看 toc_detector 调用点**

在 router.py 中找到调用 `identify_toc_items_with_llm` 或传 `llm_client` 的地方。

- [ ] **Step 2: 修改 router.py 的 parse_document 和 confirm_toc**

在 `parse_document` 函数中，获取 parser 模块的 llm_client 并传给 toc_detector：

```python
# 在 parse_document 函数中，获取 llm_client
from app.deps import get_llm_client as _get_llm
import asyncio

# 在需要传给 toc_detector 的地方：
parser_llm = await _get_llm("parser")
# 传给 toc_detector.identify_toc(llm_client=parser_llm)
```

具体地，找到 `_get_service()` 函数，改为接受可选的 llm_client 参数：

```python
def _get_service(llm_client=None) -> DocumentParserService:
    parsers = [PDFParser(), TXTParser(), EPUBParser()]
    return DocumentParserService(
        parsers=parsers,
        storage_dir=settings.FILE_STORAGE_DIR,
        llm_client=llm_client,
    )
```

- [ ] **Step 3: 修改 DocumentParserService 接受 llm_client**

在 `document_parser/service.py` 中，让 `parse_and_store` 方法把 llm_client 传给 toc_detector。

- [ ] **Step 4: 运行 document_parser 测试确认没挂**

```bash
cd backend && python -m pytest app/modules/document_parser/tests/ -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/modules/document_parser/router.py app/modules/document_parser/service.py app/modules/document_parser/toc_detector.py
git commit -m "feat(document_parser): pass module-specific LLM client to toc_detector"
```

---

### Task 8: 更新 .env 文件

**Files:**
- Modify: `backend/.env`

- [ ] **Step 1: 更新 .env**

将现有：
```
LLM_BASE_URL="https://api.longcat.chat/openai/v1"
LLM_API_KEY="ak_2gJ7ez5041gN0Mq0i69cA7v32Or57"
LLM_MODEL="LongCat-2.0-Preview"
```

改为：
```env
# ── 全局默认 LLM 配置（保底）──
LLM_DEFAULT_BASE_URL="https://api.longcat.chat/openai/v1"
LLM_DEFAULT_API_KEY="ak_2gJ7ez5041gN0Mq0i69cA7v32Or57"
LLM_DEFAULT_MODEL="LongCat-2.0-Preview"

# ── 各模块覆盖（不填则用全局默认）──
# 教学策略：类比/举例/对比生成 → 建议强模型
# LLM_TEACHING_API_KEY=""
# LLM_TEACHING_MODEL=""
# LLM_TEACHING_BASE_URL=""

# AI 分析：内容分析、出题、评估 → 建议强模型
# LLM_AI_ANALYSIS_API_KEY=""
# LLM_AI_ANALYSIS_MODEL=""
# LLM_AI_ANALYSIS_BASE_URL=""

# 书本导入：目录识别 → 弱模型即可
# LLM_PARSER_API_KEY=""
# LLM_PARSER_MODEL=""
# LLM_PARSER_BASE_URL=""

# ── 向后兼容（旧字段，优先级低于 DEFAULT）──
LLM_BASE_URL="https://api.longcat.chat/openai/v1"
LLM_API_KEY="ak_2gJ7ez5041gN0Mq0i69cA7v32Or57"
LLM_MODEL="LongCat-2.0-Preview"
```

- [ ] **Step 2: 启动后端验证配置加载正常**

```bash
cd backend && python -c "from app.config import settings; print(settings.get_llm_config('teaching'))"
```
Expected: 打印出包含 api_key, model, base_url 的字典

- [ ] **Step 3: Commit**

```bash
cd backend && git add .env
git commit -m "chore(env): add module-level LLM config structure"
```

---

### Task 9: 前端 types — 调整 UserSettings + 加 AIConfig 类型

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 修改 UserSettings 接口**

将 LLM 相关字段从 UserSettings 移除，加 AIConfig 相关类型：

```typescript
// 用户设置（仅用户偏好，不含 LLM 配置）
export interface UserSettings {
  daily_goal_minutes: number;
  daily_goal_units: number;
  review_reminder: boolean;
  reminder_time: string;
}

// AI 模块配置（只读）
export interface LLMModuleConfig {
  module: string;
  label: string;
  description: string;
  strength_hint: string;
  model: string;
  has_custom_key: boolean;
  base_url: string;
}

export interface AIConfigResponse {
  default_model: string;
  default_base_url: string;
  modules: LLMModuleConfig[];
}
```

- [ ] **Step 2: 检查 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: 无错误（或有其他无关错误）

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/types/index.ts
git commit -m "feat(types): separate UserSettings from AI config types"
```

---

### Task 10: 前端 settings API 层

**Files:**
- Modify: `frontend/src/api/settings.ts`

- [ ] **Step 1: 重写 settings.ts**

```typescript
// Settings API

import client from './client';
import type { UserSettings, AIConfigResponse } from '../types';

// 获取用户偏好
export const getPreferences = (): Promise<UserSettings> => {
  return client.get('/settings/preferences');
};

// 更新用户偏好
export const updatePreferences = (settings: Partial<UserSettings>): Promise<UserSettings> => {
  return client.put('/settings/preferences', settings);
};

// 获取 AI 配置（只读）
export const getAIConfig = (): Promise<AIConfigResponse> => {
  return client.get('/settings/ai-config');
};
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/api/settings.ts
git commit -m "feat(api): split settings API into preferences + ai-config"
```

---

### Task 11: 前端 AppContext — AI 配置独立状态

**Files:**
- Modify: `frontend/src/contexts/AppContext.tsx`

- [ ] **Step 1: 修改 AppContext**

```typescript
// Global app state - auth + user info + settings cache

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { AuthUser, UserSettings, AIConfigResponse } from '../types';
import { getPreferences, updatePreferences as apiUpdatePreferences, getAIConfig } from '../api/settings';
import client from '../api/client';

interface AppState {
  userId: string;
  user: AuthUser | null;
  isLoggedIn: boolean;
  settings: UserSettings | null;
  settingsLoaded: boolean;
  aiConfig: AIConfigResponse | null;
  login: (username: string) => Promise<void>;
  logout: () => void;
  refreshSettings: () => Promise<void>;
  saveSettings: (patch: Partial<UserSettings>) => Promise<void>;
  refreshAIConfig: () => Promise<void>;
}

const defaultSettings: UserSettings = {
  daily_goal_minutes: 30,
  daily_goal_units: 5,
  review_reminder: true,
  reminder_time: '20:00',
};

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const saved = localStorage.getItem('user');
    return saved ? JSON.parse(saved) : null;
  });
  const [userId, setUserId] = useState<string>(() =>
    localStorage.getItem('auth_token') ? (user?.id || '') : 'anonymous'
  );
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [aiConfig, setAiConfig] = useState<AIConfigResponse | null>(null);

  const isLoggedIn = !!localStorage.getItem('auth_token');

  const login = useCallback(async (username: string) => {
    const res: any = await client.post('/v1/auth/login', { username });
    localStorage.setItem('auth_token', res.token);
    localStorage.setItem('user', JSON.stringify(res.user));
    setUser(res.user);
    setUserId(res.user.id);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user');
    setUser(null);
    setUserId('anonymous');
  }, []);

  const refreshSettings = useCallback(async () => {
    try {
      const data = await getPreferences();
      setSettings(prev => ({ ...defaultSettings, ...prev, ...data }));
    } catch {
      setSettings(prev => prev ?? defaultSettings);
    } finally {
      setSettingsLoaded(true);
    }
  }, []);

  const saveSettings = useCallback(async (patch: Partial<UserSettings>) => {
    const updated = await apiUpdatePreferences(patch);
    setSettings(prev => ({ ...defaultSettings, ...prev, ...updated }));
  }, []);

  const refreshAIConfig = useCallback(async () => {
    try {
      const data = await getAIConfig();
      setAiConfig(data);
    } catch {
      // 静默失败，AI 配置非关键
    }
  }, []);

  useEffect(() => {
    refreshSettings();
    refreshAIConfig();
  }, [refreshSettings, refreshAIConfig]);

  return (
    <AppContext.Provider value={{
      userId, user, isLoggedIn, settings, settingsLoaded, aiConfig,
      login, logout, refreshSettings, saveSettings, refreshAIConfig,
    }}>
      {AppContext.Provider>
    </AppContext.Provider>
  );
}

export function useAppState(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppState must be used within <AppProvider>');
  return ctx;
}

export { defaultSettings };
```

- [ ] **Step 2: 检查 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: 无新增错误

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/contexts/AppContext.tsx
git commit -m "feat(context): separate AI config state from user preferences"
```

---

### Task 12: 前端 Settings 页面 — 去自动保存 + AI 配置展示

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: 重写 Settings.tsx**

```tsx
import { useState } from 'react';
import Card from '../components/Card';
import { useAppState, defaultSettings } from '../contexts/AppContext';

export default function Settings() {
  const { settings, settingsLoaded, saveSettings, aiConfig } = useAppState();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  // 本地草稿，保存时才提交
  const [draft, setDraft] = useState<Partial<typeof defaultSettings>>({});

  // 用 settings 或默认值，合并本地草稿
  const s = { ...(settings ?? defaultSettings), ...draft };

  const update = <K extends keyof typeof defaultSettings>(
    key: K,
    value: (typeof defaultSettings)[K],
  ) => {
    setDraft(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveSettings({ ...(settings ?? defaultSettings), ...draft });
      setDraft({});
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      alert('保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (!settingsLoaded) {
    return <div className="max-w-2xl mx-auto p-10 text-center text-gray-400">加载中...</div>;
  }

  return (
    <div className="max-w-2xl mx-auto animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-800">设置</h1>
        <p className="text-sm text-gray-400 mt-0.5">配置学习目标和模型参数</p>
      </div>

      {/* 学习目标 */}
      <Card className="mb-5">
        <h2 className="text-sm font-bold text-gray-700 mb-5 flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-blue-50 flex items-center justify-center text-sm">🎯</span>
          学习目标
        </h2>
        <div className="space-y-5">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">每日学习时长（分钟）</label>
            <input type="number" min={1} max={1440} value={s.daily_goal_minutes}
              onChange={(e) => update('daily_goal_minutes', Math.max(1, Number(e.target.value)))}
              className="w-full p-3 border border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-2">每日完成单元数</label>
            <input type="number" min={1} max={100} value={s.daily_goal_units}
              onChange={(e) => update('daily_goal_units', Math.max(1, Number(e.target.value)))}
              className="w-full p-3 border border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
          </div>
        </div>
      </Card>

      {/* 复习提醒 */}
      <Card className="mb-5">
        <h2 className="text-sm font-bold text-gray-700 mb-5 flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-amber-50 flex items-center justify-center text-sm">🔔</span>
          复习提醒
        </h2>
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm text-gray-700 font-medium">开启复习提醒</span>
              <p className="text-xs text-gray-400 mt-0.5">每天定时提醒你复习</p>
            </div>
            <button onClick={() => update('review_reminder', !s.review_reminder)}
              className={`w-11 h-6 rounded-full transition-colors relative ${
                s.review_reminder ? 'bg-blue-500' : 'bg-gray-200'
              }`}>
              <div className={`w-5 h-5 bg-white rounded-full shadow-sm absolute top-0.5 transition-transform ${
                s.review_reminder ? 'translate-x-5.5' : 'translate-x-0.5'
              }`} />
            </button>
          </div>
          {s.review_reminder && (
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-2">提醒时间</label>
              <input type="time" value={s.reminder_time}
                onChange={(e) => update('reminder_time', e.target.value)}
                className="w-full p-3 border border-gray-100 rounded-xl text-sm focus:outline-none focus:border-blue-200 focus:ring-2 focus:ring-blue-50 bg-gray-50/50 transition-all" />
            </div>
          )}
        </div>
      </Card>

      {/* 保存按钮 */}
      <div className="flex justify-end mb-8">
        <button onClick={handleSave} disabled={saving}
          className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-medium transition-all ${
            saved
              ? 'bg-emerald-500 text-white shadow-lg shadow-emerald-500/25'
              : 'bg-gradient-to-r from-blue-500 to-blue-600 text-white hover:shadow-lg hover:shadow-blue-500/25 disabled:opacity-50'
          }`}>
          {saved ? '✓ 已保存' : saving ? '保存中...' : '💾 保存设置'}
        </button>
      </div>

      {/* AI 模型配置（只读） */}
      <Card className="mb-5">
        <h2 className="text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-purple-50 flex items-center justify-center text-sm">🤖</span>
          AI 模型配置
        </h2>
        <p className="text-xs text-gray-400 mb-5">
          不同模块可使用不同 AI 模型。修改配置请编辑 <code className="bg-gray-100 px-1 rounded">.env</code> 文件并重启服务。
        </p>

        {aiConfig ? (
          <>
            {/* 全局默认 */}
            <div className="mb-4 p-3 bg-gray-50 rounded-lg">
              <div className="text-xs font-medium text-gray-500 mb-1">📌 全局默认（保底）</div>
              <div className="text-sm text-gray-700">
                <span className="font-mono">{aiConfig.default_model}</span>
                <span className="text-gray-400 ml-2">{aiConfig.default_base_url}</span>
              </div>
            </div>

            {/* 各模块配置 */}
            <div className="space-y-3">
              {aiConfig.modules.map((mod) => (
                <div key={mod.module} className="flex items-center justify-between p-3 border border-gray-100 rounded-lg">
                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-700">{mod.label}</div>
                    <div className="text-xs text-gray-400 mt-0.5">{mod.description}</div>
                  </div>
                  <div className="text-right ml-4">
                    <div className="text-xs font-mono text-gray-600">
                      {mod.model || '继承默认'}
                    </div>
                    <div className={`text-xs mt-0.5 ${
                      mod.strength_hint === '强' ? 'text-red-400' :
                      mod.strength_hint === '弱' ? 'text-green-400' :
                      'text-amber-400'
                    }`}>
                      💡 建议{mod.strength_hint}模型
                    </div>
                    {mod.has_custom_key && (
                      <div className="text-xs text-green-500 mt-0.5">✓ 独立 Key</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="text-sm text-gray-400 text-center py-4">加载中...</div>
        )}
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 检查 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -30
```
Expected: 无新增错误

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/pages/Settings.tsx
git commit -m "feat(settings): remove auto-save, add read-only AI config panel"
```

---

### Task 13: 全量测试验证

- [ ] **Step 1: 后端全量测试**

```bash
cd backend && python -m pytest app/ -v --tb=short 2>&1 | tail -40
```
Expected: 全部 PASS

- [ ] **Step 2: 前端编译检查**

```bash
cd frontend && npx tsc --noEmit 2>&1 | tail -20
```
Expected: 无错误

- [ ] **Step 3: 启动后端验证**

```bash
cd backend && python -m uvicorn app.main:app --reload --port 8000
```
Expected: 启动无报错，访问 `http://localhost:8000/api/settings/preferences` 和 `/api/settings/ai-config` 正常返回

- [ ] **Step 4: 最终 Commit**

```bash
git add -A
git commit -m "feat(settings): complete module-level LLM config refactor"
```

---

## 验收清单

- [ ] `config.py` 的 `get_llm_config("teaching")` 返回模块级配置，未配置时回退全局默认
- [ ] `deps.py` 的 `get_llm_client("teaching")` 和 `get_llm_client("parser")` 返回不同实例
- [ ] `settings_service.py` 封装了 .env 读写，有测试覆盖
- [ ] `GET /api/settings/preferences` 返回用户偏好
- [ ] `PUT /api/settings/preferences` 带校验，无效输入返回 422
- [ ] `GET /api/settings/ai-config` 返回只读 AI 配置，含模块强度提示
- [ ] 前端 Settings 页面：输入框不再自动保存，点保存按钮才提交
- [ ] 前端 Settings 页面：底部展示 AI 配置只读面板，含强度提示
- [ ] `.env` 有模块级配置结构，注释说明各模块用途
- [ ] 所有后端测试 PASS
- [ ] 前端 TypeScript 编译无错误
