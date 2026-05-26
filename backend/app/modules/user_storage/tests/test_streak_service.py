"""StreakService 测试"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.database import Base
from app.db.models import UserModel, DailyStatsModel
from app.modules.user_storage.services.streak_service import StreakService
from app.modules.user_storage.services.user_service import UserService


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


async def _create_user(db, username="streaktest"):
    svc = UserService(db)
    return await svc.create_user(username=username)


@pytest.mark.asyncio
async def test_streak_zero_when_no_data(db_session):
    """无数据时连续天数为 0"""
    user = await _create_user(db_session)
    svc = StreakService(db_session)
    streak = await svc.calculate_streak(user.id)
    assert streak == 0


@pytest.mark.asyncio
async def test_streak_continuous_days(db_session):
    """连续 5 天有学习记录"""
    user = await _create_user(db_session)
    today = datetime.now(timezone.utc).date()
    for i in range(5):
        d = today - timedelta(days=i)
        db_session.add(DailyStatsModel(
            user_id=user.id,
            date=d.strftime("%Y-%m-%d"),
            total_minutes=30,
        ))
    await db_session.flush()

    svc = StreakService(db_session)
    streak = await svc.calculate_streak(user.id)
    assert streak == 5


@pytest.mark.asyncio
async def test_streak_breaks_on_gap(db_session):
    """中间断了就停止计数"""
    user = await _create_user(db_session)
    today = datetime.now(timezone.utc).date()
    # 今天、昨天有记录，前天无，大前天有
    for offset in [0, 1, 3]:
        d = today - timedelta(days=offset)
        db_session.add(DailyStatsModel(
            user_id=user.id,
            date=d.strftime("%Y-%m-%d"),
            total_minutes=30,
        ))
    await db_session.flush()

    svc = StreakService(db_session)
    streak = await svc.calculate_streak(user.id)
    assert streak == 2  # 今天 + 昨天，前天断了


@pytest.mark.asyncio
async def test_streak_zero_minute_day_breaks(db_session):
    """total_minutes=0 的天不算连续"""
    user = await _create_user(db_session)
    today = datetime.now(timezone.utc).date()
    # 今天 30 分钟，昨天 0 分钟
    db_session.add(DailyStatsModel(
        user_id=user.id,
        date=today.strftime("%Y-%m-%d"),
        total_minutes=30,
    ))
    db_session.add(DailyStatsModel(
        user_id=user.id,
        date=(today - timedelta(days=1)).strftime("%Y-%m-%d"),
        total_minutes=0,
    ))
    await db_session.flush()

    svc = StreakService(db_session)
    streak = await svc.calculate_streak(user.id)
    assert streak == 1  # 只有今天
