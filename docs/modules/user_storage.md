# user_storage 模块

## 概述

用户数据管理模块，包括书籍 CRUD、掌握度查询、每日统计和学习连续天数。

## 文件结构

| 文件 | 职责 |
|------|------|
| `router.py` | API 路由（书籍管理、掌握度、统计） |
| `schemas.py` | 请求/响应模型 |
| `service.py` | 用户服务（书籍操作、掌握度聚合） |
| `auth.py` | 认证（JWT，当前未启用） |
| `streak_service.py` | 学习连续天数计算 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/books` | 获取书籍列表 |
| GET | `/api/v1/books/{id}` | 获取书籍详情 |
| DELETE | `/api/v1/books/{id}` | 删除书籍 |
| GET | `/api/v1/books/{id}/chapters` | 获取章节树 |
| GET | `/api/v1/mastery/{book_id}` | 获取掌握度 |
| GET | `/api/v1/stats/daily` | 获取每日统计 |
| GET | `/api/v1/stats/streak` | 获取连续学习天数 |
| POST | `/api/v1/stats/complete` | 记录学习完成 |

## 已知问题

| 严重度 | 问题 | 位置 | 状态 |
|--------|------|------|------|
| 中等 | `file_size_bytes` 来自客户端而非实际文件大小，可被伪造 | `router.py` | **已修复** |
| 中等 | `get_book_chapters` 未检查书籍是否存在，直接查询章节 | `router.py` | **已修复** |
| 中等 | `json.loads` 无异常处理，畸形 JSON 导致 500 错误 | `router.py` | **已修复** |
| 低 | `complete_record` 不是幂等的，重复调用会重复计数 | `service.py` | 待修复 |
| 低 | 无数据库外键 `CASCADE` 删除，删书后留下孤立记录 | `models.py` | 待修复 |

## 优化建议

1. ~~文件大小从服务端文件系统获取（`len(content)`）~~ ✅ 已完成
2. ~~`get_book_chapters` 先查 BookModel，不存在返回 404~~ ✅ 已完成
3. ~~`json.loads` 包装 `_safe_json_list`，失败返回空列表~~ ✅ 已完成
4. `complete_record` 改为幂等（基于 session_id 去重）
5. 外键添加 `ondelete="CASCADE"` 或在删除时手动清理关联数据

## 测试覆盖

- `tests/test_user_service.py` — 存在
- `tests/test_streak_service.py` — 存在
- `tests/test_auth.py` — 存在
- **router.py 边界情况 — 测试不足**
