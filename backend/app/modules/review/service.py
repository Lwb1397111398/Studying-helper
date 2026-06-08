"""复习服务 - 复习引擎核心业务逻辑"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select

from app.common.errors import ServiceError, ErrorCode
from app.common.llm_client import LLMClient, LLMMessage
from app.db.models import MasteryRecordModel, ReviewSessionModel
from app.modules.review.schemas import (
    MasteryRecord, ReviewSession, ReviewQuestion,
    ExamConfig, ExamResult, ExportResult, ExportFormat,
    ReviewFeedback, MasteryAssessment, FreeRecallResult, RecalledPoint,
)
from app.modules.review.spaced_repetition import calculate_next_review, quality_from_correctness
from app.modules.review.helpers import check_answer, mastery_delta, calibration_adjustment
from app.modules.review.mastery_evaluator import evaluate_mastery
from app.modules.review.question_generator import generate_questions
from app.modules.review.exam_mode import create_exam_session, evaluate_exam
from app.modules.review.exporters import (
    export_markdown, export_anki, export_wrong_answers,
    export_mindmap_mermaid, export_mindmap_plantuml,
)
from app.modules.knowledge_splitter.schemas import KnowledgeUnit

logger = logging.getLogger(__name__)


def _calc_mastery_level(score: float) -> str:
    """根据掌握度分数计算掌握等级（5级体系）"""
    if score >= 0.85:
        return "mastered"
    if score >= 0.65:
        return "proficient"
    if score >= 0.40:
        return "familiar"
    if score >= 0.20:
        return "learning"
    return "beginner"


class ReviewService:
    """复习服务（session 持久化到 DB）"""

    def __init__(self, db_session, llm_client=None):
        if db_session is None:
            raise ValueError("ReviewService 需要 db_session")
        self.db = db_session
        self._llm_client = llm_client

    def _get_llm_client(self):
        if self._llm_client is None:
            raise ServiceError(ErrorCode.EXTERNAL_API_ERROR, "LLM 客户端未配置")
        return self._llm_client

    # ===== 掌握度记录（从 DB 读写） =====

    async def _get_mastery(self, user_id: str, unit_id: str) -> Optional[MasteryRecord]:
        """从 DB 获取掌握度记录"""
        result = await self.db.execute(
            select(MasteryRecordModel).where(
                MasteryRecordModel.user_id == user_id,
                MasteryRecordModel.knowledge_unit_id == unit_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return MasteryRecord(
            id=row.id,
            user_id=row.user_id,
            knowledge_unit_id=row.knowledge_unit_id,
            book_id=row.book_id or "",
            mastery_score=row.mastery_score,
            mastery_level=row.mastery_level,
            last_reviewed_at=row.last_reviewed_at,
            next_review_at=row.next_review_at,
            review_count=row.review_count,
            ease_factor=row.ease_factor,
            interval_days=row.interval_days,
        )

    async def _upsert_mastery(self, user_id: str, unit_id: str, mastery_change: float,
                              new_interval: int, new_ease: float, new_rep: int,
                              book_id: str = "") -> None:
        """更新或创建掌握度记录"""
        existing = await self.db.execute(
            select(MasteryRecordModel).where(
                MasteryRecordModel.user_id == user_id,
                MasteryRecordModel.knowledge_unit_id == unit_id,
            )
        )
        row = existing.scalar_one_or_none()
        now = datetime.now(timezone.utc)

        if row:
            new_score = max(0.0, min(1.0, row.mastery_score + mastery_change))
            row.mastery_score = new_score
            row.mastery_level = _calc_mastery_level(new_score)
            row.review_count = new_rep
            row.ease_factor = new_ease
            row.interval_days = new_interval
            row.last_reviewed_at = now
            row.next_review_at = now + timedelta(days=new_interval)
            if book_id:
                row.book_id = book_id
        else:
            initial_score = max(0.0, min(1.0, mastery_change))
            self.db.add(MasteryRecordModel(
                id=str(uuid4()),
                user_id=user_id,
                knowledge_unit_id=unit_id,
                book_id=book_id,
                mastery_score=initial_score,
                mastery_level=_calc_mastery_level(initial_score),
                last_reviewed_at=now,
                next_review_at=now + timedelta(days=new_interval),
                review_count=new_rep,
                ease_factor=new_ease,
                interval_days=new_interval,
            ))

    # ===== Session 管理（DB 持久化） =====

    async def _save_session(self, session: ReviewSession) -> None:
        """保存 session 到 DB（upsert）"""
        questions_json = json.dumps(
            [{"id": q.id, "unit_id": q.unit_id, "question": q.question,
              "question_type": q.question_type, "options": q.options,
              "correct_answer": q.correct_answer, "user_answer": q.user_answer,
              "is_correct": q.is_correct, "pairs": q.pairs,
              "sequence": q.sequence, "statement": q.statement,
              "recall_context": q.recall_context}
             for q in session.questions],
            ensure_ascii=False,
        )
        existing = await self.db.execute(
            select(ReviewSessionModel).where(ReviewSessionModel.id == session.id)
        )
        row = existing.scalar_one_or_none()
        if row:
            row.questions_json = questions_json
            row.ended_at = session.ended_at
            row.score = session.score if hasattr(session, 'score') else None
        else:
            self.db.add(ReviewSessionModel(
                id=session.id,
                user_id=session.user_id,
                book_id=session.book_id,
                review_type=session.review_type,
                questions_json=questions_json,
                started_at=session.started_at,
                ended_at=session.ended_at,
            ))

    async def _load_session_questions(self, session_id: str) -> List[ReviewQuestion]:
        """从 DB 加载 session 的题目"""
        result = await self.db.execute(
            select(ReviewSessionModel).where(ReviewSessionModel.id == session_id)
        )
        row = result.scalar_one_or_none()
        if row is None or not row.questions_json:
            return []
        data = json.loads(row.questions_json)
        return [ReviewQuestion(**q) for q in data]

    # ===== 复习流程 =====

    def get_due_reviews(
        self,
        user_id: str,
        book_id: str,
        mastery_records: List[MasteryRecord],
    ) -> List[MasteryRecord]:
        """获取到期需要复习的知识单元"""
        now = datetime.now(timezone.utc)
        due = [r for r in mastery_records
               if r.user_id == user_id
               and r.book_id == book_id
               and r.next_review_at <= now]
        due.sort(key=lambda r: r.next_review_at)
        return due

    async def start_review(
        self,
        user_id: str,
        book_id: str,
        unit_ids: List[str],
        knowledge_units: List[KnowledgeUnit],
        review_type: str = 'spaced',
    ) -> ReviewSession:
        """开始一次复习会话"""
        if not unit_ids:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "请选择要复习的知识单元")

        unit_map = {u.id: u for u in knowledge_units}
        questions = []
        for uid in unit_ids:
            unit = unit_map.get(uid)
            if unit:
                questions.extend(generate_questions(unit, knowledge_units, count=2))

        if not questions:
            raise ServiceError(ErrorCode.INSUFFICIENT_DATA, "无法为选中的单元生成复习题")

        session = ReviewSession(
            user_id=user_id,
            book_id=book_id,
            review_type=review_type,
            questions=questions,
        )
        await self._save_session(session)
        return session

    async def submit_review_answer(
        self,
        session_id: str,
        question_id: str,
        answer: str,
        response_time: float = 0.0,
        avg_response_time: float = 30.0,
        user_id: str = "anonymous",
        confidence_level: int = 0,
    ) -> ReviewFeedback:
        """提交复习答案并获取反馈。

        Args:
            confidence_level: 信心等级 1-3（0=未提供，不启用校准）
        """
        session_result = await self.db.execute(
            select(ReviewSessionModel).where(ReviewSessionModel.id == session_id)
        )
        session_row = session_result.scalar_one_or_none()
        if session_row is None:
            raise ServiceError(ErrorCode.NOT_FOUND, "复习会话不存在")

        questions = await self._load_session_questions(session_id)
        if not questions:
            raise ServiceError(ErrorCode.NOT_FOUND, "复习会话不存在")

        question = next((q for q in questions if q.id == question_id), None)
        if not question:
            raise ServiceError(ErrorCode.NOT_FOUND, "问题不存在")

        question.user_answer = answer
        question.answered_at = datetime.now(timezone.utc)

        is_correct = check_answer(question.correct_answer, answer, question.question_type)
        question.is_correct = is_correct

        mastery = await self._get_mastery(user_id, question.unit_id)
        rep = mastery.review_count if mastery else 0
        ef = mastery.ease_factor if mastery else 2.5
        iv = mastery.interval_days if mastery else 1

        quality = quality_from_correctness(is_correct, response_time, avg_response_time)
        new_interval, new_ease, new_rep = calculate_next_review(
            quality=quality, repetitions=rep, ease_factor=ef, interval=iv,
        )

        mastery_change = mastery_delta(quality, mastery.mastery_score if mastery else 0.0)

        # 校准调整：根据信心与正确性差异调整掌握度变化
        calib_feedback = ""
        if 1 <= confidence_level <= 3:
            calib_factor, calib_feedback = calibration_adjustment(confidence_level, is_correct)
            mastery_change = round(mastery_change * calib_factor, 4)

        book_id = session_row.book_id or ""
        await self._upsert_mastery(user_id, question.unit_id, mastery_change,
                                   new_interval, new_ease, new_rep, book_id=book_id)

        await self._save_session(ReviewSession(
            id=session_id, user_id=session_row.user_id, book_id=book_id,
            review_type=session_row.review_type, questions=questions,
            started_at=session_row.started_at,
        ))

        next_review_at = datetime.now(timezone.utc) + timedelta(days=new_interval)
        return ReviewFeedback(
            is_correct=is_correct,
            correct_answer=question.correct_answer,
            explanation=f"知识点：{question.question}",
            next_review_at=next_review_at,
            mastery_change=mastery_change,
            calibration_feedback=calib_feedback or None,
        )

    def assess_mastery(
        self,
        user_id: str,
        unit_id: str,
        review_history: List[Dict],
        confused_count: int = 0,
    ) -> MasteryAssessment:
        """评估知识单元的掌握度"""
        if not review_history:
            return evaluate_mastery(
                unit_id=unit_id, correct_count=0, total_count=0,
                response_times=[], avg_response_time=30.0,
                consistency_scores=[], confused_count=confused_count,
            )
        correct_count = sum(1 for r in review_history if r.get('is_correct', False))
        total_count = len(review_history)
        response_times = [r.get('response_time', 30.0) for r in review_history]
        avg_time = sum(response_times) / len(response_times) if response_times else 30.0
        consistency_scores = [r.get('score', 0.5) for r in review_history]
        return evaluate_mastery(
            unit_id=unit_id, correct_count=correct_count, total_count=total_count,
            response_times=response_times, avg_response_time=avg_time,
            consistency_scores=consistency_scores, confused_count=confused_count,
        )

    # ===== 自由回忆（Free Recall） =====

    async def start_free_recall(
        self,
        user_id: str,
        book_id: str,
        unit_ids: List[str],
        knowledge_units: List[KnowledgeUnit],
    ) -> ReviewSession:
        """开始自由回忆复习会话"""
        unit_map = {u.id: u for u in knowledge_units}
        questions = []
        for uid in unit_ids:
            unit = unit_map.get(uid)
            if not unit:
                continue
            ref_points = []
            if unit.key_points:
                for kp in unit.key_points[:5]:
                    if hasattr(kp, 'title') and callable(kp.title):
                        ref_points.append(kp.title())
                    elif hasattr(kp, 'title'):
                        ref_points.append(kp.title)
                    else:
                        ref_points.append(str(kp))
            if not ref_points and unit.summary:
                ref_points = [unit.summary[:100]]

            # 构建概念列表
            concepts_list = []
            if unit.concepts:
                for c in unit.concepts:
                    if hasattr(c, 'name'):
                        concepts_list.append(c.name)
                    else:
                        concepts_list.append(str(c))

            questions.append(ReviewQuestion(
                unit_id=unit.id,
                question=f"请回忆「{unit.title}」的所有要点，不看任何提示，写出你记得的内容：",
                question_type="free_recall",
                correct_answer="; ".join(ref_points),
                recall_context={
                    "title": unit.title,
                    "summary": unit.summary or "",
                    "key_points": ref_points,
                    "concepts": concepts_list,
                },
            ))

        if not questions:
            raise ServiceError(ErrorCode.INSUFFICIENT_DATA, "无法为选中的单元创建回忆练习")

        session = ReviewSession(
            user_id=user_id,
            book_id=book_id,
            review_type="free_recall",
            questions=questions,
        )
        await self._save_session(session)
        return session

    async def submit_free_recall_answer(
        self,
        session_id: str,
        question_id: str,
        answer: str,
        user_id: str = "anonymous",
    ) -> FreeRecallResult:
        """提交自由回忆答案并评估"""
        questions = await self._load_session_questions(session_id)
        question = next((q for q in questions if q.id == question_id), None)
        if not question:
            raise ServiceError(ErrorCode.NOT_FOUND, "问题不存在")

        ctx = question.recall_context or {}
        ref_points = ctx.get("key_points", [])

        # 尝试 LLM 评估
        from app.modules.review.prompts import FREE_RECALL_ASSESS_PROMPT
        prompt = FREE_RECALL_ASSESS_PROMPT.format(
            unit_title=ctx.get("title", ""),
            summary=ctx.get("summary", "")[:500],
            key_points="\n".join(f"- {p}" for p in ref_points),
            concepts="\n".join(f"- {c}" for c in ctx.get("concepts", [])),
            student_recalled=answer[:3000],
        )
        try:
            llm_client = self._get_llm_client()
            response = await llm_client.chat_json(
                messages=[LLMMessage(role="user", content=prompt)],
                temperature=0.1,
            )
            result = response if isinstance(response, dict) else json.loads(response)
        except Exception:
            # 降级到本地评估
            from app.modules.review.helpers import evaluate_free_recall
            result = evaluate_free_recall(answer, ref_points, ctx.get("summary", ""))

        # 计算掌握度变化
        overall_score = result.get("overall_score", 50)
        quality = max(0, min(5, round(overall_score / 20)))
        mastery = await self._get_mastery(user_id, question.unit_id)
        rep = mastery.review_count if mastery else 0
        ef = mastery.ease_factor if mastery else 2.5
        iv = mastery.interval_days if mastery else 1

        new_interval, new_ease, new_rep = calculate_next_review(quality, rep, ef, iv)
        mastery_change_value = mastery_delta(quality, mastery.mastery_score if mastery else 0.0)

        session_result = await self.db.execute(
            select(ReviewSessionModel).where(ReviewSessionModel.id == session_id)
        )
        session_row = session_result.scalar_one_or_none()
        book_id = session_row.book_id if session_row else ""

        await self._upsert_mastery(user_id, question.unit_id, mastery_change_value,
                                   new_interval, new_ease, new_rep, book_id=book_id)

        # 更新题目状态
        question.user_answer = answer
        question.is_correct = overall_score >= 60
        question.answered_at = datetime.now(timezone.utc)
        await self._save_session(ReviewSession(
            id=session_id, user_id=user_id, book_id=book_id,
            review_type="free_recall", questions=questions,
            started_at=session_row.started_at if session_row else datetime.now(timezone.utc),
        ))

        return FreeRecallResult(
            question_id=question_id,
            unit_id=question.unit_id,
            coverage=result.get("coverage", 0),
            accuracy=result.get("accuracy", 0),
            depth=result.get("depth", 0),
            overall_score=overall_score,
            recalled_points=[RecalledPoint(**p) if isinstance(p, dict) else p
                             for p in result.get("recalled_points", [])],
            missed_points=result.get("missed_points", []),
            incorrect_points=result.get("incorrect_points", []),
            gap_report=result.get("gap_report", ""),
            mastery_change=mastery_change_value,
            next_review_at=datetime.now(timezone.utc) + timedelta(days=new_interval),
        )

    async def start_exam(
        self,
        user_id: str,
        book_id: str,
        chapter_ids: List[str],
        config: ExamConfig,
        knowledge_units: List[KnowledgeUnit],
        mastery_records: List[MasteryRecord],
        confused_unit_ids: Optional[List[str]] = None,
    ) -> ReviewSession:
        """开始考前模式"""
        session = create_exam_session(
            user_id=user_id, book_id=book_id, chapter_ids=chapter_ids,
            config=config, knowledge_units=knowledge_units,
            mastery_records=mastery_records, confused_unit_ids=confused_unit_ids,
        )
        await self._save_session(session)
        return session

    async def submit_exam(
        self,
        session_id: str,
        answers: Dict[str, str],
        user_id: str = "anonymous",
    ) -> ExamResult:
        """提交考试答案，并更新所有题目的掌握度"""
        questions = await self._load_session_questions(session_id)
        if not questions:
            raise ServiceError(ErrorCode.NOT_FOUND, "考试会话不存在")

        session_result = await self.db.execute(
            select(ReviewSessionModel).where(ReviewSessionModel.id == session_id)
        )
        session_row = session_result.scalar_one_or_none()
        book_id = session_row.book_id if session_row else ""

        session = ReviewSession(
            id=session_id, user_id=user_id, book_id=book_id,
            review_type='exam', questions=questions,
        )
        session.ended_at = datetime.now(timezone.utc)
        result = evaluate_exam(session, answers)

        for question in session.questions:
            mastery = await self._get_mastery(user_id, question.unit_id)
            rep = mastery.review_count if mastery else 0
            ef = mastery.ease_factor if mastery else 2.5
            iv = mastery.interval_days if mastery else 1
            quality = quality_from_correctness(question.is_correct, 0, 30.0)
            new_interval, new_ease, new_rep = calculate_next_review(
                quality=quality, repetitions=rep, ease_factor=ef, interval=iv,
            )
            mastery_change = mastery_delta(quality, mastery.mastery_score if mastery else 0.0)
            await self._upsert_mastery(user_id, question.unit_id,
                                       mastery_change, new_interval, new_ease, new_rep,
                                       book_id=book_id)

        await self._save_session(session)
        return result

    def export(
        self,
        book_title: str,
        export_format: ExportFormat,
        chapters: List[Dict],
        knowledge_units: List[Dict],
        mastery_records: Dict[str, Dict],
        wrong_questions: Optional[List[Dict]] = None,
    ) -> ExportResult:
        """导出复习资料"""
        if export_format == ExportFormat.MARKDOWN:
            return export_markdown(book_title, chapters, knowledge_units, mastery_records)
        elif export_format == ExportFormat.ANKI:
            return export_anki(book_title, knowledge_units, mastery_records)
        elif export_format == ExportFormat.WRONG_ANSWERS:
            return export_wrong_answers(book_title, wrong_questions or [])
        elif export_format == ExportFormat.MIND_MAP_MERMAID:
            return export_mindmap_mermaid(book_title, chapters, knowledge_units, mastery_records)
        elif export_format == ExportFormat.MIND_MAP_PLANTUML:
            return export_mindmap_plantuml(book_title, chapters, knowledge_units, mastery_records)
        else:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, f"不支持的导出格式：{export_format}")


def _generate_review_question(unit: KnowledgeUnit) -> ReviewQuestion:
    """根据知识单元生成复习题"""
    if unit.key_points:
        return ReviewQuestion(
            unit_id=unit.id,
            question=f"请解释以下概念：{unit.title}",
            question_type='short_answer',
            correct_answer="; ".join(unit.key_points[:3]) if isinstance(unit.key_points, list) else str(unit.key_points)[:200],
        )
    elif unit.summary:
        return ReviewQuestion(
            unit_id=unit.id,
            question=f"请简述：{unit.title}",
            question_type='short_answer',
            correct_answer=unit.summary[:200],
        )
    else:
        return ReviewQuestion(
            unit_id=unit.id,
            question=f"请描述：{unit.title}",
            question_type='short_answer',
            correct_answer=unit.content[:200],
        )


