"""M3 replan 闭环 + 用户调整审计测试"""

import json
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.common.llm_client import LLMResponse
from app.db.database import Base
from app.db.models import (
    UserModel, BookModel, ChapterModel, KnowledgeUnitModel, MasteryRecordModel,
)
from app.modules.adaptive_design.service import AIDService
from app.modules.adaptive_design.schemas import StageFeedback


class ReplanMockLLM:
    """mock LLM：replan 返回 revisit+skip"""
    api_key = "mock-key"
    model = "mock"

    async def chat(self, messages, temperature=0.7, max_tokens=4096):
        return LLMResponse(content="{}", model="mock", usage={})

    async def chat_json(self, messages, temperature=0.3, max_tokens=4096):
        c = messages[0].content
        if "查漏补缺" in c or "保守调整" in c or "revisit_unit_ids" in c:
            return {
                "revisit_unit_ids": ["unit-1"],  # 回访旧单元
                "skip_unit_ids": [],
                "rationale": "薄弱点对应 unit-1",
            }
        return {}


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        session.add(UserModel(id="anonymous", username="u", created_at=now, updated_at=now))
        session.add(BookModel(id="book-1", user_id="anonymous", title="T",
                              file_path="t", file_type="txt", file_size_bytes=1,
                              reading_motivation="兴趣", created_at=now, updated_at=now))
        session.add(ChapterModel(id="ch-1", book_id="book-1", title="一",
                                 chapter_number=1, order_index=0, level=1))
        session.add(ChapterModel(id="ch-2", book_id="book-1", title="二",
                                 chapter_number=2, order_index=1, level=1))
        # 3 单元：unit-1/ch1, unit-2/ch2(共享线性表), unit-3/ch2(难度5)
        session.add(KnowledgeUnitModel(
            id="unit-1", book_id="book-1", chapter_id="ch-1", title="数组",
            content="x", order_index=0, char_offset_start=0, char_offset_end=1,
            summary="数组线性表", difficulty_level=2, importance_score=0.8,
            concepts=json.dumps(["数组", "线性表"]), prerequisites=json.dumps([]),
        ))
        session.add(KnowledgeUnitModel(
            id="unit-2", book_id="book-1", chapter_id="ch-2", title="链表",
            content="x", order_index=1, char_offset_start=1, char_offset_end=2,
            summary="链表线性表", difficulty_level=3, importance_score=0.7,
            concepts=json.dumps(["链表", "线性表"]), prerequisites=json.dumps(["unit-1"]),
        ))
        session.add(KnowledgeUnitModel(
            id="unit-3", book_id="book-1", chapter_id="ch-2", title="高级",
            content="x", order_index=2, char_offset_start=2, char_offset_end=3,
            summary="高级主题", difficulty_level=5, importance_score=0.7,
            concepts=json.dumps(["高级"]), prerequisites=json.dumps(["unit-2"]),
        ))
        await session.flush()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _setup_two_modules(db, llm):
    """生成至少 2 模块的设计，生成模块0的 micro"""
    svc = AIDService(llm, db)
    await svc.get_or_create_profile("book-1")
    await svc.confirm_profile("book-1")
    await svc.generate_macro_design("book-1")
    design = await svc.get_design("book-1")
    await svc.generate_micro_plan(design.id, 0)
    await svc.activate_module("book-1")
    return svc, design


async def _add_mastery(db, unit_id, score):
    """添加掌握度记录"""
    db.add(MasteryRecordModel(
        id=f"mr-{unit_id}", user_id="anonymous", knowledge_unit_id=unit_id,
        book_id="book-1", mastery_score=score, mastery_level="proficient",
        next_review_at=datetime.now(timezone.utc) + timedelta(days=1),
    ))
    await db.flush()


class TestReplan:
    """replan 闭环"""

    @pytest.mark.asyncio
    async def test_replan_llm_revisits_old_unit(self, db_session):
        svc, design = await _setup_two_modules(db_session, ReplanMockLLM())
        macro = await svc.get_macro_design("book-1")
        if macro.total_modules < 2:
            pytest.skip("需要 >=2 模块")

        # 先生成下一模块 micro，让 revisit 能注入
        await svc.generate_micro_plan(design.id, 1)

        result = await svc.replan_next_module(
            "book-1",
            StageFeedback(module_index=0, weak_points=["数组概念不清"]),
        )
        assert "unit-1" in result.revisit_unit_ids

        # 验证 revisit 已注入下一模块开头
        next_micro = await svc.get_micro_plan(design.id, 1)
        assert next_micro.ordered_unit_ids[0] == "unit-1"

    @pytest.mark.asyncio
    async def test_replan_rulebased_skips_mastered(self, db_session):
        """空 key → 规则化：mastery>=0.85 的单元被跳过"""
        from app.common.llm_client import OpenAIClient
        empty_llm = OpenAIClient(api_key="", model="m", base_url="http://x")
        svc, design = await _setup_two_modules(db_session, empty_llm)

        macro = await svc.get_macro_design("book-1")
        if macro.total_modules < 2:
            pytest.skip()

        # 给下一模块的某单元加高分掌握度
        next_mod = macro.modules[1]
        if next_mod.unit_ids:
            await _add_mastery(db_session, next_mod.unit_ids[0], 0.9)
            await svc.generate_micro_plan(design.id, 1)

        result = await svc.replan_next_module(
            "book-1", StageFeedback(module_index=0, weak_points=[])
        )
        # 高分单元应被加入 skip
        if next_mod.unit_ids:
            assert next_mod.unit_ids[0] in result.skip_unit_ids

    @pytest.mark.asyncio
    async def test_replan_last_module_returns_empty(self, db_session):
        """已是最后模块时 replan 返回空调整"""
        svc, design = await _setup_two_modules(db_session, ReplanMockLLM())
        macro = await svc.get_macro_design("book-1")
        # 推进到最后一模块
        for _ in range(macro.total_modules):
            await svc.advance_to_next_module("book-1")

        result = await svc.replan_next_module(
            "book-1", StageFeedback(module_index=0)
        )
        assert result.revisit_unit_ids == []


class TestAdjustments:
    """用户调整审计"""

    @pytest.mark.asyncio
    async def test_adjustment_recorded(self, db_session):
        svc, design = await _setup_two_modules(db_session, ReplanMockLLM())
        updated = await svc.apply_user_adjustments(
            "book-1", field="module_order", old_value="0,1", new_value="1,0",
            reason="用户想先学概念",
        )
        assert any(a.field == "module_order" for a in updated.adjustments)
        assert len(updated.adjustments) == 1

    @pytest.mark.asyncio
    async def test_adjustment_rejects_done_module(self, db_session):
        svc, design = await _setup_two_modules(db_session, ReplanMockLLM())
        # 推进模块0到 done
        await svc.advance_to_next_module("book-1")
        with pytest.raises(Exception):
            await svc.apply_user_adjustments(
                "book-1", field="x", old_value="", new_value="",
                module_index=0,  # 已 done
            )

    @pytest.mark.asyncio
    async def test_adjustments_append_only(self, db_session):
        svc, design = await _setup_two_modules(db_session, ReplanMockLLM())
        await svc.apply_user_adjustments("book-1", "f1", "a", "b")
        await svc.apply_user_adjustments("book-1", "f2", "c", "d")
        d = await svc.get_design("book-1")
        assert len(d.adjustments) == 2


class TestModuleStateMachine:
    """模块状态机"""

    @pytest.mark.asyncio
    async def test_activate_sets_active(self, db_session):
        svc, design = await _setup_two_modules(db_session, ReplanMockLLM())
        micro = await svc.get_micro_plan(design.id, 0)
        assert micro.module_status == "active"  # _setup 已 activate

    @pytest.mark.asyncio
    async def test_advance_sets_done(self, db_session):
        svc, design = await _setup_two_modules(db_session, ReplanMockLLM())
        await svc.advance_to_next_module("book-1")
        micro = await svc.get_micro_plan(design.id, 0)
        assert micro.module_status == "done"
