"""AID 服务 - 三层教学设计核心（M1 规则化版）

画像 CRUD + 规则化 Macro（跨章节聚类/章节分组）+ 规则化 Micro（拓扑序+标注）
+ teaching 集成入口 get_active_module_ordered_unit_ids。

M2 接入 LLM，本文件保留规则化作为回退。
"""

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ServiceError, ErrorCode
from app.common.llm_client import LLMClient, LLMMessage
from app.common.json_utils import parse_llm_json
from app.db.models import (
    LearnerIntentProfileModel,
    TeachingDesignModel,
    ModuleMicroPlanModel,
    KnowledgeUnitModel,
)
from app.modules.adaptive_design.kg_adapter import KGAdapter, UnitBrief
from app.modules.adaptive_design.profile_builder import infer_profile
from app.modules.adaptive_design.prompts import (
    MACRO_DESIGN_PROMPT, MICRO_PLAN_PROMPT, REPLAN_PROMPT,
)
from app.modules.adaptive_design.schemas import (
    LearnerIntentProfileSchema,
    MacroDesignSchema,
    ModuleSkeleton,
    MicroPlanSchema,
    UnitRetrofitAnnotation,
    ProfileUpdateRequest,
    UserAdjustment,
    TeachingDesignSchema,
    STRATEGY_TAGS,
)


class AIDService:
    """适应性教学设计服务"""

    def __init__(self, llm_client: LLMClient, db: AsyncSession):
        self.llm = llm_client
        self.db = db
        self.kg = KGAdapter(db)

    # ========== 画像 ==========

    async def get_or_create_profile(
        self, book_id: str, user_id: str = "anonymous"
    ) -> LearnerIntentProfileSchema:
        """获取或创建画像。存在则返回，不存在则规则化推断后创建。"""
        existing = await self._load_profile(book_id, user_id)
        if existing:
            return existing

        schema = await infer_profile(self.db, book_id, user_id, self.llm)
        model = LearnerIntentProfileModel(
            id=schema.id,
            user_id=user_id,
            book_id=book_id,
            identity_background=schema.identity_background,
            goal_depth=schema.goal_depth,
            cognitive_pref=schema.cognitive_pref,
            restructure_tolerance=schema.restructure_tolerance,
            time_budget_minutes=schema.time_budget_minutes,
            source=schema.source,
            status=schema.status,
            extra_json=schema.extra_json,
        )
        self.db.add(model)
        await self.db.flush()
        return schema

    async def update_profile(
        self, book_id: str, update: ProfileUpdateRequest, user_id: str = "anonymous"
    ) -> LearnerIntentProfileSchema:
        """用户调整画像。任何字段非 None 即更新。"""
        model = await self._load_profile_model(book_id, user_id)
        if not model:
            raise ServiceError(ErrorCode.NOT_FOUND, "画像不存在，请先创建")

        changed = False
        for field_name in (
            "identity_background",
            "goal_depth",
            "cognitive_pref",
            "restructure_tolerance",
            "time_budget_minutes",
        ):
            val = getattr(update, field_name)
            if val is not None and getattr(model, field_name) != val:
                setattr(model, field_name, val)
                changed = True

        if changed:
            model.source = "user_adjusted"
            model.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
        return self._profile_model_to_schema(model)

    async def confirm_profile(
        self, book_id: str, user_id: str = "anonymous"
    ) -> LearnerIntentProfileSchema:
        """draft → confirmed（生成 macro 的前置门禁）"""
        model = await self._load_profile_model(book_id, user_id)
        if not model:
            raise ServiceError(ErrorCode.NOT_FOUND, "画像不存在")
        if model.status == "confirmed":
            return self._profile_model_to_schema(model)
        # 首次确认视为用户确认 AI 推断值
        model.status = "confirmed"
        if model.source == "ai_inferred":
            model.source = "user_set"
        model.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return self._profile_model_to_schema(model)

    # ========== Macro ==========

    async def generate_macro_design(
        self, book_id: str, user_id: str = "anonymous"
    ) -> MacroDesignSchema:
        """生成宏观设计（跨章节模块化）。前置：画像已 confirmed。

        规则化策略（M1）：
        - keep_book_order：按章节分模块（保留书结构）
        - moderate / aggressive：基于概念共现跨章节聚类
        """
        profile = await self._load_profile(book_id, user_id)
        if not profile:
            raise ServiceError(ErrorCode.NOT_FOUND, "画像不存在")
        if profile.status != "confirmed":
            raise ServiceError(
                ErrorCode.VALIDATION_ERROR,
                "画像未确认，请先确认画像后再生成教学设计",
            )

        briefs = await self.kg.get_unit_briefs(book_id, user_id)
        if not briefs:
            raise ServiceError(ErrorCode.INSUFFICIENT_DATA, "该书无知识单元，无法设计")

        tolerance = profile.restructure_tolerance
        # 优先 LLM 跨章节聚类，失败回退规则化
        modules = None
        try:
            modules = await self._macro_with_llm(briefs, profile)
        except Exception:
            modules = None

        if modules is None:
            if tolerance == "keep_book_order":
                modules = self._macro_by_chapter(briefs, profile)
            else:
                modules = self._macro_by_concept_clusters(
                    briefs, profile, aggressive=(tolerance == "aggressive")
                )
                # 若聚类失败（无共现概念），回退章节分组，保证可用
                if not modules:
                    modules = self._macro_by_chapter(briefs, profile)
        else:
            # LLM 产出的模块做拓扑校验：模块间不得有反向依赖
            if not self._validate_macro_topology(modules, briefs):
                # 校验失败：回退规则化
                if tolerance == "keep_book_order":
                    modules = self._macro_by_chapter(briefs, profile)
                else:
                    modules = self._macro_by_concept_clusters(
                        briefs, profile, aggressive=(tolerance == "aggressive")
                    ) or self._macro_by_chapter(briefs, profile)

        # 应用画像驱动的全局策略标签
        global_strategy = self._global_strategy(profile)
        for m in modules:
            if not m.strategy_tags:
                m.strategy_tags = [self._default_module_tag(profile)]

        macro = MacroDesignSchema(
            book_id=book_id,
            profile_id=profile.id,
            modules=modules,
            global_strategy=global_strategy,
            total_modules=len(modules),
        )

        # 持久化设计总账（覆盖旧的 active 设计：旧置 superseded，version 递增）
        next_version = await self._supersede_old_designs(book_id, user_id)
        model = TeachingDesignModel(
            id=macro.id,
            user_id=user_id,
            book_id=book_id,
            profile_id=profile.id,
            macro_design_json=macro.model_dump_json(),
            current_module_index=0,
            generated_module_count=0,
            adjustments_json="[]",
            status="active",
            version=next_version,
        )
        macro.version = next_version
        self.db.add(model)
        await self.db.flush()
        return macro

    async def get_macro_design(
        self, book_id: str, user_id: str = "anonymous"
    ) -> Optional[MacroDesignSchema]:
        """获取当前 active 的宏观设计"""
        model = await self._load_active_design(book_id, user_id)
        if not model or not model.macro_design_json:
            return None
        return MacroDesignSchema.model_validate_json(model.macro_design_json)

    # ========== Micro ==========

    async def generate_micro_plan(
        self, design_id: str, module_index: int, user_id: str = "anonymous"
    ) -> MicroPlanSchema:
        """生成模块微观编排。幂等：同 design+module 已有 pending/active 直接返回。"""
        existing = await self._load_micro_plan(design_id, module_index)
        if existing and existing.module_status in ("pending", "active"):
            return existing

        design = await self._load_design_by_id(design_id, user_id)
        if not design:
            raise ServiceError(ErrorCode.NOT_FOUND, "教学设计不存在")
        if design.status not in ("active", "completed"):
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "教学设计非活跃状态")

        macro = MacroDesignSchema.model_validate_json(design.macro_design_json)
        if module_index < 0 or module_index >= len(macro.modules):
            raise ServiceError(ErrorCode.VALIDATION_ERROR, f"模块索引 {module_index} 越界")

        module_skel = macro.modules[module_index]
        briefs = await self.kg.get_unit_briefs(design.book_id, user_id)
        brief_map = {b.unit_id: b for b in briefs}
        module_briefs = [brief_map[u] for u in module_skel.unit_ids if u in brief_map]

        # 优先 LLM 微观编排，失败回退规则化
        llm_result = None
        try:
            llm_result = await self._micro_with_llm(
                module_skel, module_briefs, module_index, design
            )
        except Exception:
            llm_result = None

        if llm_result is not None:
            ordered, annotations, intro = llm_result
        else:
            ordered, annotations = await self._micro_arrange(
                module_briefs, design.book_id, module_index
            )
            intro = self._module_intro(module_skel, module_briefs)

        # 构造 annotation（被 defer 到后续模块的单元从 ordered 中剔除）
        defer_set = {a.unit_id for a in annotations if a.defer_to_module is not None}
        ordered = [u for u in ordered if u not in defer_set]

        schema = MicroPlanSchema(
            design_id=design_id,
            module_index=module_index,
            module_title=module_skel.title,
            ordered_unit_ids=ordered,
            unit_annotations=annotations,
            module_intro=intro,
            module_status="pending",
        )

        if existing:
            # 已完成/skipped 不覆盖；理论上前面已拦截，此处兜底
            existing.module_title = schema.module_title
            existing.ordered_unit_ids_json = json.dumps(ordered)
            existing.unit_annotations_json = json.dumps(
                [a.model_dump() for a in annotations], ensure_ascii=False
            )
            existing.module_intro = intro
            existing.module_status = "pending"
            existing.updated_at = datetime.now(timezone.utc)
        else:
            self.db.add(ModuleMicroPlanModel(
                id=schema.id,
                design_id=design_id,
                book_id=design.book_id,
                user_id=user_id,
                module_index=module_index,
                module_title=schema.module_title,
                ordered_unit_ids_json=json.dumps(ordered),
                unit_annotations_json=json.dumps(
                    [a.model_dump() for a in annotations], ensure_ascii=False
                ),
                module_intro=intro,
                module_status="pending",
                parent_design_version=design.version,
            ))
            design.generated_module_count = max(design.generated_module_count, module_index + 1)
        await self.db.flush()

        # M4：把 memorize/understand/skip 标注写回 KnowledgeUnitModel.ai_cognitive_hint
        # 供 teaching 的 select_teaching_strategy 读取以微调 pace。
        # 仅写本模块实际会教的单元（defer 到后续模块的不在此写）。
        await self._write_cognitive_hints(annotations)

        return schema

    async def get_micro_plan(
        self, design_id: str, module_index: int
    ) -> Optional[MicroPlanSchema]:
        return await self._load_micro_plan(design_id, module_index)

    async def get_active_module_ordered_unit_ids(
        self, book_id: str, user_id: str = "anonymous"
    ) -> list[str]:
        """teaching 集成唯一入口。

        返回当前模块的重排后 unit_ids（已剔除 defer/skip）。
        AID 未启用 / 无设计 / 当前模块未生成 → 返回 []，调用方回退章节序。
        当前模块 micro 未生成时自动生成。
        """
        design = await self._load_active_design(book_id, user_id)
        if not design:
            return []

        macro = MacroDesignSchema.model_validate_json(design.macro_design_json)
        if not macro.modules:
            return []
        idx = min(design.current_module_index, len(macro.modules) - 1)

        micro = await self._load_micro_plan(design.id, idx)
        if not micro:
            # 自动生成当前模块 micro
            try:
                micro = await self.generate_micro_plan(design.id, idx, user_id)
            except ServiceError:
                return []
        if micro.module_status == "done":
            # 当前模块已学完但未推进 → 返回空让 teaching 判定完成
            return []
        return list(micro.ordered_unit_ids)

    async def advance_to_next_module(
        self, book_id: str, user_id: str = "anonymous"
    ) -> Optional[int]:
        """推进到下一模块。返回新模块索引，已是最后则返回 None 且置 completed。"""
        design = await self._load_active_design(book_id, user_id)
        if not design:
            return None
        # 当前模块状态置 done（改 ORM，非 schema）
        await self._set_micro_status(design.id, design.current_module_index, "done")

        macro = MacroDesignSchema.model_validate_json(design.macro_design_json)
        if design.current_module_index + 1 < len(macro.modules):
            design.current_module_index += 1
            await self.db.flush()
            return design.current_module_index
        design.status = "completed"
        await self.db.flush()
        return None

    async def activate_module(
        self, book_id: str, user_id: str = "anonymous"
    ) -> Optional[int]:
        """激活当前模块（pending→active）。返回当前模块索引。"""
        design = await self._load_active_design(book_id, user_id)
        if not design:
            return None
        micro = await self._load_micro_plan(design.id, design.current_module_index)
        if micro and micro.module_status == "pending":
            await self._set_micro_status(design.id, design.current_module_index, "active")
        return design.current_module_index

    async def replan_next_module(
        self,
        book_id: str,
        feedback: "StageFeedback",
        user_id: str = "anonymous",
    ) -> "ReplanResult":
        """模块结束触发 replan：读 MasteryRecord + LLM 保守调整下一模块。

        保守原则：跳过需 mastery>=0.85；revisit<=2。
        LLM 不可用回退为"按 mastery 阈值的规则化"。
        """
        from app.modules.adaptive_design.schemas import ReplanResult as _RR

        design = await self._load_active_design(book_id, user_id)
        if not design:
            raise ServiceError(ErrorCode.NOT_FOUND, "教学设计不存在")
        macro = MacroDesignSchema.model_validate_json(design.macro_design_json)
        next_idx = design.current_module_index + 1
        if next_idx >= len(macro.modules):
            return _RR(next_module_index=design.current_module_index,
                       revisit_unit_ids=[], skip_unit_ids=[], rationale="已是最后模块")

        # 收集刚结束模块 + 下一模块的掌握度
        cur_mastery = await self._read_module_mastery(
            design.id, design.current_module_index, user_id
        )
        next_mastery = await self._read_module_mastery(design.id, next_idx, user_id)

        # LLM replan（保守），失败回退规则化
        result = None
        if self._llm_enabled():
            try:
                result = await self._replan_with_llm(
                    macro.modules[next_idx], feedback, cur_mastery, design
                )
            except Exception:
                result = None
        if result is None:
            result = self._replan_rulebased(
                macro.modules[next_idx], feedback, next_mastery
            )

        # 把 revisit 单元插到下一模块开头（落库到 micro 的 ordered_unit_ids）
        await self._inject_revisit_into_next_module(
            design.id, next_idx, result.revisit_unit_ids, result.skip_unit_ids
        )
        # 回写当前模块 summary
        await self._set_micro_summary(
            design.id, design.current_module_index,
            {"weak_points": feedback.weak_points, "user_feedback": feedback.user_feedback,
             "mastery": cur_mastery},
        )
        return result

    async def apply_user_adjustments(
        self,
        book_id: str,
        field: str,
        old_value: str,
        new_value: str,
        module_index: Optional[int] = None,
        reason: Optional[str] = None,
        user_id: str = "anonymous",
    ) -> "TeachingDesignSchema":
        """记录用户调整到 append-only 审计。拒绝改已完成模块。"""
        design = await self._load_active_design(book_id, user_id)
        if not design:
            raise ServiceError(ErrorCode.NOT_FOUND, "教学设计不存在")

        if module_index is not None:
            micro = await self._load_micro_plan(design.id, module_index)
            if micro and micro.module_status == "done":
                raise ServiceError(ErrorCode.VALIDATION_ERROR, "不能修改已完成模块")

        adj = UserAdjustment(
            module_index=module_index, field=field,
            old_value=old_value, new_value=new_value, reason=reason,
        )
        adjustments = json.loads(design.adjustments_json or "[]")
        adjustments.append(adj.model_dump(mode="json"))
        design.adjustments_json = json.dumps(adjustments, ensure_ascii=False)
        design.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return await self.get_design(book_id, user_id)

    async def _read_module_mastery(
        self, design_id: str, module_index: int, user_id: str
    ) -> dict:
        """读某模块所有单元的掌握度 {unit_id: 0..1}。

        用 macro 模块的 unit_ids（全量，含被 defer 的单元），
        而非 micro.ordered_unit_ids（已剔除 defer/skip）。
        """
        from app.db.models import MasteryRecordModel, TeachingDesignModel
        # 取 macro 该模块的全量 unit_ids
        d_result = await self.db.execute(
            select(TeachingDesignModel.macro_design_json).where(
                TeachingDesignModel.id == design_id
            )
        )
        macro_json = d_result.scalar_one_or_none()
        if not macro_json:
            return {}
        macro = MacroDesignSchema.model_validate_json(macro_json)
        if module_index < 0 or module_index >= len(macro.modules):
            return {}
        unit_ids = macro.modules[module_index].unit_ids
        if not unit_ids:
            return {}
        result = await self.db.execute(
            select(MasteryRecordModel.knowledge_unit_id, MasteryRecordModel.mastery_score).where(
                MasteryRecordModel.user_id == user_id,
                MasteryRecordModel.knowledge_unit_id.in_(unit_ids),
            )
        )
        return {uid: float(s) for uid, s in result.all() if s is not None}

    async def _replan_with_llm(
        self, next_skel: ModuleSkeleton, feedback, mastery_map: dict, design,
    ):
        from app.modules.adaptive_design.schemas import ReplanResult as _RR
        prompt = REPLAN_PROMPT.format(
            weak_points=", ".join(feedback.weak_points[:5]) or "无",
            user_feedback=(feedback.user_feedback or "无")[:200],
            time_spent=feedback.time_spent_minutes or "未知",
            next_module_skeleton=f"{next_skel.title}: {next_skel.unit_ids}",
            goal_depth="",  # 可从 design.profile 取，简化
        )
        resp = await self.llm.chat_json(
            messages=[LLMMessage(role="user", content=prompt)], temperature=0.2,
        )
        data = parse_llm_json(resp)
        revisit = [u for u in data.get("revisit_unit_ids", []) if u][:2]  # 上限2
        skip = [u for u in data.get("skip_unit_ids", []) if u in next_skel.unit_ids]
        return _RR(
            next_module_index=next_skel.index,
            revisit_unit_ids=revisit, skip_unit_ids=skip,
            rationale=data.get("rationale", ""),
        )

    def _replan_rulebased(self, next_skel, feedback, mastery_map: dict):
        """规则化 replan：按 mastery 阈值跳过，无 revisit（保守）"""
        from app.modules.adaptive_design.schemas import ReplanResult as _RR
        # 下一模块中前置已被高分掌握的单元可跳过（阈值 0.85）
        skip = [u for u, m in mastery_map.items() if m >= 0.85 and u in next_skel.unit_ids]
        return _RR(
            next_module_index=next_skel.index,
            revisit_unit_ids=[], skip_unit_ids=skip[:2],
            rationale="规则化：跳过已高分掌握单元",
        )

    async def _inject_revisit_into_next_module(
        self, design_id: str, next_idx: int,
        revisit_ids: list, skip_ids: list,
    ):
        """把 revisit 单元插到下一模块开头，剔除 skip 单元"""
        # 下一模块可能还没生成 micro；若没生成，revisit/skip 等生成时再处理（简化：仅当已存在时调整）
        from app.db.models import ModuleMicroPlanModel
        result = await self.db.execute(
            select(ModuleMicroPlanModel).where(
                ModuleMicroPlanModel.design_id == design_id,
                ModuleMicroPlanModel.module_index == next_idx,
            )
        )
        m = result.scalar_one_or_none()
        if not m:
            return  # 未生成，replan 结果仅作记录，生成 micro 时由调用方决定是否应用
        ordered = json.loads(m.ordered_unit_ids_json or "[]")
        # 剔除 skip
        ordered = [u for u in ordered if u not in skip_ids]
        # 插入 revisit 到开头（去重）
        for r in reversed(revisit_ids):
            if r not in ordered:
                ordered.insert(0, r)
        m.ordered_unit_ids_json = json.dumps(ordered)
        m.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def _set_micro_status(self, design_id: str, module_index: int, status: str):
        from app.db.models import ModuleMicroPlanModel
        result = await self.db.execute(
            select(ModuleMicroPlanModel).where(
                ModuleMicroPlanModel.design_id == design_id,
                ModuleMicroPlanModel.module_index == module_index,
            )
        )
        m = result.scalar_one_or_none()
        if m:
            m.module_status = status
            m.updated_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def _set_micro_summary(self, design_id: str, module_index: int, summary: dict):
        from app.db.models import ModuleMicroPlanModel
        result = await self.db.execute(
            select(ModuleMicroPlanModel).where(
                ModuleMicroPlanModel.design_id == design_id,
                ModuleMicroPlanModel.module_index == module_index,
            )
        )
        m = result.scalar_one_or_none()
        if m:
            m.module_summary_json = json.dumps(summary, ensure_ascii=False)
            m.updated_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def _write_cognitive_hints(self, annotations: list):
        """把 memorize/understand/skip_if_mastered 标注写回 KnowledgeUnitModel。

        defer 到后续模块的单元不写（等目标模块生成时再写）。
        teaching 的 select_teaching_strategy 读 ai_cognitive_hint 微调教学策略。
        """
        from sqlalchemy import update
        for a in annotations:
            if a.defer_to_module is not None:
                continue
            await self.db.execute(
                update(KnowledgeUnitModel)
                .where(KnowledgeUnitModel.id == a.unit_id)
                .values(ai_cognitive_hint=a.cognitive_mode)
            )
        await self.db.flush()

    async def get_design(
        self, book_id: str, user_id: str = "anonymous"
    ) -> Optional[TeachingDesignSchema]:
        design = await self._load_active_design(book_id, user_id)
        if not design:
            return None
        macro = (
            MacroDesignSchema.model_validate_json(design.macro_design_json)
            if design.macro_design_json
            else None
        )
        adjustments = [
            UserAdjustment.model_validate(a)
            for a in json.loads(design.adjustments_json or "[]")
        ]
        return TeachingDesignSchema(
            id=design.id,
            user_id=design.user_id,
            book_id=design.book_id,
            profile_id=design.profile_id,
            macro_design=macro,
            current_module_index=design.current_module_index,
            generated_module_count=design.generated_module_count,
            adjustments=adjustments,
            status=design.status,
            version=design.version,
            created_at=design.created_at,
            updated_at=design.updated_at,
        )

    def _llm_enabled(self) -> bool:
        """LLM 是否可用（配置了 api_key）。空 key 时直接走规则化，避免无谓超时。"""
        return bool(self.llm) and bool(getattr(self.llm, "api_key", ""))

    # ========== Macro 规则化聚类策略 ==========

    async def _macro_with_llm(
        self, briefs: list[UnitBrief], profile: LearnerIntentProfileSchema
    ) -> Optional[list[ModuleSkeleton]]:
        """LLM 跨章节聚类成 Module。失败返回 None 由调用方回退。"""
        if not self._llm_enabled():
            return None
        units_brief = "\n".join(
            f"- {b.unit_id} [章节={b.chapter_id} 难度={b.difficulty_level} 重要性={b.importance_score:.2f}] "
            f"{b.title} | 概念: {', '.join(b.concepts[:5])} | 前置: {', '.join(b.prerequisites[:3])}"
            for b in briefs
        )
        # 概念共现摘要（跨章节同现的概念）
        concept_units: dict[str, list[str]] = {}
        unit_chapter = {b.unit_id: b.chapter_id for b in briefs}
        for b in briefs:
            for c in b.concepts:
                concept_units.setdefault(c, []).append(b.unit_id)
        cross = []
        for c, uids in concept_units.items():
            if len(uids) > 1:
                chs = {unit_chapter.get(u, "?") for u in uids}
                cross.append(f"「{c}」: {', '.join(uids)} (跨{len(chs)}章)")
            if len(cross) >= 15:
                break
        concept_relations = "\n".join(cross) or "无明显跨章节共现概念"

        tolerance_rule = {
            "keep_book_order": "尽量保留书的章节顺序，仅在概念高度同构时合并相邻章节",
            "moderate": "适度跨章节重组，同构/对比概念可跨章归组",
            "aggressive": "大胆跨章节重组，以概念关联为主、章节为辅",
        }[profile.restructure_tolerance]

        prompt = MACRO_DESIGN_PROMPT.format(
            identity_background=profile.identity_background,
            goal_depth=profile.goal_depth,
            cognitive_pref=profile.cognitive_pref,
            restructure_tolerance=profile.restructure_tolerance,
            global_strategy=self._global_strategy(profile),
            units_brief=units_brief,
            concept_relations=concept_relations,
            adjustments_summary="无",  # M3 接入审计
            restructure_rule=tolerance_rule,
            restructure_rule_detail="",
        )
        resp = await self.llm.chat_json(
            messages=[LLMMessage(role="user", content=prompt)], temperature=0.3,
        )
        data = parse_llm_json(resp)
        raw_modules = data.get("modules", [])
        if not raw_modules:
            return None

        valid_unit_ids = {b.unit_id for b in briefs}
        modules: list[ModuleSkeleton] = []
        for i, m in enumerate(raw_modules):
            uids = [u for u in m.get("unit_ids", []) if u in valid_unit_ids]
            if not uids:
                continue
            modules.append(ModuleSkeleton(
                index=i,
                title=m.get("title", f"模块{i + 1}"),
                unit_ids=uids,
                concept_ids=m.get("concept_ids", [])[:10],
                strategy_tags=m.get("strategy_tags", [])[:5],
                rationale=m.get("rationale", ""),
            ))
        # 覆盖率校验：所有单元都应被分到某模块；遗漏则补一个尾巴模块
        covered = {u for m in modules for u in m.unit_ids}
        missing = [b.unit_id for b in briefs if b.unit_id not in covered]
        if missing:
            modules.append(ModuleSkeleton(
                index=len(modules), title=f"模块{len(modules) + 1}",
                unit_ids=missing, strategy_tags=[self._default_module_tag(profile)],
                rationale="LLM 未覆盖的剩余单元",
            ))
        # 重排 index 连续
        for i, m in enumerate(modules):
            m.index = i
        return modules if modules else None

    def _validate_macro_topology(
        self, modules: list[ModuleSkeleton], briefs: list[UnitBrief]
    ) -> bool:
        """校验模块间无反向依赖：模块 i 的单元不能依赖模块 j (j>i) 的单元。"""
        unit_to_module: dict[str, int] = {}
        for m in modules:
            for u in m.unit_ids:
                unit_to_module[u] = m.index
        unit_id_set = {b.unit_id for b in briefs}
        for b in briefs:
            mi = unit_to_module.get(b.unit_id)
            if mi is None:
                continue
            for pre in b.prerequisites:
                # prerequisites 可能是 unit_id 或概念名，只校验 unit_id 形式
                if pre in unit_id_set and pre in unit_to_module:
                    if unit_to_module[pre] > mi:
                        return False  # 反向依赖
        return True

    async def _micro_with_llm(
        self, skel: ModuleSkeleton, briefs: list[UnitBrief],
        module_index: int, design,
    ) -> Optional[tuple[list[str], list[UnitRetrofitAnnotation], str]]:
        """LLM 微观编排。返回 (ordered, annotations, intro) 或 None。"""
        if not self._llm_enabled():
            return None
        units_detail = "\n".join(
            f"- {b.unit_id} [难度={b.difficulty_level} 重要性={b.importance_score:.2f}] "
            f"{b.title} | 概念: {', '.join(b.concepts[:5])} | 前置: {', '.join(b.prerequisites[:3])} | "
            f"摘要: {b.summary[:80]}"
            for b in briefs
        )
        # 上一模块反馈摘要（M3 完善，此处取现有 summary）
        prev_summary = "无（首模块或无反馈）"

        prompt = MICRO_PLAN_PROMPT.format(
            identity_background="",  # 可从 design 取，此处简化
            goal_depth="",
            cognitive_pref="",
            module_title=skel.title,
            module_strategy=",".join(skel.strategy_tags),
            units_detail=units_detail,
            prev_summary=prev_summary,
            adjustments_summary="无",
        )
        resp = await self.llm.chat_json(
            messages=[LLMMessage(role="user", content=prompt)], temperature=0.4,
        )
        data = parse_llm_json(resp)
        ordered = data.get("ordered_unit_ids", [])
        anns_raw = data.get("unit_annotations", [])
        intro = data.get("module_intro", "")

        valid = {b.unit_id for b in briefs}
        ordered = [u for u in ordered if u in valid]
        # 补齐 LLM 遗漏的（非 defer）单元
        ann_map = {a.get("unit_id"): a for a in anns_raw if a.get("unit_id") in valid}
        deferred = {a.get("unit_id") for a in anns_raw if a.get("defer_to_module") is not None}
        for b in briefs:
            if b.unit_id not in ordered and b.unit_id not in deferred:
                ordered.append(b.unit_id)

        annotations: list[UnitRetrofitAnnotation] = []
        for b in briefs:
            a = ann_map.get(b.unit_id, {})
            mode = a.get("cognitive_mode", "understand")
            if mode not in ("memorize", "understand", "skip_if_mastered"):
                mode = self._decide_cognitive_mode(b)
            annotations.append(UnitRetrofitAnnotation(
                unit_id=b.unit_id,
                cognitive_mode=mode,
                merge_group=a.get("merge_group"),
                defer_to_module=a.get("defer_to_module"),
                emphasis=a.get("emphasis"),
                note=a.get("note"),
            ))
        if not ordered:
            return None
        return ordered, annotations, (intro or self._module_intro(skel, briefs))

    def _macro_by_chapter(
        self, briefs: list[UnitBrief], profile: LearnerIntentProfileSchema
    ) -> list[ModuleSkeleton]:
        """按章节分组（keep_book_order）：每章一个模块，保留书结构。"""
        chapters: dict[str, list[UnitBrief]] = {}
        for b in briefs:
            chapters.setdefault(b.chapter_id or "_no_chapter", []).append(b)
        modules: list[ModuleSkeleton] = []
        for i, (_, items) in enumerate(
            sorted(chapters.items(), key=lambda kv: kv[1][0].order_index)
        ):
            modules.append(ModuleSkeleton(
                index=i,
                title=f"模块{i + 1}",
                unit_ids=[b.unit_id for b in items],
                concept_ids=sorted({c for b in items for c in b.concepts}),
                strategy_tags=["deep_dive"] if profile.goal_depth == "exam_memorize" else ["rapid_survey"],
                rationale="按书章节顺序组织，保留原书叙事结构",
            ))
        return modules

    def _macro_by_concept_clusters(
        self,
        briefs: list[UnitBrief],
        profile: LearnerIntentProfileSchema,
        aggressive: bool,
    ) -> list[ModuleSkeleton]:
        """基于概念共现跨章节聚类（moderate/aggressive）。

        策略：用并查集把共享概念的单元聚成一组；无共享概念的单元各自成组
        或与相邻组合并。aggressive 更倾向合并（更少模块）。
        """
        # 概念 → 单元集合
        concept_units: dict[str, set[str]] = {}
        for b in briefs:
            for c in b.concepts:
                concept_units.setdefault(c, set()).add(b.unit_id)

        # 只在共现 >= min_cooccurrence 时认为单元同组
        min_co = 1 if aggressive else 2
        parent = {b.unit_id: b.unit_id for b in briefs}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b_):
            ra, rb = find(a), find(b_)
            if ra != rb:
                parent[ra] = rb

        for u_ids in concept_units.values():
            if len(u_ids) >= min_co:
                u_list = list(u_ids)
                for i in range(1, len(u_list)):
                    union(u_list[0], u_list[i])

        groups: dict[str, list[UnitBrief]] = {}
        for b in briefs:
            root = find(b.unit_id)
            groups.setdefault(root, []).append(b)

        # aggressive：再多一轮按概念相邻合并小模块（合并到 4-7 模块目标）
        modules: list[ModuleSkeleton] = []
        sorted_groups = sorted(
            groups.values(),
            key=lambda g: min(b.order_index for b in g),
        )
        for i, items in enumerate(sorted_groups):
            concepts = sorted({c for b in items for c in b.concepts})
            is_cross = len({b.chapter_id for b in items}) > 1
            tags = ["comparison_group"] if is_cross else (["deep_dive"] if profile.goal_depth == "exam_memorize" else ["concept_merge_overview"])
            modules.append(ModuleSkeleton(
                index=i,
                title=f"模块{i + 1}" + ("（跨章节）" if is_cross else ""),
                unit_ids=[b.unit_id for b in items],
                concept_ids=concepts,
                strategy_tags=tags,
                rationale="按概念关联跨章节聚合，强化对比学习" if is_cross else "按概念关联聚合",
            ))
        return modules

    def _global_strategy(self, profile: LearnerIntentProfileSchema) -> str:
        parts = {
            "exam_memorize": "应试导向：术语纳入考察，强化记忆与检索练习",
            "apply_understand": "应用导向：重在理解机制，适度记忆核心术语",
            "general_interest": "兴趣导向：生动讲解，重在建立直觉，弱化术语记忆",
        }
        cog = {
            "vivid_analogy": "讲解风格：生动类比优先",
            "rigorous_system": "讲解风格：严谨系统优先",
            "problem_driven": "讲解风格：问题驱动优先",
        }
        tol = {
            "keep_book_order": "组织方式：保留书结构按章走",
            "moderate": "组织方式：适度跨章节重组",
            "aggressive": "组织方式：大胆跨章节重组",
        }
        return "；".join([parts.get(profile.goal_depth, ""), cog.get(profile.cognitive_pref, ""), tol.get(profile.restructure_tolerance, "")])

    def _default_module_tag(self, profile: LearnerIntentProfileSchema) -> str:
        if profile.goal_depth == "exam_memorize":
            return "deep_dive"
        if profile.goal_depth == "general_interest":
            return "rapid_survey"
        return "concept_merge_overview"

    # ========== Micro 规则化编排 ==========

    async def _micro_arrange(
        self,
        briefs: list[UnitBrief],
        book_id: str,
        module_index: int,
    ) -> tuple[list[str], list[UnitRetrofitAnnotation]]:
        """模块内重排：拓扑序兜底 + 记忆/理解标注。

        难度高且模块索引>0 的概念可标 defer_to_module（推后），M3 接 LLM 后更智能。
        """
        # 取本模块单元的拓扑序
        layers = await self.kg.get_topological_layers(book_id)
        module_id_set = {b.unit_id for b in briefs}
        ordered: list[str] = []
        if layers:
            for layer in layers:
                for uid in layer:
                    if uid in module_id_set and uid not in ordered:
                        ordered.append(uid)
        # 未被拓扑覆盖的单元按书序补
        for b in briefs:
            if b.unit_id not in ordered:
                ordered.append(b.unit_id)

        annotations: list[UnitRetrofitAnnotation] = []
        for uid in ordered:
            b = next((x for x in briefs if x.unit_id == uid), None)
            if not b:
                continue
            mode = self._decide_cognitive_mode(b)
            ann = UnitRetrofitAnnotation(unit_id=uid, cognitive_mode=mode)
            # 简单 defer 规则：难度 >=5 且非首模块且非高重要性的单元，推后一模块（M3 增强）
            if module_index > 0 and b.difficulty_level >= 5 and b.importance_score < 0.8:
                ann.defer_to_module = module_index + 1
                ann.note = "难度高，规则化推后"
            annotations.append(ann)
        return ordered, annotations

    def _decide_cognitive_mode(self, b: UnitBrief) -> str:
        """规则化决定记忆/理解模式。

        事实/术语密度高（概念多摘要短）→ memorize；原理机制 → understand。
        已掌握的 → skip_if_mastered（replan 阶段会用到）。
        """
        if b.mastery_score is not None and b.mastery_score >= 0.85:
            return "skip_if_mastered"
        # 启发式：概念数 / 摘要长度 高 → 偏术语密集 → memorize
        if b.summary and len(b.concepts) / max(len(b.summary), 1) > 0.05:
            return "memorize"
        return "understand"

    def _module_intro(self, skel: ModuleSkeleton, briefs: list[UnitBrief]) -> str:
        """生成模块地图提示导言（规则化，M2 由 LLM 增强）"""
        chapters = sorted({b.chapter_id for b in briefs if b.chapter_id})
        ch_desc = f"对应书里共 {len(chapters)} 个章节内容" if chapters else "内容来自全书"
        titles = "、".join(b.title for b in briefs[:3])
        return f"本模块「{skel.title}」聚焦概念：{'、'.join(skel.concept_ids[:5]) or '相关知识点'}。{ch_desc}，包含：{titles} 等。建议{STRATEGY_TAGS.get(skel.strategy_tags[0], '学习') if skel.strategy_tags else '学习'}。"

    # ========== 模型读写辅助 ==========

    async def _load_profile(
        self, book_id: str, user_id: str
    ) -> Optional[LearnerIntentProfileSchema]:
        m = await self._load_profile_model(book_id, user_id)
        return self._profile_model_to_schema(m) if m else None

    async def _load_profile_model(
        self, book_id: str, user_id: str
    ) -> Optional[LearnerIntentProfileModel]:
        result = await self.db.execute(
            select(LearnerIntentProfileModel).where(
                LearnerIntentProfileModel.book_id == book_id,
                LearnerIntentProfileModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _profile_model_to_schema(m: LearnerIntentProfileModel) -> LearnerIntentProfileSchema:
        return LearnerIntentProfileSchema(
            id=m.id,
            user_id=m.user_id,
            book_id=m.book_id,
            identity_background=m.identity_background,
            goal_depth=m.goal_depth,
            cognitive_pref=m.cognitive_pref,
            restructure_tolerance=m.restructure_tolerance,
            time_budget_minutes=m.time_budget_minutes,
            source=m.source,
            status=m.status,
            extra_json=m.extra_json or "{}",
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    async def _load_active_design(
        self, book_id: str, user_id: str
    ) -> Optional[TeachingDesignModel]:
        result = await self.db.execute(
            select(TeachingDesignModel).where(
                TeachingDesignModel.book_id == book_id,
                TeachingDesignModel.user_id == user_id,
                TeachingDesignModel.status.in_(["active", "completed"]),
            ).order_by(TeachingDesignModel.version.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def _load_design_by_id(
        self, design_id: str, user_id: str
    ) -> Optional[TeachingDesignModel]:
        result = await self.db.execute(
            select(TeachingDesignModel).where(
                TeachingDesignModel.id == design_id,
                TeachingDesignModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _load_micro_plan(
        self, design_id: str, module_index: int
    ) -> Optional[MicroPlanSchema]:
        result = await self.db.execute(
            select(ModuleMicroPlanModel).where(
                ModuleMicroPlanModel.design_id == design_id,
                ModuleMicroPlanModel.module_index == module_index,
            )
        )
        m = result.scalar_one_or_none()
        if not m:
            return None
        return MicroPlanSchema(
            id=m.id,
            design_id=m.design_id,
            module_index=m.module_index,
            module_title=m.module_title,
            ordered_unit_ids=json.loads(m.ordered_unit_ids_json or "[]"),
            unit_annotations=[
                UnitRetrofitAnnotation.model_validate(a)
                for a in json.loads(m.unit_annotations_json or "[]")
            ],
            module_intro=m.module_intro,
            module_status=m.module_status,
            module_summary_json=m.module_summary_json,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    async def _supersede_old_designs(self, book_id: str, user_id: str) -> int:
        """将旧 active 设计置 superseded（保留审计，不删），返回下一个可用 version"""
        result = await self.db.execute(
            select(TeachingDesignModel).where(
                TeachingDesignModel.book_id == book_id,
                TeachingDesignModel.user_id == user_id,
            )
        )
        all_rows = result.scalars().all()
        max_version = 0
        for d in all_rows:
            if d.status == "active":
                d.status = "superseded"
            if d.version and d.version > max_version:
                max_version = d.version
        return max_version + 1
