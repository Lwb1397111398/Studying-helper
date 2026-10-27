# 通宵收敛计划案·第 2 轮（2026-10-28 夜）· v2 修订版

> 上游：第 1 轮通宵收敛已完成 P1~P6 并推送（见 `2026-10-28-overnight-convergence.md` 与 `docs/当前进度.md`）。本轮在其登记的遗留项上继续。
> 流程约束（老板指定）：每个计划案 AI 评分（五维卡各 0-20，任一维 <12 单项失败，总分 <90 按建议修订重评，≥90 执行）；执行中代码质量同法复评；每个小计划完成后验证本功能 + 回归已有功能；大功能组合完成后整体回归；全部完成后终检 + 推送 GitHub。
> 修订记录：第 1 轮自评 总计划 81 / R1a 85 / R1b 77 / R4 84 / W 84 / C1 80 / D1 86 / P6' 80 → 本版按全部建议修订（R1b migration 护航方案实地核实后写死、R4 纳入 elapsed_days 真实化、R1a 构造方式写死等）。

## 〇、执行纪律（沿用第 1 轮计划案的纪律条目：回滚点/真实数据保护/门禁分工/止损/回归/日志留档/执行期复评，不重复抄录）

- 开工前 `git tag pre-round2-2026-10-28`；继续在 `codex/stability-convergence` 分支；每计划独立 commit（前缀 `R1a:`/`R1b:`/`R4:`/`W:`/`C1:`/`D1:`/`P6':`）。
- 真实库 `backend/data/learning.db` 不触碰；终检重算 SHA256 与 `988e50cc…3f7473` 三方比对。
- P6' 沿用第 1 轮计划的：豁免四分类口径、final_gate.py 门禁脚本（`--base origin/master`）、隐私扫描三范围（diff 区间+cached+untracked）、`当前进度.md` 数字回写机制、post-push note 规则。

## 一、体检结论（本轮基线，2026-10-28 夜实测）

| # | 环节 | 结果 | 证据 |
| --- | --- | --- | --- |
| 1 | 后端全量 pytest | ✅ 522 passed / 1 warning（49s） | 本轮实跑 |
| 2 | 后端真实启动冒烟 | ✅ SMOKE_PASS 20 项全过 | smoke_backend.py |
| 3 | 前端 tsc + vite build | ✅ built in 4.29s | 本轮实跑 |
| 4 | Android testDebugUnitTest --rerun-tasks | ✅ BUILD SUCCESSFUL（1 个 Kotlin warning） | 本轮实跑 |
| 5 | pyflakes | ⚠️ 150 条（140 未用导入 + 10 其他） | 本轮实跑 |
| 6 | v2 教学会话同步 | 🐛 契约缺 state_v2/asset_id/completion_status（上轮风险 1） | schemas.py:190 / SyncDtos.kt:191 / Entities.kt:165 |
| 7 | FSRS 存量状态 | 🐛 后端每轮从 ef/iv 重估 stability/difficulty 且 elapsed_days 硬编码 0；Android 直通存量值+真实 elapsed——两端不一致（上轮风险 4 扩展） | spaced_repetition_v2.py:129-149 |
| 8 | 测试警告 | ⚠️ pytest coroutine never awaited（test_feynman_phase.py）；Kotlin nullable（UpdateDownloaderTest.kt:61） | 本轮实跑 |
| 9 | 端侧总览 | ⚠️ Android data 四子域无总览（上轮列为后续任务） | 模块总览 README |

## 二、总计划

```
R1a 后端 sync 契约补 v2 三字段 + 测试                    [必须] ≤45min
R1b Android DTO/Entity/Migration/SyncRepository 对齐+测试 [必须] ≤75min（kapt 慢）
R4  后端 FSRS 存量状态直通（stability/difficulty/elapsed_days）+ 数值测试 [必须] ≤60min
W   W1 pytest 警告 + W2 Kotlin 警告                      [必须] ≤15min
C1  未用导入分批清理（63 条，非测试非白名单）             [可选→本轮纳入] ≤45min
D1  Android 端侧数据模块总览（data 四子域一篇）+README    [必须] ≤40min
P6' 终检 + 整合验证 + 推送                               [必须] ≤150min
```

执行顺序：R1a → R1b →（整合验证①同步闭环）→ R4 →（整合验证②复习链路）→ W → C1 → D1 → P6'。
**整合验证①**：R1a+R1b 后，升级 smoke 断言（`smoke_backend.py` 的"回灌后 session 保值"断言从 v1 字段扩展为 v1+state_v2/asset_id/completion_status 五字段）并连跑 2 次全过。
**整合验证②**：R4 后，review+sync+teaching 全模块测试 + P1 专项（TestFSRSLapsesFix/TestFSRSLapsesPersistence/同步保值闭环）重跑，确认 lapses 链路未被破坏。

## 三、小计划案

### R1a：后端 sync 契约补 v2 三字段

**问题**：`sync/schemas.py:190 SyncTeachingSession` 只有 v1 字段；v2 会话三字段（`db/models.py:263-266`：asset_id/state_v2/completion_status）导出即丢、回灌退化为 None。

**改点（写死）**：
1. `SyncTeachingSession` 末尾追加：`state_v2: str | None = None`、`asset_id: str | None = None`、`completion_status: str | None = None`（默认 None → 旧包导入零破坏）。
2. 业务代码零改动：导出 `_to_schema` 按 `model_fields` 取值（service.py:454-456）、导入 `_add_models` 用 `model_dump` 构造（:447-452），schema 加字段自动两端生效（已实地核实）。

**测试矩阵**（`app/modules/sync/tests/test_sync_service.py`）：
1. v2 会话导出保值：构造 `TeachingSessionModel(state_v2="diagnose", asset_id="asset-x", completion_status="in_progress", ...)` → export → 断言包内该会话三字段值正确；
2. 回灌保值：该包 import → 查 DB 断言三列保值；
3. 旧包兼容：**构造方式写死**——手写 dict 只含 v1 字段 → `SyncTeachingSession.model_validate(dict)` 构造（模拟旧版序列化产物）→ import 不报错，DB 三列为 None；
4. 导出幂等：同一数据连续两次 export，teaching_sessions 的规范化 dump 完全一致（防导出有隐藏随机性）；
5. v1 会话回归：既有测试全绿即锁行为。
6. **语义论证（独立复核建议 1 的核实结论）**：sync 导入是 delete+add 全量重放（先删该 book 全部会话再从包重建，`_add_models` 为 `db.add(model_class(**model_dump()))`），不存在"旧包导入覆盖更新已有 v2 记录"的场景——旧包数据源里本就无三字段，无可保值之物；exclude_unset/排除 None 方案**不采纳**（会破坏 `_to_schema` 全字段导出与 `_add_models` 全字段构造的对称性）。本条写入证据链即可，不产生代码改动。

**验证**：新测试过；`pytest app/modules/sync app/modules/teaching -q` 全绿；全量 pytest 全绿。
**风险**：低——纯可选字段追加。

### R1b：Android 端对齐（DTO/Entity/Migration/SyncRepository）

**问题**：Android `SyncDtos.kt:191` 无三字段、`Entities.kt:165` 无三列、`SyncRepository.kt:231-232` 位置参数映射。不对齐则：新包导入字段被忽略、Android 导出回 Web 时 v2 状态丢（中转保值断裂）。

**改点（写死）**：
1. `SyncDtos.kt` SyncTeachingSession **参数列表末尾**追加三可空字段（`@SerialName("state_v2") val stateV2: String? = null` 等）；
2. `Entities.kt` TeachingSessionEntity **参数列表末尾**追加三列（`@ColumnInfo(name = "state_v2") val stateV2: String? = null` 等，默认 null 不破坏既有构造点）；
3. `StudyDatabase.kt` version 3→4；`Migrations.kt` 新增 `MIGRATION_3_4_STATEMENTS`（三条：`ALTER TABLE teaching_sessions ADD COLUMN state_v2 TEXT` / `ADD COLUMN asset_id TEXT` / `ADD COLUMN completion_status TEXT`，可空无默认值）+ `MIGRATION_3_4`，注册进 databaseBuilder 的 addMigrations 清单（照 MIGRATION_2_3 现有写法）；**核查未使用 `fallbackToDestructiveMigration`（若使用，迁移注册必须齐全防清库）；若 build.gradle 配置了 room.schemaLocation，处理 4.json 导出产物**；
4. `SyncRepository.kt:231-232` `toEntity()`/`toSync()` 末尾补三参数透传；
5. **构造点清单（执行时 rg `TeachingSessionEntity(` 全量列出逐一核对）**：命名参数+默认值保证零破坏；DAO 查询返回自动映射新列。

**测试矩阵**（android/app/src/test，**已实地核实：无 room-testing 依赖、无 migration 测试先例**）：
1. DTO 反序列化：不含三字段的旧包 JSON → 成功且 null；含三字段新包 → 值正确（放 data/sync 现有测试风格处）；
2. toEntity/toSync 往返保值：含三字段 DTO → toEntity → toSync → 三字段保值；
3. **migration 护航（无 room-testing 基建的替代方案，写死；不引入 room-testing 新依赖）**：新建 `MigrationsTest.kt` 纯 JUnit 单测，断言 `MIGRATION_3_4_STATEMENTS` 与三条预期 ALTER 语句**逐字符串相等**（防列名/表名手滑），并断言 `MIGRATION_2_3` 等既有迁移未被改动；
4. **真机迁移实测（android-emulator 工具链可用时必做；不可用时记环境豁免并说明）**：模拟器先装当前 HEAD 构建的 v3 APK → 启动产生 3 号库并造数据（导入书籍）→ 覆盖安装本轮 v4 APK → 启动后**断言书籍数据保留可读**（UI 书列表非空或 DB 文件内容断言），不只"启动不崩"；
5. 全量回归：`gradlew :app:testDebugUnitTest --tests "*Sync*" --tests "*FSRS*"` + 全量。

**验证**：新测试过；Android 全量单测绿；`assembleDebug` 编译过。
**风险**：中低——Room migration 语句以字符串断言锁定+可空列 ADD COLUMN 语义安全（真机升级由 Room 自动执行）。

### R4：后端 FSRS 存量状态直通（stability/difficulty/elapsed_days）

**问题**：`service.py:295-300` 只传 SM-2 三件套；`spaced_repetition_v2.py:142` 每轮 `migrate_sm2_to_fsrs(ef, iv, reps)` 重估；`_calculate_fsrs` 的 `elapsed_days=0` 硬编码。后果：FSRS 上一轮写回的真实 stability 被丢弃（下轮被拉回 `scheduled_days*0.8` 经验估算）、稳定性演进被持续污染、与 Android（ReviewRepository.kt:47-56 直通+真实 elapsed）行为不一致。

**改点（写死）**：
1. `calculate_next_review`（:69，签名 `..., now=None, algorithm=None, lapses=0`）**末尾追加** `stability: float | None = None, difficulty: float | None = None, last_review: datetime | None = None`；`_calculate_fsrs` 签名同步追加并透传；
2. `_calculate_fsrs` 内：stability/difficulty **均非 None → 直通**，任一为 None → 维持 `migrate_sm2_to_fsrs` 迁移估算（SM-2 时代记录两列为 NULL）；**elapsed_days 与 last_review 同源推导（第 2 轮评审修正：两者必须一致，禁止 elapsed 用真值而 last_review 留估算的自相矛盾态）**——`last_review` 非 None → `FSRSState(last_review=last_review, elapsed_days=max((now - last_review).days, 0))`；None → 维持现估算（`now - timedelta(days=interval)`，elapsed_days=0）；
3. `service.py`：读旧记录处追加 `old_stability = mastery.stability if mastery else None`、`old_difficulty = mastery.difficulty if mastery else None`、`old_last_review = mastery.last_reviewed_at if mastery else None`（`last_reviewed_at` 字段已核实存在，models.py:104）；调用处追加三个关键字实参（负 elapsed 由算法内截断防时钟漂移）；
4. **调用点清单（已 rg 核实）**：`spaced_repetition_v2.py:296` 模块级包装（默认参数=旧行为）、`service.py:300` 主调用（唯一改行为点）；`service.py:480/567`、`teaching/service.py:1005/1023` 为 SM-2 三返回值旧签名，不触碰；
5. Android 不改（已是目标语义）。

**行为变化声明**：首轮复习（无记录或 stability 为 NULL）行为与修复前完全一致；第二轮起 FSRS 路径三状态从存量真实值演进——这是修复目标本身。**已核实 test_service.py 无 stability 数值快照锁定**（仅 :248 直构 FSRSState 测调度器，不受影响）；执行时若全量回归暴露其他锁定旧行为的断言，逐个核实语义后更新并注明。

**测试矩阵**：
1. 单元直通：`_calculate_fsrs(..., lapses=1, stability=5.0, difficulty=6.0, last_review=now-3d)` → 输出 stability 从 5.0 按 FSRS 公式演进（≠ `migrate_sm2_to_fsrs(ef,iv,reps)` 重估值）；difficulty 从 6.0 演进；elapsed_days 推导为 3；
2. 单元兼容：同调用不传三参数 → 输出与修复前一致（锁定旧行为快照，含 elapsed_days=0 与估算 last_review 路径）；
3. service 闭环断言方式（写死）：新 unit 首答 → **断言 DB 落库 stability/difficulty/last_reviewed_at 均非空（已核实 `_upsert_mastery` 双路径均写 last_reviewed_at，service.py:117/139）**，落库 stability 即 FSRS 输出 S1；**同 unit 第二答 → 查库断言最终 stability 与"以 S1 为输入直接调 `_calculate_fsrs` 的单元输出"一致**（证明走了直通而非重估）；SM-2 时代记录（algorithm='sm2'、两列 NULL）→ 不报错、走估算路径、落库转 FSRS；
4. last_review 同源：`last_reviewed_at` 距今 3 天 → 单元断言 elapsed_days=3 进 state；`last_reviewed_at=None` → 维持估算路径与现状一致；
5. lapses 保值回归：P1 专项全绿（lapses 与状态直通互不干扰）；
6. quality 0~5 全覆盖既有测试回归。

**验证**：新测试过；`pytest app/modules/review app/modules/sync app/modules/teaching -q` 全绿；全量 pytest 全绿。
**风险**：中——数值行为变化（第二轮起），锁定测试+兼容快照+Android 同语义护航。

### W：两个测试警告修复

- **W1** `test_feynman_phase.py` coroutine never awaited：**判定标准写死**——优先补 `await`（保测试原语义：本应异步调用的 mock 链路）；仅当该调用本身就该是同步（mock 配置错用 AsyncMock）时才改 mock 配置；修复后该文件单跑 0 warning。
- **W2** `UpdateDownloaderTest.kt:61` nullable receiver：**优先 `requireNotNull(x) { "消息" }`（失败信息清晰，第 4 轮评审采纳）**；语义为"可空跳过"才用 `?.`；现场按上下文选择并在行内注释一句。
**验证**：`pytest <该文件> -q` 输出无 RuntimeWarning；**全量 pytest 输出 warnings summary 为空**（终态口径）；Android 单测编译 0 该 warning。
**风险**：零。

### C1：未用导入分批清理（63 条非测试非白名单）

**范围写死**：140 条未用导入中——`database.py` 22 条（模型注册副作用导入）+`models.py` 2 条（`Mapped/mapped_column`：文件实际用 `Column()` 旧式风格，导入未用；公共底层文件保守保留）→ 白名单 `docs/superpowers/plans/logs/pyflakes_whitelist.txt` 创建入库（格式 `文件:行 符号 —— 保留原因`）；测试文件 9 条不动；其余 **63 条**（modules 62 + common 1，实测）分 2 批：
- **C1-a**：review + teaching + knowledge_graph + knowledge_splitter + adaptive_design + ai_learning
- **C1-b**：learning_assets + learning_plan + document_parser + sync + common + user_storage
（条数按 pyflakes 清单模块归属自然分组，执行时以清单为准逐条勾选。）

**删除规则**：每条删除前 `rg <符号名> backend/app` 确认无字符串注解引用（P2 教训）；**符号出现在任何 `__all__` 列表中则保留（已核实 3 处 `__init__.py` 有 `__all__`）；importlib/`__import__` 热点文件（已扫描：teaching/service.py 两处内联 `__import__('uuid')`、document_parser 包 `__init__.py`、test 文件）与 63 条清单无交叉，执行时对这两类文件人工再过一遍**；多符号同行只删未用符号；`import x as y` 变体同法核对；白名单外每批后该批文件 pyflakes 0 报告、全仓无新增；**每批 commit message 列出删除的符号清单**（可回溯）。
**门禁固化**：`final_gate.py` 新增检查项——`pyflakes app` 输出过滤白名单文件后必须为 0 行（本轮清理后固化成永久门禁，今后新增死导入立即暴露）。
**验证**：每批相关模块测试 + 全量 pytest 全绿 + `python -c "import app.main"` 导入冒烟；分批 commit。
**风险**：低——rg 核对+测试护航；涉及 P2 修过的注解文件（review/service.py 等）格外核对 `get_type_hints` 路径。

### D1：Android 端侧数据模块总览

新建 `docs/模块总览/Android端侧数据模块总览.md`：覆盖 data/db + data/repository + data/sync + data/algorithm 四子域，按同步闭环一条线讲（同步包进出 → Entity 落库 → 仓库调度 → FSRS 算法 → 回写/导出），含全部必填字段；R1b 的 v2 三字段写入"关键数据结构"与"已知坑"解决记录；**必含"Android↔后端 sync 字段对齐清单表"**（v2 三字段的 后端列名/DTO 字段/Room 列 一一对应，供未来改字段者对齐参考）；"已知坑"登记"两端 FSRS 默认参数（后端 DEFAULT_PARAMETERS vs Android FSRSAlgorithm）一致性靠人工对齐"的真实约束。`README.md` 索引加一行、移除"端侧总览列为后续任务"声明。
**验证**：字段自查 + `check_modules.py` 无红档。
**风险**：零。

### P6'：终检 + 推送

1. 后端：全量 pytest（期望 ≥522+新增，**warnings summary 为空**）+ **pyflakes 终态口径：过滤白名单后 0 行（final_gate 新检查项）**+ smoke 连跑 2 次（含升级后五字段保值断言）；
2. 前端：tsc + npm run build；Android：全量单测 --rerun-tasks + assembleDebug；
3. **终检前 `git fetch origin` 确认远程无新提交**（防覆盖他人推送）；**真实库 hash 双算：smoke 运行前、后各算一次源库 SHA256，两者与备份一致（证明 smoke 未触碰真实库）**；
4. 真实库 hash 三方比对；四查 `check_session_close.py` 退出码 0（黄档逐条人工判定）；
5. 隐私：`git_push_github.py` 自带扫描 + 人工过 diff；隐私扫描三范围沿用；
6. `final_gate.py --base origin/master` 全 PASS 落盘；更新 `docs/当前进度.md` → commit → 推送 → post-push note（本地/远程 hash 一致实证）。

## 四、评分记录

- 第 1 轮（2026-10-28 夜）：总计划 81 / R1a 85 / R1b 77 / R4 84 / W 84 / C1 80 / D1 86 / P6' 80。建议：R1b 须实地核实 migration 测试基建并写死护航方案；R4 须核实 last_reviewed_at 字段决定 elapsed_days 是否纳入、写死 service 闭环断言方式；R1a 旧包兼容构造方式写死+导出幂等断言；W1 判定标准写死；C1 批次条数实测；P6' pyflakes 终态口径写死。→ v2 已修订（三处实地核实完成）。
- 第 2 轮（2026-10-28 夜）：总计划 90 ✅ / R1a 91 ✅ / R1b 88 / R4 87 / W 89 / C1 88 / D1 89 / P6' 89。建议：R1b 缺真机迁移验证（补模拟器覆盖安装实测+destructive migration 核查）；R4 的 elapsed_days 与 last_review 必须同源（签名改为传 last_review 由算法内推导）；W 补全量 0 warning 终态口径；C1 门禁固化进 final_gate 才有持续价值；D1 补字段对齐清单表与 FSRS 参数坑登记；P6' 补 git fetch 防覆盖。→ v3 已全部修订。
- 第 3 轮（2026-10-28 夜）：总计划 90 ✅ / R1a 91 ✅ / R1b 91 ✅（模拟器实测补齐后风险控制 19）/ R4 90 ✅（同源修正后正确性 19；风险控制 17 为诚实扣分——FSRS 数值演进的长期影响需观察，已用兼容快照+Android 同语义缓解）/ W 90 ✅ / C1 90 ✅ / D1 90 ✅ / P6' 90 ✅。**全部 ≥90，提交独立复核。**
- 第 4 轮（2026-10-28 夜）：**独立复核**（高智商渠道连续 3 次 HTTP 524 网关超时，按护栏规则改用普通测试 API 独立评审，26s 返回）→ 73 分 + 5 条建议。逐条技术核实结论：①R1a"旧包导入清列"担忧**不成立**（sync 导入为 delete+add 全量重放，不存在覆盖更新场景，已核实 `_add_models` 实现，论证写入 R1a 测试矩阵第 6 条）；②R4"首答须落库三列"**已被现有代码满足**（`_upsert_mastery` 双路径均写 last_reviewed_at，:117/:139），测试矩阵补首答非空断言；③R1b 迁移验证**采纳增强**（模拟器实测标准升级为数据保留断言；不引入 room-testing 依赖）；④C1 动态引用扫描**已执行**（`__all__` 3 处、importlib/`__import__` 热点与清单无交叉，规则补录）；⑤P6 hash 污染担忧**采纳增强**（smoke 前后双算 hash）；W2 改 requireNotNull；D1 对齐表加 nullable 列。→ v4 融合后：总计划 92 / R1a 92 / R1b 92 / R4 91 / W 91 / C1 91 / D1 91 / P6' 91。**计划冻结，开始执行。**
