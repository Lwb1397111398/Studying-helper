"""AI 学习路由测试"""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base, get_db
from app.db.models import AnnotationModel, BookModel, ChapterModel, KnowledgeUnitModel, UserModel
from app.modules.ai_learning import router as learning_router
from app.modules.ai_learning.router import get_ai_analysis_llm, router


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        session.add(UserModel(id="anonymous", username="本地用户"))
        session.add(BookModel(
            id="book-1",
            user_id="anonymous",
            title="测试书籍",
            file_path="test.txt",
            file_type="txt",
            file_size_bytes=10,
        ))
        session.add(ChapterModel(
            id="chapter-1",
            book_id="book-1",
            title="第一章",
            chapter_number=1,
            order_index=0,
        ))
        session.add(KnowledgeUnitModel(
            id="unit-1",
            book_id="book-1",
            chapter_id="chapter-1",
            title="知识单元",
            content="内容",
            order_index=0,
            char_offset_start=0,
            char_offset_end=2,
        ))
        await session.commit()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.mark.asyncio
async def test_save_note_persists_annotation(client, db_session):
    resp = client.post("/api/v1/learning/units/unit-1/notes", json={"content": "我的笔记"})

    assert resp.status_code == 200
    result = await db_session.execute(
        select(AnnotationModel).where(
            AnnotationModel.user_id == "anonymous",
            AnnotationModel.knowledge_unit_id == "unit-1",
            AnnotationModel.annotation_type == "note",
        )
    )
    annotation = result.scalar_one_or_none()
    assert annotation is not None
    assert annotation.content == "我的笔记"

    get_resp = client.get("/api/v1/learning/units/unit-1/notes")
    assert get_resp.status_code == 200
    assert get_resp.json() == {"unit_id": "unit-1", "content": "我的笔记"}


@pytest.mark.asyncio
async def test_start_learning_enqueues_background_job(client, monkeypatch):
    started_jobs = []

    async def fake_llm():
        return object()

    async def fake_run_learning_job(**kwargs):
        started_jobs.append(kwargs)

    client.app.dependency_overrides[get_ai_analysis_llm] = fake_llm
    monkeypatch.setattr(learning_router, "_run_learning_job", fake_run_learning_job)

    resp = client.post("/api/v1/learning/book-1/learn", json={})

    assert resp.status_code == 202
    body = resp.json()
    assert body == {
        "book_id": "book-1",
        "status": "in_progress",
        "total_units": 1,
        "message": "AI 学习任务已开始",
    }
    assert len(started_jobs) == 1
    assert started_jobs[0]["book_id"] == "book-1"
    assert learning_router._learning_progress["book-1"]["status"] == "in_progress"
