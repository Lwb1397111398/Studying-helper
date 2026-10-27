# -*- coding: utf-8 -*-
"""备选复核：普通测试 API 独立评审计划案（高智商渠道 524 时的护栏备选）"""
import sys
sys.path.insert(0, r"E:\AI Agent\Agent Manager\tools")
from ai_client import chat

sysmsg = (
    "你是资深软件架构评审，对通宵自动化任务的执行计划做独立复核。"
    "输出：①总分（五维：正确性/完整性/风险控制/可执行性/收益成本比各0-20，满分100，90为执行线）；"
    "②必须修复的实质问题清单（若无则写：无）；③可选改进最多3条。直接挑剔，不为挑刺而挑刺。回答控制在600字内。"
)
usermsg = """背景：个人AI学习辅助系统（FastAPI+SQLite / React / Kotlin Compose+Room，离线包同步）。上轮已修FSRS lapses全链路。本轮修上轮遗留：
【R1a 后端sync契约补v2三字段】SyncTeachingSession缺 state_v2/asset_id/completion_status（DB已有列）。导出按model_fields取值、导入用model_dump构造——schema加可选字段(默认None)即两端生效。测试：导出保值/回灌查库保值/旧包兼容/导出幂等。
【R1b Android对齐】SyncDtos、Entities末尾追加可空字段、Room version 3→4+三条ALTER TABLE ADD COLUMN可空TEXT、toEntity/toSync补参。无room-testing基建→护航=JUnit断言迁移语句逐字符串相等+模拟器覆盖安装实测(v3 apk造数据→v4 apk启动不崩)。核查未用fallbackToDestructiveMigration。
【R4 FSRS存量状态直通】后端每轮从ef/iv重估stability/difficulty且elapsed_days=0硬编码；Android已直通+真实elapsed——两端不一致。修法：算法签名末尾追加stability/difficulty/last_review=None；非None直通，None走旧估算(兼容SM-2记录)；last_review非None时elapsed_days=max((now-last_review).days,0)同源推导。行为变化：首轮(存量NULL)与修复前一致；第二轮起从存量真实值演进=修复目标。已核实无stability数值快照锁定。测试：单元直通/单元兼容旧行为快照/service闭环(第二答输入=首答落库值,查库断言)/last_review=None兼容/lapses保值回归/quality0-5回归。
【W】W1 coroutine未await：优先补await；终态=全量pytest 0 warning。W2 Kotlin nullable：按断言语义选!!或?.。
【C1 未用导入清理】140条中22条副作用导入+2条底层文件保留→白名单入库；测试9条不动；其余63条分2批。每条删前rg防字符串注解引用；批后pyflakes 0+全量pytest+import冒烟；final_gate固化pyflakes过滤白名单=0。
【D1】Android端侧数据模块总览一篇（四子域同步闭环）含字段对齐清单表。
【P6'终检推送】全量pytest+pyflakes口径+smoke连跑2次(断言升级含v2五字段)+三端build+真实库hash三方比对+四查+隐私扫描+final_gate→推送。
执行纪律：独立commit、止损回滚、每计划完成全量回归+之前计划专项重跑、执行期五维复评≥90。
请复核：指出仍存在的实质漏洞（尤其R4数值行为变化风险、R1b Room迁移风险、C1删除风险）。"""
messages = [
    {"role": "system", "content": sysmsg},
    {"role": "user", "content": usermsg},
]
reply, secs = chat(messages)
print(reply)
print(f"---耗时 {secs:.0f}s---")
