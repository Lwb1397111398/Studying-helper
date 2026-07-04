# teaching 模块

## 职责

管理交互式 AI 教学会话：开始会话、按阶段生成教学内容、回答用户问题、提交检查答案、继续阶段、跳转单元、生成测试和 Cornell 笔记。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `router.py` | `/api/v1/teaching` 路由 |
| `service.py` | 教学会话主服务，当前仍较大 |
| `schemas.py` | TeachingSession、TeachingMessage、TeachingStrategy、TestQuestion 等 |
| `strategies.py` | 教学策略选择，读取掌握度、难度、AID hint |
| `strategies_v2.py` | 新版策略扩展 |
| `teaching_plan.py` | 教学计划/覆盖相关扩展 |
| `prompts.py` | 教学、问答、测试、Cornell prompt |

## API 入口

前缀：`/api/v1/teaching`

常用端点：

- `POST /sessions/start`
- `GET /sessions/active`
- `GET /sessions/{session_id}/next-message`
- `POST /sessions/{session_id}/ask`
- `POST /sessions/{session_id}/answer`
- `POST /sessions/{session_id}/continue`
- `POST /sessions/{session_id}/jump-to-unit`
- `POST /sessions/{session_id}/clear`
- `GET /sessions/{session_id}/messages`
- `POST /sessions/{session_id}/test`
- `POST /tests/{test_id}/submit`
- `POST /sessions/{session_id}/complete`
- `POST /sessions/{session_id}/adapt-strategy`
- `POST /annotations`
- `POST /annotations/cornell/cues`
- `POST /annotations/cornell/summary`
- `GET /annotations/cornell/{unit_id}`
- `GET /stats`
- `GET /sessions/{session_id}/units/{unit_id}/coverage`

## 教学阶段

当前阶段体系包含：

```text
activate -> intro -> core -> retrieval/check -> reflect/connect
```

具体推进逻辑以 `TeachingService._advance_phase` 和 strategy 选择为准。

## AID 接入点

- `router.py` 开始教学时会尝试读取 AID 当前 active module 的有序 unit ids。
- `strategies.py` 会读取 `KnowledgeUnit.ai_cognitive_hint` 调整 pace/策略。
- 若没有 confirmed design 或 active module，教学仍应能回退到普通知识单元顺序。

## Android 差异

Android 有端侧 `TeachingRepository.kt`，可直接调用本地配置的 OpenAI 兼容接口生成教学内容。不要假设 Android 教学完全复用后端 `/api/v1/teaching`。

## 验证入口

```bash
cd backend && python -m pytest app/modules/teaching/tests/ -q
```

## 已知风险

- `service.py` 很大，修改时先定位具体方法，不要顺手重构整类。
- 阶段推进、掌握度更新、测试生成耦合较强。
- 改 teaching schema 时要检查 Web、Android sync 和历史数据兼容。
