# user_storage 模块

## 职责

管理用户、书籍、章节、学习记录、每日统计和本地文件存储。它是后端多数业务模块的数据入口。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `router.py` | `/api/v1` 下的用户、书籍、章节、统计路由 |
| `service.py` | 聚合服务入口 |
| `schemas.py` | User、Book、Chapter、LearningRecord、DailyStats 等模型 |
| `auth.py` | JWT/认证辅助；当前主路径仍是单用户 |
| `services/book_service.py` | 书籍 CRUD 和状态 |
| `services/file_storage.py` | 文件保存、备份目录 |
| `services/learning_record_service.py` | 学习记录 |
| `services/streak_service.py` | 连续学习天数 |
| `services/user_service.py` | 用户偏好 |
| `services/cache_service.py` | 缓存服务 |

## API 入口

前缀：`/api/v1`

常用端点：

- `GET /users/{user_id}`
- `PUT /users/preferences`
- `GET /users/profile`
- `POST /books`
- `GET /books`
- `GET /books/{book_id}`
- `DELETE /books/{book_id}`
- `GET /books/{book_id}/chapters`
- `PUT /books/{book_id}/status`
- `PUT /books/{book_id}/motivation`
- `POST /records`
- `PUT /records/{record_id}/complete`
- `GET /stats/daily/{date}`
- `GET /stats/streak`
- `GET /books/{book_id}/mastery`

## 数据流

```text
上传/新建书籍
  -> BookModel
  -> ChapterModel
  -> KnowledgeUnitModel
  -> 学习/教学/复习/同步模块继续处理
```

## 与 Android 的关系

Android 也能本地新建书籍、章节、知识单元。跨端数据最终通过 `sync` 覆盖式导入导出合流。

## 验证入口

```bash
cd backend && python -m pytest app/modules/user_storage/tests/ -q
```

## 已知风险

- 删除书籍会牵涉章节、知识单元、图谱、教学、复习、AID 和同步数据。
- 文件路径和数据库记录必须保持一致。
- 单用户假设深入代码，改多用户需要系统性处理。
