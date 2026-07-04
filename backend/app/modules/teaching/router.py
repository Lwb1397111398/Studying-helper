"""教学API路由"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ServiceError, ErrorCode, ERROR_STATUS_MAP
from app.db.database import get_db
from app.db.models import KnowledgeUnitModel, TeachingSessionModel
from app.deps import get_teaching_llm_client
from app.modules.ai_learning.schemas import LearnedUnit, Concept, KeyPoint
from app.modules.teaching.service import TeachingService
from app.modules.teaching.schemas import TeachingMessage, UserQuestion, Annotation, SessionTest

router = APIRouter(prefix="/api/v1/teaching", tags=["teaching"])

DEFAULT_USER_ID = "anonymous"


class StartSessionRequest(BaseModel):
    plan_session_id: str = ""
    book_id: str
    unit_ids: List[str]


class AskQuestionRequest(BaseModel):
    question: str


class SubmitAnswerRequest(BaseModel):
    answer: str


class JumpToUnitRequest(BaseModel):
    unit_id: str


class AnnotationRequest(BaseModel):
    unit_id: str
    annotation_type: str
    content: Optional[str] = None
    related_concepts: List[str] = []
    example: Optional[str] = None
    cornell_cues: Optional[List[str]] = None
    cornell_summary: Optional[str] = None


class SubmitTestRequest(BaseModel):
    answers: List[str]


async def _load_learned_units(db: AsyncSession, unit_ids: List[str]) -> List[LearnedUnit]:
    """从DB加载已学习单元"""
    if not unit_ids:
        return []
    result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.id.in_(unit_ids))
    )
    db_units = result.scalars().all()
    units = []
    for u in db_units:
        concepts = []
        if u.concepts:
            try:
                raw = json.loads(u.concepts)
                for c in raw:
                    if isinstance(c, dict):
                        concepts.append(Concept(
                            name=c.get("name", ""),
                            definition=c.get("definition", ""),
                            examples=c.get("examples", []),
                            related_concepts=c.get("related_concepts", []),
                        ))
                    else:
                        concepts.append(Concept(name=str(c), definition=""))
            except (json.JSONDecodeError, TypeError):
                pass
        # 解析 key_points（兼容字符串列表和对象列表两种格式）
        key_points = []
        if u.key_points:
            try:
                raw_kps = json.loads(u.key_points)
                for kp in raw_kps:
                    if isinstance(kp, dict):
                        key_points.append(KeyPoint(
                            title=kp.get("title", ""),
                            explanation=kp.get("explanation", ""),
                            examples=kp.get("examples", []),
                        ))
                    else:
                        key_points.append(KeyPoint(title=str(kp)))
            except (json.JSONDecodeError, TypeError):
                pass

        units.append(LearnedUnit(
            unit_id=u.id,
            book_id=u.book_id,
            summary=u.summary or "",
            key_points=key_points,
            concepts=concepts,
            difficulty_level=u.difficulty_level or 1,
            importance_score=u.importance_score or 0.5,
            prerequisites=[],
            ai_cognitive_hint=u.ai_cognitive_hint,
        ))
    return units


async def _get_units_for_session(db: AsyncSession, session_id: str) -> List[LearnedUnit]:
    """通过会话ID加载关联的知识单元"""
    result = await db.execute(
        select(TeachingSessionModel).where(TeachingSessionModel.id == session_id)
    )
    db_session = result.scalar_one_or_none()
    if not db_session:
        raise HTTPException(status_code=404, detail="会话不存在")

    unit_ids = json.loads(db_session.unit_ids)
    return await _load_learned_units(db, unit_ids)


def _get_service(
    db: AsyncSession = Depends(get_db),
    llm_client=Depends(get_teaching_llm_client),
) -> TeachingService:
    return TeachingService(llm_client=llm_client, db=db)


@router.post("/sessions/start")
async def start_session(
    request: StartSessionRequest,
    svc: TeachingService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
):
    """开始教学会话（自动排序）

    优先级：AID 教学设计（含跨章节重组+拓扑+重构标注）> KG 拓扑排序 > 原始请求顺序
    """
    try:
        # 1. 优先使用 AID 教学设计的当前模块重排单元（若已生成设计）
        unit_ids = request.unit_ids
        try:
            from app.modules.adaptive_design.service import AIDService
            from app.deps import get_aid_llm_client
            aid_llm = await get_aid_llm_client()
            aid_svc = AIDService(llm_client=aid_llm, db=db)
            aid_unit_ids = await aid_svc.get_active_module_ordered_unit_ids(
                request.book_id, DEFAULT_USER_ID
            )
            if aid_unit_ids:
                # AID 已重组：用其顺序，并补上 AID 未覆盖但请求里有的单元
                remaining = [uid for uid in request.unit_ids if uid not in aid_unit_ids]
                unit_ids = aid_unit_ids + remaining
        except Exception as e:
            print(f"AID 教学设计获取失败，回退拓扑排序: {e}")

        # 2. 无 AID 设计时，尝试知识图谱拓扑排序
        if not unit_ids or unit_ids == request.unit_ids:
            try:
                from app.modules.knowledge_graph.service import KnowledgeGraphService
                kg_service = KnowledgeGraphService(db)
                ordered_unit_ids = await kg_service.get_topological_order(request.book_id)

                # 过滤出请求的单元并保持顺序
                if ordered_unit_ids:
                    unit_ids = [uid for uid in ordered_unit_ids if uid in request.unit_ids]
                    # 如果有未在图谱中的单元，追加到末尾
                    remaining = [uid for uid in request.unit_ids if uid not in unit_ids]
                    unit_ids.extend(remaining)
            except Exception as e:
                # 知识图谱不存在或出错时，使用原始顺序
                print(f"拓扑排序失败，使用原始顺序: {e}")
                unit_ids = request.unit_ids

        units = await _load_learned_units(db, unit_ids)
        session = await svc.start_session(
            user_id=DEFAULT_USER_ID,
            plan_session_id=request.plan_session_id,
            book_id=request.book_id,
            unit_ids=unit_ids,
            units=units,
        )
        return session.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/sessions/active")
async def get_active_session(
    book_id: str,
    svc: TeachingService = Depends(_get_service),
):
    """获取某本书的活跃教学会话"""
    session = await svc.get_active_session(DEFAULT_USER_ID, book_id)
    if not session:
        raise HTTPException(status_code=404, detail="没有活跃会话")
    return session.model_dump()


@router.get("/sessions/{session_id}/next-message")
async def get_next_message(
    session_id: str,
    svc: TeachingService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
):
    """获取下一条教学消息"""
    try:
        units = await _get_units_for_session(db, session_id)
        message = await svc.get_next_message(session_id, units)
        return message.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/sessions/{session_id}/ask")
async def ask_question(
    session_id: str,
    request: AskQuestionRequest,
    svc: TeachingService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
):
    """提问"""
    try:
        units = await _get_units_for_session(db, session_id)
        answer = await svc.answer_question(session_id, request.question, units)
        return answer.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/sessions/{session_id}/answer")
async def submit_answer(
    session_id: str,
    request: SubmitAnswerRequest,
    svc: TeachingService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
):
    """学生提交回答，AI 评估掌握程度"""
    try:
        units = await _get_units_for_session(db, session_id)
        result = await svc.submit_answer(session_id, request.answer, units)
        return result.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/sessions/{session_id}/continue")
async def continue_to_next_phase(
    session_id: str,
    svc: TeachingService = Depends(_get_service),
):
    """手动推进到下一教学阶段"""
    try:
        session = await svc.continue_to_next_phase(session_id)
        return session.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/sessions/{session_id}/jump-to-unit")
async def jump_to_unit(
    session_id: str,
    request: JumpToUnitRequest,
    svc: TeachingService = Depends(_get_service),
):
    """跳转到指定知识单元"""
    try:
        session = await svc.jump_to_unit(session_id, request.unit_id)
        return session.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/sessions/{session_id}/clear")
async def clear_messages(
    session_id: str,
    svc: TeachingService = Depends(_get_service),
):
    """清空会话消息，重置到当前单元起始阶段"""
    try:
        session = await svc.clear_messages(session_id)
        return session.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    svc: TeachingService = Depends(_get_service),
):
    """获取会话所有消息"""
    try:
        messages = await svc.get_session_messages(session_id)
        return [m.model_dump() for m in messages]
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/annotations")
async def add_annotation(
    request: AnnotationRequest,
    svc: TeachingService = Depends(_get_service),
):
    """添加笔记/标记"""
    try:
        annotation = await svc.add_annotation(
            user_id=DEFAULT_USER_ID,
            unit_id=request.unit_id,
            annotation_type=request.annotation_type,
            content=request.content,
            related_concepts=request.related_concepts,
            example=request.example,
            cornell_cues=request.cornell_cues,
            cornell_summary=request.cornell_summary,
        )
        return annotation.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


class RunTestRequest(BaseModel):
    weak_points: List[str] = []


@router.post("/sessions/{session_id}/test")
async def run_test(
    session_id: str,
    request: Optional[RunTestRequest] = None,
    svc: TeachingService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
):
    """运行测试（支持薄弱点聚焦）"""
    try:
        units = await _get_units_for_session(db, session_id)
        weak_points = request.weak_points if request else []
        test = await svc.run_session_test(session_id, units, weak_points)
        return test.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/tests/{test_id}/submit")
async def submit_test(
    test_id: str,
    request: SubmitTestRequest,
    svc: TeachingService = Depends(_get_service),
):
    """提交测试答案"""
    try:
        test = await svc.submit_test_answers(test_id, request.answers)
        return test.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    svc: TeachingService = Depends(_get_service),
):
    """完成会话"""
    try:
        summary = await svc.complete_session(session_id)
        return summary.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


class AdaptStrategyRequest(BaseModel):
    questions_asked: int = 0
    correct_rate: float = 0.0
    confusing_marks: int = 0
    avg_response_time: float = 0.0


@router.post("/sessions/{session_id}/adapt-strategy")
async def adapt_strategy(
    session_id: str,
    request: AdaptStrategyRequest,
    svc: TeachingService = Depends(_get_service),
):
    """根据学生互动调整教学策略"""
    try:
        strategy = await svc.adapt_strategy(session_id, request.model_dump())
        return strategy.model_dump()
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


class CornellNotesRequest(BaseModel):
    unit_id: str
    notes_content: str


class CornellSummaryRequest(BaseModel):
    unit_id: str
    notes_content: str


@router.post("/annotations/cornell/cues")
async def generate_cornell_cues(
    request: CornellNotesRequest,
    svc: TeachingService = Depends(_get_service),
):
    """AI 生成康奈尔笔记线索栏"""
    try:
        result = await svc.generate_cornell_cues(
            unit_id=request.unit_id,
            notes_content=request.notes_content,
        )
        return result
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.post("/annotations/cornell/summary")
async def generate_cornell_summary(
    request: CornellSummaryRequest,
    svc: TeachingService = Depends(_get_service),
):
    """AI 生成康奈尔笔记总结栏"""
    try:
        result = await svc.generate_cornell_summary(
            unit_id=request.unit_id,
            notes_content=request.notes_content,
        )
        return result
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/annotations/cornell/{unit_id}")
async def get_cornell_notes(
    unit_id: str,
    svc: TeachingService = Depends(_get_service),
):
    """获取知识单元的康奈尔笔记"""
    try:
        result = await svc.get_cornell_notes(unit_id=unit_id)
        return result
    except ServiceError as e:
        raise HTTPException(status_code=ERROR_STATUS_MAP.get(e.code, 500), detail=e.message)


@router.get("/stats")
async def get_teaching_stats(
    book_id: Optional[str] = None,
    days: int = 7,
    svc: TeachingService = Depends(_get_service),
):
    """获取教学统计"""
    try:
        stats = await svc.get_teaching_stats(book_id=book_id, days=days)
        return stats
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"教学统计异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取教学统计失败")


@router.get("/sessions/{session_id}/units/{unit_id}/coverage")
async def get_teaching_plan_coverage(
    session_id: str,
    unit_id: str,
    svc: TeachingService = Depends(_get_service),
):
    """获取教学计划的覆盖报告

    返回：
    - total_items: 总内容项数
    - covered_items: 已覆盖的内容项数
    - coverage_rate: 覆盖率 (0-1)
    - is_complete: 是否完成（严格模式下需要 100% 覆盖）
    - missing_items: 未覆盖的内容项列表
    - phase_coverage: 每个阶段的覆盖情况
    """
    try:
        coverage_report = svc.get_teaching_plan_coverage(session_id, unit_id)
        return coverage_report
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"获取教学计划覆盖报告异常: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取教学计划覆盖报告失败")
