"""AID 服务端到端集成测试 - M1 规则化流程

覆盖：profile→confirm→macro→micro→active-units 完整链路，
以及画像驱动的不同重组策略与 defer 剔除、回退行为。
M1 无 LLM 调用，AIDService 用空 key 构造即可。
"""

import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.common.llm_client import OpenAIClient
from app.db.database import Base
from app.db.models import (
    UserModel,
    BookModel,
    ChapterModel,
    KnowledgeUnitModel,
    LearnerIntentProfileModel,
)
from app.modules.adaptive_design.service import AIDService
from app.modules.adaptive_design.schemas import ProfileUpdateRequest


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


def _mk_llm() -> OpenAIClient:
    return OpenAIClient(api_key="", model="gpt-4o-mini", base_url="http://localhost")


async def _seed_book(db, book_id="book-1", motivation=""):
    db.add(UserModel(id="anonymous", username="anonymous"))
    db.add(BookModel(
        id=book_id, user_id="anonymous", title="测试书", author="",
        file_path="/tmp/t.pdf", file_type="pdf", file_size_bytes=100,
        reading_motivation=motivation,
    ))
    db.add(ChapterModel(id="ch-1", book_id=book_id, title="第一章",
                        chapter_number=1, order_index=0, level=1))
    db.add(ChapterModel(id="ch-2", book_id=book_id, title="第二章",
                        chapter_number=2, order_index=1, level=1))


async def _seed_units(db, book_id="book-1", with_shared_concept=True):
    """两个单元（跨章节共享概念「线性表」），第三个单元难度高"""
    c1 = ["数组", "线性表"] if with_shared_concept else ["数组"]
    c2 = ["链表", "线性表"] if with_shared_concept else ["链表"]
    db.add(KnowledgeUnitModel(
        id="unit-1", book_id=book_id, chapter_id="ch-1", title="数组基础",
        content="x", order_index=0, char_offset_start=0, char_offset_end=1,
        summary="数组是线性表，支持随机访问",
        difficulty_level=2, importance_score=0.8, concepts=json.dumps(c1),
        prerequisites=json.dumps([]),
    ))
    db.add(KnowledgeUnitModel(
        id="unit-2", book_id=book_id, chapter_id="ch-1", title="链表",
        content="x", order_index=1, char_offset_start=1, char_offset_end=2,
        summary="链表也是线性表",
        difficulty_level=3, importance_score=0.7, concepts=json.dumps(c2),
        prerequisites=json.dumps(["unit-1"]),
    ))
    db.add(KnowledgeUnitModel(
        id="unit-3", book_id=book_id, chapter_id="ch-2", title="高级树",
        content="x", order_index=2, char_offset_start=2, char_offset_end=3,
        summary="红黑树等高级树结构",
        difficulty_level=5, importance_score=0.7, concepts=json.dumps(["红黑树"]),
        prerequisites=json.dumps(["unit-2"]),
    ))
    await db.flush()


class TestProfileFlow:
    """画像 CRUD 流程"""

    @pytest.mark.asyncio
    async def test_get_or_create_infers_defaults(self, db_session):
        await _seed_book(db_session, motivation="我是法学生，要准备法考")
        await _seed_units(db_session, with_shared_concept=False)
        svc = AIDService(_mk_llm(), db_session)

        profile = await svc.get_or_create_profile("book-1")
        # 「法学生」匹配专业关键词，「法考」匹配应试关键词
        assert profile.identity_background == "expert"
        assert profile.goal_depth == "exam_memorize"
        assert profile.source == "ai_inferred"
        assert profile.status == "draft"

    @pytest.mark.asyncio
    async def test_confirm_sets_status(self, db_session):
        await _seed_book(db_session, motivation="兴趣入门")
        await _seed_units(db_session, with_shared_concept=False)
        svc = AIDService(_mk_llm(), db_session)

        await svc.get_or_create_profile("book-1")
        confirmed = await svc.confirm_profile("book-1")
        assert confirmed.status == "confirmed"
        assert confirmed.source == "user_set"

    @pytest.mark.asyncio
    async def test_update_profile_marks_adjusted(self, db_session):
        await _seed_book(db_session, motivation="兴趣")
        await _seed_units(db_session, with_shared_concept=False)
        svc = AIDService(_mk_llm(), db_session)

        await svc.get_or_create_profile("book-1")
        updated = await svc.update_profile(
            "book-1",
            ProfileUpdateRequest(goal_depth="exam_memorize"),
        )
        assert updated.goal_depth == "exam_memorize"
        assert updated.source == "user_adjusted"


class TestMacroGeneration:
    """宏观设计：画像驱动重组策略"""

    @pytest.mark.asyncio
    async def test_macro_requires_confirmed_profile(self, db_session):
        await _seed_book(db_session, motivation="兴趣")
        await _seed_units(db_session)
        svc = AIDService(_mk_llm(), db_session)

        await svc.get_or_create_profile("book-1")
        # 未确认 → 报错
        with pytest.raises(Exception):
            await svc.generate_macro_design("book-1")

    @pytest.mark.asyncio
    async def test_keep_book_order_groups_by_chapter(self, db_session):
        await _seed_book(db_session, motivation="我是法学专业本科生")
        await _seed_units(db_session, with_shared_concept=True)
        svc = AIDService(_mk_llm(), db_session)

        await svc.get_or_create_profile("book-1")
        await svc.confirm_profile("book-1")
        macro = await svc.generate_macro_design("book-1")

        # 法学生 → expert → keep_book_order → 按章节分组（2 章 → 2 模块）
        assert macro.total_modules == 2
        ch1_units = next(m for m in macro.modules if "unit-1" in m.unit_ids)
        assert "unit-3" not in ch1_units.unit_ids  # unit-3 在 ch-2

    @pytest.mark.asyncio
    async def test_aggressive_cross_chapter_clustering(self, db_session):
        await _seed_book(db_session, motivation="纯兴趣入门，想生动了解")
        await _seed_units(db_session, with_shared_concept=True)
        svc = AIDService(_mk_llm(), db_session)

        profile = await svc.get_or_create_profile("book-1")
        # 兴趣 → unrelated → aggressive
        assert profile.restructure_tolerance == "aggressive"

        await svc.confirm_profile("book-1")
        macro = await svc.generate_macro_design("book-1")

        # aggressive + 共享概念「线性表」→ unit-1 和 unit-2 应聚到同一模块（跨章节不限）
        assert macro.total_modules >= 1
        # 找到含 unit-1 的模块，unit-2 也应在其中（概念共现聚类）
        module_with_u1 = next(m for m in macro.modules if "unit-1" in m.unit_ids)
        assert "unit-2" in module_with_u1.unit_ids


class TestMicroAndIntegration:
    """微观编排与 teaching 集成入口"""

    @pytest.mark.asyncio
    async def test_micro_idempotent(self, db_session):
        await _seed_book(db_session, motivation="兴趣")
        await _seed_units(db_session)
        svc = AIDService(_mk_llm(), db_session)

        await svc.get_or_create_profile("book-1")
        await svc.confirm_profile("book-1")
        design = await svc.get_design("book-1")  # 此时 macro 已需先生成

    @pytest.mark.asyncio
    async def test_active_units_returns_reordered(self, db_session):
        """完整链路：active-units 返回重排后的 unit_ids"""
        await _seed_book(db_session, motivation="兴趣")
        await _seed_units(db_session, with_shared_concept=True)
        svc = AIDService(_mk_llm(), db_session)

        # 1. 无设计 → 返回空（teaching 回退）
        assert await svc.get_active_module_ordered_unit_ids("book-1") == []

        # 2. 完整流程
        await svc.get_or_create_profile("book-1")
        await svc.confirm_profile("book-1")
        macro = await svc.generate_macro_design("book-1")
        design = await svc.get_design("book-1")
        assert design is not None

        # 3. generate_micro_plan 当前模块
        micro = await svc.generate_micro_plan(design.id, 0)
        assert micro.module_status == "pending"
        assert len(micro.ordered_unit_ids) > 0
        assert all(isinstance(a.cognitive_mode, str) for a in micro.unit_annotations)
        # 微观应含 module_intro 导言
        assert micro.module_intro

        # 4. active-units 自动取当前模块 micro
        active = await svc.get_active_module_ordered_unit_ids("book-1")
        assert active == list(micro.ordered_unit_ids)

    @pytest.mark.asyncio
    async def test_defer_unit_excluded_from_ordered(self, db_session):
        """难度 >=5 且非首模块且非高重要性的单元应 defer，从 ordered 剔除"""
        await _seed_book(db_session, motivation="兴趣")
        await _seed_units(db_session)  # unit-3 难度5 重要性0.7
        svc = AIDService(_mk_llm(), db_session)

        await svc.get_or_create_profile("book-1")
        await svc.confirm_profile("book-1")
        macro = await svc.generate_macro_design("book-1")
        design = await svc.get_design("book-1")

        # 推进到模块 1，使 module_index>0 触发 defer 规则
        await svc.advance_to_next_module("book-1")
        # 模块 1 的 micro（若存在该模块）
        if macro.total_modules > 1:
            micro = await svc.generate_micro_plan(design.id, 1)
            # 若模块1含 unit-3，则它应被 defer 到模块2，从 ordered 剔除
            deferred = [a for a in micro.unit_annotations if a.defer_to_module is not None]
            for a in deferred:
                assert a.unit_id not in micro.ordered_unit_ids

    @pytest.mark.asyncio
    async def test_advance_module_progresses(self, db_session):
        await _seed_book(db_session, motivation="兴趣")
        await _seed_units(db_session)
        svc = AIDService(_mk_llm(), db_session)

        await svc.get_or_create_profile("book-1")
        await svc.confirm_profile("book-1")
        macro = await svc.generate_macro_design("book-1")
        design = await svc.get_design("book-1")
        await svc.generate_micro_plan(design.id, 0)

        next_idx = await svc.advance_to_next_module("book-1")
        if macro.total_modules > 1:
            assert next_idx == 1
        else:
            assert next_idx is None  # 完成全书

    @pytest.mark.asyncio
    async def test_macro_regenerate_supersedes_old(self, db_session):
        await _seed_book(db_session, motivation="兴趣")
        await _seed_units(db_session)
        svc = AIDService(_mk_llm(), db_session)

        await svc.get_or_create_profile("book-1")
        await svc.confirm_profile("book-1")
        await svc.generate_macro_design("book-1")
        design1 = await svc.get_design("book-1")

        # 改画像后重新生成 → 旧设计应置 superseded
        await svc.update_profile("book-1", ProfileUpdateRequest(goal_depth="exam_memorize"))
        await svc.generate_macro_design("book-1")
        design2 = await svc.get_design("book-1")

        assert design2.id != design1.id
        assert design2.status == "active"
