import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.db.models import BookModel, ChapterModel, KnowledgeUnitModel, UserModel
from app.modules.learning_assets.context_builder import build_analysis_context


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
                title="生物",
                author="测试",
                file_path="/tmp/t.txt",
                file_type="txt",
                file_size_bytes=10,
            )
        )
        session.add(
            ChapterModel(
                id="ch-1",
                book_id="book-1",
                title="第一章",
                chapter_number=1,
                order_index=0,
                summary="章摘要",
            )
        )
        session.add(
            KnowledgeUnitModel(
                id="unit-1",
                book_id="book-1",
                chapter_id="ch-1",
                title="光合",
                content="光合作用是植物利用光能的过程。",
                order_index=0,
                char_offset_start=0,
                char_offset_end=20,
                concepts='["叶绿体"]',
            )
        )
        session.add(
            KnowledgeUnitModel(
                id="unit-2",
                book_id="book-1",
                chapter_id="ch-1",
                title="呼吸",
                content="呼吸作用释放能量。",
                order_index=1,
                char_offset_start=20,
                char_offset_end=40,
            )
        )
        await session.commit()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_build_context_includes_unit_blocks(db_session: AsyncSession):
    ctx = await build_analysis_context(db_session, "unit-1")
    assert ctx.unit_id == "unit-1"
    assert ctx.document_revision_id
    assert ctx.unit_blocks
    assert "光合" in ctx.unit_text
    assert "生物" in ctx.book_context_text
    assert ctx.sent_block_ids
    pipeline_ctx = ctx.to_pipeline_ctx()
    assert pipeline_ctx["blocks"]
