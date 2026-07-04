"""教学服务 - DB持久化版

集成教学计划系统，确保知识覆盖完整性
"""

import json
from uuid import uuid4
from typing import List, Optional, Dict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ServiceError, ErrorCode
from app.common.llm_client import LLMClient, LLMMessage
from app.db.models import (
    TeachingSessionModel, TeachingMessageModel,
    UserQuestionModel, SessionTestModel, LearningEfficiencyModel,
)
from app.modules.ai_learning.schemas import LearnedUnit, TestQuestion
from app.modules.teaching.schemas import (
    TeachingSession, TeachingPhase, TeachingMessage,
    UserQuestion, Annotation, SessionTest, TeachingStrategy,
    SessionSummary, UserTeachingProfile, CornellNote,
)
from app.modules.teaching.prompts import (
    INTENT_PROMPT, EXPLAIN_PROMPT, ANSWER_PROMPT,
    ACTIVATE_PROMPT, CHECK_PROMPT, REFLECT_PROMPT, GRADE_PROMPT,
    MATCHING_PROMPT, ORDERING_PROMPT, TRUE_FALSE_PROMPT,
    ASSESS_PROMPT, SUMMARY_PROMPT,
    FEYNMAN_EXPLAIN_PROMPT, FEYNMAN_ASSESS_PROMPT,
    CORNELL_CUES_PROMPT, CORNELL_SUMMARY_PROMPT,
    EXAMPLE_PROMPT,
)
from app.modules.teaching.strategies import select_teaching_strategy
from app.modules.teaching.teaching_plan import (
    TeachingPlan, TeachingPlanGenerator, CoverageTracker,
    plan_generator, coverage_tracker,
)


class TeachingService:
    """教学服务（会话和消息持久化到数据库）

    集成教学计划系统，确保知识覆盖完整性
    """

    def __init__(self, llm_client: LLMClient, db: AsyncSession):
        self.llm = llm_client
        self.db = db
        # 教学计划存储 (session_id -> TeachingPlan)
        self._teaching_plans: Dict[str, TeachingPlan] = {}

    async def start_session(
        self,
        user_id: str,
        plan_session_id: str,
        book_id: str,
        unit_ids: List[str],
        units: List[LearnedUnit],
        user_profile: Optional[UserTeachingProfile] = None,
    ) -> TeachingSession:
        """开始教学会话"""
        from app.modules.teaching.strategies import select_phases

        strategy = select_teaching_strategy(units[0], user_profile) if units else TeachingStrategy()

        # 根据内容复杂度选择教学阶段
        if units:
            mastery = user_profile.avg_mastery_score if user_profile else 0.5
            strategy.phases = select_phases(units[0], mastery)

        session = TeachingSession(
            user_id=user_id,
            plan_session_id=plan_session_id,
            book_id=book_id,
            unit_ids=unit_ids,
            strategy=strategy,
        )

        self.db.add(TeachingSessionModel(
            id=session.id,
            user_id=user_id,
            plan_session_id=plan_session_id,
            book_id=book_id,
            unit_ids=json.dumps(unit_ids),
            current_phase=session.current_phase.value,
            strategy_json=json.dumps(strategy.model_dump()),
            status="active",
        ))
        await self.db.flush()

        # 为每个单元生成教学计划
        for unit in units:
            plan = plan_generator.generate_plan(unit, book_id)
            self._teaching_plans[f"{session.id}_{unit.unit_id}"] = plan
            # 初始化覆盖追踪器
            coverage_tracker.initialize(plan)

        return session

    async def get_active_session(self, user_id: str, book_id: str) -> Optional[TeachingSession]:
        """获取某本书的活跃教学会话"""
        result = await self.db.execute(
            select(TeachingSessionModel).where(
                TeachingSessionModel.user_id == user_id,
                TeachingSessionModel.book_id == book_id,
                TeachingSessionModel.status == "active",
            ).order_by(TeachingSessionModel.started_at.desc()).limit(1)
        )
        db_session = result.scalars().first()
        if not db_session:
            return None
        strategy_data = json.loads(db_session.strategy_json) if db_session.strategy_json else {}
        return TeachingSession(
            id=db_session.id,
            user_id=db_session.user_id,
            plan_session_id=db_session.plan_session_id or "",
            book_id=db_session.book_id,
            unit_ids=json.loads(db_session.unit_ids) if db_session.unit_ids else [],
            current_unit_index=db_session.current_unit_index or 0,
            current_phase=TeachingPhase(db_session.current_phase),
            started_at=db_session.started_at,
            ended_at=db_session.ended_at,
            status=db_session.status,
            strategy=TeachingStrategy(**strategy_data),
        )

    async def get_next_message(
        self,
        session_id: str,
        units: List[LearnedUnit],
    ) -> TeachingMessage:
        """获取下一条教学消息（幂等：同一单元同一阶段已有消息则直接返回）

        集成教学计划系统：
        1. 检查教学计划的覆盖情况
        2. 追踪生成内容的覆盖情况
        3. 确保严格模式下 100% 覆盖
        """
        session = await self._get_session(session_id)

        if session.current_unit_index >= len(session.unit_ids):
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "所有单元已学完")

        current_unit_id = session.unit_ids[session.current_unit_index]
        phase = TeachingPhase(session.current_phase)
        is_interactive = phase in (TeachingPhase.CHECK, TeachingPhase.REFLECT, TeachingPhase.RETRIEVAL, TeachingPhase.FEYNMAN)

        # 幂等性检查：同一单元+同一阶段已有消息则直接返回
        existing = await self.db.execute(
            select(TeachingMessageModel).where(
                TeachingMessageModel.session_id == session_id,
                TeachingMessageModel.unit_id == current_unit_id,
                TeachingMessageModel.phase == phase.value,
            )
        )
        if existing_msg := existing.scalar_one_or_none():
            # 所有阶段均不自动推进，用户通过 /continue 手动推进
            return TeachingMessage(
                id=existing_msg.id,
                session_id=existing_msg.session_id,
                unit_id=existing_msg.unit_id,
                phase=TeachingPhase(existing_msg.phase),
                content=existing_msg.content,
                requires_answer=is_interactive,
                next_phase=None,
            )

        current_unit = next((u for u in units if u.unit_id == current_unit_id), None)
        if not current_unit:
            raise ServiceError(ErrorCode.NOT_FOUND, f"知识单元 {current_unit_id} 不存在")

        # 获取教学计划
        plan_key = f"{session_id}_{current_unit_id}"
        teaching_plan = self._teaching_plans.get(plan_key)

        # 根据教学计划调整生成策略
        if teaching_plan and phase == TeachingPhase.CORE:
            # 核心讲解阶段：确保覆盖所有未覆盖的内容
            content = await self._generate_core_with_coverage(current_unit, session.strategy, teaching_plan)
        elif phase == TeachingPhase.ACTIVATE:
            content = await self._generate_activate(current_unit, session.strategy)
        elif phase == TeachingPhase.INTRO:
            content = await self._generate_intro(current_unit, session.strategy)
        elif phase == TeachingPhase.CORE:
            content = await self._generate_core(current_unit, session.strategy)
        elif phase == TeachingPhase.EXAMPLE:
            content = await self._generate_example(current_unit, session.strategy)
        elif phase == TeachingPhase.FEYNMAN:
            content = await self._generate_feynman(current_unit)
        elif phase == TeachingPhase.RETRIEVAL:
            content = await self._generate_retrieval(current_unit, units)
        elif phase == TeachingPhase.CHECK:
            content = await self._generate_check(current_unit)
        elif phase == TeachingPhase.REFLECT:
            content = await self._generate_reflect(current_unit, session.strategy)
        elif phase == TeachingPhase.CONNECT:
            content = await self._generate_connect(current_unit, session_id)
        else:
            content = await self._generate_core(current_unit, session.strategy)

        # 追踪覆盖情况
        if teaching_plan:
            coverage_tracker.track_message(teaching_plan, content, phase.value)

        msg_id = str(uuid4())
        self.db.add(TeachingMessageModel(
            id=msg_id,
            session_id=session_id,
            unit_id=current_unit_id,
            phase=phase.value,
            content=content,
            content_type="text",
        ))

        # 单元学完（CONNECT 阶段），检查覆盖率并更新掌握度
        if phase == TeachingPhase.CONNECT:
            # 检查覆盖率
            if teaching_plan:
                coverage_report = coverage_tracker.get_coverage_report(teaching_plan)
                if not coverage_report["is_complete"]:
                    # 严格模式：覆盖率不足，需要补充教学
                    missing_items = coverage_report["missing_items"]
                    if missing_items:
                        # 生成补充教学内容
                        supplement_content = await self._generate_supplement(current_unit, missing_items)
                        supplement_msg_id = str(uuid4())
                        self.db.add(TeachingMessageModel(
                            id=supplement_msg_id,
                            session_id=session_id,
                            unit_id=current_unit_id,
                            phase="supplement",
                            content=supplement_content,
                            content_type="text",
                        ))
                        # 追踪补充内容的覆盖
                        coverage_tracker.track_message(teaching_plan, supplement_content, "supplement")

            # 更新掌握度
            await self._update_mastery_on_unit_complete(current_unit_id, session.book_id, session_id)

        # 所有阶段均不自动推进，用户通过 /continue 手动推进
        db_session = await self._get_db_session(session_id)
        if db_session:
            db_session.current_unit_index = session.current_unit_index
            db_session.current_phase = session.current_phase.value

        await self.db.flush()

        return TeachingMessage(
            id=msg_id,
            session_id=session_id,
            unit_id=current_unit_id,
            phase=phase,
            content=content,
            requires_answer=is_interactive,
            next_phase=None,  # 不自动推进，用户通过 /continue 手动推进
        )

    async def answer_question(
        self,
        session_id: str,
        question: str,
        units: List[LearnedUnit],
    ) -> UserQuestion:
        """回答用户问题"""
        session = await self._get_session(session_id)

        if session.current_unit_index >= len(session.unit_ids):
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "所有单元已学完")

        current_unit_id = session.unit_ids[session.current_unit_index]
        current_unit = next((u for u in units if u.unit_id == current_unit_id), None)

        intent = await self._classify_intent(question, current_unit)
        answer, follow_ups = await self._generate_answer(question, intent, current_unit)

        user_question = UserQuestion(
            session_id=session_id,
            question=question,
            answer=answer,
            intent=intent,
            follow_up_questions=follow_ups,
        )

        self.db.add(UserQuestionModel(
            id=user_question.id,
            session_id=session_id,
            question=question,
            answer=answer,
            intent=intent,
            follow_up_json=json.dumps(follow_ups),
        ))
        await self.db.flush()

        return user_question

    async def submit_answer(
        self,
        session_id: str,
        answer: str,
        units: List[LearnedUnit],
    ) -> TeachingMessage:
        """学生提交回答，AI 评估掌握程度并决定是否推进"""
        session = await self._get_session(session_id)
        phase = TeachingPhase(session.current_phase)

        if phase not in (TeachingPhase.CHECK, TeachingPhase.REFLECT, TeachingPhase.RETRIEVAL, TeachingPhase.FEYNMAN):
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "当前阶段不需要回答")

        current_unit_id = session.unit_ids[session.current_unit_index]
        current_unit = next((u for u in units if u.unit_id == current_unit_id), None)
        if not current_unit:
            raise ServiceError(ErrorCode.NOT_FOUND, f"知识单元 {current_unit_id} 不存在")

        # 找到当前阶段的 AI 问题
        result = await self.db.execute(
            select(TeachingMessageModel).where(
                TeachingMessageModel.session_id == session_id,
                TeachingMessageModel.unit_id == current_unit_id,
                TeachingMessageModel.phase == phase.value,
            ).order_by(TeachingMessageModel.created_at.desc()).limit(1)
        )
        ai_message = result.scalars().first()
        question_text = ai_message.content if ai_message else "请总结刚才学习的内容"

        # LLM 评估学生回答
        if phase == TeachingPhase.FEYNMAN:
            assessment = await self._assess_feynman_explanation(current_unit, answer)
        else:
            prompt = ASSESS_PROMPT.format(
                topic=current_unit.summary[:200],
                question=question_text,
                student_answer=answer,
            )
            try:
                response = await self.llm.chat_json(
                    messages=[LLMMessage(role="user", content=prompt)],
                    temperature=0.1,
                )
                assessment = response if isinstance(response, dict) else json.loads(response)
            except Exception:
                assessment = {
                    "score": 50, "mastery_level": "partial",
                    "feedback": "无法评估，请继续学习",
                    "should_advance": True, "suggestion": "继续下一阶段",
                }

        score = assessment.get("score", 50)
        should_advance = assessment.get("should_advance", score >= 60)

        # 保存学生的回答消息
        answer_msg_id = str(uuid4())
        self.db.add(TeachingMessageModel(
            id=answer_msg_id,
            session_id=session_id,
            unit_id=current_unit_id,
            phase=phase.value,
            content=answer,
            content_type="text",
        ))

        # 保存 AI 评估消息
        eval_msg_id = str(uuid4())
        feedback_text = assessment.get("feedback", "")
        suggestion = assessment.get("suggestion", "")
        eval_content = f"**评估结果**：{feedback_text}"

        # 费曼评估：补充覆盖/遗漏要点
        if phase == TeachingPhase.FEYNMAN:
            covered = assessment.get("covered_points", [])
            missed = assessment.get("missed_points", [])
            if covered:
                eval_content += "\n\n**你提到了**：" + "、".join(covered)
            if missed:
                eval_content += "\n\n**遗漏了**：" + "、".join(missed)

        if suggestion:
            eval_content += f"\n\n**建议**：{suggestion}"

        self.db.add(TeachingMessageModel(
            id=eval_msg_id,
            session_id=session_id,
            unit_id=current_unit_id,
            phase=phase.value,
            content=eval_content,
            content_type="text",
            assessment_json=json.dumps(assessment, ensure_ascii=False),
        ))

        db_session = await self._get_db_session(session_id)
        if db_session:
            db_session.current_unit_index = session.current_unit_index
            db_session.current_phase = session.current_phase.value
        await self.db.flush()

        return TeachingMessage(
            id=eval_msg_id,
            session_id=session_id,
            unit_id=current_unit_id,
            phase=phase,
            content=eval_content,
            assessment=assessment,
            next_phase=None,  # 不自动推进，用户手动继续
        )

    async def continue_to_next_phase(
        self,
        session_id: str,
    ) -> TeachingSession:
        """手动推进到下一阶段"""
        session = await self._get_session(session_id)
        self._advance_phase(session)

        db_session = await self._get_db_session(session_id)
        if db_session:
            db_session.current_unit_index = session.current_unit_index
            db_session.current_phase = session.current_phase.value
        await self.db.flush()
        return session

    async def jump_to_unit(
        self,
        session_id: str,
        unit_id: str,
    ) -> TeachingSession:
        """跳转到指定知识单元"""
        session = await self._get_session(session_id)

        if unit_id not in session.unit_ids:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, f"单元 {unit_id} 不在当前会话中")

        target_index = session.unit_ids.index(unit_id)
        session.current_unit_index = target_index
        session.current_phase = session.strategy.phases[0]

        db_session = await self._get_db_session(session_id)
        if db_session:
            db_session.current_unit_index = target_index
            db_session.current_phase = session.current_phase.value
        await self.db.flush()

        return session

    async def clear_messages(self, session_id: str) -> TeachingSession:
        """清空会话的所有消息，重置到当前单元的起始阶段"""
        from sqlalchemy import delete as sa_delete

        session = await self._get_session(session_id)

        # 删除该会话的所有教学消息和学生提问
        await self.db.execute(
            sa_delete(TeachingMessageModel).where(TeachingMessageModel.session_id == session_id)
        )
        await self.db.execute(
            sa_delete(UserQuestionModel).where(UserQuestionModel.session_id == session_id)
        )

        # 重置到当前单元的第一阶段
        session.current_phase = session.strategy.phases[0]
        db_session = await self._get_db_session(session_id)
        if db_session:
            db_session.current_phase = session.current_phase.value
        await self.db.flush()

        return session

    async def add_annotation(
        self,
        user_id: str,
        unit_id: str,
        annotation_type: str,
        content: Optional[str] = None,
        related_concepts: Optional[List[str]] = None,
        example: Optional[str] = None,
        cornell_cues: Optional[List[str]] = None,
        cornell_summary: Optional[str] = None,
    ) -> Annotation:
        """添加笔记或标记"""
        from app.db.models import AnnotationModel

        annotation = Annotation(
            user_id=user_id,
            knowledge_unit_id=unit_id,
            annotation_type=annotation_type,
            content=content,
            related_concepts=related_concepts or [],
            example=example,
            cornell_cues=cornell_cues or [],
            cornell_summary=cornell_summary,
        )

        self.db.add(AnnotationModel(
            id=annotation.id,
            user_id=user_id,
            knowledge_unit_id=unit_id,
            annotation_type=annotation_type,
            content=content or "",
            related_concepts_json=json.dumps(related_concepts or []),
            example=example,
            cornell_cues=json.dumps(cornell_cues or [], ensure_ascii=False),
            cornell_summary=cornell_summary,
        ))
        await self.db.flush()

        return annotation

    async def generate_cornell_cues(
        self, unit_id: str, notes_content: str,
    ) -> List[str]:
        """AI 根据笔记内容生成线索栏"""
        from app.db.models import KnowledgeUnitModel, AnnotationModel

        result = await self.db.execute(
            select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
        )
        unit = result.scalar_one_or_none()
        key_points_str = ""
        if unit and unit.key_points:
            kps = json.loads(unit.key_points)
            key_points_str = "\n".join(
                f"- {kp.get('title', str(kp))}" if isinstance(kp, dict) else f"- {kp}"
                for kp in kps
            )

        prompt = CORNELL_CUES_PROMPT.format(
            unit_title=unit.title if unit else "未知",
            notes_content=notes_content[:2000],
            key_points=key_points_str or "无",
        )
        try:
            response = await self.llm.chat_json(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.5,
            )
            cues = response.get("cues", []) if isinstance(response, dict) else []
        except Exception:
            cues = []

        # 查找或创建该单元的康奈尔笔记 annotation
        ann_result = await self.db.execute(
            select(AnnotationModel).where(
                AnnotationModel.knowledge_unit_id == unit_id,
                AnnotationModel.annotation_type == "cornell_note",
            ).order_by(AnnotationModel.created_at.desc())
        )
        annotation = ann_result.scalars().first()
        if annotation:
            annotation.cornell_cues = json.dumps(cues, ensure_ascii=False)
        else:
            self.db.add(AnnotationModel(
                id=str(__import__('uuid').uuid4()),
                user_id="anonymous",
                knowledge_unit_id=unit_id,
                annotation_type="cornell_note",
                content=notes_content[:2000],
                cornell_cues=json.dumps(cues, ensure_ascii=False),
            ))
        await self.db.flush()

        return cues

    async def generate_cornell_summary(
        self, unit_id: str, notes_content: str,
    ) -> str:
        """AI 根据笔记内容生成总结栏"""
        from app.db.models import KnowledgeUnitModel, AnnotationModel

        result = await self.db.execute(
            select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == unit_id)
        )
        unit = result.scalar_one_or_none()
        key_points_str = ""
        if unit and unit.key_points:
            kps = json.loads(unit.key_points)
            key_points_str = "\n".join(
                f"- {kp.get('title', str(kp))}" if isinstance(kp, dict) else f"- {kp}"
                for kp in kps
            )

        prompt = CORNELL_SUMMARY_PROMPT.format(
            unit_title=unit.title if unit else "未知",
            notes_content=notes_content[:2000],
            key_points=key_points_str or "无",
        )
        try:
            response = await self.llm.chat_json(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.5,
            )
            summary = response.get("summary", "") if isinstance(response, dict) else ""
        except Exception:
            summary = ""

        # 查找或创建该单元的康奈尔笔记 annotation
        ann_result = await self.db.execute(
            select(AnnotationModel).where(
                AnnotationModel.knowledge_unit_id == unit_id,
                AnnotationModel.annotation_type == "cornell_note",
            ).order_by(AnnotationModel.created_at.desc())
        )
        annotation = ann_result.scalars().first()
        if annotation:
            annotation.cornell_summary = summary
        else:
            self.db.add(AnnotationModel(
                id=str(__import__('uuid').uuid4()),
                user_id="anonymous",
                knowledge_unit_id=unit_id,
                annotation_type="cornell_note",
                content=notes_content[:2000],
                cornell_summary=summary,
            ))
        await self.db.flush()

        return summary

    async def get_cornell_notes(self, unit_id: str) -> List[CornellNote]:
        """获取某知识单元的所有康奈尔笔记"""
        from app.db.models import AnnotationModel

        result = await self.db.execute(
            select(AnnotationModel).where(
                AnnotationModel.knowledge_unit_id == unit_id,
                AnnotationModel.annotation_type == "cornell_note",
            ).order_by(AnnotationModel.created_at.desc())
        )
        rows = result.scalars().all()
        notes = []
        for row in rows:
            cues = json.loads(row.cornell_cues) if row.cornell_cues else []
            notes.append(CornellNote(
                annotation_id=row.id,
                knowledge_unit_id=row.knowledge_unit_id,
                notes=row.content or "",
                cues=cues,
                summary=row.cornell_summary,
                ai_generated=bool(cues or row.cornell_summary),
            ))
        return notes

    async def run_session_test(
        self,
        session_id: str,
        units: List[LearnedUnit],
        weak_points: Optional[List[str]] = None,
    ) -> SessionTest:
        """运行会话结束后的理解测试（支持薄弱点聚焦）"""
        session = await self._get_session(session_id)

        session_units = [u for u in units if u.unit_id in session.unit_ids]

        if weak_points:
            # 使用自适应题目生成，优先覆盖薄弱点
            questions = await self._generate_adaptive_questions(
                session_units, weak_points, session.strategy, count=3,
            )
        else:
            questions = []
            for unit in session_units[:3]:
                question = await self._generate_test_question(unit, session.strategy)
                questions.append(question)

        test = SessionTest(session_id=session_id, questions=questions)

        self.db.add(SessionTestModel(
            id=test.id,
            session_id=session_id,
            questions_json=json.dumps([q.model_dump() for q in questions]),
        ))
        await self.db.flush()

        return test

    async def submit_test_answers(
        self,
        test_id: str,
        answers: List[str],
    ) -> SessionTest:
        """提交测试答案（LLM 语义判分）"""
        result = await self.db.execute(
            select(SessionTestModel).where(SessionTestModel.id == test_id)
        )
        db_test = result.scalar_one_or_none()
        if not db_test:
            raise ServiceError(ErrorCode.NOT_FOUND, "测试不存在")

        questions_data = json.loads(db_test.questions_json)
        questions = [TestQuestion(**q) for q in questions_data]

        if len(answers) != len(questions):
            raise ServiceError(ErrorCode.VALIDATION_ERROR, f"答案数量({len(answers)})与题目数量({len(questions)})不匹配")

        total_score = 0
        weak_points = []
        for i, (question, answer) in enumerate(zip(questions, answers)):
            score = await self._grade_answer(question, answer)
            total_score += score
            if score < 70:
                weak_points.append(f"问题{i + 1}: {question.question}")

        avg_score = total_score / len(questions) if questions else 0

        db_test.user_answers_json = json.dumps(answers)
        db_test.score = avg_score
        db_test.weak_points_json = json.dumps(weak_points)
        db_test.completed_at = datetime.now(timezone.utc)
        await self.db.flush()

        return SessionTest(
            id=db_test.id,
            session_id=db_test.session_id,
            questions=questions,
            user_answers=answers,
            score=avg_score,
            weak_points=weak_points,
            completed_at=db_test.completed_at,
        )

    async def adapt_strategy(
        self,
        session_id: str,
        interaction_data: dict,
    ) -> TeachingStrategy:
        """根据学生互动调整教学策略

        Args:
            session_id: 会话ID
            interaction_data: 互动数据，包含：
                - questions_asked: 提问次数
                - correct_rate: 回答正确率
                - confusing_marks: "不懂"标记次数
                - avg_response_time: 平均响应时间（秒）

        Returns:
            调整后的教学策略
        """
        session = await self._get_session(session_id)
        strategy = session.strategy

        # 如果学生提问频繁，降低节奏，增加脚手架
        if interaction_data.get('questions_asked', 0) > 3:
            strategy.pace = 'slow'
            strategy.scaffold_level = 'full'
            strategy.interaction_frequency = 'high'

        # 如果学生回答正确率高，提高节奏
        if interaction_data.get('correct_rate', 0) > 0.8:
            strategy.pace = 'fast'
            strategy.scaffold_level = 'minimal'

        # 如果学生标记"不懂"，增加互动频率和脚手架
        if interaction_data.get('confusing_marks', 0) > 0:
            strategy.interaction_frequency = 'high'
            strategy.scaffold_level = 'full'

        # 如果响应时间慢，降低节奏
        if interaction_data.get('avg_response_time', 0) > 30:
            strategy.pace = 'slow'

        # 保存调整后的策略
        db_session = await self._get_db_session(session_id)
        if db_session:
            db_session.strategy_json = json.dumps(strategy.model_dump())
            await self.db.flush()

        return strategy

    async def complete_session(
        self,
        session_id: str,
        questions_asked: int = 0,
        test_score: Optional[float] = None,
        annotations_created: int = 0,
    ) -> SessionSummary:
        """完成教学会话并触发间隔重复"""
        db_session = await self._get_db_session(session_id)
        if not db_session:
            raise ServiceError(ErrorCode.NOT_FOUND, "会话不存在")

        db_session.status = "completed"
        db_session.ended_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.db.flush()

        duration = (db_session.ended_at - db_session.started_at).total_seconds() / 60
        unit_ids = json.loads(db_session.unit_ids)

        # 触发间隔重复调度
        await self._schedule_reviews(unit_ids, session_id, test_score)

        return SessionSummary(
            session_id=session_id,
            duration_minutes=int(duration),
            units_covered=len(unit_ids),
            questions_asked=questions_asked,
            test_score=test_score,
            annotations_created=annotations_created,
        )

    async def _schedule_reviews(
        self, unit_ids: List[str], session_id: str, test_score: Optional[float] = None,
    ):
        """为学习过的单元安排间隔重复，综合教学表现和测试分数更新掌握度"""
        from app.modules.review.spaced_repetition import calculate_next_review
        from app.db.models import MasteryRecordModel
        from datetime import timedelta

        # 收集该会话所有交互阶段的评估分数
        assess_result = await self.db.execute(
            select(TeachingMessageModel.unit_id, TeachingMessageModel.assessment_json).where(
                TeachingMessageModel.session_id == session_id,
                TeachingMessageModel.assessment_json.isnot(None),
            )
        )
        unit_scores: dict[str, list[float]] = {}
        for unit_id_val, assessment_json in assess_result:
            try:
                data = json.loads(assessment_json)
                if "score" in data:
                    unit_scores.setdefault(unit_id_val, []).append(float(data["score"]))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        for unit_id in unit_ids:
            # 计算该单元的 teaching_score
            scores = unit_scores.get(unit_id, [])
            teaching_score = (sum(scores) / len(scores) / 100) if scores else 0.5

            # 综合计算 mastery
            if test_score is not None:
                mastery = teaching_score * 0.6 + (test_score / 100) * 0.4
            else:
                mastery = teaching_score * 0.8
            mastery = round(max(0.0, min(1.0, mastery)), 2)

            # 计算质量分数用于间隔重复调度
            mastery_100 = mastery * 100
            if mastery_100 >= 90:
                quality = 5
            elif mastery_100 >= 80:
                quality = 4
            elif mastery_100 >= 70:
                quality = 3
            elif mastery_100 >= 60:
                quality = 2
            else:
                quality = 1
            # 查找或创建掌握度记录
            result = await self.db.execute(
                select(MasteryRecordModel).where(
                    MasteryRecordModel.user_id == "anonymous",
                    MasteryRecordModel.knowledge_unit_id == unit_id,
                )
            )
            mastery_record = result.scalar_one_or_none()

            if mastery_record:
                # 更新现有记录
                new_interval, new_ease, new_reps = calculate_next_review(
                    quality=quality,
                    repetitions=mastery_record.review_count,
                    ease_factor=mastery_record.ease_factor,
                    interval=mastery_record.interval_days,
                )
                mastery_record.interval_days = new_interval
                mastery_record.ease_factor = new_ease
                mastery_record.review_count = new_reps
                mastery_record.next_review_at = datetime.now(timezone.utc) + timedelta(days=new_interval)
                mastery_record.last_reviewed_at = datetime.now(timezone.utc)
                # 加权移动平均：70% 历史 + 30% 新观察
                mastery_record.mastery_score = round(
                    mastery_record.mastery_score * 0.7 + mastery * 0.3, 2
                )
                mastery_record.mastery_level = self._score_to_level(mastery_record.mastery_score)
            else:
                # 创建新记录
                new_interval, new_ease, new_reps = calculate_next_review(
                    quality=quality,
                    repetitions=0,
                    ease_factor=2.5,
                    interval=1,
                )
                self.db.add(MasteryRecordModel(
                    user_id="anonymous",
                    knowledge_unit_id=unit_id,
                    book_id="",
                    mastery_score=mastery,
                    mastery_level=self._score_to_level(mastery),
                    last_reviewed_at=datetime.now(timezone.utc),
                    next_review_at=datetime.now(timezone.utc) + timedelta(days=new_interval),
                    review_count=new_reps,
                    ease_factor=new_ease,
                    interval_days=new_interval,
                ))

        await self.db.flush()

    async def _update_mastery_on_unit_complete(
        self, unit_id: str, book_id: str, session_id: str, test_score: Optional[float] = None,
    ):
        """单元学完后，基于 AI 评估分数计算掌握度

        计算规则：
        - 收集 CHECK/REFLECT 阶段的 AI 评估分数 → teaching_score（0-1）
        - 有测试：mastery = teaching_score * 0.6 + test_score * 0.4
        - 无测试：mastery = teaching_score * 0.8（上限 0.8）
        - 每次重学取历史最高分
        """
        from app.db.models import MasteryRecordModel
        from datetime import timedelta

        # 收集该单元所有交互阶段的 AI 评估分数
        result = await self.db.execute(
            select(TeachingMessageModel.assessment_json).where(
                TeachingMessageModel.session_id == session_id,
                TeachingMessageModel.unit_id == unit_id,
                TeachingMessageModel.assessment_json.isnot(None),
            )
        )
        assessment_rows = result.scalars().all()

        scores = []
        for row in assessment_rows:
            try:
                data = json.loads(row)
                if "score" in data:
                    scores.append(float(data["score"]))
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # 计算 teaching_score（AI 评估的平均分，0-100 → 0-1）
        teaching_score = (sum(scores) / len(scores) / 100) if scores else 0.5

        # 综合计算 mastery
        if test_score is not None:
            mastery = teaching_score * 0.6 + (test_score / 100) * 0.4
        else:
            mastery = teaching_score * 0.8  # 无测试，上限 0.8

        mastery = round(max(0.0, min(1.0, mastery)), 2)

        # 更新或创建掌握度记录
        db_result = await self.db.execute(
            select(MasteryRecordModel).where(
                MasteryRecordModel.user_id == "anonymous",
                MasteryRecordModel.knowledge_unit_id == unit_id,
            )
        )
        record = db_result.scalar_one_or_none()

        if record:
            # 加权移动平均：70% 历史 + 30% 新观察
            record.mastery_score = round(record.mastery_score * 0.7 + mastery * 0.3, 2)
            record.mastery_level = self._score_to_level(record.mastery_score)
            record.last_reviewed_at = datetime.now(timezone.utc)
            record.review_count += 1
        else:
            self.db.add(MasteryRecordModel(
                user_id="anonymous",
                knowledge_unit_id=unit_id,
                book_id=book_id,
                mastery_score=mastery,
                mastery_level=self._score_to_level(mastery),
                last_reviewed_at=datetime.now(timezone.utc),
                next_review_at=datetime.now(timezone.utc) + timedelta(days=1),
                review_count=1,
                ease_factor=2.5,
                interval_days=1,
            ))

    @staticmethod
    def _score_to_level(score: float) -> str:
        """分数转掌握等级（5级体系）"""
        if score >= 0.85:
            return "mastered"
        if score >= 0.65:
            return "proficient"
        if score >= 0.40:
            return "familiar"
        if score >= 0.20:
            return "learning"
        return "beginner"

    async def get_session_messages(self, session_id: str) -> List[TeachingMessage]:
        """获取会话的所有消息"""
        result = await self.db.execute(
            select(TeachingMessageModel)
            .where(TeachingMessageModel.session_id == session_id)
            .order_by(TeachingMessageModel.created_at)
        )
        db_messages = result.scalars().all()
        messages = []
        for m in db_messages:
            phase = TeachingPhase(m.phase)
            assessment = json.loads(m.assessment_json) if m.assessment_json else None
            messages.append(TeachingMessage(
                id=m.id, session_id=m.session_id, unit_id=m.unit_id,
                phase=phase, content=m.content,
                content_type=m.content_type, created_at=m.created_at,
                requires_answer=phase in (TeachingPhase.CHECK, TeachingPhase.REFLECT, TeachingPhase.RETRIEVAL, TeachingPhase.FEYNMAN) and assessment is None,
                assessment=assessment,
            ))
        return messages

    # ---- 私有方法 ----

    async def _get_session(self, session_id: str) -> TeachingSession:
        """从DB加载教学会话"""
        db_session = await self._get_db_session(session_id)
        if not db_session:
            raise ServiceError(ErrorCode.NOT_FOUND, "会话不存在")

        strategy_data = json.loads(db_session.strategy_json) if db_session.strategy_json else {}
        return TeachingSession(
            id=db_session.id,
            user_id=db_session.user_id,
            plan_session_id=db_session.plan_session_id,
            book_id=db_session.book_id,
            unit_ids=json.loads(db_session.unit_ids),
            current_unit_index=db_session.current_unit_index,
            current_phase=TeachingPhase(db_session.current_phase),
            started_at=db_session.started_at,
            ended_at=db_session.ended_at,
            status=db_session.status,
            strategy=TeachingStrategy(**strategy_data),
        )

    async def _get_db_session(self, session_id: str) -> Optional[TeachingSessionModel]:
        result = await self.db.execute(
            select(TeachingSessionModel).where(TeachingSessionModel.id == session_id)
        )
        return result.scalar_one_or_none()

    def _advance_phase(self, session: TeachingSession):
        """推进教学阶段：使用策略中的阶段列表"""
        phase_order = session.strategy.phases
        try:
            current_idx = phase_order.index(session.current_phase)
        except ValueError:
            # 未知阶段：回退到第一个阶段
            session.current_phase = phase_order[0]
            return

        if current_idx + 1 < len(phase_order):
            session.current_phase = phase_order[current_idx + 1]
        else:
            session.current_unit_index += 1
            session.current_phase = phase_order[0]  # 使用策略的第一个阶段

    async def _generate_activate(self, unit: LearnedUnit, strategy: TeachingStrategy) -> str:
        """激活旧知：提问题唤醒已有知识"""
        prerequisites = "、".join(unit.prerequisites) if unit.prerequisites else "无"
        prompt = ACTIVATE_PROMPT.format(
            summary=unit.summary,
            prerequisites=prerequisites,
        )
        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.7,
        )
        return response.content

    async def _generate_intro(self, unit: LearnedUnit, strategy: TeachingStrategy) -> str:
        intro = f"今天我们要学习：{unit.summary[:100]}..."
        if unit.prerequisites:
            intro += f"\n\n前置知识：{', '.join(unit.prerequisites)}"
        return intro

    async def _generate_core(self, unit: LearnedUnit, strategy: TeachingStrategy) -> str:
        # 提取概念列表
        concepts_list = []
        for c in (unit.concepts or []):
            if hasattr(c, 'name') and hasattr(c, 'definition'):
                concepts_list.append(f"- {c.name}: {c.definition}")
            elif hasattr(c, 'name'):
                concepts_list.append(f"- {c.name}")
            else:
                concepts_list.append(f"- {c}")
        concepts_str = "\n".join(concepts_list) if concepts_list else "无"

        # 提取关键要点列表
        kp_list = []
        for kp in (unit.key_points or []):
            if hasattr(kp, 'title'):
                text = kp.title
                if hasattr(kp, 'explanation') and kp.explanation:
                    text += f": {kp.explanation}"
                kp_list.append(f"- {text}")
            else:
                kp_list.append(f"- {kp}")
        key_points_str = "\n".join(kp_list) if kp_list else "无"

        prompt = EXPLAIN_PROMPT.format(
            title=unit.summary[:50],
            content=unit.summary,
            summary=unit.summary,
            concepts=concepts_str,
            key_points=key_points_str,
            explanation_style=strategy.explanation_style,
            visual_level=strategy.visual_level,
            interaction_frequency=strategy.interaction_frequency,
            knowledge_type=strategy.knowledge_type,
            cognitive_level=strategy.cognitive_level,
            scaffold_level=strategy.scaffold_level,
        )
        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.7,
        )
        return response.content

    async def _generate_core_with_coverage(
        self,
        unit: LearnedUnit,
        strategy: TeachingStrategy,
        teaching_plan: TeachingPlan,
    ) -> str:
        """生成核心讲解内容，确保覆盖教学计划中的所有未覆盖内容"""

        # 获取未覆盖的内容项
        missing_items = teaching_plan.get_missing_items()

        # 按类型分组
        missing_key_points = [item for item in missing_items if item.content_type == "key_point"]
        missing_concepts = [item for item in missing_items if item.content_type == "concept"]
        missing_examples = [item for item in missing_items if item.content_type == "example"]

        # 构建提示词
        kp_str = "\n".join(f"- {item.title}: {item.content}" for item in missing_key_points) or "无"
        concepts_str = "\n".join(f"- {item.title}: {item.content}" for item in missing_concepts) or "无"
        examples_str = "\n".join(f"- {item.content}" for item in missing_examples[:3]) or "无"

        prompt = f"""你是一位专业的教师，请讲解以下知识点。

## 知识点
标题：{unit.summary[:50]}
内容：{unit.summary}

## 必须覆盖的关键要点（未讲解）
{kp_str}

## 必须覆盖的核心概念（未讲解）
{concepts_str}

## 可用的例子
{examples_str}

## 教学策略
讲解风格：{strategy.explanation_style}
视觉辅助：{strategy.visual_level}
知识类型：{strategy.knowledge_type}

## 任务
请生成一段讲解内容（300-500字），要求：
1. 开头说明今天学什么（1-2句话）
2. **逐一讲解上面列出的每一个关键要点和核心概念**，不要遗漏任何一个
3. 每个要点都要有具体的例子或类比帮助理解
4. 结尾引导思考

请直接返回讲解文本，不需要JSON格式。"""

        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.7,
        )
        return response.content

    async def _generate_example(self, unit: LearnedUnit, strategy: TeachingStrategy) -> str:
        """生成示例说明，通过例子加深理解"""

        # 提取所有可用的例子
        examples = []

        # 从关键要点中提取例子
        for kp in (unit.key_points or []):
            if hasattr(kp, 'examples') and kp.examples:
                for example in kp.examples:
                    examples.append(f"- {kp.title}的例子：{example}")

        # 从核心概念中提取例子
        for concept in (unit.concepts or []):
            if hasattr(concept, 'examples') and concept.examples:
                for example in concept.examples:
                    examples.append(f"- {concept.name}的例子：{example}")

        examples_str = "\n".join(examples[:5]) if examples else "无"

        prompt = f"""你是一位专业的教师，请通过例子帮助学生理解知识点。

## 学习内容
{unit.summary[:300]}

## 可用的例子
{examples_str}

## 任务
请生成 2-3 个生动具体的例子，帮助学生理解上面的知识点。要求：
1. 例子要贴近生活，容易理解
2. 每个例子要说明为什么这个例子能帮助理解
3. 例子之间要有差异性，从不同角度说明
4. 最后引导学生思考例子与知识点的关系

请直接返回例子说明，不需要JSON格式。"""

        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.7,
        )
        return response.content

    async def _generate_supplement(
        self,
        unit: LearnedUnit,
        missing_items: List[dict],
    ) -> str:
        """生成补充教学内容，覆盖遗漏的知识点"""

        # 构建遗漏内容列表
        missing_str = "\n".join(
            f"- [{item['type']}] {item['title']}"
            for item in missing_items
        )

        prompt = f"""你是一位专业的教师，需要补充讲解遗漏的知识点。

## 原始学习内容
{unit.summary[:200]}

## 遗漏的知识点
{missing_str}

## 任务
请针对上面列出的遗漏知识点，生成补充讲解内容。要求：
1. 逐一讲解每个遗漏的知识点
2. 用简洁明了的语言
3. 提供简单的例子帮助理解
4. 确保覆盖所有遗漏的内容

请直接返回补充讲解文本，不需要JSON格式。"""

        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.7,
        )
        return response.content

    async def _generate_feynman(self, unit: LearnedUnit) -> str:
        """费曼学习法：引导学生用自己的话解释"""
        kp_list = []
        for kp in (unit.key_points or []):
            kp_list.append(f"- {kp.title}" if hasattr(kp, 'title') else f"- {kp}")
        key_points_str = "\n".join(kp_list) or "无"

        concepts_list = []
        for c in (unit.concepts or []):
            concepts_list.append(f"- {c.name}" if hasattr(c, 'name') else f"- {c}")
        concepts_str = "\n".join(concepts_list) or "无"

        prompt = FEYNMAN_EXPLAIN_PROMPT.format(
            summary=unit.summary[:500],
            key_points=key_points_str,
            concepts=concepts_str,
        )
        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.7,
        )
        return response.content

    async def _assess_feynman_explanation(self, unit: LearnedUnit, explanation: str) -> dict:
        """评估费曼解释的质量"""
        kp_list = []
        for kp in (unit.key_points or []):
            if hasattr(kp, 'title') and hasattr(kp, 'explanation') and kp.explanation:
                kp_list.append(f"- {kp.title}: {kp.explanation}")
            elif hasattr(kp, 'title'):
                kp_list.append(f"- {kp.title}")
            else:
                kp_list.append(f"- {kp}")
        key_points_str = "\n".join(kp_list) or "无"

        concepts_list = []
        for c in (unit.concepts or []):
            if hasattr(c, 'name') and hasattr(c, 'definition') and c.definition:
                concepts_list.append(f"- {c.name}: {c.definition}")
            elif hasattr(c, 'name'):
                concepts_list.append(f"- {c.name}")
            else:
                concepts_list.append(f"- {c}")
        concepts_str = "\n".join(concepts_list) or "无"

        prompt = FEYNMAN_ASSESS_PROMPT.format(
            summary=unit.summary[:500],
            key_points=key_points_str,
            concepts=concepts_str,
            student_explanation=explanation[:2000],
        )
        try:
            response = await self.llm.chat_json(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.1,
            )
            result = response if isinstance(response, dict) else json.loads(response)
            # 确保必要字段存在
            result.setdefault("completeness", 0.5)
            result.setdefault("accuracy", 0.5)
            result.setdefault("depth", 0.5)
            result.setdefault("overall_score", 50)
            result.setdefault("covered_points", [])
            result.setdefault("missed_points", [])
            result.setdefault("inaccurate_points", [])
            result.setdefault("feedback", "")
            result.setdefault("suggestion", "")
            result.setdefault("should_advance", result.get("overall_score", 50) >= 60)
            # 将 overall_score 映射到 score 字段（兼容通用评估格式）
            result["score"] = result["overall_score"]
            result["mastery_level"] = (
                "excellent" if result["overall_score"] >= 80 else
                "good" if result["overall_score"] >= 60 else
                "partial" if result["overall_score"] >= 40 else "poor"
            )
            return result
        except Exception:
            return {
                "completeness": 0.5, "accuracy": 0.5, "depth": 0.5,
                "overall_score": 50, "score": 50, "mastery_level": "partial",
                "covered_points": [], "missed_points": [], "inaccurate_points": [],
                "feedback": "无法评估，请继续学习",
                "suggestion": "继续下一阶段", "should_advance": True,
            }

    async def _generate_retrieval(self, unit: LearnedUnit, all_units: List[LearnedUnit]) -> str:
        """检索练习：从前置单元生成 2-3 个快速回忆问题"""
        prereq_names = unit.prerequisites or []
        if not prereq_names:
            return "请回忆你之前学过的相关知识，尝试总结要点。"

        # 找到前置单元（精确匹配 unit_id 或概念名）
        prereq_set = set(prereq_names)
        prereq_units = []
        for u in all_units:
            if u.unit_id in prereq_set:
                prereq_units.append(u)
            elif u.concepts:
                concept_names = {c.name for c in u.concepts if hasattr(c, 'name')}
                if prereq_set & concept_names:
                    prereq_units.append(u)

        if not prereq_units:
            return f"在学习新内容前，请回忆以下前置知识：{', '.join(prereq_names[:3])}"

        # 从前置单元提取要点构造回忆问题
        questions = []
        for pu in prereq_units[:2]:
            if pu.key_points:
                kp = pu.key_points[0]
                title = kp.title if hasattr(kp, 'title') else str(kp)
                questions.append(f"• {pu.summary[:30]}：{title} 的核心要点是什么？")
            else:
                questions.append(f"• 请简述 {pu.summary[:50]} 的主要内容")

        header = "在学习新内容前，先快速回忆一下前置知识：\n"
        return header + "\n".join(questions)

    async def _generate_check(self, unit: LearnedUnit) -> str:
        # 提取所有关键要点
        kp_list = []
        for kp in (unit.key_points or []):
            if hasattr(kp, 'title'):
                kp_list.append(f"- {kp.title}")
            else:
                kp_list.append(f"- {kp}")
        key_points_str = "\n".join(kp_list) if kp_list else "无"

        prompt = CHECK_PROMPT.format(
            summary=unit.summary[:500],
            key_points=key_points_str,
        )
        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.5,
        )
        return response.content

    async def _generate_reflect(self, unit: LearnedUnit, strategy: TeachingStrategy) -> str:
        """元认知反思：引导学生自评理解程度"""
        kp_list = []
        for kp in (unit.key_points or []):
            if hasattr(kp, 'title'):
                kp_list.append(f"- {kp.title}")
            else:
                kp_list.append(f"- {kp}")
        key_points_str = "\n".join(kp_list) if kp_list else "无"

        prompt = REFLECT_PROMPT.format(summary=unit.summary, key_points=key_points_str)
        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.7,
        )
        return response.content

    async def _generate_connect(self, unit: LearnedUnit, session_id: str) -> str:
        """生成单元总结：使用 LLM 生成包含学生表现的个性化总结"""
        concepts = []
        if unit.concepts:
            for c in unit.concepts:
                if hasattr(c, 'name'):
                    concepts.append(c.name)
                else:
                    concepts.append(str(c))
        concepts_str = "、".join(concepts) if concepts else "核心概念"

        # 收集当前单元的学生提问记录
        result = await self.db.execute(
            select(UserQuestionModel).where(
                UserQuestionModel.session_id == session_id,
            ).order_by(UserQuestionModel.asked_at)
        )
        q_records = result.scalars().all()
        questions_str = "\n".join(
            f"- {r.question}（意图：{r.intent}）" for r in q_records
        ) or "无"

        # 收集当前单元的学生回答记录
        current_unit_id = unit.unit_id
        answer_result = await self.db.execute(
            select(TeachingMessageModel).where(
                TeachingMessageModel.session_id == session_id,
                TeachingMessageModel.unit_id == current_unit_id,
                TeachingMessageModel.phase.in_([
                    TeachingPhase.CHECK.value, TeachingPhase.REFLECT.value,
                ]),
            ).order_by(TeachingMessageModel.created_at)
        )
        all_messages = answer_result.scalars().all()
        answers_str = "\n".join(f"- {m.content[:200]}" for m in all_messages) or "无"

        try:
            prompt = SUMMARY_PROMPT.format(
                summary=unit.summary[:500],
                concepts=concepts_str,
                questions=questions_str,
                answers=answers_str,
            )
            response = await self.llm.chat(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.5,
            )
            return response.content
        except Exception:
            return f"今天我们学习了：{concepts_str}\n\n重要程度：{unit.importance_score:.0%}"

    async def _classify_intent(self, question: str, unit: Optional[LearnedUnit]) -> str:
        topic = unit.summary[:100] if unit else "未知"
        prompt = INTENT_PROMPT.format(question=question, current_topic=topic)
        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.1,
        )
        intent = response.content.strip().lower()
        valid_intents = ['concept', 'principle', 'example', 'comparison', 'application']
        return intent if intent in valid_intents else 'concept'

    async def _generate_answer(self, question: str, intent: str,
                               unit: Optional[LearnedUnit]) -> tuple:
        content = unit.summary if unit else "无相关内容"
        prompt = ANSWER_PROMPT.format(
            current_content=content,
            question=question,
            intent=intent,
        )
        response = await self.llm.chat_json(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.5,
        )
        result = response if isinstance(response, dict) else json.loads(response)
        answer = result.get("answer", "抱歉，我无法回答这个问题。")
        follow_ups = result.get("follow_up_questions", [])

        if not follow_ups:
            if unit and unit.concepts:
                concepts = []
                for c in unit.concepts:
                    if hasattr(c, 'name'):
                        concepts.append(c.name)
                    else:
                        concepts.append(str(c))
                if not concepts:
                    concepts = ["核心概念"]
            else:
                concepts = ["核心概念"]
            follow_ups = [
                f"能举一个{concepts[0]}的实际例子吗？",
                f"{concepts[0]}的优缺点是什么？",
                f"{concepts[0]}在实际中有哪些应用场景？",
            ]

        return answer, follow_ups

    async def _grade_answer(self, question: TestQuestion, student_answer: str) -> float:
        """LLM 语义判分，返回 0-100"""
        prompt = GRADE_PROMPT.format(
            question=question.question,
            correct_answer=question.correct_answer,
            student_answer=student_answer,
        )
        try:
            response = await self.llm.chat_json(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.1,
            )
            result = response if isinstance(response, dict) else json.loads(response)
            return float(result.get("score", 0))
        except Exception:
            # LLM 判分失败时回退到精确匹配
            if student_answer.strip().lower() == question.correct_answer.strip().lower():
                return 100.0
            return 0.0

    async def _generate_test_question(self, unit: LearnedUnit, strategy: TeachingStrategy) -> TestQuestion:
        """根据知识类型生成不同题型"""
        from app.modules.teaching.schemas import KnowledgeType

        first_concept = unit.concepts[0] if unit.concepts else None
        if first_concept and hasattr(first_concept, 'name'):
            concept_name = first_concept.name
            definition = first_concept.definition
        elif first_concept:
            concept_name = str(first_concept)
            definition = unit.summary[:100]
        else:
            concept_name = "核心概念"
            definition = unit.summary[:100]

        kt = strategy.knowledge_type

        if kt == KnowledgeType.PROCEDURE.value:
            return TestQuestion(
                question=f"请描述 {concept_name} 的具体步骤或操作流程",
                question_type="short_answer",
                correct_answer=definition,
                explanation=unit.summary[:200],
            )
        elif kt == KnowledgeType.PRINCIPLE.value:
            return TestQuestion(
                question=f"请解释 {concept_name} 的原理：为什么？",
                question_type="short_answer",
                correct_answer=definition,
                explanation=unit.summary[:200],
            )
        elif kt == KnowledgeType.FACT.value:
            return TestQuestion(
                question=f"请补充完整：{concept_name} 是指 ______",
                question_type="fill_blank",
                correct_answer=definition,
                explanation=unit.summary[:200],
            )
        else:  # CONCEPT
            options = [definition]
            if unit.concepts and len(unit.concepts) > 1:
                options.extend(c.definition for c in unit.concepts[1:3] if c.definition)
            while len(options) < 4:
                options.append(f"与{concept_name}无关的描述")

            return TestQuestion(
                question=f"以下哪项最准确地描述了 {concept_name}？",
                question_type="choice",
                options=options[:4],
                correct_answer=definition,
                explanation=unit.summary[:200],
            )

    async def _generate_matching_question(self, unit: LearnedUnit) -> TestQuestion:
        """生成连线题：概念与定义配对"""
        concepts_str = ""
        pairs = []
        for c in unit.concepts[:5]:
            if hasattr(c, 'name') and hasattr(c, 'definition'):
                concepts_str += f"- {c.name}: {c.definition}\n"
                pairs.append({"left": c.name, "right": c.definition})
            elif isinstance(c, str):
                concepts_str += f"- {c}\n"
                pairs.append({"left": c, "right": unit.summary[:50]})

        # 概念不足时用 LLM 补充
        if len(pairs) < 3:
            prompt = MATCHING_PROMPT.format(
                summary=unit.summary[:300],
                concepts=concepts_str or unit.summary[:200],
            )
            try:
                response = await self.llm.chat_json(
                    messages=[LLMMessage(role="user", content=prompt)],
                    temperature=0.7,
                )
                result = response if isinstance(response, dict) else json.loads(response)
                pairs = result.get("pairs", pairs)
                explanation = result.get("explanation", unit.summary[:200])
            except Exception:
                explanation = unit.summary[:200]
        else:
            explanation = unit.summary[:200]

        return TestQuestion(
            question="请将以下概念与正确的定义连线",
            question_type="matching",
            pairs=pairs,
            correct_answer=json.dumps(pairs, ensure_ascii=False),
            explanation=explanation,
        )

    async def _generate_ordering_question(self, unit: LearnedUnit) -> TestQuestion:
        """生成排序题：按正确顺序排列步骤"""
        steps = []
        for kp in unit.key_points[:5]:
            if hasattr(kp, 'title'):
                steps.append(kp.title)
            else:
                steps.append(str(kp))

        if len(steps) < 3:
            prompt = ORDERING_PROMPT.format(
                summary=unit.summary[:300],
                key_points="\n".join(kp.title if hasattr(kp, 'title') else str(kp) for kp in unit.key_points[:5]) or unit.summary[:200],
            )
            try:
                response = await self.llm.chat_json(
                    messages=[LLMMessage(role="user", content=prompt)],
                    temperature=0.7,
                )
                result = response if isinstance(response, dict) else json.loads(response)
                steps = result.get("steps", steps)
                explanation = result.get("explanation", unit.summary[:200])
                question_text = result.get("question", "请将以下步骤按正确顺序排列")
            except Exception:
                if len(steps) < 2:
                    steps = [f"步骤{i+1}" for i in range(4)]
                explanation = unit.summary[:200]
                question_text = "请将以下步骤按正确顺序排列"
        else:
            explanation = unit.summary[:200]
            question_text = "请将以下步骤按正确顺序排列"

        return TestQuestion(
            question=question_text,
            question_type="ordering",
            options=steps,
            sequence=steps,
            correct_answer=json.dumps(steps, ensure_ascii=False),
            explanation=explanation,
        )

    async def _generate_true_false_question(self, unit: LearnedUnit) -> TestQuestion:
        """生成判断题"""
        prompt = TRUE_FALSE_PROMPT.format(summary=unit.summary[:300])
        try:
            response = await self.llm.chat_json(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.7,
            )
            result = response if isinstance(response, dict) else json.loads(response)
            statement = result.get("statement", unit.summary[:100])
            is_correct = result.get("is_correct", True)
            explanation = result.get("explanation", unit.summary[:200])
        except Exception:
            statement = unit.summary[:100] if unit.summary else "这是一个正确的陈述"
            is_correct = True
            explanation = unit.summary[:200]

        return TestQuestion(
            question="请判断以下陈述是否正确",
            question_type="true_false",
            statement=statement,
            options=["正确", "错误"],
            correct_answer="正确" if is_correct else "错误",
            explanation=explanation,
        )

    async def _generate_adaptive_questions(
        self,
        units: List[LearnedUnit],
        weak_points: List[str],
        strategy: TeachingStrategy,
        count: int = 3,
    ) -> List[TestQuestion]:
        """根据薄弱点生成针对性题目"""
        questions = []

        # 优先为薄弱点相关单元生成题目
        for unit in units:
            if any(wp.lower() in unit.summary.lower() for wp in weak_points):
                q = await self._generate_test_question(unit, strategy)
                questions.append(q)
                if len(questions) >= count:
                    break

        # 补充其他题目（混合题型）
        remaining = count - len(questions)
        if remaining > 0:
            extra_generators = [
                self._generate_matching_question,
                self._generate_ordering_question,
                self._generate_true_false_question,
            ]
            for i, unit in enumerate(units):
                if len(questions) >= count:
                    break
                gen = extra_generators[i % len(extra_generators)]
                try:
                    q = await gen(unit)
                    questions.append(q)
                except Exception:
                    q = await self._generate_test_question(unit, strategy)
                    questions.append(q)

        return questions[:count]

    async def track_learning_efficiency(
        self,
        session_id: str,
        unit_id: str,
        phase: str,
        duration_seconds: int,
        interaction_count: int,
    ):
        """跟踪学习效率"""
        # 计算效率分数（每分钟互动次数）
        duration_minutes = duration_seconds / 60
        efficiency_score = interaction_count / duration_minutes if duration_minutes > 0 else 0

        self.db.add(LearningEfficiencyModel(
            session_id=session_id,
            unit_id=unit_id,
            phase=phase,
            duration_seconds=duration_seconds,
            interaction_count=interaction_count,
            efficiency_score=efficiency_score,
        ))
        await self.db.flush()

    async def get_session_efficiency(self, session_id: str) -> dict:
        """获取会话的效率统计"""
        result = await self.db.execute(
            select(LearningEfficiencyModel)
            .where(LearningEfficiencyModel.session_id == session_id)
            .order_by(LearningEfficiencyModel.created_at)
        )
        records = result.scalars().all()

        if not records:
            return {
                'total_duration': 0,
                'total_interactions': 0,
                'avg_efficiency': 0,
                'phase_stats': {},
            }

        total_duration = sum(r.duration_seconds for r in records)
        total_interactions = sum(r.interaction_count for r in records)
        avg_efficiency = total_interactions / (total_duration / 60) if total_duration > 0 else 0

        # 按阶段统计
        phase_stats = {}
        for r in records:
            if r.phase not in phase_stats:
                phase_stats[r.phase] = {
                    'duration': 0,
                    'interactions': 0,
                    'count': 0,
                }
            phase_stats[r.phase]['duration'] += r.duration_seconds
            phase_stats[r.phase]['interactions'] += r.interaction_count
            phase_stats[r.phase]['count'] += 1

        return {
            'total_duration': total_duration,
            'total_interactions': total_interactions,
            'avg_efficiency': round(avg_efficiency, 2),
            'phase_stats': phase_stats,
        }

    async def get_teaching_stats(
        self,
        book_id: Optional[str] = None,
        user_id: str = "anonymous",
        days: int = 7,
    ) -> dict:
        """获取教学统计"""
        from datetime import timedelta

        start_date = datetime.now(timezone.utc) - timedelta(days=days)

        # 查询已完成的教学会话
        query = select(TeachingSessionModel).where(
            TeachingSessionModel.user_id == user_id,
            TeachingSessionModel.started_at >= start_date,
            TeachingSessionModel.status == "completed",
        )
        if book_id:
            query = query.where(TeachingSessionModel.book_id == book_id)

        result = await self.db.execute(query)
        sessions = result.scalars().all()

        if not sessions:
            return {
                'total_sessions': 0,
                'total_minutes': 0,
                'questions_asked': 0,
                'avg_test_score': 0,
                'units_covered': 0,
            }

        # 统计数据
        total_sessions = len(sessions)
        total_minutes = 0
        units_covered = 0

        for session in sessions:
            if session.ended_at and session.started_at:
                duration = (session.ended_at - session.started_at).total_seconds() / 60
                total_minutes += duration
            unit_ids = json.loads(session.unit_ids) if session.unit_ids else []
            units_covered += len(unit_ids)

        # 查询提问数量
        session_ids = [s.id for s in sessions]
        questions_result = await self.db.execute(
            select(UserQuestionModel).where(
                UserQuestionModel.session_id.in_(session_ids)
            )
        )
        questions_asked = len(questions_result.scalars().all())

        # 查询测试分数
        tests_result = await self.db.execute(
            select(SessionTestModel).where(
                SessionTestModel.session_id.in_(session_ids),
                SessionTestModel.score.isnot(None),
            )
        )
        tests = tests_result.scalars().all()
        avg_test_score = sum(t.score for t in tests) / len(tests) if tests else 0

        return {
            'total_sessions': total_sessions,
            'total_minutes': round(total_minutes),
            'questions_asked': questions_asked,
            'avg_test_score': round(avg_test_score, 1),
            'units_covered': units_covered,
        }

    def get_teaching_plan_coverage(self, session_id: str, unit_id: str) -> dict:
        """获取教学计划的覆盖报告"""
        plan_key = f"{session_id}_{unit_id}"
        teaching_plan = self._teaching_plans.get(plan_key)

        if not teaching_plan:
            return {
                "unit_id": unit_id,
                "total_items": 0,
                "covered_items": 0,
                "coverage_rate": 0.0,
                "is_complete": False,
                "missing_items": [],
                "phase_coverage": [],
            }

        return coverage_tracker.get_coverage_report(teaching_plan)
