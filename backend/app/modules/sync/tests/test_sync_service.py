"""数据同步服务测试"""

from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.db.models import (
    AnnotationModel,
    BookModel,
    ChapterModel,
    DailyStatsModel,
    KGEdgeModel,
    KGNodeModel,
    KnowledgeUnitModel,
    LearningEfficiencyModel,
    LearnerIntentProfileModel,
    MasteryRecordModel,
    ModuleMicroPlanModel,
    TeachingMessageModel,
    TeachingDesignModel,
    TeachingSessionModel,
    UserModel,
)
import json
from app.modules.sync.service import SyncService
from app.modules.sync.schemas import SyncPackage


ROUND4_FIXTURE = Path(__file__).resolve().parents[5] / "docs" / "samples" / "round4_sync_package.json"


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


async def _seed(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    session.add(UserModel(id="anonymous", username="本地用户", created_at=now, updated_at=now))
    session.add(
        BookModel(
            id="book-1",
            user_id="anonymous",
            title="同步测试书籍",
            file_path="test.txt",
            file_type="txt",
            file_size_bytes=100,
            parse_status="completed",
            split_status="completed",
            learn_status="completed",
            total_chapters=1,
            total_units=1,
            learned_units=1,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        ChapterModel(
            id="chapter-1",
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
            chapter_id="chapter-1",
            title="知识单元",
            content="内容",
            order_index=0,
            char_offset_start=0,
            char_offset_end=2,
            key_points='["重点"]',
            concepts='[{"name":"概念"}]',
            prerequisites='["pre-1"]',
            ai_cognitive_hint="understand",
        )
    )
    session.add(
        MasteryRecordModel(
            id="mastery-1",
            user_id="anonymous",
            knowledge_unit_id="unit-1",
            book_id="book-1",
            mastery_score=0.8,
            mastery_level="familiar",
            next_review_at=now,
            stability=3.5,
            difficulty=4.2,
            lapses=1,
            reps=4,
            last_elapsed_days=2,
            scheduled_days=6,
            algorithm="fsrs",
        )
    )
    session.add(
        AnnotationModel(
            id="annotation-1",
            user_id="anonymous",
            knowledge_unit_id="unit-1",
            annotation_type="note",
            content="笔记",
            related_concepts_json='["概念"]',
            created_at=now,
            updated_at=now,
        )
    )
    session.add(KGNodeModel(id="node-1", node_type="unit", label="A", book_id="book-1"))
    session.add(KGNodeModel(id="node-2", node_type="concept", label="B", book_id="book-1"))
    session.add(
        KGEdgeModel(
            id="edge-1",
            source_id="node-1",
            target_id="node-2",
            relation_type="contains",
            metadata_json='{"reason":"test"}',
        )
    )
    session.add(
        DailyStatsModel(
            user_id="anonymous",
            date="2026-06-07",
            total_minutes=30,
            units_learned=1,
            streak_day=1,
        )
    )
    session.add(
        TeachingSessionModel(
            id="teaching-1",
            user_id="anonymous",
            plan_session_id="plan-1",
            book_id="book-1",
            unit_ids='["unit-1"]',
            strategy_json='{"mode":"test"}',
            started_at=now,
        )
    )
    session.add(
        TeachingMessageModel(
            id="message-1",
            session_id="teaching-1",
            unit_id="unit-1",
            phase="activate",
            content="教学内容",
            assessment_json='{"score":1}',
            created_at=now,
        )
    )
    session.add(
        LearningEfficiencyModel(
            id="eff-1",
            session_id="teaching-1",
            unit_id="unit-1",
            phase="activate",
            duration_seconds=60,
            interaction_count=2,
            efficiency_score=2.0,
            created_at=now,
        )
    )
    session.add(
        LearnerIntentProfileModel(
            id="profile-1",
            user_id="anonymous",
            book_id="book-1",
            identity_background="unknown",
            goal_depth="apply_understand",
            cognitive_pref="rigorous_system",
            restructure_tolerance="moderate",
            status="confirmed",
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        TeachingDesignModel(
            id="design-1",
            user_id="anonymous",
            book_id="book-1",
            profile_id="profile-1",
            macro_design_json='{"modules":[]}',
            generated_module_count=1,
            status="active",
            version=1,
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        ModuleMicroPlanModel(
            id="micro-1",
            design_id="design-1",
            book_id="book-1",
            user_id="anonymous",
            module_index=0,
            module_title="入门模块",
            ordered_unit_ids_json='["unit-1"]',
            unit_annotations_json='[]',
            module_status="active",
            parent_design_version=1,
            created_at=now,
            updated_at=now,
        )
    )
    await session.commit()


@pytest.mark.asyncio
async def test_export_book_contains_related_data(db_session):
    package = await SyncService(db_session).export_book("anonymous", "book-1")

    assert package.schema_version == "1.0"
    assert len(package.books) == 1
    assert len(package.chapters) == 1
    assert len(package.knowledge_units) == 1
    assert len(package.kg_nodes) == 2
    assert len(package.kg_edges) == 1
    assert len(package.mastery_records) == 1
    assert len(package.annotations) == 1
    assert len(package.daily_stats) == 0
    assert len(package.teaching_sessions) == 1
    assert len(package.teaching_messages) == 1
    assert len(package.learning_efficiency) == 1
    assert len(package.learner_intent_profiles) == 1
    assert len(package.teaching_designs) == 1
    assert len(package.module_micro_plans) == 1
    assert package.knowledge_units[0].key_points == '["重点"]'
    assert package.knowledge_units[0].ai_cognitive_hint == "understand"
    assert package.mastery_records[0].algorithm == "fsrs"
    assert package.mastery_records[0].stability == 3.5
    assert package.kg_edges[0].metadata_json == '{"reason":"test"}'


@pytest.mark.asyncio
async def test_export_all_contains_user_books(db_session):
    package = await SyncService(db_session).export_all("anonymous")

    assert len(package.books) == 1
    assert package.books[0].id == "book-1"
    assert len(package.knowledge_units) == 1
    assert len(package.daily_stats) == 1


@pytest.mark.asyncio
async def test_preview_package_marks_overwritten_books(db_session):
    service = SyncService(db_session)
    package = await service.export_book("anonymous", "book-1")

    preview = await service.preview_package(package)

    assert preview.source == "web"
    assert preview.books_count == 1
    assert preview.chapters_count == 1
    assert preview.units_count == 1
    assert preview.mastery_records_count == 1
    assert preview.annotations_count == 1
    assert preview.kg_nodes_count == 2
    assert preview.kg_edges_count == 1
    assert preview.daily_stats_count == 0
    assert preview.learning_records_count == 0
    assert preview.review_sessions_count == 0
    assert preview.teaching_sessions_count == 1
    assert preview.teaching_messages_count == 1
    assert preview.user_questions_count == 0
    assert preview.session_tests_count == 0
    assert preview.learning_efficiency_count == 1
    assert preview.learner_intent_profiles_count == 1
    assert preview.teaching_designs_count == 1
    assert preview.module_micro_plans_count == 1
    assert preview.books[0].id == "book-1"
    assert preview.books[0].will_overwrite is True
    assert preview.books[0].local_title == "同步测试书籍"


@pytest.mark.asyncio
async def test_preview_rejects_child_records_outside_package_books(db_session):
    service = SyncService(db_session)
    package = await service.export_book("anonymous", "book-1")
    package.mastery_records[0].book_id = "book-outside"

    with pytest.raises(Exception) as exc_info:
        await service.preview_package(package)

    assert "同步包包含不属于导入书籍的掌握度记录" in str(exc_info.value)


@pytest.mark.asyncio
async def test_import_package_replaces_existing_book(db_session):
    service = SyncService(db_session)
    package = await service.export_book("anonymous", "book-1")
    package.books[0].title = "导入后的标题"
    package.knowledge_units[0].key_points = '["导入重点"]'

    result = await service.import_package("anonymous", package)

    book = (await db_session.execute(select(BookModel).where(BookModel.id == "book-1"))).scalar_one()
    units = list((await db_session.execute(select(KnowledgeUnitModel))).scalars().all())
    edges = list((await db_session.execute(select(KGEdgeModel))).scalars().all())
    stats = list((await db_session.execute(select(DailyStatsModel))).scalars().all())
    messages = list((await db_session.execute(select(TeachingMessageModel))).scalars().all())

    assert result.overwritten_books == ["book-1"]
    assert result.books_imported == 1
    assert result.chapters_imported == 1
    assert result.units_imported == 1
    assert result.mastery_records_imported == 1
    assert result.annotations_imported == 1
    assert result.kg_nodes_imported == 2
    assert result.kg_edges_imported == 1
    assert result.learning_records_imported == 0
    assert result.daily_stats_imported == 0
    assert result.review_sessions_imported == 0
    assert result.teaching_sessions_imported == 1
    assert result.teaching_messages_imported == 1
    assert result.user_questions_imported == 0
    assert result.session_tests_imported == 0
    assert result.learning_efficiency_imported == 1
    assert result.learner_intent_profiles_imported == 1
    assert result.teaching_designs_imported == 1
    assert result.module_micro_plans_imported == 1
    assert book.title == "导入后的标题"
    assert len(units) == 1
    assert units[0].key_points == '["导入重点"]'
    assert units[0].ai_cognitive_hint == "understand"
    assert len(edges) == 1
    assert len(stats) == 1
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_shared_round4_fixture_import_export_preserves_aid_fsrs_and_teaching_order(db_session):
    raw = ROUND4_FIXTURE.read_text(encoding="utf-8")
    package = SyncPackage.model_validate_json(raw)
    service = SyncService(db_session)

    preview = await service.preview_package(package)
    result = await service.import_package("anonymous", package)
    exported = await service.export_book("anonymous", "round4-book")

    assert preview.source == "android"
    assert preview.books_count == 1
    assert preview.units_count == 2
    assert preview.mastery_records_count == 1
    assert preview.learner_intent_profiles_count == 1
    assert preview.teaching_designs_count == 1
    assert preview.module_micro_plans_count == 1
    assert result.books_imported == 1
    assert result.units_imported == 2
    assert result.mastery_records_imported == 1
    assert result.learner_intent_profiles_imported == 1
    assert result.teaching_designs_imported == 1
    assert result.module_micro_plans_imported == 1
    assert [unit.id for unit in exported.knowledge_units] == ["round4-unit-a", "round4-unit-b"]
    assert exported.knowledge_units[0].ai_cognitive_hint == "understand"
    assert exported.knowledge_units[1].ai_cognitive_hint == "memorize"
    assert exported.mastery_records[0].algorithm == "fsrs"
    assert exported.mastery_records[0].stability == 2.5
    assert exported.module_micro_plans[0].ordered_unit_ids_json == '["round4-unit-b","round4-unit-a"]'


async def test_sync_roundtrip_preserves_mastery_lapses(db_session):
    """P1 测试 7（同步保值闭环）：mastery lapses=3 → export → import → DB 仍为 3。

    锁死"修复后 lapses 不被同步链路抹掉"；机制依据：SyncMasteryRecord 整包序列化搬运
    （backend schemas.py / Android SyncDtos.kt 均含 lapses 字段）。
    """
    raw = json.loads(ROUND4_FIXTURE.read_text(encoding="utf-8"))
    raw["mastery_records"][0]["lapses"] = 3
    package = SyncPackage.model_validate(raw)
    service = SyncService(db_session)

    await service.import_package("anonymous", package)
    exported = await service.export_book("anonymous", "round4-book")
    assert exported.mastery_records[0].lapses == 3

    # 回灌：把导出包再导入（delete+add 重放），DB 查询断言保值
    await service.import_package("anonymous", exported)
    row = (
        await db_session.execute(
            select(MasteryRecordModel).where(MasteryRecordModel.id == "round4-mastery")
        )
    ).scalar_one()
    assert row.lapses == 3
    assert row.algorithm == "fsrs"


async def test_legacy_package_without_lapses_field_clears_to_zero(db_session):
    """P1 测试 7b（既有行为锁定）：不含 lapses 字段的旧包导入后 lapses 覆盖为 0。

    终裁口径（第 6-14 轮评审）：这是修复前就存在的覆盖式同步行为，本次修复不改变它；
    归 P6 豁免类别④"既有行为风险"，"是否改契约保留旧值"为老板决策项。
    导入后 AGAIN 提交按 0 处理（读侧 None/0 兜底），不报错。
    """
    raw = json.loads(ROUND4_FIXTURE.read_text(encoding="utf-8"))
    raw["mastery_records"][0].pop("lapses", None)
    package = SyncPackage.model_validate(raw)
    service = SyncService(db_session)

    await service.import_package("anonymous", package)
    row = (
        await db_session.execute(
            select(MasteryRecordModel).where(MasteryRecordModel.id == "round4-mastery")
        )
    ).scalar_one()
    assert row.lapses == 0  # schema 默认值（既有行为）
