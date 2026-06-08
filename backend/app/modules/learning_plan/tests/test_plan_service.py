"""学习方案服务测试"""
import json
import pytest
import pytest_asyncio
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.database import Base
from app.db.models import (
    UserModel, BookModel, KnowledgeUnitModel, ChapterModel,
    LearningRecordModel, DailyStatsModel,
)
from app.modules.ai_learning.schemas import LearnedUnit, Concept, KeyPoint, SelfAssessment
from app.modules.learning_plan.service import LearningPlanService
from app.modules.learning_plan.style_analyzer import LearningStyleAnalyzer
from app.modules.learning_plan.schemas import LearningStyle, SessionPerformance


@pytest_asyncio.fixture
async def db_session():
    """创建内存数据库"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def sample_learned_units():
    """创建测试用的LearnedUnit列表"""
    units = []
    for i in range(10):
        units.append(LearnedUnit(
            unit_id=f"unit-{i}",
            book_id="book-1",
            summary=f"这是第{i}个单元的摘要",
            key_points=[KeyPoint(title=f"要点{i}-1"), KeyPoint(title=f"要点{i}-2")],
            concepts=[Concept(name=f"概念{i}", definition=f"定义{i}")],
            difficulty_level=(i % 5) + 1,
            importance_score=0.5 + (i % 5) * 0.1,
            prerequisites=[],
            self_assessment=SelfAssessment(
                score=85,
                test_questions=[],
                self_answers=[],
                weak_points=[],
                needs_deepening=False
            )
        ))
    return units


@pytest.fixture
def style_analyzer():
    return LearningStyleAnalyzer()


# ===== 原有测试（保持不变） =====

class TestLearningPlanService:
    def test_generate_plan_basic(self, style_analyzer, sample_learned_units):
        """基本方案生成"""
        service = LearningPlanService(style_analyzer=style_analyzer)
        import asyncio
        plan = asyncio.run(
            service.generate_plan("user-1", "book-1", sample_learned_units)
        )
        assert len(plan.sessions) > 0
        assert plan.total_estimated_minutes > 0
        assert len(plan.milestones) > 0
        assert plan.user_id == "user-1"

    def test_plan_respects_daily_goal(self, style_analyzer, sample_learned_units):
        """每日目标：每个会话时长不超过每日目标的1.5倍"""
        service = LearningPlanService(style_analyzer=style_analyzer)
        import asyncio
        plan = asyncio.run(
            service.generate_plan("user-1", "book-1", sample_learned_units, daily_goal_minutes=30)
        )
        for session in plan.sessions:
            assert session.estimated_minutes <= 45  # 30 * 1.5

    def test_fast_paced_style(self, sample_learned_units):
        """快节奏风格：每个会话包含更多单元"""
        style = LearningStyle(fast_paced=True, step_by_step=False)
        # 直接注入自定义 get_style，避免修改类变量
        class _FastAnalyzer(LearningStyleAnalyzer):
            async def get_style(self, user_id: str) -> LearningStyle:
                return style
        service = LearningPlanService(style_analyzer=_FastAnalyzer())
        import asyncio
        plan = asyncio.run(
            service.generate_plan("user-1", "book-1", sample_learned_units)
        )
        assert len(plan.sessions) <= 5

    def test_complete_session_basic(self, style_analyzer, sample_learned_units):
        """完成会话：基本流程"""
        service = LearningPlanService(style_analyzer=style_analyzer)
        import asyncio
        plan = asyncio.run(
            service.generate_plan("user-1", "book-1", sample_learned_units)
        )
        first_session = plan.sessions[0]
        performance = SessionPerformance(
            correct_rate=0.8,
            avg_response_time=10.0,
            questions_asked=3,
            duration_minutes=25
        )
        update = asyncio.run(
            service.complete_session(plan, first_session.id, performance)
        )
        assert update.next_session is not None

    def test_complete_session_low_performance(self, style_analyzer, sample_learned_units):
        """低表现：触发调整建议"""
        service = LearningPlanService(style_analyzer=style_analyzer)
        import asyncio
        plan = asyncio.run(
            service.generate_plan("user-1", "book-1", sample_learned_units)
        )
        first_session = plan.sessions[0]
        performance = SessionPerformance(
            correct_rate=0.3,
            avg_response_time=30.0,
            questions_asked=1,
            duration_minutes=25
        )
        update = asyncio.run(
            service.complete_session(plan, first_session.id, performance)
        )
        assert update.adjusted is True
        assert update.reason is not None

    def test_get_current_session(self, style_analyzer, sample_learned_units):
        """获取当前会话"""
        service = LearningPlanService(style_analyzer=style_analyzer)
        import asyncio
        plan = asyncio.run(
            service.generate_plan("user-1", "book-1", sample_learned_units)
        )
        current = service.get_current_session(plan, 0)
        assert current is not None
        assert current.session_number == 1
        current = service.get_current_session(plan, len(plan.sessions) + 1)
        assert current is None


# ===== 新增：异步DB集成测试 =====

class TestLearningPlanServiceWithDB:
    """带数据库的学习方案服务测试"""

    @pytest.mark.asyncio
    async def test_generate_plan_with_db(self, db_session, sample_learned_units):
        """DB集成：生成方案"""
        analyzer = LearningStyleAnalyzer(db_session=db_session)
        service = LearningPlanService(style_analyzer=analyzer, db_session=db_session)

        plan = await service.generate_plan("user-1", "book-1", sample_learned_units)
        assert len(plan.sessions) > 0
        assert plan.style_snapshot is not None

    @pytest.mark.asyncio
    async def test_complete_session_persists_record(self, db_session, sample_learned_units):
        """DB集成：完成会话写入学习记录"""
        analyzer = LearningStyleAnalyzer(db_session=db_session)
        service = LearningPlanService(style_analyzer=analyzer, db_session=db_session)

        plan = await service.generate_plan("user-1", "book-1", sample_learned_units)
        first_session = plan.sessions[0]
        performance = SessionPerformance(
            correct_rate=0.8,
            avg_response_time=10.0,
            questions_asked=3,
            duration_minutes=25,
        )
        update = await service.complete_session(plan, first_session.id, performance)

        # 验证学习记录已写入
        result = await db_session.execute(
            select(LearningRecordModel).where(
                LearningRecordModel.session_id == first_session.id
            )
        )
        record = result.scalar_one_or_none()
        assert record is not None
        assert record.user_id == "user-1"
        assert record.book_id == "book-1"
        assert record.test_score == 80.0  # 0.8 * 100

    @pytest.mark.asyncio
    async def test_complete_session_not_found(self, db_session, sample_learned_units):
        """DB集成：完成不存在的会话"""
        from app.common.errors import ServiceError
        analyzer = LearningStyleAnalyzer(db_session=db_session)
        service = LearningPlanService(style_analyzer=analyzer, db_session=db_session)

        plan = await service.generate_plan("user-1", "book-1", sample_learned_units)
        performance = SessionPerformance(
            correct_rate=0.8, avg_response_time=10.0,
            questions_asked=3, duration_minutes=25,
        )
        with pytest.raises(ServiceError) as exc_info:
            await service.complete_session(plan, "nonexistent-id", performance)
        assert exc_info.value.code.value == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_load_units_from_db(self, db_session):
        """从DB加载知识单元"""
        book_id = str(uuid4())
        # 创建测试数据
        chapter = ChapterModel(
            id=str(uuid4()), book_id=book_id,
            title="第1章", chapter_number=1, order_index=0,
        )
        db_session.add(chapter)
        await db_session.flush()

        for i in range(3):
            unit = KnowledgeUnitModel(
                id=f"ku-{i}",
                book_id=book_id,
                chapter_id=chapter.id,
                title=f"单元{i}",
                content=f"内容{i}",
                order_index=i,
                char_offset_start=i * 100,
                char_offset_end=(i + 1) * 100,
                summary=f"摘要{i}",
                key_points=json.dumps([f"要点{i}-1", f"要点{i}-2"]),
                difficulty_level=i + 1,
                importance_score=0.5 + i * 0.1,
            )
            db_session.add(unit)
        await db_session.flush()

        units = await LearningPlanService.load_units_from_db(db_session, book_id)
        assert len(units) == 3
        assert units[0].unit_id == "ku-0"
        assert units[0].difficulty_level == 1
        assert units[2].difficulty_level == 3

    @pytest.mark.asyncio
    async def test_load_units_empty_book(self, db_session):
        """空书籍加载返回空列表"""
        units = await LearningPlanService.load_units_from_db(db_session, "nonexistent-book")
        assert units == []


class TestLearningStyleAnalyzer:
    """学习风格分析器测试"""

    @pytest.mark.asyncio
    async def test_no_db_returns_default(self):
        """无DB时返回默认风格"""
        analyzer = LearningStyleAnalyzer(db_session=None)
        style = await analyzer.get_style("user-1")
        assert style == LearningStyleAnalyzer.DEFAULT_STYLE

    @pytest.mark.asyncio
    async def test_new_user_returns_default(self, db_session):
        """新用户返回默认风格（零置信度）"""
        analyzer = LearningStyleAnalyzer(db_session=db_session)
        style = await analyzer.get_style("nonexistent-user")
        assert style.confidence == 0.0

    @pytest.mark.asyncio
    async def test_user_with_insufficient_data(self, db_session):
        """数据不足时返回低置信度默认风格"""
        user = UserModel(
            id="user-1", username="testuser",
            daily_goal_minutes=30, preferred_language="zh",
        )
        db_session.add(user)
        await db_session.flush()

        # 创建5条记录（不足MIN_SESSIONS_FOR_ANALYSIS=10）
        for i in range(5):
            record = LearningRecordModel(
                user_id="user-1",
                book_id="book-1",
                session_id=f"session-{i}",
                duration_minutes=20,
                questions_asked=2,
                test_score=70.0,
            )
            db_session.add(record)
        await db_session.flush()

        analyzer = LearningStyleAnalyzer(db_session=db_session)
        style = await analyzer.get_style("user-1")
        assert style.confidence < 0.6  # 5/10 = 0.5

    @pytest.mark.asyncio
    async def test_user_with_sufficient_data(self, db_session):
        """有足够数据时返回分析结果"""
        user = UserModel(
            id="user-1", username="testuser",
            daily_goal_minutes=30, preferred_language="zh",
        )
        db_session.add(user)
        await db_session.flush()

        # 创建15条记录
        for i in range(15):
            record = LearningRecordModel(
                user_id="user-1",
                book_id="book-1",
                session_id=f"session-{i}",
                duration_minutes=45,  # 长时间 → 快节奏
                questions_asked=5,    # 多提问 → 互动式
                test_score=80.0,      # 高正确率 → 爱举例
            )
            db_session.add(record)
        await db_session.flush()

        analyzer = LearningStyleAnalyzer(db_session=db_session)
        style = await analyzer.get_style("user-1")
        assert style.confidence >= 1.0
        assert style.fast_paced is True
        assert style.interactive is True
        assert style.example_heavy is True

    @pytest.mark.asyncio
    async def test_cached_style_in_user_model(self, db_session):
        """用户表中已缓存风格时直接返回"""
        cached_style = {
            "visual_score": 0.4,
            "auditory_score": 0.2,
            "reading_score": 0.3,
            "kinesthetic_score": 0.1,
            "fast_paced": False,
            "step_by_step": True,
            "holistic": False,
            "example_heavy": True,
            "theory_first": False,
            "problem_based": False,
            "interactive": True,
            "self_paced": False,
            "confidence": 0.8,
        }
        user = UserModel(
            id="user-1", username="testuser",
            learning_style_json=json.dumps(cached_style),
        )
        db_session.add(user)
        await db_session.flush()

        analyzer = LearningStyleAnalyzer(db_session=db_session)
        style = await analyzer.get_style("user-1")
        assert style.confidence == 0.8
        assert style.visual_score == 0.4
        assert style.step_by_step is True

    @pytest.mark.asyncio
    async def test_update_from_session(self, db_session):
        """从会话数据更新风格"""
        user = UserModel(
            id="user-1", username="testuser",
        )
        db_session.add(user)
        await db_session.flush()

        analyzer = LearningStyleAnalyzer(db_session=db_session)
        from app.modules.learning_plan.schemas import SessionData
        session_data = SessionData(
            content_types_viewed={"visual": 5, "text": 2, "practice": 3},
            question_count=8,
            practice_correct_rate=0.9,
            practice_speed=1.5,
        )
        await analyzer.update_from_session("user-1", session_data)

        # 验证风格已更新
        result = await db_session.execute(
            select(UserModel).where(UserModel.id == "user-1")
        )
        updated_user = result.scalar_one()
        saved = json.loads(updated_user.learning_style_json)
        assert saved["fast_paced"] is True
        assert saved["interactive"] is True
        assert saved["example_heavy"] is True

    def test_calculate_confidence(self):
        """置信度计算"""
        analyzer = LearningStyleAnalyzer()
        assert analyzer._calculate_confidence(0) == 0.0
        assert analyzer._calculate_confidence(5) == 0.5
        assert analyzer._calculate_confidence(10) == 1.0
        assert analyzer._calculate_confidence(20) == 1.0
