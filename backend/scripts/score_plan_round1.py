"""计划案 AI 评分脚本（第一轮）：总计划 + P1~P6 逐项打分。

输出 JSON：{名称: {score, verdict, issues[], suggestions[]}}
<90 分的项目将按 suggestions 修改后重评。
"""
import sys
sys.path.insert(0, r"E:\AI Agent\Agent Manager\tools")
import json
from ai_client import chat

PLAN_PATH = r"E:\AI Agent\work area\Studying-helper\docs\superpowers\plans\2026-10-28-overnight-convergence.md"

RUBRIC = """你是资深软件工程评审。请对以下"通宵收敛计划案"做严格评分。

背景：这是一个个人 AI 学习辅助系统（FastAPI 后端 + React 前端 + Kotlin/Compose Android 端，离线同步包架构，SQLite 单用户）。计划目标是：修复体检发现的复习算法真 bug（FSRS lapses 丢失）、健壮性埋雷、死代码清理，固化冒烟脚本，补文档，最后三端终检后推送 GitHub。执行者是一个 AI agent，通宵自主工作，老板是编程小白。

评分维度（各 20 分）：
1. 正确性：技术方案是否真的能修好问题（特别是 FSRS lapses 数据流、向后兼容）
2. 完整性：是否漏了该做的验证/回归/边界情况
3. 风险控制：改动是否可能破坏现有功能，护栏是否足够
4. 可执行性：步骤是否具体到真实文件名/函数名，AI 能否照做不跑偏
5. 收益/成本比：是否值得做，有没有过度工程或漏掉更高价值的事

评分纪律：
- 90 分是执行门槛。给分要诚实：有明显缺口的计划就该低于 90。
- 每个 <90 的项必须给出具体、可操作的修改建议（指明缺什么、怎么补）。
- 不要客套，不要为了让人高兴而放水。

覆盖性核查（第 12 轮起启用）：本计划已经过 11 轮评审修订。给出建议前，先在文中检索该建议是否已被覆盖：
- 若建议内容计划已写明（哪怕措辞不同），不得再作为扣分项或新建议提出；
- 只对"计划确实没写"的实质缺口扣分；
- 若某项无实质缺口，应给 90 以上并明说"无新增实质缺口"。

输出严格 JSON（不要 markdown 代码块包裹）：
{"总计划": {"score": int, "issues": ["..."], "suggestions": ["..."]},
 "P1": {...}, "P2": {...}, "P3": {...}, "P4": {...}, "P5": {...}, "P6": {...}}

计划案全文如下：

"""

with open(PLAN_PATH, encoding="utf-8") as f:
    plan_text = f.read()

resp = chat([{"role": "user", "content": RUBRIC + plan_text}], timeout=180)
if isinstance(resp, tuple):  # ai_client.chat 返回 (文本, 耗时秒)
    resp = resp[0]
text = resp if isinstance(resp, str) else str(resp)
# 容错：剥围栏 + 正则抽取首尾大括号之间的 JSON
t = text.strip()
if t.startswith("```"):
    t = t.split("\n", 1)[1] if "\n" in t else t
if t.endswith("```"):
    t = t.rsplit("```", 1)[0]
import re
# 容错解析：从每个 "{" 位置尝试 raw_decode，第一个完整解析成功的 JSON 对象即采纳
last_err = "?"
dec = json.JSONDecoder()
data = None
for i, ch in enumerate(t):
    if ch != "{":
        continue
    candidate = t[i:]
    for attempt in (candidate, re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', candidate)):
        try:
            obj, _end = dec.raw_decode(attempt)
            if isinstance(obj, dict) and "总计划" in obj:
                data = obj
                break
        except json.JSONDecodeError as e:
            last_err = f"pos={e.pos} 附近: ...{attempt[max(0, e.pos-80):e.pos+80]}..."
            continue
    if data:
        break
if not data:
    print("原始回复开头 300 字：", t[:300])
    print("最后解析错误：", last_err)
    print("回复总长：", len(t))
    raise SystemExit(2)

with open(r"E:\AI Agent\work area\Studying-helper\docs\superpowers\plans\score_round16.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

for name, item in data.items():
    print(f"{name}: {item['score']} 分")
    for s in item.get("suggestions", [])[:3]:
        print(f"  - {s}")
