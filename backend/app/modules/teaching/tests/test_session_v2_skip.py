"""skip 不产生 mastered；visited_only 不写 mastery。"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.db.models import (
    BookModel,
    ChapterModel,
    KnowledgeUnitModel,
    MasteryRecordModel,
    UserModel,
)
from app.modules.learning_assets.pipeline import analyze_unit
from app.modules.teaching import state_machine_v2 as sm
from app.modules.teaching.session_v2_service import apply_event, start_session_v2


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
                title="t",
                file_path="/tmp/t.txt",
                file_type="txt",
                file_size_bytes=1,
            )
        )
        session.add(
            ChapterModel(
                id="ch-1", book_id="book-1", title="c", chapter_number=1, order_index=0
            )
        )
        session.add(
            KnowledgeUnitModel(
                id="unit-1",
                book_id="book-1",
                chapter_id="ch-1",
                title="u",
                content="核心结论：能量守恒。",
                order_index=0,
                char_offset_start=0,
                char_offset_end=10,
            )
        )
        await session.commit()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_assessment_skip_does_not_write_mastery(db_session: AsyncSession):
    await analyze_unit(db_session, "unit-1")
    await db_session.commit()
    ts = await start_session_v2(
        db_session, user_id="anonymous", book_id="book-1", unit_id="unit-1"
    )
    ts = await apply_event(db_session, ts.id, sm.ASSESSMENT_SKIPPED)
    # reflect/schedule may auto-complete with visited_only
    await db_session.commit()
    assert ts.completion_status in ("visited_only", "in_progress") or "do_not" in str(
        ts.completion_status
    )
    # even if completed path, mastery must not be projected for skip
    # force complete path check: if state completed with visited_only, mastery absent
    if ts.state_v2 == sm.COMPLETED:
        assert ts.completion_status == "visited_only"
    mastery = (
        await db_session.execute(
            select(MasteryRecordModel).where(
                MasteryRecordModel.knowledge_unit_id == "unit-1"
            )
        )
    ).scalar_one_or_none()
    assert mastery is None
