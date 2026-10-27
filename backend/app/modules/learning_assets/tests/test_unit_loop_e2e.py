"""单单元闭环 E2E：回填 → 分析 → 教学 v2 → 证据 → 掌握投影。"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.db.models import (
    BookModel,
    ChapterModel,
    KnowledgeUnitModel,
    LearningEvidenceModel,
    MasteryRecordModel,
    UserModel,
)
from app.modules.learning_assets.models_domain import UnitLearningAssetPayload
from app.modules.learning_assets.pipeline import analyze_unit
from app.modules.teaching import state_machine_v2 as sm
from app.modules.teaching.session_v2_service import (
    apply_event,
    start_session_v2,
    submit_attempt,
)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with factory() as session:
        session.add(UserModel(id="anonymous", username="anon"))
        session.add(
            BookModel(
                id="book-1",
                user_id="anonymous",
                title="测试书",
                file_path="/tmp/t.txt",
                file_type="txt",
                file_size_bytes=100,
            )
        )
        session.add(
            ChapterModel(
                id="ch-1",
                book_id="book-1",
                title="第一章",
                chapter_number=1,
                order_index=0,
            )
        )
        session.add(
            KnowledgeUnitModel(
                id="unit-1",
                book_id="book-1",
                chapter_id="ch-1",
                title="光合作用",
                content="光合作用是植物利用光能把二氧化碳和水转化为有机物的过程。",
                order_index=0,
                char_offset_start=0,
                char_offset_end=40,
            )
        )
        await session.commit()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_unit_learning_loop_e2e(db_session: AsyncSession):
    asset = await analyze_unit(db_session, "unit-1")
    await db_session.commit()
    assert asset.status == "active"
    assert asset.readiness_status in ("teachable", "degraded_teachable")

    payload = UnitLearningAssetPayload.model_validate_json(asset.payload_json)
    item = next(
        i for i in payload.assessment_items if "assessment" in i.phase_usage or not i.phase_usage
    )
    # prefer assessment phase
    assess_items = [i for i in payload.assessment_items if "assessment" in (i.phase_usage or [])]
    if assess_items:
        item = assess_items[0]
    reassess_items = [
        i
        for i in payload.assessment_items
        if "reassessment" in (i.phase_usage or []) and i.id != item.id
    ]

    ts = await start_session_v2(
        db_session,
        user_id="anonymous",
        book_id="book-1",
        unit_id="unit-1",
        asset_id=asset.id,
    )
    await db_session.commit()
    assert ts.asset_id == asset.id
    assert ts.state_v2 == sm.DIAGNOSE

    ts = await apply_event(
        db_session,
        ts.id,
        sm.DIAGNOSIS_SUBMITTED,
        {"diagnosis_summary": "mixed"},
    )
    ts = await apply_event(db_session, ts.id, sm.EXPLANATION_ACKNOWLEDGED)
    assert ts.state_v2 == sm.EXPLAIN
    ts = await apply_event(db_session, ts.id, sm.EXPLANATION_ACKNOWLEDGED)
    assert ts.state_v2 == sm.GUIDED_PRACTICE
    ts = await apply_event(db_session, ts.id, sm.PRACTICE_SUBMITTED)
    assert ts.state_v2 == sm.ASSESS

    # wrong answer → repair path
    wrong = await submit_attempt(
        db_session,
        session_id=ts.id,
        user_id="anonymous",
        assessment_item_id=item.id,
        response={"answer": "完全错误的答案"},
        idempotency_key="att-wrong-1",
        source_type="assessment",
    )
    assert wrong["result"] in ("incorrect", "partial")

    ts = await apply_event(
        db_session,
        ts.id,
        sm.ASSESSMENT_SUBMITTED,
        {"required_objectives_passed": False, "repairable_gaps": True, "repair_rounds": 0},
    )
    assert ts.state_v2 == sm.REPAIR
    ts = await apply_event(db_session, ts.id, sm.REPAIR_COMPLETED)
    assert ts.state_v2 == sm.REASSESS

    re_item = reassess_items[0] if reassess_items else item
    expected = re_item.expected_answer or item.expected_answer
    ok = await submit_attempt(
        db_session,
        session_id=ts.id,
        user_id="anonymous",
        assessment_item_id=re_item.id,
        response={"answer": expected},
        idempotency_key="att-right-1",
        source_type="reassessment",
    )
    assert ok["score"] >= 0.8

    # idempotent replay
    ok2 = await submit_attempt(
        db_session,
        session_id=ts.id,
        user_id="anonymous",
        assessment_item_id=re_item.id,
        response={"answer": expected},
        idempotency_key="att-right-1",
        source_type="reassessment",
    )
    assert ok2["idempotent"] is True

    ts = await apply_event(db_session, ts.id, sm.REASSESSMENT_SUBMITTED, {})
    await db_session.commit()

    assert ts.state_v2 == sm.COMPLETED
    assert ts.completion_status == "completed_mastered"

    evidences = (
        await db_session.execute(
            select(LearningEvidenceModel).where(LearningEvidenceModel.session_id == ts.id)
        )
    ).scalars().all()
    assert len(evidences) >= 2

    mastery = (
        await db_session.execute(
            select(MasteryRecordModel).where(
                MasteryRecordModel.user_id == "anonymous",
                MasteryRecordModel.knowledge_unit_id == "unit-1",
            )
        )
    ).scalar_one_or_none()
    assert mastery is not None
    assert mastery.mastery_score >= 0.9
