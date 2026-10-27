import json

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.db.models import (
    BookModel,
    ChapterModel,
    KnowledgeUnitModel,
    UnitLearningAssetModel,
    UserModel,
)
from app.modules.learning_assets.pipeline import analyze_unit


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
async def test_rule_pipeline_publishes_active_asset(db_session: AsyncSession):
    asset = await analyze_unit(db_session, "unit-1")
    await db_session.commit()

    assert asset.status == "active"
    assert asset.readiness_status in ("teachable", "degraded_teachable")
    payload = json.loads(asset.payload_json)
    assert payload["claims"]
    assert payload["learning_objectives"]
    assert payload["assessment_items"]

    # dual write
    unit = (
        await db_session.execute(
            select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == "unit-1")
        )
    ).scalar_one()
    assert unit.summary or unit.explanation

    # idempotent second call same asset active single
    asset2 = await analyze_unit(db_session, "unit-1")
    await db_session.commit()
    actives = (
        await db_session.execute(
            select(UnitLearningAssetModel).where(
                UnitLearningAssetModel.unit_id == "unit-1",
                UnitLearningAssetModel.status == "active",
            )
        )
    ).scalars().all()
    assert len(actives) == 1
    assert asset2.id == actives[0].id
