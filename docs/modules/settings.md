# settings 模块

## 概述

用户偏好和 AI 配置管理模块，支持 `.env` 文件持久化和热更新。

## 文件结构

| 文件 | 职责 |
|------|------|
| `router.py` | API 路由（偏好读写、AI 配置读写） |
| `schemas.py` | 请求/响应模型 |
| `settings_service.py` | 设置服务（.env 文件读写、配置同步） |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/settings/preferences` | 获取用户偏好 |
| PUT | `/api/v1/settings/preferences` | 更新用户偏好 |
| GET | `/api/v1/settings/ai-config` | 获取 AI 配置（只读展示） |
| PUT | `/api/v1/settings/ai-config` | 更新 AI 配置 |

## 配置层级

```
模块级 (LLM_TEACHING_*)  ←  最高优先级
  ↓
全局默认 (LLM_DEFAULT_*)
  ↓
旧字段兼容 (LLM_*)  ←  最低优先级
```

## 用户偏好项

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| daily_goal_minutes | int | 30 | 每日学习目标（分钟） |
| daily_goal_units | int | 5 | 每日学习单元目标 |
| review_reminder | bool | true | 复习提醒 |
| reminder_time | str | "20:00" | 提醒时间 |
| preferred_language | str | "zh" | 偏好语言 |

## 已知问题

| 严重度 | 问题 | 位置 |
|--------|------|------|
| 中等 | `write_env` 无文件锁，并发写入可能导致数据丢失 | `settings_service.py` | **已修复** |
| 中等 | 写入 `.env` 后 Settings 单例未同步，需重启才生效 | `settings_service.py` | **已修复** |
| 中等 | `.env` 解析不支持行内注释（`KEY=VALUE # comment` 会把注释也读进去） | `settings_service.py` | **已修复** |
| 低 | AI 配置写入后需手动清除 LLM 客户端缓存 | `settings_service.py` | 待优化 |

## 优化建议

1. ~~添加写锁 + 原子写入（threading.Lock + tempfile + os.replace）~~ ✅ 已完成
2. ~~写入后自动同步 Settings 单例（setattr）~~ ✅ 已完成
3. ~~`.env` 解析添加行内注释支持（`#` 前有空格时忽略后面内容）~~ ✅ 已完成
4. AI 配置变更后自动触发 LLM 客户端缓存清除（已由 router 层处理）

## 测试覆盖

- `tests/test_settings_service.py` — 存在
- **.env 解析边界情况 — 测试不足**
- **并发写入 — 无测试**
