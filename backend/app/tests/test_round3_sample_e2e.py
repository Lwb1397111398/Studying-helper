"""第三轮真实样例端到端验收。

用仓库内中文 TXT 样例覆盖：解析 -> 拆分 -> AID fallback -> 教学会话
-> 同步导出/预览。这个测试不依赖真实 LLM。
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.common.llm_client import LLMMessage, LLMResponse
from app.db.database import Base
from app.db.models import (
    BookModel,
    ChapterModel,
    KnowledgeUnitModel,
    MasteryRecordModel,
    UserModel,
)
from app.modules.adaptive_design.service import AIDService
from app.modules.ai_learning.schemas import Concept, KeyPoint, LearnedUnit
from app.modules.document_parser.parsers.txt_parser import TXTParser
from app.modules.document_parser.service import DocumentParserService
from app.modules.knowledge_splitter.service import KnowledgeSplitterService
from app.modules.sync.service import SyncService
from app.modules.teaching.service import TeachingService


REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_BOOK = REPO_ROOT / "docs" / "samples" / "round3_sample_book.txt"


class FailingLLM:
    """确保测试覆盖 LLM 不可用时的规则化 fallback。"""

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        raise RuntimeError("LLM disabled in round3 e2e test")

    async def chat_json(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> dict:
        raise RuntimeError("LLM disabled in round3 e2e test")

    async def close(self) -> None:
        return None


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _concept_names(unit) -> list[str]:
    if unit.concepts:
        return unit.concepts
    return [unit.title]


def _learned_unit_from_split_unit(unit) -> LearnedUnit:
    concepts = _concept_names(unit)
    return LearnedUnit(
        unit_id=unit.id,
        book_id=unit.book_id,
        summary=unit.summary or unit.content[:80],
        explanation=unit.content,
        key_points=[KeyPoint(title=unit.title, explanation=unit.content[:120])],
        concepts=[
            Concept(name=name, definition=f"{name} 是本样例书中的核心概念")
            for name in concepts[:3]
        ],
        difficulty_level=unit.difficulty_level or 3,
        importance_score=unit.importance_score or 0.7,
        prerequisites=[],
        ai_cognitive_hint=getattr(unit, "ai_cognitive_hint", None),
    )


async def _persist_split_result(db: AsyncSession, parsed, split_result) -> None:
    now = datetime.now(timezone.utc)
    db.add(UserModel(id="anonymous", username="anonymous", created_at=now, updated_at=now))
    db.add(
        BookModel(
            id="round3-book",
            user_id="anonymous",
            title=parsed.metadata.title,
            author=parsed.metadata.author,
            file_path=str(SAMPLE_BOOK),
            file_type="txt",
            file_size_bytes=parsed.metadata.file_size_bytes,
            parse_status="completed",
            split_status="completed",
            learn_status="completed",
            total_chapters=len(split_result.chapters),
            total_units=len(split_result.units),
            learned_units=len(split_result.units),
            reading_motivation="第三轮端到端验收：理解主动学习并测试离线同步",
            created_at=now,
            updated_at=now,
        )
    )
    for chapter in split_result.chapters:
        db.add(
            ChapterModel(
                id=chapter.id,
                book_id=chapter.book_id,
                title=chapter.title,
                chapter_number=chapter.chapter_number,
                parent_id=chapter.parent_id,
                level=chapter.level,
                order_index=chapter.order_index,
                summary=chapter.summary,
            )
        )
    for unit in split_result.units:
        concepts = _concept_names(unit)
        db.add(
            KnowledgeUnitModel(
                id=unit.id,
                book_id=unit.book_id,
                chapter_id=unit.chapter_id,
                section_id=unit.section_id,
                title=unit.title,
                content=unit.content,
                order_index=unit.order_index,
                char_offset_start=unit.char_offset_start,
                char_offset_end=unit.char_offset_end,
                summary=unit.summary or unit.content[:80],
                explanation=unit.content,
                key_points=json.dumps([unit.title], ensure_ascii=False),
                concepts=json.dumps(concepts, ensure_ascii=False),
                prerequisites=json.dumps([], ensure_ascii=False),
                difficulty_level=unit.difficulty_level or 3,
                importance_score=unit.importance_score or 0.7,
            )
        )
    first_unit = split_result.units[0]
    db.add(
        MasteryRecordModel(
            id="round3-mastery-1",
            user_id="anonymous",
            knowledge_unit_id=first_unit.id,
            book_id="round3-book",
            mastery_score=0.62,
            mastery_level="familiar",
            next_review_at=now,
            review_count=1,
            ease_factor=2.4,
            interval_days=1,
            stability=2.5,
            difficulty=5.5,
            lapses=0,
            reps=1,
            scheduled_days=1,
            algorithm="fsrs",
        )
    )
    await db.flush()


@pytest.mark.asyncio
async def test_round3_sample_book_runs_core_web_to_sync_flow(db_session):
    assert SAMPLE_BOOK.exists()

    parser = DocumentParserService(
        parsers=[TXTParser()],
        storage_dir=str(SAMPLE_BOOK.parent),
        llm_client=FailingLLM(),
    )
    parsed = parser.parse_and_store(str(SAMPLE_BOOK), "anonymous")
    assert parsed.full_text
    assert len(parsed.toc) >= 3

    split_result = KnowledgeSplitterService().split(parsed, "round3-book")
    assert len(split_result.chapters) >= 3
    assert len(split_result.units) >= 3

    await _persist_split_result(db_session, parsed, split_result)

    aid = AIDService(FailingLLM(), db_session)
    profile = await aid.get_or_create_profile("round3-book")
    assert profile.status == "draft"
    await aid.confirm_profile("round3-book")
    macro = await aid.generate_macro_design("round3-book")
    assert macro.total_modules > 0
    design = await aid.get_design("round3-book")
    assert design is not None
    micro = await aid.generate_micro_plan(design.id, 0)
    active_unit_ids = await aid.get_active_module_ordered_unit_ids("round3-book")
    assert active_unit_ids == list(micro.ordered_unit_ids)

    unit_by_id = {unit.id: unit for unit in split_result.units}
    ordered_learned_units = [
        _learned_unit_from_split_unit(unit_by_id[unit_id])
        for unit_id in active_unit_ids
        if unit_id in unit_by_id
    ]
    teaching = await TeachingService(FailingLLM(), db_session).start_session(
        user_id="anonymous",
        plan_session_id="round3-plan",
        book_id="round3-book",
        unit_ids=active_unit_ids,
        units=ordered_learned_units,
    )
    assert teaching.unit_ids == active_unit_ids

    sync = SyncService(db_session)
    package = await sync.export_book("anonymous", "round3-book")
    preview = await sync.preview_package(package)

    assert preview.books_count == 1
    assert preview.chapters_count == len(split_result.chapters)
    assert preview.units_count == len(split_result.units)
    assert preview.mastery_records_count == 1
    assert preview.teaching_sessions_count == 1
    assert preview.learner_intent_profiles_count == 1
    assert preview.teaching_designs_count == 1
    assert preview.module_micro_plans_count == 1
    assert package.mastery_records[0].algorithm == "fsrs"
    assert any(unit.ai_cognitive_hint for unit in package.knowledge_units)
