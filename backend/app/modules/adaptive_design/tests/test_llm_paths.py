"""AID LLM 路径测试 - 用 mock LLM 验证 macro/micro/画像的 LLM 分支正确解析"""

import json
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.common.llm_client import LLMMessage, LLMResponse
from app.db.database import Base
from app.db.models import UserModel, BookModel, ChapterModel, KnowledgeUnitModel
from app.modules.adaptive_design.service import AIDService
from app.modules.adaptive_design.schemas import ProfileUpdateRequest


class MacroMockLLM:
    """mock LLM：macro 返回跨章节聚类，micro 返回重排+标注，profile 返回画像"""

    def __init__(self):
        self.calls = 0
        self.model = "mock"
        self.api_key = "mock-key"  # 让 _llm_enabled() 识别为可用

    async def chat(self, messages, temperature=0.7, max_tokens=4096):
        return LLMResponse(content="{}", model="mock", usage={})

    async def chat_json(self, messages, temperature=0.3, max_tokens=4096):
        self.calls += 1
        content = messages[0].content
        if "推断其学习画像" in content or "学习顾问" in content:
            return {
                "identity_background": "unrelated",
                "goal_depth": "general_interest",
                "cognitive_pref": "vivid_analogy",
                "restructure_tolerance": "aggressive",
                "reason": "mock",
            }
        if "学习模块" in content and "unit_ids" in content:
            # 跨章节聚类：unit-1(ch1) 和 unit-2(ch2) 归一组
            return {
                "modules": [
                    {"title": "线性表对比", "unit_ids": ["unit-1", "unit-2"],
                     "concept_ids": ["线性表"], "strategy_tags": ["comparison_group"],
                     "rationale": "跨章对比"},
                ]
            }
        if "教授顺序与重构标注" in content or "module_intro" in content:
            return {
                "ordered_unit_ids": ["unit-1", "unit-2"],
                "unit_annotations": [
                    {"unit_id": "unit-1", "cognitive_mode": "understand",
                     "merge_group": None, "defer_to_module": None, "emphasis": "基础"},
                    {"unit_id": "unit-2", "cognitive_mode": "understand",
                     "merge_group": None, "defer_to_module": None, "emphasis": "对比"},
                ],
                "module_intro": "本模块对比学习两种线性表结构。",
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
                              reading_motivation="我是纯兴趣入门的爱好者，想生动了解",
                              created_at=now, updated_at=now))
        session.add(ChapterModel(id="ch-1", book_id="book-1", title="一",
                                 chapter_number=1, order_index=0, level=1))
        session.add(ChapterModel(id="ch-2", book_id="book-1", title="二",
                                 chapter_number=2, order_index=1, level=1))
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
        await session.flush()
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


class TestLLMPaths:
    """验证 LLM 分支被走到且产出正确"""

    @pytest.mark.asyncio
    async def test_profile_llm_inference(self, db_session):
        """LLM 画像推断：reading_motivation 命中兴趣→画像来自 LLM"""
        svc = AIDService(MacroMockLLM(), db_session)
        profile = await svc.get_or_create_profile("book-1")
        # mock 返回 unrelated + general_interest（与规则化可能一致，关键是 LLM 被调）
        assert profile.identity_background in ("unrelated", "related")
        assert svc.llm.calls >= 1  # LLM 确实被调用

    @pytest.mark.asyncio
    async def test_macro_llm_cross_chapter(self, db_session):
        """LLM macro：跨章节把 unit-1(ch1)+unit-2(ch2) 合一模块"""
        svc = AIDService(MacroMockLLM(), db_session)
        await svc.get_or_create_profile("book-1")
        await svc.confirm_profile("book-1")
        macro = await svc.generate_macro_design("book-1")

        # LLM 返回 1 个跨章节模块含两个 unit
        assert macro.total_modules >= 1
        m0 = macro.modules[0]
        assert "unit-1" in m0.unit_ids and "unit-2" in m0.unit_ids
        assert "comparison_group" in m0.strategy_tags

    @pytest.mark.asyncio
    async def test_micro_llm_arrangement(self, db_session):
        """LLM micro：产出 ordered + annotations + intro"""
        svc = AIDService(MacroMockLLM(), db_session)
        await svc.get_or_create_profile("book-1")
        await svc.confirm_profile("book-1")
        await svc.generate_macro_design("book-1")
        design = await svc.get_design("book-1")
        micro = await svc.generate_micro_plan(design.id, 0)

        assert micro.ordered_unit_ids == ["unit-1", "unit-2"]
        assert len(micro.unit_annotations) == 2
        assert micro.module_intro  # LLM 提供了导言
        assert all(a.cognitive_mode == "understand" for a in micro.unit_annotations)

    @pytest.mark.asyncio
    async def test_macro_topology_validation_rejects_reverse_dep(self, db_session):
        """拓扑校验：LLM 若产出反向依赖模块应被拒绝回退"""

        class BadLLM(MacroMockLLM):
            async def chat_json(self, messages, temperature=0.3, max_tokens=4096):
                self.calls += 1
                content = messages[0].content
                if "学习模块" in content and "unit_ids" in content:
                    # 反向：unit-2(依赖unit-1) 放模块0，unit-1 放模块1
                    return {"modules": [
                        {"title": "M0", "unit_ids": ["unit-2"], "concept_ids": [],
                         "strategy_tags": [], "rationale": ""},
                        {"title": "M1", "unit_ids": ["unit-1"], "concept_ids": [],
                         "strategy_tags": [], "rationale": ""},
                    ]}
                return await super().chat_json(messages, temperature, max_tokens)

        svc = AIDService(BadLLM(), db_session)
        await svc.get_or_create_profile("book-1")
        await svc.confirm_profile("book-1")
        macro = await svc.generate_macro_design("book-1")
        # 反向依赖被校验拒绝 → 回退规则化（按章节：unit-1 在 ch1，unit-2 在 ch2 → 2 模块）
        # 或 LLM 拒绝后规则化聚类。总之不应是 [unit-2],[unit-1] 的反向结构
        m0_units = macro.modules[0].unit_ids
        assert "unit-1" in m0_units  # unit-1 应在靠前模块（拓扑正确）
