# 用户模块优化设计

> 2026-05-27 | 方案 A：最小修补，不引入新依赖

## 1. 问题诊断

| # | 问题 | 严重度 | 根因 |
|---|------|--------|------|
| 1 | 无认证机制，`user_id` 前端随便传 | 🔴 高 | 无 auth 中间件，`DEFAULT_USER_ID = "anonymous"` |
| 2 | 文件删除和 DB 事务不一致 | 🟡 中 | `os.remove` 在 DB commit 之后，无法回滚 |
| 3 | `LearningRecordService` 反向依赖 `UserService` | 🟡 中 | `get_streak` 内部 import `UserService` |
| 4 | `_calculate_streak` 查 364 天数据 | 🟡 中 | 范围查代替提前终止 |
| 5 | `CacheEntryModel` 和业务表混在同一个 DB | 🟢 低 | 单文件 SQLite |
| 6 | `learning_style_json` 自由格式 Text，无结构 | 🟢 低 | 无 Pydantic 模型约束 |

## 2. 改动清单

### 2.1 认证机制（JWT）

**方案**：轻量 JWT，不引入 Redis/第三方。用户登录后拿 token，后续请求带 `Authorization: Bearer <token>`。

- 新增 `backend/app/modules/user_storage/auth.py`：JWT 签发/验证
- 新增 `backend/app/deps.py` 中的 `get_current_user` 依赖
- `router.py` 中所有需要 `user_id` 的端点改为从 token 取
- 前端 `client.ts` 加请求拦截器自动带 token
- 前端 `AppContext.tsx` 登录后存 token 到 localStorage

**保留匿名用户兼容**：未登录时仍可传 `user_id=anonymous`，但标记为 `is_anonymous`。

### 2.2 文件删除一致性

**两阶段删除**：
1. 先把 `book.file_path` 置为 `NULL`，commit 事务
2. 事务成功后再 `os.remove`
3. 文件删除失败只打 warning，不抛异常
4. 启动时后台任务清理 `file_path` 为 NULL 但物理文件还在的孤儿文件

### 2.3 解耦 streak 计算

- 抽 `StreakService`，独立在 `services/streak_service.py`
- `UserService._calculate_streak` 和 `LearningRecordService.get_streak` 都调 `StreakService`
- 去掉 `LearningRecordService` 中对 `UserService` 的 import

### 2.4 streak 算法优化

从最新日期往前扫，遇到 `total_minutes == 0` 立即停，不用查全年：
```sql
WHERE user_id = ? AND total_minutes > 0
ORDER BY date DESC
```
然后 Python 从最新往前数连续天数，遇到断档就 break。

### 2.5 learning_style 结构化

新增 Pydantic 模型：
```python
class LearningStyle(BaseModel):
    visual_score: float = 0.5    # 0-1 视觉偏好
    verbal_score: float = 0.5     # 0-1 文字偏好
    active_score: float = 0.5     # 0-1 主动练习偏好
    sequential_score: float = 0.5 # 0-1 顺序学习偏好
```
`learning_style_json` 存 JSON，写入时用 `LearningStyle` 校验。

### 2.6 缓存表分离（可选低优先级）

`CacheEntryModel` 单独存一个 SQLite 文件 `cache.db`，`CacheService` 连单独的引擎。
**本次暂缓**——单文件 SQLite 在中小规模下不是瓶颈。

## 3. 文件变更

| 操作 | 文件 |
|------|------|
| 新增 | `backend/app/modules/user_storage/auth.py` |
| 新增 | `backend/app/modules/user_storage/services/streak_service.py` |
| 修改 | `backend/app/modules/user_storage/services/user_service.py` |
| 修改 | `backend/app/modules/user_storage/services/learning_record_service.py` |
| 修改 | `backend/app/modules/user_storage/services/book_service.py` |
| 修改 | `backend/app/modules/user_storage/router.py` |
| 修改 | `backend/app/modules/user_storage/schemas.py` |
| 修改 | `backend/app/deps.py` |
| 修改 | `backend/app/config.py`（加 JWT 配置项） |
| 修改 | `backend/requirements.txt`（加 PyJWT） |
| 修改 | `frontend/src/api/client.ts`（加 token 拦截器） |
| 修改 | `frontend/src/contexts/AppContext.tsx`（加登录态） |
| 修改 | `frontend/src/types/index.ts`（加 User 类型） |

## 4. 不改动

- `CacheService` 实现（DB 缓存够用）
- 数据库表结构（不加表，只改 ORM 校验）
- 其他模块（document_parser、knowledge_splitter 等）
- 测试框架（pytest + 内存 SQLite）

## 5. 验证方式

1. 现有 11 个测试用例全部通过
2. 新增 auth 相关测试：token 签发/验证、过期、伪造
3. 新增 streak 优化测试：断档场景验证提前终止
4. 手动验：上传→删书→确认文件消失
