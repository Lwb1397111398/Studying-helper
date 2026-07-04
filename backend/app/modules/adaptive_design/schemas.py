"""AID 模块 Pydantic 模型

枚举用 Literal（而非 Enum），sync 的 _to_schema 反射取字符串免 converter。
所有 *_json 字段在 sync schema 里用 str，service 层 json.loads。
"""

from datetime import datetime
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ── 学习者意图画像四维 + 重组 tolerance ──
IdentityBackground = Literal["expert", "related", "unrelated", "unknown"]
GoalDepth = Literal["exam_memorize", "apply_understand", "general_interest"]
CognitivePref = Literal["vivid_analogy", "rigorous_system", "problem_driven"]
RestructureTolerance = Literal["keep_book_order", "moderate", "aggressive"]


class LearnerIntentProfileSchema(BaseModel):
    """学习者意图画像（每书一份）"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = "anonymous"
    book_id: str
    identity_background: IdentityBackground = "unknown"
    goal_depth: GoalDepth = "apply_understand"
    cognitive_pref: CognitivePref = "rigorous_system"
    restructure_tolerance: RestructureTolerance = "moderate"
    time_budget_minutes: Optional[int] = None
    source: Literal["ai_inferred", "user_set", "user_adjusted"] = "ai_inferred"
    status: Literal["draft", "confirmed"] = "draft"
    extra_json: str = "{}"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ProfileUpdateRequest(BaseModel):
    """用户调整画像（None 表示不改）"""

    identity_background: Optional[IdentityBackground] = None
    goal_depth: Optional[GoalDepth] = None
    cognitive_pref: Optional[CognitivePref] = None
    restructure_tolerance: Optional[RestructureTolerance] = None
    time_budget_minutes: Optional[int] = None


# ── Macro：跨章节模块骨架 ──
class ModuleSkeleton(BaseModel):
    """宏观模块骨架 - 跨章节聚类，单元顺序由 micro 决定"""

    index: int
    title: str
    unit_ids: list[str] = Field(default_factory=list)  # 该模块覆盖的 unit（未排序）
    concept_ids: list[str] = Field(default_factory=list)  # 跨章节关联概念
    strategy_tags: list[str] = Field(default_factory=list)  # 见 STRATEGY_TAGS
    rationale: str = ""  # 为何这么分
    estimated_minutes: Optional[int] = None


class MacroDesignSchema(BaseModel):
    """宏观设计：N 个跨章节模块 + 全书策略"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    book_id: str
    profile_id: str
    modules: list[ModuleSkeleton] = Field(default_factory=list)
    global_strategy: str = ""
    total_modules: int = 0
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.now)


# ── Micro：模块内教授计划 ──
class UnitRetrofitAnnotation(BaseModel):
    """单元重构标注 - 决定单单元如何被教授"""

    unit_id: str
    cognitive_mode: Literal["memorize", "understand", "skip_if_mastered"]
    merge_group: Optional[str] = None  # 同组单元合并讲解；None=独立
    defer_to_module: Optional[int] = None  # 推迟到第几模块；None=不推迟
    emphasis: Optional[str] = None  # 提示 teaching 侧重什么
    note: Optional[str] = None


class MicroPlanSchema(BaseModel):
    """微观编排：模块内重排路径 + 标注 + 地图提示"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    design_id: str
    module_index: int
    module_title: str = ""
    ordered_unit_ids: list[str] = Field(default_factory=list)
    unit_annotations: list[UnitRetrofitAnnotation] = Field(default_factory=list)
    module_intro: Optional[str] = None  # 地图提示导言
    module_status: Literal["pending", "active", "done", "skipped"] = "pending"
    module_summary_json: Optional[str] = None  # replan 回写
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# ── Replan ──
class StageFeedback(BaseModel):
    """模块结束反馈（replan 输入）"""

    module_index: int
    weak_points: list[str] = Field(default_factory=list)
    user_feedback: Optional[str] = None
    time_spent_minutes: Optional[int] = None


class ReplanResult(BaseModel):
    """replan 产出：对下一模块的调整"""

    next_module_index: int
    revisit_unit_ids: list[str] = Field(default_factory=list)  # 需回访精讲的旧单元
    skip_unit_ids: list[str] = Field(default_factory=list)  # 已掌握跳过
    rationale: str = ""


class UserAdjustment(BaseModel):
    """用户调整审计记录（append-only，喂给 LLM 防反复拉锯）"""

    module_index: Optional[int] = None
    field: str
    old_value: str = ""
    new_value: str = ""
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)


# ── 响应/承载模型 ──
class TeachingDesignSchema(BaseModel):
    """教学设计总账（API 响应）"""

    id: str
    user_id: str = "anonymous"
    book_id: str
    profile_id: Optional[str] = None
    macro_design: Optional[MacroDesignSchema] = None
    current_module_index: int = 0
    generated_module_count: int = 0
    adjustments: list[UserAdjustment] = Field(default_factory=list)
    status: Literal["draft", "active", "completed", "superseded"] = "draft"
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# 策略标签枚举（供 LLM 与规则化共同使用）
STRATEGY_TAGS = {
    "concept_merge_overview": "多概念合并概览",
    "defer_hard_point": "难点延迟精讲",
    "rapid_survey": "快速浏览建立全局",
    "deep_dive": "深度精讲",
    "spaced_revisit_seed": "埋点后续回访",
    "comparison_group": "对比学习组",
}
