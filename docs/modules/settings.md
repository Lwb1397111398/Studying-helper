# settings 模块

## 职责

管理用户偏好和 AI 配置。配置写入 `.env` 后需要同步内存中的 settings，并清理 LLM client 缓存，让新配置即时生效。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `router.py` | `/api/v1/settings` 路由 |
| `settings_service.py` | `.env` 读写、偏好和 AI 配置持久化 |
| `tests/test_settings_service.py` | 设置服务测试 |
| `backend/app/config.py` | Settings 类和 LLM 配置优先级 |
| `backend/app/deps.py` | 模块级 LLM client 缓存 |

## API 入口

前缀：`/api/v1/settings`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/preferences` | 获取用户偏好 |
| PUT | `/preferences` | 更新用户偏好 |
| GET | `/ai-config` | 获取 AI 配置 |
| PUT | `/ai-config` | 更新 AI 配置 |

## 配置层级

```text
模块级 LLM_TEACHING_* / LLM_AI_ANALYSIS_* / LLM_PARSER_* / LLM_AID_*
  -> 全局默认 LLM_DEFAULT_*
  -> 旧字段 LLM_API_KEY / LLM_MODEL / LLM_BASE_URL
```

## 当前模块级配置

- `teaching`
- `ai_analysis`
- `parser`
- `aid`

## 验证入口

```bash
cd backend && python -m pytest app/modules/settings/tests/test_settings_service.py -q
```

## 已知风险

- `.env` 写入要避免覆盖用户已有注释和未知配置。
- 改 AI 配置后要清理 `deps.py` 中缓存的 LLM client。
- 不要把密钥写进文档、测试或日志。
