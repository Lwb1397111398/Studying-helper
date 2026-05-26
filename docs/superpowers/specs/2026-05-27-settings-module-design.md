# 设置模块优化设计

> 日期：2026-05-27
> 状态：待评审

---

## 一、背景与问题

### 当前架构

```
前端 Settings.tsx → localStorage (用户偏好)
                   ↕ AppContext
前端 settings.ts → GET/PUT /api/settings → router.py → 读写 .env 文件
                                         ↕
后端 config.py → pydantic BaseSettings → 启动时读 .env → 全局单例 settings
                                         ↕
后端 deps.py → get_llm_client() → 用 settings.LLM_API_KEY 创建全局 OpenAIClient
```

### 已识别问题

| # | 问题 | 严重程度 |
|---|------|---------|
| 1 | 保存行为混乱：每个输入框改完自动调 saveSettings()，底部又有"保存设置"按钮，做一次操作触发多次请求 | 中 |
| 2 | 无输入校验：API Key 格式、时间格式、数值范围都没校验 | 中 |
| 3 | 无 service 层：router 直接操作文件系统，和其他模块 router→service→model 模式不一致 | 中 |
| 4 | LLM 配置暴露在前端：用户能看到/改 API Key，且改一个影响所有人（单用户场景虽影响不大，但架构不清晰） | 低 |
| 5 | .env 并发写不安全：_write_env() 直接拼接字符串写文件 | 低 |

### 新需求

**不同模块用不同 AI 模型**：知识图谱/教学策略用强模型（gpt-4），知识切块/复习出题用弱模型（gpt-4o-mini），节约成本。

- 全局默认模型 + API Key 保底
- 每个模块可单独覆盖模型和 Key
- 用户自己在前端配置

---

## 二、配置分类

优化后，所有配置拆成两类：

| 类型 | 存哪里 | 谁管 | 内容 |
|------|--------|------|------|
| **系统配置** | `.env` 文件（后端） | 管理员/部署时 | LLM 全局默认模型 + Key、DB_URL、文件路径等 |
| **用户偏好** | localStorage（前端） | 用户自己 | 每日学习目标、复习提醒等 |

**AI 模型配置**属于系统配置，存 `.env`，前端只读不写。

---

## 三、AI 模型配置设计

### 3.1 .env 格式

```env
# ── 全局默认（保底）──
LLM_DEFAULT_API_KEY="sk-..."
LLM_DEFAULT_MODEL="gpt-4o-mini"
LLM_DEFAULT_BASE_URL="https://api.openai.com/v1"

# ── 各模块覆盖（不填则用全局默认）──
# 知识图谱：概念提取、关系识别 → 强模型
LLM_KG_API_KEY="sk-..."
LLM_KG_MODEL="gpt-4"
LLM_KG_BASE_URL="https://api.openai.com/v1"

# 教学策略：类比/举例/对比生成 → 强模型
LLM_TEACHING_API_KEY="sk-..."
LLM_TEACHING_MODEL="gpt-4"
LLM_TEACHING_BASE_URL="https://api.openai.com/v1"

# AI 分析：内容分析、出题、评估 → 强模型
LLM_AI_ANALYSIS_API_KEY="sk-..."
LLM_AI_ANALYSIS_MODEL="gpt-4"
LLM_AI_ANALYSIS_BASE_URL="https://api.openai.com/v1"

# 知识切块：切块边界判断、摘要生成 → 弱模型
LLM_SPLIT_API_KEY="sk-..."
LLM_SPLIT_MODEL="gpt-4o-mini"
LLM_SPLIT_BASE_URL="https://api.openai.com/v1"

# 复习：出题 → 弱模型
LLM_REVIEW_API_KEY="sk-..."
LLM_REVIEW_MODEL="gpt-4o-mini"
LLM_REVIEW_BASE_URL="https://api.openai.com/v1"

# 文档解析：目录识别 → 弱模型
LLM_PARSER_API_KEY="sk-..."
LLM_PARSER_MODEL="gpt-4o-mini"
LLM_PARSER_BASE_URL="https://api.openai.com/v1"

# 学习计划：顺序编排、节奏规划 → 弱~中模型
LLM_PLAN_API_KEY="sk-..."
LLM_PLAN_MODEL="gpt-4o"
LLM_PLAN_BASE_URL="https://api.openai.com/v1"
```

### 3.2 前端展示

AI 配置面板只读展示当前生效的配置，标注每个模块的功能和建议强度：

```
┌─────────────────────────────────────────────────────────────┐
│ 🤖 AI 模型配置                          [ℹ️ 只读，改 .env 生效] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 📌 全局默认（保底）                                         │
│ ┌─────────────┬──────────┬────────────────────┐             │
│ │ Model        │ gpt-4o-  │ Key: sk-***xxx     │             │
│ │              │ mini     │ Base: openai.com   │             │
│ └─────────────┴──────────┴────────────────────┘             │
│                                                             │
│ 📚 书本导入                    💡 弱模型即可                  │
│ ┌─────────────┬──────────┬────────────────────┐             │
│ │ Model        │ 继承默认 │ Key: 继承默认       │             │
│ └─────────────┴──────────┴────────────────────┘             │
│                                                             │
│ ✂️ 知识切块                    💡 弱~中模型                   │
│ ┌─────────────┬──────────┬────────────────────┐             │
│ │ Model        │ 继承默认 │ Key: 继承默认       │             │
│ └─────────────┴──────────┴────────────────────┘             │
│                                                             │
│ 🕸️ 知识图谱                    💡 建议强模型                  │
│ ┌─────────────┬──────────┬────────────────────┐             │
│ │ Model        │ 继承默认 │ Key: 继承默认       │             │
│ └─────────────┴──────────┴────────────────────┘             │
│                                                             │
│ 🧠 AI 分析                     💡 建议强模型                  │
│ ┌─────────────┬──────────┬────────────────────┐             │
│ │ Model        │ 继承默认 │ Key: 继承默认       │             │
│ └─────────────┴──────────┴────────────────────┘             │
│                                                             │
│ 📅 学习计划                    💡 中模型即可                  │
│ ┌─────────────┬──────────┬────────────────────┐             │
│ │ Model        │ 继承默认 │ Key: 继承默认       │             │
│ └─────────────┴──────────┴────────────────────┘             │
│                                                             │
│ 🎯 教学策略                    💡 建议强模型                  │
│ ┌─────────────┬──────────┬────────────────────┐             │
│ │ Model        │ 继承默认 │ Key: 继承默认       │             │
│ └─────────────┴──────────┴────────────────────┘             │
│                                                             │
│ 🔁 复习                        💡 弱~中模型                   │
│ ┌─────────────┬──────────┬────────────────────┐             │
│ │ Model        │ 继承默认 │ Key: 继承默认       │             │
│ └─────────────┴──────────┴────────────────────┘             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 四、后端改造

### 4.1 config.py — 支持模块级覆盖

```python
class Settings(BaseSettings):
    # 全局默认
    LLM_DEFAULT_API_KEY: str = ""
    LLM_DEFAULT_MODEL: str = "gpt-4o-mini"
    LLM_DEFAULT_BASE_URL: str = "https://api.openai.com/v1"

    # 知识图谱 (kg)
    LLM_KG_API_KEY: str = ""
    LLM_KG_MODEL: str = ""
    LLM_KG_BASE_URL: str = ""

    # 教学 (teaching)
    LLM_TEACHING_API_KEY: str = ""
    LLM_TEACHING_MODEL: str = ""
    LLM_TEACHING_BASE_URL: str = ""

    # AI 分析 (ai_analysis)
    LLM_AI_ANALYSIS_API_KEY: str = ""
    LLM_AI_ANALYSIS_MODEL: str = ""
    LLM_AI_ANALYSIS_BASE_URL: str = ""

    # 知识切块 (split)
    LLM_SPLIT_API_KEY: str = ""
    LLM_SPLIT_MODEL: str = ""
    LLM_SPLIT_BASE_URL: str = ""

    # 复习 (review)
    LLM_REVIEW_API_KEY: str = ""
    LLM_REVIEW_MODEL: str = ""
    LLM_REVIEW_BASE_URL: str = ""

    # 文档解析 (parser)
    LLM_PARSER_API_KEY: str = ""
    LLM_PARSER_MODEL: str = ""
    LLM_PARSER_BASE_URL: str = ""

    # 学习计划 (plan)
    LLM_PLAN_API_KEY: str = ""
    LLM_PLAN_MODEL: str = ""
    LLM_PLAN_BASE_URL: str = ""

    # 原有配置
    DB_URL: str = "sqlite+aiosqlite:///./data/learning.db"
    FILE_STORAGE_DIR: str = "./data/files"
    BACKUP_DIR: str = "./data/backups"

    def get_llm_config(self, module: str) -> dict:
        """获取指定模块的 LLM 配置，未配置则回退到全局默认"""
        prefix = f"LLM_{module.upper()}"
        api_key = getattr(self, f"{prefix}_API_KEY", "") or self.LLM_DEFAULT_API_KEY
        model = getattr(self, f"{prefix}_MODEL", "") or self.LLM_DEFAULT_MODEL
        base_url = getattr(self, f"{prefix}_BASE_URL", "") or self.LLM_DEFAULT_BASE_URL
        return {"api_key": api_key, "model": model, "base_url": base_url}

    class Config:
        env_file = ".env"
```

### 4.2 deps.py — 模块级 LLM 客户端工厂

```python
# 模块名 → 客户端实例 缓存
_module_clients: dict[str, OpenAIClient] = {}

async def get_llm_client(module: str = "default") -> OpenAIClient:
    """获取指定模块的 LLM 客户端，相同模块复用同一实例"""
    if module not in _module_clients:
        cfg = settings.get_llm_config(module)
        _module_clients[module] = OpenAIClient(
            api_key=cfg["api_key"],
            model=cfg["model"],
            base_url=cfg["base_url"],
        )
    return _module_clients[module]
```

### 4.3 router.py — 抽 service 层 + 只读 AI 配置

**settings_service.py**（新增）：

```python
"""设置服务层 — 封装 .env 读写逻辑"""
from pathlib import Path

ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"

def read_env() -> dict[str, str]:
    result = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip().strip('"').strip("'")
    return result

def write_env(updates: dict[str, str | None]):
    existing = read_env()
    existing.update({k: v for k, v in updates.items() if v is not None})
    # 按 key 分组排序，确保写入稳定
    lines = [f'{k}="{v}"' for k, v in sorted(existing.items())]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 同步更新 os.environ
    import os
    os.environ.update({k: v for k, v in updates.items() if v})
```

**router.py**（改造后）：

```python
"""设置模块 REST 端点"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.modules.settings.settings_service import read_env, write_env

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

# 存储键映射
PREF_KEYS = {
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
    updates = {PREF_KEYS[k]: str(v) for k, v in body.model_dump(exclude_none=True).items()}
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
    strength_hint: str  # "弱" | "弱~中" | "中" | "强"
    model: str
    has_custom_key: bool
    base_url: str

class AIConfigResponse(BaseModel):
    default_model: str
    default_base_url: str
    modules: list[LLMModuleConfig]

_MODULE_META = [
    {"key": "parser",    "label": "📚 书本导入", "desc": "目录识别、章节标题优化",       "hint": "弱"},
    {"key": "split",     "label": "✂️ 知识切块",  "desc": "切块边界判断、摘要生成",       "hint": "弱~中"},
    {"key": "kg",        "label": "🕸️ 知识图谱",  "desc": "概念提取、关系识别",           "hint": "强"},
    {"key": "ai_analysis","label": "🧠 AI 分析",  "desc": "内容分析、出题、评估",         "hint": "强"},
    {"key": "plan",      "label": "📅 学习计划",  "desc": "顺序编排、节奏规划",           "hint": "弱~中"},
    {"key": "teaching",  "label": "🎯 教学策略",  "desc": "类比/举例/对比生成",          "hint": "强"},
    {"key": "review",    "label": "🔁 复习",      "desc": "出题、掌握度评估",             "hint": "弱~中"},
]

@router.get("/ai-config", response_model=AIConfigResponse)
async def get_ai_config():
    """获取 AI 模型配置（只读，需改 .env 重启生效）"""
    from app.config import settings
    modules = []
    for m in _MODULE_META:
        cfg = settings.get_llm_config(m["key"])
        modules.append(LLMModuleConfig(
            module=m["key"],
            label=m["label"],
            description=m["desc"],
            strength_hint=m["hint"],
            model=cfg["model"],
            has_custom_key=bool(getattr(settings, f"LLM_{m['key'].upper()}_API_KEY", "")),
            base_url=cfg["base_url"],
        ))
    return AIConfigResponse(
        default_model=settings.LLM_DEFAULT_MODEL,
        default_base_url=settings.LLM_DEFAULT_BASE_URL,
        modules=modules,
    )
```

### 4.4 各模块 service 层改造

每个需要 LLM 的模块，从 `get_llm_client(module_name)` 获取专用客户端：

| 模块 | 传入的 module 名 | 改动点 |
|------|-----------------|--------|
| `teaching` | `"teaching"` | router 的 `_get_service()` 传参 |
| `ai_learning` | `"ai_analysis"` | 同上 |
| `knowledge_graph` → `graph_builder` | `"kg"` | graph_builder 创建节点时调用 LLM |
| `knowledge_splitter` | `"split"` | 切块时调用 LLM |
| `review` | `"review"` | 出题时调用 LLM |
| `document_parser` → `toc_detector` | `"parser"` | 目录识别 fallback 调用 LLM |
| `learning_plan` | `"plan"` | 方案生成调用 LLM |

示例（teaching router 改造）：

```python
# 改造前
async def _get_service(db=Depends(get_db), llm_client=Depends(get_llm_client)):
    return TeachingService(llm_client=llm_client, db=db)

# 改造后
async def _get_service(db=Depends(get_db), llm_client=Depends(lambda: get_llm_client("teaching"))):
    return TeachingService(llm_client=llm_client, db=db)
```

---

## 五、前端改造

### 5.1 保存行为统一

去掉输入框的自动保存，只保留底部保存按钮。改一次 → 点保存 → 一次请求。

### 5.2 Settings 页面分两块

```
┌──────────────────────────────────────┐
│ ⚙️ 设置                              │
├──────────────────────────────────────┤
│                                      │
│ 🎯 学习目标                           │
│   每日学习时长 [30] 分钟              │
│   每日完成单元 [5] 个                 │
│                                      │
│ 🔔 复习提醒                           │
│   开启复习提醒 [开关]                 │
│   提醒时间 [20:00]                    │
│                                      │
│ 💾 保存设置                           │
│                                      │
├──────────────────────────────────────┤
│ 🤖 AI 模型配置              [只读]    │
│                                      │
│ 全局默认: gpt-4o-mini                 │
│                                      │
│ 📚 书本导入    💡弱    继承默认       │
│ ✂️ 知识切块    💡弱~中  继承默认       │
│ 🕸️ 知识图谱    💡强    继承默认       │
│ 🧠 AI 分析     💡强    继承默认       │
│ 📅 学习计划    💡弱~中  继承默认       │
│ 🎯 教学策略    💡强    继承默认       │
│ 🔁 复习        💡弱~中  继承默认       │
│                                      │
│ ℹ️ 修改 AI 配置请编辑 .env 重启服务    │
└──────────────────────────────────────┘
```

### 5.3 前端 API 层

```typescript
// settings.ts（改造后）
import client from './client';
import type { UserSettings } from '../types';

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

### 5.4 AppContext 调整

```typescript
// AppContext.tsx 改造
// settings 只含用户偏好，不再混 AI 配置
const [settings, setSettings] = useState<UserSettings | null>(null);

// AI 配置单独状态
const [aiConfig, setAiConfig] = useState<AIConfigResponse | null>(null);
```

---

## 六、文件改动清单

| 文件 | 改动 | 类型 |
|------|------|------|
| `backend/app/config.py` | 加模块级 LLM 配置字段 + `get_llm_config()` | 修改 |
| `backend/app/deps.py` | `get_llm_client()` 支持 module 参数 | 修改 |
| `backend/app/modules/settings/settings_service.py` | 抽离 .env 读写逻辑 | **新增** |
| `backend/app/modules/settings/router.py` | 拆分端点 + 校验 + 只读 AI 配置 | 修改 |
| `backend/app/modules/teaching/router.py` | 传 `"teaching"` 模块名 | 修改 |
| `backend/app/modules/ai_learning/router.py` | 传 `"ai_analysis"` 模块名 | 修改 |
| `backend/app/modules/knowledge_graph/service.py` | graph_builder 传 `"kg"` 模块名 | 修改 |
| `backend/app/modules/knowledge_splitter/service.py` | 传 `"split"` 模块名 | 修改 |
| `backend/app/modules/review/service.py` | 传 `"review"` 模块名 | 修改 |
| `backend/app/modules/document_parser/toc_detector.py` | 传 `"parser"` 模块名 | 修改 |
| `backend/app/modules/learning_plan/service.py` | 传 `"plan"` 模块名 | 修改 |
| `frontend/src/api/settings.ts` | 拆分 API 函数 | 修改 |
| `frontend/src/contexts/AppContext.tsx` | AI 配置独立状态 | 修改 |
| `frontend/src/pages/Settings.tsx` | 去掉自动保存 + 加 AI 配置展示区 | 修改 |
| `.env` | 加模块级配置项 | 修改 |

---

## 七、兼容性

- 不填模块级配置 → 自动回退全局默认，**零配置即可运行**
- 原有 `.env` 中的 `LLM_API_KEY` / `LLM_MODEL` / `LLM_BASE_URL` 映射为 `LLM_DEFAULT_*`
- 前端用户偏好 API 路径变更：`/settings` → `/settings/preferences`，需同步更新前端

---

## 八、后续可选优化

1. **前端编辑 AI 配置**：加写端点，让普通用户也能改（需要鉴权）
2. **配置热重载**：不用重启服务，通过信号或端点触发重读 `.env`
3. **配置导出/导入**：方便迁移和备份
