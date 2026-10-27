"""KnowledgeUnit → DocumentBlock 回填。"""

import pytest
import pytest_asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.db.models import (
    BookModel,
    ChapterModel,
    DocumentBlockModel,
    KnowledgeUnitModel,
    UserModel,
)
from app.modules.learning_assets.block_builder import (
    ensure_document_blocks_for_book,
    get_blocks_for_unit,
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
                title="定义",
                content="光合作用是植物利用光能把二氧化碳和水转化为有机物的过程。",
                order_index=0,
                char_offset_start=0,
                char_offset_end=30,
            )
        )
        session.add(
            KnowledgeUnitModel(
                id="unit-2",
                book_id="book-1",
                chapter_id="ch-1",
                title="条件",
                content="该过程需要叶绿体和可见光。",
                order_index=1,
                char_offset_start=30,
                char_offset_end=50,
            )
        )
        await session.commit()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_backfill_blocks_from_units(db_session: AsyncSession):
    rev_id = await ensure_document_blocks_for_book(db_session, "book-1")
    await db_session.commit()

    blocks = (
        await db_session.execute(
            select(DocumentBlockModel)
            .where(DocumentBlockModel.document_revision_id == rev_id)
            .order_by(DocumentBlockModel.ordinal)
        )
    ).scalars().all()
    assert len(blocks) == 2
    assert all(b.text for b in blocks)

    rev_id2 = await ensure_document_blocks_for_book(db_session, "book-1")
    assert rev_id2 == rev_id

    count = (
        await db_session.execute(
            select(func.count()).select_from(DocumentBlockModel).where(
                DocumentBlockModel.document_revision_id == rev_id
            )
        )
    ).scalar()
    assert count == 2


@pytest.mark.asyncio
async def test_get_blocks_for_unit(db_session: AsyncSession):
    await ensure_document_blocks_for_book(db_session, "book-1")
    await db_session.commit()
    blocks = await get_blocks_for_unit(db_session, "unit-1")
    assert len(blocks) == 1
    assert "光合" in blocks[0].text
