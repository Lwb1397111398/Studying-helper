# common 模块

## 概述

共享基础组件，包括 LLM 客户端、错误处理、Pydantic 模型和时间工具。

## 文件结构

| 文件 | 职责 |
|------|------|
| `llm_client.py` | LLM 客户端抽象（OpenAI 兼容协议）、并发信号量、重试逻辑 |
| `errors.py` | ErrorCode 枚举、ServiceError 异常、HTTP 状态码映射 |
| `schemas.py` | 共享 Pydantic 模型（TimestampMixin、PaginationParams 等） |
| `time_utils.py` | 时间工具函数 |

## LLM 客户端 (`llm_client.py`)

### 核心类型

```python
class LLMClient(Protocol):
    async def chat(self, messages, temperature, max_tokens) -> str: ...
    async def close(self) -> None: ...  # BUG: 未在 Protocol 中声明
```

### 关键机制

- **信号量并发控制**: `init_semaphore(n)` → `_sema.acquire()` / `_sema.release()`
- **优雅关闭**: `request_shutdown()` 拒绝新请求，`wait_inflight()` 等待在途请求
- **模块级客户端**: 每个模块可独立配置 LLM，通过 `get_module_llm_client()` 获取

### 已知问题

| 严重度 | 问题 | 位置 | 状态 |
|--------|------|------|------|
| **严重** | HTTP 429/5xx 和 TimeoutException 未重试 | ~L111-120 | **已修复** |
| **严重** | `_inflight_count` 与信号量存在竞态条件 | ~L100-101 | **已修复** |
| 中等 | LLMClient Protocol 缺少 `close()` 方法声明 | ~L60-62 | **已修复** |
| 低 | 300s 统一超时过长，应区分首 token 和生成超时 | ~L72 | 待优化 |

### 优化建议

1. ~~添加指数退避重试（429/5xx/Timeout），最多 3 次~~ ✅ 已完成
2. ~~`wait_inflight` 读取 `_inflight_count` 时加锁保护~~ ✅ 已完成
3. ~~在 Protocol 中补充 `close()` 声明~~ ✅ 已完成
4. 拆分 `timeout` 为 `connect_timeout` + `read_timeout`，生成场景用更长的 read_timeout

## 错误处理 (`errors.py`)

### 结构

```python
class ErrorCode(str, Enum):
    NOT_FOUND = "NOT_FOUND"              # → 404
    VALIDATION_ERROR = "VALIDATION_ERROR" # → 400
    PROCESSING_ERROR = "PROCESSING_ERROR" # → 500
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"  # → 502
    RATE_LIMITED = "RATE_LIMITED"        # → 429
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA" # → 422
    DATABASE_ERROR = "DATABASE_ERROR"    # → 500

class ServiceError(Exception):
    code: ErrorCode
    message: str
    details: dict
```

### 已知问题

| 严重度 | 问题 |
|--------|------|
| 低 | ErrorCode 枚举与 ERROR_STATUS_MAP 无同步校验，新增枚举可能忘记加映射 |
| 低 | 未使用的 HTTPException 导入 |

## 共享模型 (`schemas.py`)

### 已知问题

| 严重度 | 问题 |
|--------|------|
| 中等 | **死代码**: TimestampMixin、PaginationParams、PaginatedResponse 均未被任何模块导入使用 |

### 优化建议

确认无使用后删除 `schemas.py`，或将其内容迁移到实际使用的模块中。

## 测试覆盖

- `tests/test_llm_client.py` — 存在但覆盖不足
- `schemas.py` — 无测试（且为死代码）
- `errors.py` — 无独立测试
