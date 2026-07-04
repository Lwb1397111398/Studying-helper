"""意图画像推断器 - LLM 增强 + 规则化回退

从 BookModel.reading_motivation（用户导入时填写的学习动机）和单元难度分布，
推断画像四维 + 重组 tolerance 的默认值，供用户预览确认。
LLM 不可用或失败时回退到规则化关键词匹配。
"""

import json
import re
from typing import Optional

from sqlalchemy import select, func

from app.common.llm_client import LLMClient, LLMMessage
from app.db.models import BookModel, KnowledgeUnitModel
from app.modules.adaptive_design.schemas import LearnerIntentProfileSchema
from app.modules.adaptive_design.prompts import PROFILE_INFER_PROMPT


# 关键词 -> 画像维度映射（保守、低误判）
_EXAM_KEYWORDS = ["考试", "考研", "考证", "应试", "司考", "法考", "注会", "cpa", "quiz", "exam"]
_PROFESSIONAL_KEYWORDS = ["专业", "法学", "法学生", "本科", "研究生", "从业者", "工作需要"]
_HOBBY_KEYWORDS = ["兴趣", "爱好", "好奇", "入门", "了解", "随便看看", "自学"]
_ANALOGY_KEYWORDS = ["生动", "有趣", "通俗", "白话", "类比", "举例"]
_RIGOR_KEYWORDS = ["严谨", "系统", "专业", "深入", "理论"]


def _match(text: str, keywords: list[str]) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(k.lower() in t for k in keywords)


async def infer_profile(
    db,
    book_id: str,
    user_id: str = "anonymous",
    llm_client: Optional[LLMClient] = None,
) -> LearnerIntentProfileSchema:
    """推断意图画像默认值。LLM 增强优先，失败回退规则化。

    Args:
        db: AsyncSession
        book_id: 书 ID
        user_id: 默认 anonymous
        llm_client: 可选 LLM 客户端，None 或调用失败则用规则化

    Returns:
        LearnerIntentProfileSchema（source=ai_inferred, status=draft）
    """
    # 读 book 的 reading_motivation
    result = await db.execute(
        select(BookModel.reading_motivation).where(BookModel.id == book_id)
    )
    motivation: Optional[str] = result.scalar_one_or_none()

    # 单元难度均值（用于推断 tolerance：高难度书倾向保守，避免打乱）
    diff_result = await db.execute(
        select(func.avg(KnowledgeUnitModel.difficulty_level))
        .where(KnowledgeUnitModel.book_id == book_id)
    )
    avg_diff = diff_result.scalar_one_or_none()

    # 优先 LLM 增强（reading_motivation 为空或 LLM 无 key 时跳过，直接规则化）
    llm_has_key = llm_client is not None and bool(getattr(llm_client, "api_key", ""))
    if llm_has_key and motivation:
        try:
            llm_result = await _infer_with_llm(llm_client, motivation, avg_diff)
            if llm_result:
                return LearnerIntentProfileSchema(
                    user_id=user_id,
                    book_id=book_id,
                    identity_background=llm_result["identity_background"],
                    goal_depth=llm_result["goal_depth"],
                    cognitive_pref=llm_result["cognitive_pref"],
                    restructure_tolerance=llm_result["restructure_tolerance"],
                    source="ai_inferred",
                    status="draft",
                )
        except Exception:
            pass  # LLM 失败，回退规则化

    return _infer_rulebased(motivation, avg_diff, book_id, user_id)


async def _infer_with_llm(
    llm_client: LLMClient, motivation: str, avg_diff
) -> Optional[dict]:
    """用 LLM 推断画像。返回四维 dict 或 None。"""
    prompt = PROFILE_INFER_PROMPT.format(
        motivation=motivation[:500],
        avg_difficulty=f"{avg_diff:.1f}" if avg_diff else "未知",
    )
    resp = await llm_client.chat_json(
        messages=[LLMMessage(role="user", content=prompt)],
        temperature=0.2,
    )
    if isinstance(resp, str):
        resp = json.loads(resp)
    # 校验枚举值合法
    valid = {
        "identity_background": {"expert", "related", "unrelated", "unknown"},
        "goal_depth": {"exam_memorize", "apply_understand", "general_interest"},
        "cognitive_pref": {"vivid_analogy", "rigorous_system", "problem_driven"},
        "restructure_tolerance": {"keep_book_order", "moderate", "aggressive"},
    }
    result = {}
    for k, allowed in valid.items():
        v = resp.get(k)
        result[k] = v if v in allowed else None
    if all(result.values()):
        # 高难度新手仍要防过载
        if avg_diff and avg_diff > 3.5 and result["restructure_tolerance"] == "aggressive":
            result["restructure_tolerance"] = "moderate"
        return result
    return None


def _infer_rulebased(
    motivation: Optional[str], avg_diff, book_id: str, user_id: str
) -> LearnerIntentProfileSchema:
    """规则化推断（LLM 不可用时回退）"""

    # 默认值
    identity = "unknown"
    goal = "apply_understand"
    cognitive = "rigorous_system"
    tolerance = "moderate"

    if motivation:
        if _match(motivation, _PROFESSIONAL_KEYWORDS):
            identity = "expert" if _match(motivation, ["法学", "法学生", "从业者"]) else "related"
        elif _match(motivation, _HOBBY_KEYWORDS):
            identity = "unrelated"

        if _match(motivation, _EXAM_KEYWORDS):
            goal = "exam_memorize"
        elif _match(motivation, _HOBBY_KEYWORDS):
            goal = "general_interest"

        if _match(motivation, _ANALOGY_KEYWORDS):
            cognitive = "vivid_analogy"
        elif _match(motivation, _RIGOR_KEYWORDS):
            cognitive = "rigorous_system"

    # 画像驱动 tolerance（计划里的护栏：专家型保留书结构，新手型大胆重组）
    if identity == "expert":
        tolerance = "keep_book_order"
    elif identity == "unrelated" or goal == "general_interest":
        tolerance = "aggressive"
    # 高难度（avg_diff > 3.5）即使新手也适度保守，避免认知过载
    if avg_diff and avg_diff > 3.5 and tolerance == "aggressive":
        tolerance = "moderate"

    return LearnerIntentProfileSchema(
        user_id=user_id,
        book_id=book_id,
        identity_background=identity,
        goal_depth=goal,
        cognitive_pref=cognitive,
        restructure_tolerance=tolerance,
        source="ai_inferred",
        status="draft",
    )
