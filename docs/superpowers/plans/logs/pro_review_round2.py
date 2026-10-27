# -*- coding: utf-8 -*-
"""高智商 API 终审：通宵收敛第 2 轮计划案（压缩版）"""
import sys
sys.path.insert(0, r"E:\AI Agent\Agent Manager\tools")
from pro_client import consult

sysmsg = (
    "你是资深软件架构评审，对通宵自动化任务的执行计划做终审。"
    "输出：①总分（五维：正确性/完整性/风险控制/可执行性/收益成本比各0-20，满分100，90为执行线）；"
    "②必须修复的实质问题清单（若无则写：无）；③可选改进最多3条。直接挑剔，不为挑刺而挑刺。回答控制在600字内。"
)
usermsg = """背景：个人AI学习辅助系统（FastAPI+SQLite / React / Kotlin Compose+Room，离线包同步）。上轮已修FSRS lapses全链路。本轮修上轮遗留：
【R1a 后端sync契约补v2三字段】SyncTeachingSession(schema.py:190)缺 state_v2/asset_id/completion_status（DB models.py:263-266 已有列）。导出_to_schema按model_fields取值、导入_add_models用model_dump构造——schema加可选字段(默认None)即两端生效，业务零改动。测试：导出保值/回灌查库保值/旧包model_validate兼容/导出幂等。
【R1b Android对齐】SyncDtos.kt:191、Entities.kt:165(末尾追加可空字段)、Room version 3→4+MIGRATION_3_4(三条ALTER TABLE teaching_sessions ADD COLUMN 可空TEXT)、SyncRepository toEntity/toSync末尾补参。已核实无room-testing基建→护航=JUnit断言MIGRATION_3_4_STATEMENTS逐字符串相等+模拟器覆盖安装实测(装v3 apk造数据→装v4 apk启动不崩)。核查未用fallbackToDestructiveMigration。
【R4 FSRS存量状态直通】service.py:295-300只传SM-2三件套，v2.py:142每轮migrate_sm2_to_fsrs(ef,iv,reps)重估stability/difficulty且elapsed_days=0硬编码；Android端ReviewRepository.kt:47已直通+真实elapsed——两端不一致。修法：calculate_next_review/_calculate_fsrs签名末尾追加 stability/difficulty/last_review=None；均非None直通，None走旧估算(兼容SM-2记录两列为NULL)；last_review非None时FSRSState(last_review=真值, elapsed_days=max((now-last_review).days,0))——elapsed与last_review同源推导。service读mastery.stability/difficulty/last_reviewed_at(models.py:104已核实存在)传关键字实参。行为变化：首轮(存量NULL)与修复前一致；第二轮起从存量真实值演进=修复目标。已核实test_service.py无stability数值快照锁定。测试：单元直通(5.0/6.0/3天前→输出≠重估值)/单元兼容(不传=旧行为快照)/service闭环(第二答输入=首答落库S1,查库断言)/last_review=None兼容/lapses保值(P1专项回归)/quality0-5回归。
【W】W1 test_feynman_phase coroutine未await：优先补await，仅mock配置错用AsyncMock时改配置；终态=全量pytest warnings summary为空。W2 Kotlin UpdateDownloaderTest.kt:61 nullable：按断言语义选!!或?.。
【C1 未用导入清理】pyflakes 140条中：database.py 22条(模型注册副作用导入)+models.py 2条(Column旧式风格,公共底层保守保留)→白名单入库；测试文件9条不动；其余63条(实测)分2批按模块清理。每条删前rg符号名防字符串注解引用；批后pyflakes 0+全量pytest+import app.main冒烟；commit列符号清单；final_gate固化pyflakes过滤白名单=0检查。
【D1 文档】Android端侧数据模块总览一篇(data/db+repository+sync+algorithm按同步闭环讲)，含后端↔Android字段对齐清单表、登记两端FSRS默认参数靠人工对齐的坑；README索引更新。
【P6'终检推送】全量pytest+pyflakes口径+smoke连跑2次(断言升级含v2五字段保值)+前端build+Android全测assembleDebug+真实库hash三方比对+四查工具+隐私扫描+final_gate+当前进度.md回写→推送。
执行纪律：独立commit、止损(reset --hard回滚+落盘失败现场)、每计划完成后全量回归+之前计划专项重跑(B完成回看A)、执行期五维复评≥90。整合验证：R1a+R1b后smoke断言升级连跑；R4后review/sync/teaching全模块+P1专项回归。
评分史：第1轮81/85/77/84/84/80/86/80→修订；第2轮90/91/88/87/89/88/89/89(建议：模拟器实测/elapsed同源/0warning终态/门禁固化/对齐表/git fetch)→v3已全部落实；第3轮90/91/91/90/90/90/90/90。
请终审：指出v3仍存在的实质漏洞（尤其R4数值行为变化的风险、R1b Room迁移风险、C1删除风险）。"""
messages = [
    {"role": "system", "content": sysmsg},
    {"role": "user", "content": usermsg},
]
reply, secs = consult(messages, task="通宵收敛第2轮计划案终审（压缩版v3）")
print(reply)
print(f"---耗时 {secs:.0f}s---")
