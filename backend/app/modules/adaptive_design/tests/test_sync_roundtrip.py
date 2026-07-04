"""AID 三表同步往返测试 - 验证 export/import 数据一致"""

import json

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.common.llm_client import OpenAIClient
from app.db.database import Base
from app.db.models import (
    UserModel, BookModel, ChapterModel, KnowledgeUnitModel,
    LearnerIntentProfileModel, TeachingDesignModel, ModuleMicroPlanModel,
)
from app.modules.adaptive_design.service import AIDService
from app.modules.sync.service import SyncService


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        await _seed(session)
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _seed(session):
    now = datetime.now(timezone.utc)
    session.add(UserModel(id="anonymous", username="user", created_at=now, updated_at=now))
    session.add(BookModel(
        id="book-1", user_id="anonymous", title="T", file_path="t.txt",
        file_type="txt", file_size_bytes=100, reading_motivation="兴趣入门",
        created_at=now, updated_at=now,
    ))
    session.add(ChapterModel(id="ch-1", book_id="book-1", title="第一章",
                             chapter_number=1, order_index=0, level=1))
    session.add(ChapterModel(id="ch-2", book_id="book-1", title="第二章",
                             chapter_number=2, order_index=1, level=1))
    # 两单元共享概念「线性表」
    session.add(KnowledgeUnitModel(
        id="unit-1", book_id="book-1", chapter_id="ch-1", title="数组",
        content="x", order_index=0, char_offset_start=0, char_offset_end=1,
        summary="数组是线性表", difficulty_level=2, importance_score=0.8,
        concepts=json.dumps(["数组", "线性表"]), prerequisites=json.dumps([]),
    ))
    session.add(KnowledgeUnitModel(
        id="unit-2", book_id="book-1", chapter_id="ch-2", title="链表",
        content="x", order_index=1, char_offset_start=1, char_offset_end=2,
        summary="链表也是线性表", difficulty_level=3, importance_score=0.7,
        concepts=json.dumps(["链表", "线性表"]), prerequisites=json.dumps(["unit-1"]),
    ))
    await session.flush()


def _mk_llm():
    return OpenAIClient(api_key="", model="gpt-4o-mini", base_url="http://localhost")


async def _build_aid_data(db):
    """用 AIDService 生成画像+设计+微观编排"""
    svc = AIDService(_mk_llm(), db)
    await svc.get_or_create_profile("book-1")
    await svc.confirm_profile("book-1")
    await svc.generate_macro_design("book-1")
    design = await svc.get_design("book-1")
    await svc.generate_micro_plan(design.id, 0)


class TestAIDSyncRoundtrip:
    """AID 三表 export→import 数据一致性"""

    @pytest.mark.asyncio
    async def test_export_contains_aid_tables(self, db_session):
        await _build_aid_data(db_session)
        pkg = await SyncService(db_session).export_book("anonymous", "book-1")
        assert len(pkg.learner_intent_profiles) == 1
        assert len(pkg.teaching_designs) == 1
        assert len(pkg.module_micro_plans) >= 1

    @pytest.mark.asyncio
    async def test_roundtrip_preserves_unit_cognitive_hint(self, db_session):
        """knowledge_units.ai_cognitive_hint 应随同步包导出并导入"""
        from sqlalchemy import select

        unit = await db_session.get(KnowledgeUnitModel, "unit-1")
        unit.ai_cognitive_hint = "memorize"
        await db_session.flush()

        svc = SyncService(db_session)
        pkg = await svc.export_book("anonymous", "book-1")

        exported_unit = next(item for item in pkg.knowledge_units if item.id == "unit-1")
        assert exported_unit.ai_cognitive_hint == "memorize"

        await svc.import_package("anonymous", pkg)
        imported_hint = (
            await db_session.execute(
                select(KnowledgeUnitModel.ai_cognitive_hint).where(KnowledgeUnitModel.id == "unit-1")
            )
        ).scalar_one()
        assert imported_hint == "memorize"

    @pytest.mark.asyncio
    async def test_roundtrip_preserves_data(self, db_session):
        """export 后清空再 import，AID 数据应一致"""
        await _build_aid_data(db_session)
        svc = SyncService(db_session)
        pkg = await svc.export_book("anonymous", "book-1")

        # 记录原始数据
        orig_profile = pkg.learner_intent_profiles[0].model_copy()
        orig_design = pkg.teaching_designs[0].model_copy()
        orig_plan = pkg.module_micro_plans[0].model_copy()

        # 删除该书数据（含 AID 三表）
        await svc.import_package("anonymous", pkg)
        # 再次导出验证
        pkg2 = await svc.export_book("anonymous", "book-1")

        assert len(pkg2.learner_intent_profiles) == 1
        assert len(pkg2.teaching_designs) == 1
        assert len(pkg2.module_micro_plans) >= 1

        p2 = pkg2.learner_intent_profiles[0]
        assert p2.identity_background == orig_profile.identity_background
        assert p2.goal_depth == orig_profile.goal_depth
        assert p2.restructure_tolerance == orig_profile.restructure_tolerance
        assert p2.status == orig_profile.status

        d2 = pkg2.teaching_designs[0]
        assert d2.book_id == orig_design.book_id
        assert d2.status == orig_design.status
        assert d2.version == orig_design.version

        plan2 = pkg2.module_micro_plans[0]
        assert plan2.ordered_unit_ids_json == orig_plan.ordered_unit_ids_json
        assert plan2.module_status == orig_plan.module_status

    @pytest.mark.asyncio
    async def test_delete_book_removes_aid_data(self, db_session):
        """_delete_book_data 应删除 AID 三表"""
        from sqlalchemy import select
        await _build_aid_data(db_session)
        svc = SyncService(db_session)
        await svc._delete_book_data("book-1")

        profiles = (await db_session.execute(
            select(LearnerIntentProfileModel).where(LearnerIntentProfileModel.book_id == "book-1")
        )).scalars().all()
        designs = (await db_session.execute(
            select(TeachingDesignModel).where(TeachingDesignModel.book_id == "book-1")
        )).scalars().all()
        plans = (await db_session.execute(
            select(ModuleMicroPlanModel).where(ModuleMicroPlanModel.book_id == "book-1")
        )).scalars().all()
        assert profiles == [] and designs == [] and plans == []

    @pytest.mark.asyncio
    async def test_validate_rejects_orphan_profile(self, db_session):
        """孤立画像（book_id 不在 books 中）应被校验拒绝"""
        from app.modules.sync.schemas import (
            SyncPackage, SyncBook, SyncLearnerIntentProfile, SCHEMA_VERSION,
        )
        from datetime import datetime, timezone
        from app.common.errors import ServiceError

        now = datetime.now(timezone.utc)
        pkg = SyncPackage(
            schema_version=SCHEMA_VERSION, user_id="anonymous", source="web",
            books=[SyncBook(id="book-1", user_id="anonymous", title="T",
                            file_path="t", file_type="txt", file_size_bytes=1,
                            created_at=now, updated_at=now)],
            learner_intent_profiles=[SyncLearnerIntentProfile(
                id="p1", user_id="anonymous", book_id="other-book",  # 不在 books
                created_at=now, updated_at=now,
            )],
        )
        with pytest.raises(ServiceError):
            SyncService(db_session)._validate_package_scope(pkg)
