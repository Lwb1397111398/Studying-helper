"""教学服务 - DB持久化版"""

import json
from typing import List, Optional
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ServiceError, ErrorCode
from app.common.llm_client import LLMClient, LLMMessage
from app.db.models import (
    TeachingSessionModel, TeachingMessageModel,
    UserQuestionModel, SessionTestModel,
)
from app.modules.ai_learning.schemas import LearnedUnit, TestQuestion
from app.modules.teaching.schemas import (
    TeachingSession, TeachingPhase, TeachingMessage,
    UserQuestion, Annotation, SessionTest, TeachingStrategy,
    SessionSummary, UserTeachingProfile,
)
from app.modules.teaching.prompts import (
    INTENT_PROMPT, EXPLAIN_PROMPT, ANSWER_PROMPT,
    ACTIVATE_PROMPT, REFLECT_PROMPT, GRADE_PROMPT,
)
from app.modules.teaching.strategies import select_teaching_strategy


class TeachingService:
    """教学服务（会话和消息持久化到数据库）"""

    def __init__(self, llm_client: LLMClient, db: AsyncSession):
        self.llm = llm_client
        self.db = db

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
        strategy = select_teaching_strategy(units[0], user_profile) if units else TeachingStrategy()

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

        return session

    async def get_next_message(
        self,
        session_id: str,
        units: List[LearnedUnit],
    ) -> TeachingMessage:
        """获取下一条教学消息"""
        session = await self._get_session(session_id)

        if session.current_unit_index >= len(session.unit_ids):
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "所有单元已学完")

        current_unit_id = session.unit_ids[session.current_unit_index]
        current_unit = next((u for u in units if u.unit_id == current_unit_id), None)
        if not current_unit:
            raise ServiceError(ErrorCode.NOT_FOUND, f"知识单元 {current_unit_id} 不存在")

        phase = TeachingPhase(session.current_phase)
        if phase == TeachingPhase.ACTIVATE:
            content = await self._generate_activate(current_unit, session.strategy)
        elif phase == TeachingPhase.INTRO:
            content = await self._generate_intro(current_unit, session.strategy)
        elif phase == TeachingPhase.CORE:
            content = await self._generate_core(current_unit, session.strategy)
        elif phase == TeachingPhase.CHECK:
            content = await self._generate_check(current_unit)
        elif phase == TeachingPhase.REFLECT:
            content = await self._generate_reflect(current_unit, session.strategy)
        else:
            content = await self._generate_connect(current_unit)

        message = TeachingMessage(
            session_id=session_id,
            unit_id=current_unit_id,
            phase=phase,
            content=content,
        )

        self.db.add(TeachingMessageModel(
            id=message.id,
            session_id=session_id,
            unit_id=current_unit_id,
            phase=phase.value,
            content=content,
            content_type="text",
        ))

        self._advance_phase(session)

        db_session = await self._get_db_session(session_id)
        if db_session:
            db_session.current_unit_index = session.current_unit_index
            db_session.current_phase = session.current_phase.value

        await self.db.flush()
        return message

    async def answer_question(
        self,
        session_id: str,
        question: str,
        units: List[LearnedUnit],
    ) -> UserQuestion:
        """回答用户问题"""
        session = await self._get_session(session_id)

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

    async def add_annotation(
        self,
        user_id: str,
        unit_id: str,
        annotation_type: str,
        content: Optional[str] = None,
    ) -> Annotation:
        """添加笔记或标记"""
        from app.db.models import AnnotationModel

        annotation = Annotation(
            user_id=user_id,
            knowledge_unit_id=unit_id,
            annotation_type=annotation_type,
            content=content,
        )

        self.db.add(AnnotationModel(
            id=annotation.id,
            user_id=user_id,
            knowledge_unit_id=unit_id,
            annotation_type=annotation_type,
            content=content or "",
        ))
        await self.db.flush()

        return annotation

    async def run_session_test(
        self,
        session_id: str,
        units: List[LearnedUnit],
    ) -> SessionTest:
        """运行会话结束后的理解测试"""
        session = await self._get_session(session_id)

        session_units = [u for u in units if u.unit_id in session.unit_ids]
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

    async def complete_session(
        self,
        session_id: str,
        questions_asked: int = 0,
        test_score: Optional[float] = None,
        annotations_created: int = 0,
    ) -> SessionSummary:
        """完成教学会话"""
        db_session = await self._get_db_session(session_id)
        if not db_session:
            raise ServiceError(ErrorCode.NOT_FOUND, "会话不存在")

        db_session.status = "completed"
        db_session.ended_at = datetime.utcnow()
        await self.db.flush()

        duration = (db_session.ended_at - db_session.started_at).total_seconds() / 60
        unit_ids = json.loads(db_session.unit_ids)

        return SessionSummary(
            session_id=session_id,
            duration_minutes=int(duration),
            units_covered=len(unit_ids),
            questions_asked=questions_asked,
            test_score=test_score,
            annotations_created=annotations_created,
        )

    async def get_session_messages(self, session_id: str) -> List[TeachingMessage]:
        """获取会话的所有消息"""
        result = await self.db.execute(
            select(TeachingMessageModel)
            .where(TeachingMessageModel.session_id == session_id)
            .order_by(TeachingMessageModel.created_at)
        )
        db_messages = result.scalars().all()
        return [
            TeachingMessage(
                id=m.id, session_id=m.session_id, unit_id=m.unit_id,
                phase=TeachingPhase(m.phase), content=m.content,
                content_type=m.content_type, created_at=m.created_at,
            )
            for m in db_messages
        ]

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
        """推进教学阶段：ACTIVATE → INTRO → CORE → CHECK → REFLECT → CONNECT"""
        phase_order = [
            TeachingPhase.ACTIVATE, TeachingPhase.INTRO, TeachingPhase.CORE,
            TeachingPhase.CHECK, TeachingPhase.REFLECT, TeachingPhase.CONNECT,
        ]
        current_idx = phase_order.index(session.current_phase)

        if current_idx + 1 < len(phase_order):
            session.current_phase = phase_order[current_idx + 1]
        else:
            session.current_unit_index += 1
            session.current_phase = TeachingPhase.ACTIVATE

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
        prompt = EXPLAIN_PROMPT.format(
            title=unit.summary[:50],
            content=unit.summary,
            summary=unit.summary,
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

    async def _generate_check(self, unit: LearnedUnit) -> str:
        return f"请回答以下问题来检验你的理解：\n{unit.key_points[0] if unit.key_points else '请总结刚才学习的内容。'}"

    async def _generate_reflect(self, unit: LearnedUnit, strategy: TeachingStrategy) -> str:
        """元认知反思：引导学生自评理解程度"""
        prompt = REFLECT_PROMPT.format(summary=unit.summary)
        response = await self.llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.7,
        )
        return response.content

    async def _generate_connect(self, unit: LearnedUnit) -> str:
        concepts = [c.name for c in unit.concepts] if unit.concepts else []
        connect = f"今天我们学习了：{', '.join(concepts) if concepts else '核心概念'}"
        connect += f"\n\n重要程度：{unit.importance_score:.0%}"
        return connect

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
            concepts = [c.name for c in (unit.concepts if unit else [])] or ["核心概念"]
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
        concept_name = first_concept.name if first_concept else "核心概念"
        definition = first_concept.definition if first_concept else unit.summary[:100]

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
