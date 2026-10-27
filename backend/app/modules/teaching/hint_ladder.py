"""三级提示阶梯（REPAIR / 答错递进）。

纯函数模块：不计状态、不加新表。
- 第 1 次错 → hint_level=1 引导性提示
- 第 2 次错 → hint_level=2 部分解析
- 第 3 次错 → hint_level=3 完整答案 + 标记 review

错误类型：memory | confusion | missing_prereq | unknown
"""

from __future__ import annotations

from typing import Any, Optional


MAX_HINT_LEVEL = 3
PASS_SCORE = 60


def fail_count_from_assessments(assessments: list[dict[str, Any]]) -> int:
    """从历史 assessment 列表统计连续失败次数（从最近往前，遇通过则断）。"""
    count = 0
    for a in reversed(assessments or []):
        if not isinstance(a, dict):
            continue
        score = a.get("score")
        try:
            score_f = float(score) if score is not None else 0.0
        except (TypeError, ValueError):
            score_f = 0.0
        passed = a.get("should_advance")
        if passed is None:
            passed = score_f >= PASS_SCORE
        if passed or score_f >= PASS_SCORE:
            break
        count += 1
    return count


def next_hint_level(fail_count_before: int, hint_policy: str = "ladder") -> int:
    """根据「本次答错前」的已失败次数，给出本次应使用的 hint_level (1–3)。

    fail_count_before=0 → 第 1 次错 → level 1
    fail_count_before=1 → 第 2 次错 → level 2
    fail_count_before>=2 → 第 3 次错 → level 3
    """
    if hint_policy and hint_policy != "ladder":
        if hint_policy == "answer_first":
            return MAX_HINT_LEVEL
        if hint_policy == "hint_only":
            return 1
    return min(MAX_HINT_LEVEL, max(1, fail_count_before + 1))


def hint_level_from_repair_rounds(repair_rounds: int) -> int:
    """v2 状态机：进入 REPAIR 时 repair_rounds 为「即将/已完成」轮次。

    rounds=0 → level1；1 → level2；>=2 → level3
    """
    return min(MAX_HINT_LEVEL, max(1, int(repair_rounds) + 1))


def classify_error_type(
    student_answer: str,
    claim_text: str = "",
    mastery_check: str = "",
    feedback: str = "",
) -> str:
    """粗分错误类型（规则，无 LLM）。"""
    ans = (student_answer or "").strip().lower()
    fb = (feedback or "").lower()
    claim = (claim_text or "").lower()
    check = (mastery_check or "").lower()

    if not ans or ans in ("不知道", "不会", "不清楚", "?", "？", "idk", "no idea"):
        return "memory"

    prereq_kw = ("前置", "基础", "先学", "依赖", "没学过", "prereq", "prerequisite")
    if any(k in fb for k in prereq_kw) or any(k in ans for k in ("没学", "不会基础", "前置")):
        return "missing_prereq"

    confusion_kw = ("混淆", "搞混", "相反", "不是", "误以为", "confus")
    if any(k in fb for k in confusion_kw):
        return "confusion"

    # 答案与命题有部分词重叠但反馈低分 → 更像混淆
    if claim:
        tokens = [t for t in claim.replace("，", " ").replace("。", " ").split() if len(t) >= 2]
        hit = sum(1 for t in tokens[:8] if t.lower() in ans)
        if hit >= 2 and ("错" in fb or "不" in fb or "缺" in fb):
            return "confusion"

    if check and any(k in fb for k in ("记", "回忆", "背", "漏")):
        return "memory"

    return "unknown"


def should_mark_review(hint_level: int) -> bool:
    return hint_level >= MAX_HINT_LEVEL


def build_repair_instruction(
    hint_level: int,
    error_type: str = "unknown",
    claim_text: str = "",
    mastery_check: str = "",
) -> str:
    """生成注入 REPAIR prompt 的阶梯指令。"""
    et_note = {
        "memory": "学生像是记不清关键事实/定义，提示时帮他回忆线索，不要指责。",
        "confusion": "学生可能把相近概念搞混了，提示时做对比辨析。",
        "missing_prereq": "学生可能缺前置知识，提示时点出需要回顾的基础，勿直接讲新内容全貌。",
        "unknown": "按一般理解困难处理。",
    }.get(error_type, "按一般理解困难处理。")

    level_guides = {
        1: (
            "【hint_level=1 引导性提示】\n"
            "- 只给方向：指向 mastery_check 的观察点，抛 1 个引导问题\n"
            "- **禁止**给出最终答案、关键步骤结论或可直接抄写的完整表述\n"
            "- 2–4 句即可"
        ),
        2: (
            "【hint_level=2 部分解析】\n"
            "- 拆出关键步骤/推理的前半段，留最后一步让学生完成\n"
            "- 可给类比或中间结论，**仍不要**写完整标准答案\n"
            "- 4–8 句"
        ),
        3: (
            "【hint_level=3 完整答案 + 解析】\n"
            "- 给出对照 mastery_check 的完整示范回答\n"
            "- 简要说明为什么这样答、之前可能错在哪\n"
            "- 明确告知：本题已标记复习，稍后会再练\n"
            "- 语气鼓励，不要羞辱"
        ),
    }
    level_guide = level_guides.get(
        hint_level,
        "【hint_level=1 引导性提示】只给方向，不给答案。",
    )

    parts = [
        f"当前提示等级：{hint_level}/{MAX_HINT_LEVEL}",
        f"错误类型：{error_type} — {et_note}",
        level_guide,
    ]
    if mastery_check:
        parts.append(f"掌握标准（mastery_check）：{mastery_check}")
    if claim_text:
        parts.append(f"相关命题：{claim_text}")
    return "\n".join(parts)


def rule_based_repair_text(
    hint_level: int,
    *,
    claim_text: str = "",
    mastery_check: str = "",
    error_type: str = "unknown",
    question: str = "",
) -> str:
    """无 LLM 时的阶梯 fallback 文案。"""
    mc = mastery_check or "能正确说明该知识点"
    ct = claim_text or "相关要点"
    et = {
        "memory": "先试着回忆定义里最关键的一两个词。",
        "confusion": "想想它和相近概念差在哪一点。",
        "missing_prereq": "若觉得缺基础，先回顾前置概念再回来。",
        "unknown": "对照掌握标准，看看缺了哪一步。",
    }.get(error_type, "对照掌握标准再想一步。")

    if hint_level <= 1:
        return (
            f"**提示（1/3）**\n"
            f"请对照掌握标准再想一想：{mc}\n"
            f"引导：{et}\n"
            f"想一想：如果要用自己的话解释「{ct[:40]}」，你会先说哪一句？"
        )
    if hint_level == 2:
        return (
            f"**部分解析（2/3）**\n"
            f"掌握标准：{mc}\n"
            f"关键方向：围绕「{ct[:60]}」——先写出你已知的一半，再补上「为什么成立」。\n"
            f"{et}\n"
            f"请你完成后半段：它为什么重要 / 如何检验自己真懂了？"
        )
    # level 3
    q = f"\n原题：{question}" if question else ""
    return (
        f"**完整解析（3/3）+ 已标记复习**\n"
        f"{q}\n"
        f"示范要点：{ct}\n"
        f"达到标准的表现：{mc}\n"
        f"本题已加入复习队列，之后会用间隔重复再练一次。先看懂示范，再用自己的话复述一遍。"
    )


def format_repair_assessment(
    *,
    hint_level: int,
    error_type: str,
    repair_text: str,
    score: int,
    mark_review: bool,
    claim_id: Optional[str] = None,
    mastery_check: str = "",
) -> dict[str, Any]:
    """组装写入 assessment_json 的结构化结果。"""
    data: dict[str, Any] = {
        "score": score,
        "should_advance": False if hint_level < MAX_HINT_LEVEL else True,
        "mastery_level": "poor" if score < 40 else "partial",
        "feedback": repair_text,
        "suggestion": (
            "已给出完整解析并标记复习" if mark_review
            else f"请根据 {hint_level} 级提示再答一次"
        ),
        "hint_level": hint_level,
        "error_type": error_type,
        "mark_review": mark_review,
        "hint_policy": "ladder",
    }
    if claim_id:
        data["claim_id"] = claim_id
    if mastery_check:
        data["mastery_check"] = mastery_check
    return data
