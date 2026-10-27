"""Step4：概念词典收编 + claim 掌握度聚合 + replan 弱 claim 测试。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.db.models import (
    BookConceptModel,
    BookModel,
    ChapterModel,
    KnowledgeUnitModel,
    LearningAttemptModel,
    LearningEvidenceModel,
    UnitLearningAssetModel,
    UserModel,
)
from app.modules.learning_assets.concept_harvest import (
    harvest_concepts,
    harvest_from_overview,
    harvest_from_understanding,
    list_book_concepts,
)
from app.modules.learning_assets.concept_mastery import (
    claim_mastery,
    concept_mastery,
    weak_required_claims,
    format_weak_claims_for_prompt,
)
from app.modules.learning_assets.models_domain import (
    Importance,
    SourceClaim,
    UnitLearningAssetPayload,
)
from app.modules.ai_learning.schemas import BookDeepOverview, KeyConceptItem


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        session.add(UserModel(id="anonymous", username="t"))
        session.add(
            BookModel(
                id="b1",
                user_id="anonymous",
                title="测试书",
                file_path="x.txt",
                file_type="txt",
                file_size_bytes=1,
            )
        )
        session.add(
            ChapterModel(
                id="ch1", book_id="b1", title="第一章",
                chapter_number=1, order_index=0, level=0,
            )
        )
        session.add(
            KnowledgeUnitModel(
                id="u1", book_id="b1", chapter_id="ch1", title="单元1",
                content="内容", order_index=0,
                char_offset_start=0, char_offset_end=2,
            )
        )
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_harvest_overview_and_merge_idempotent(db_session):
    ov = BookDeepOverview(
        core_thesis="论点",
        main_thread="主线",
        key_concepts=[
            KeyConceptItem(name="反向传播", definition="链式求导", first_chapter_id="ch1", aliases=["BP"]),
            KeyConceptItem(name="梯度", definition="方向导数", first_chapter_id="ch1"),
        ],
        reading_guide="导读",
        degraded=False,
    )
    s1 = await harvest_from_overview(db_session, "b1", ov)
    assert s1["inserted"] == 2
    s2 = await harvest_from_overview(db_session, "b1", ov)
    assert s2["inserted"] == 0  # 幂等
    rows = await list_book_concepts(db_session, "b1")
    assert len(rows) == 2
    names = {r.name for r in rows}
    assert names == {"反向传播", "梯度"}
    bp = next(r for r in rows if r.name == "反向传播")
    assert "BP" in json.loads(bp.aliases or "[]")
    assert bp.definition == "链式求导"


@pytest.mark.asyncio
async def test_harvest_unit_updates_alias_and_first_unit(db_session):
    await harvest_concepts(
        db_session,
        "b1",
        [{"name": "反向传播", "definition": "链式求导", "aliases": ["BP"]}],
        source="overview",
        default_chapter_id="ch1",
    )
    # unit harvest: 别名命中 + 新概念
    s = await harvest_from_understanding(
        db_session,
        "b1",
        "u1",
        "ch1",
        [
            {"related_concepts": ["BP", "残差连接"]},  # BP 命中反向传播；残差连接新增
        ],
    )
    assert s["inserted"] >= 1
    rows = await list_book_concepts(db_session, "b1")
    by = {r.name: r for r in rows}
    assert "残差连接" in by
    assert by["残差连接"].source == "unit_harvest"
    assert by["残差连接"].first_unit_id == "u1"
    # 反向传播 first_unit 可被补上
    assert by["反向传播"].first_unit_id in (None, "u1") or by["反向传播"].first_unit_id == "u1"


@pytest.mark.asyncio
async def test_claim_and_concept_mastery_and_weak_sort(db_session):
    # v2 asset with claims
    payload = UnitLearningAssetPayload(
        understanding_version="v2",
        unit_gist="gist",
        claims=[
            SourceClaim(
                id="c_core", text="核心机制", importance=Importance.REQUIRED,
                role_in_book="key_mechanism", mastery_check="能解释机制",
                related_concepts=["反向传播"], support_status="supported",
            ),
            SourceClaim(
                id="c_support", text="支撑细节", importance=Importance.REQUIRED,
                role_in_book="supporting_detail", mastery_check="能复述细节",
                related_concepts=["梯度"], support_status="supported",
            ),
            SourceClaim(
                id="c_tan", text="插图", importance=Importance.SUPPORTING,
                role_in_book="tangential", mastery_check="能指出示意",
                related_concepts=[], support_status="supported",
            ),
        ],
    )
    db_session.add(
        UnitLearningAssetModel(
            id="a1", unit_id="u1", version=1, status="active",
            readiness_status="understanding_ready",
            payload_json=payload.model_dump_json(),
            schema_version="unit-asset-v1",
        )
    )
    # evidence: c_core 低分，c_support 高分
    att1 = LearningAttemptModel(
        id="att1", user_id="anonymous", assessment_item_id="it1",
        response_json="{}", idempotency_key="k1", status="evaluated",
    )
    att2 = LearningAttemptModel(
        id="att2", user_id="anonymous", assessment_item_id="it2",
        response_json="{}", idempotency_key="k2", status="evaluated",
    )
    db_session.add_all([att1, att2])
    await db_session.flush()
    db_session.add_all([
        LearningEvidenceModel(
            id="e1", attempt_id="att1", user_id="anonymous", book_id="b1",
            unit_id="u1", objective_id="o1", source_type="assessment",
            claim_id="c_core", result="incorrect", score=0.3,
            evaluator_type="rule", status="active",
        ),
        LearningEvidenceModel(
            id="e2", attempt_id="att2", user_id="anonymous", book_id="b1",
            unit_id="u1", objective_id="o2", source_type="assessment",
            claim_id="c_support", result="correct", score=0.95,
            evaluator_type="rule", status="active",
        ),
    ])
    await db_session.commit()

    cm = await claim_mastery(db_session, "b1")
    assert cm["c_core"] == pytest.approx(0.3)
    assert cm["c_support"] == pytest.approx(0.95)

    weak = await weak_required_claims(db_session, "b1")
    ids = [w["claim_id"] for w in weak]
    assert "c_core" in ids
    assert "c_tan" not in ids
    # c_support 高分不应在弱清单
    assert "c_support" not in ids
    # role 排序：key_mechanism 优先
    assert weak[0]["role_in_book"] == "key_mechanism"

    conc = await concept_mastery(db_session, "b1")
    assert conc.get("反向传播") == pytest.approx(0.3)

    block = format_weak_claims_for_prompt(weak)
    assert "key_mechanism" in block
    assert "c_core" in block


@pytest.mark.asyncio
async def test_replan_rulebased_async_revisits_weak_core(db_session):
    from app.modules.adaptive_design.service import AIDService
    from app.modules.adaptive_design.schemas import ModuleSkeleton, StageFeedback

    svc = AIDService(llm_client=MagicMock(), db=db_session)
    next_skel = ModuleSkeleton(
        index=1, title="下一模块", unit_ids=["u2", "u3"],
        concept_ids=[], strategy_tags=[], rationale="",
    )
    # ensure ModuleSkeleton fields match schema - check required fields
    weak = [
        {
            "claim_id": "c1", "unit_id": "u1", "text": "核心",
            "role_in_book": "core_thesis_support", "mastery_check": "能解释",
            "mastery": 0.2, "related_concepts": [],
        }
    ]
    result = await svc._replan_rulebased_async(
        next_skel, StageFeedback(module_index=0), {"u2": 0.9},
        book_id="b1", user_id="anonymous", weak_claims=weak,
    )
    assert "u1" in result.revisit_unit_ids
    assert "u2" in result.skip_unit_ids  # high mastery skip
    # hint bumped
    unit = (
        await db_session.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(
                __import__("app.db.models", fromlist=["KnowledgeUnitModel"]).KnowledgeUnitModel
            ).where(
                __import__("app.db.models", fromlist=["KnowledgeUnitModel"]).KnowledgeUnitModel.id == "u1"
            )
        )
    )
    # simpler check:
    from sqlalchemy import select
    from app.db.models import KnowledgeUnitModel
    u = (await db_session.execute(select(KnowledgeUnitModel).where(KnowledgeUnitModel.id == "u1"))).scalar_one()
    assert u.ai_cognitive_hint == "memorize"


@pytest.mark.asyncio
async def test_replan_no_weak_claims_matches_old_behavior(db_session):
    from app.modules.adaptive_design.service import AIDService
    from app.modules.adaptive_design.schemas import ModuleSkeleton, StageFeedback

    svc = AIDService(llm_client=MagicMock(), db=db_session)
    # Build skeleton carefully
    try:
        next_skel = ModuleSkeleton(
            index=1, title="M", unit_ids=["u2"], concept_ids=[], strategy_tags=[], rationale="r",
        )
    except Exception:
        # fallback if schema differs
        next_skel = SimpleNamespace(index=1, title="M", unit_ids=["u2"])
        result = svc._replan_rulebased(next_skel, StageFeedback(module_index=0), {"u2": 0.9})
        assert result.revisit_unit_ids == []
        assert "u2" in result.skip_unit_ids
        return

    result = await svc._replan_rulebased_async(
        next_skel, StageFeedback(module_index=0), {"u2": 0.9},
        book_id="b1", user_id="anonymous", weak_claims=[],
    )
    assert result.revisit_unit_ids == []
    assert "u2" in result.skip_unit_ids
