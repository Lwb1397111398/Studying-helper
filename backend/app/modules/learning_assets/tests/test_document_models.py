"""Document / Revision / Block ORM 与 AnalysisJob 基础测试。"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.db.models import (
    AnalysisJobModel,
    BookModel,
    DocumentBlockModel,
    DocumentModel,
    DocumentRevisionModel,
    UserModel,
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
                title="t",
                file_path="/tmp/t.txt",
                file_type="txt",
                file_size_bytes=10,
            )
        )
        await session.commit()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_document_block_belongs_to_revision(db_session: AsyncSession):
    doc = DocumentModel(
        id="doc_1",
        book_id="book-1",
        source_type="txt",
        source_uri="/tmp/t.txt",
        status="active",
    )
    rev = DocumentRevisionModel(
        id="rev_1",
        document_id="doc_1",
        revision_no=1,
        source_hash="sha256:abc",
        parser_version="test",
        normalization_version="v1",
        status="active",
    )
    blk = DocumentBlockModel(
        id="blk_1",
        document_revision_id="rev_1",
        chapter_id=None,
        block_type="paragraph",
        ordinal=0,
        text="Hello",
        text_hash="h1",
    )
    db_session.add_all([doc, rev, blk])
    await db_session.commit()

    rows = (
        await db_session.execute(
            select(DocumentBlockModel).where(
                DocumentBlockModel.document_revision_id == "rev_1"
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].text == "Hello"


@pytest.mark.asyncio
async def test_analysis_job_idempotency_unique(db_session: AsyncSession):
    job = AnalysisJobModel(
        id="job_1",
        scope_type="unit",
        scope_id="unit-1",
        status="queued",
        idempotency_key="unit_analyze:unit-1:h:v1",
    )
    db_session.add(job)
    await db_session.commit()

    dup = AnalysisJobModel(
        id="job_2",
        scope_type="unit",
        scope_id="unit-1",
        status="queued",
        idempotency_key="unit_analyze:unit-1:h:v1",
    )
    db_session.add(dup)
    with pytest.raises(Exception):
        await db_session.commit()
    await db_session.rollback()
