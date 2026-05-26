"""用户与存储模块的测试用例"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.db.database import Base
from app.modules.user_storage.service import (
    UserService, BookService, LearningRecordService, CacheService,
)


@pytest_asyncio.fixture
async def db_session():
    """创建内存SQLite测试数据库"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    """测试创建用户"""
    svc = UserService(db_session)
    user = await svc.create_user(username="testuser", email="test@example.com")
    assert user.id is not None
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.daily_goal_minutes == 30
    assert user.preferred_language == "zh"


@pytest.mark.asyncio
async def test_get_user(db_session: AsyncSession):
    """测试获取用户"""
    svc = UserService(db_session)
    created = await svc.create_user(username="fetchme")
    fetched = await svc.get_user(created.id)
    assert fetched.id == created.id
    assert fetched.username == "fetchme"


@pytest.mark.asyncio
async def test_update_preferences(db_session: AsyncSession):
    """测试更新用户偏好"""
    svc = UserService(db_session)
    user = await svc.create_user(username="prefuser")
    updated = await svc.update_preferences(
        user.id, daily_goal_minutes=60, preferred_language="en"
    )
    assert updated.daily_goal_minutes == 60
    assert updated.preferred_language == "en"


@pytest.mark.asyncio
async def test_get_profile_aggregation(db_session: AsyncSession):
    """测试用户画像聚合"""
    user_svc = UserService(db_session)
    user = await svc_user(user_svc, "profileuser")

    book_svc = BookService(db_session)
    await book_svc.upload_book(
        user_id=user.id, title="Test Book", file_path="/tmp/test.pdf",
        file_type="pdf", file_size_bytes=1024,
    )

    profile = await user_svc.get_profile(user.id)
    assert profile["total_books"] == 1
    assert profile["total_learning_minutes"] == 0
    assert profile["current_streak"] == 0


@pytest.mark.asyncio
async def test_upload_book(db_session: AsyncSession):
    """测试上传书籍"""
    user_svc = UserService(db_session)
    user = await svc_user(user_svc, "bookuser")

    book_svc = BookService(db_session)
    book = await book_svc.upload_book(
        user_id=user.id, title="Python编程", author="张三",
        file_path="/files/python.epub", file_type="epub", file_size_bytes=2048,
    )
    assert book.id is not None
    assert book.title == "Python编程"
    assert book.user_id == user.id
    assert book.parse_status == "pending"


@pytest.mark.asyncio
async def test_list_books(db_session: AsyncSession):
    """测试列出书籍"""
    user_svc = UserService(db_session)
    user = await svc_user(user_svc, "listuser")

    book_svc = BookService(db_session)
    for i in range(5):
        await book_svc.upload_book(
            user_id=user.id, title=f"Book {i}", file_path=f"/files/book{i}.pdf",
            file_type="pdf", file_size_bytes=100,
        )

    result = await book_svc.list_books(user.id, page=1, page_size=3)
    assert result["total"] == 5
    assert len(result["items"]) == 3
    assert result["has_next"] is True


@pytest.mark.asyncio
async def test_delete_book_cascades(db_session: AsyncSession):
    """测试级联删除书籍"""
    user_svc = UserService(db_session)
    user = await svc_user(user_svc, "deluser")

    book_svc = BookService(db_session)
    book = await book_svc.upload_book(
        user_id=user.id, title="ToDelete", file_path="/tmp/del.pdf",
        file_type="pdf", file_size_bytes=512,
    )
    book_id = book.id
    await book_svc.delete_book(book_id)

    # 验证已删除
    from app.common.errors import ServiceError
    with pytest.raises(ServiceError):
        await book_svc.get_book(book_id)


@pytest.mark.asyncio
async def test_create_record(db_session: AsyncSession):
    """测试创建学习记录"""
    user_svc = UserService(db_session)
    user = await svc_user(user_svc, "recuser")

    book_svc = BookService(db_session)
    book = await book_svc.upload_book(
        user_id=user.id, title="Record Book", file_path="/tmp/rec.pdf",
        file_type="pdf", file_size_bytes=100,
    )

    rec_svc = LearningRecordService(db_session)
    record = await rec_svc.create_record(user_id=user.id, book_id=book.id, session_id="sess-1")
    assert record.id is not None
    assert record.ended_at is None


@pytest.mark.asyncio
async def test_streak_calculation(db_session: AsyncSession):
    """测试连续天数计算"""
    from app.db.models import DailyStatsModel
    from datetime import datetime, timedelta, timezone

    user_svc = UserService(db_session)
    user = await svc_user(user_svc, "streakuser")

    # 插入连续3天的统计数据
    today = datetime.now(timezone.utc).date()
    for i in range(3):
        d = today - timedelta(days=i)
        stats = DailyStatsModel(
            user_id=user.id,
            date=d.strftime("%Y-%m-%d"),
            total_minutes=30,
            units_learned=2,
        )
        db_session.add(stats)
    await db_session.flush()

    rec_svc = LearningRecordService(db_session)
    streak = await rec_svc.get_streak(user.id)
    assert streak == 3


@pytest.mark.asyncio
async def test_cache_set_get(db_session: AsyncSession):
    """测试缓存读写"""
    svc = CacheService(db_session)

    await svc.set("test_key", "test_value", ttl_seconds=60)
    result = await svc.get("test_key")
    assert result == "test_value"


@pytest.mark.asyncio
async def test_cache_expiration(db_session: AsyncSession):
    """测试缓存过期"""
    from app.db.models import CacheEntryModel
    from datetime import datetime, timedelta, timezone

    svc = CacheService(db_session)

    # 手动插入一个已过期的条目
    past = datetime.now(timezone.utc) - timedelta(seconds=10)
    entry = CacheEntryModel(
        key="expired_key", value="old_value",
        created_at=past, expires_at=past,
    )
    db_session.add(entry)
    await db_session.flush()

    result = await svc.get("expired_key")
    assert result is None


# ========== 辅助函数 ==========

async def svc_user(svc: UserService, username: str):
    """快速创建测试用户"""
    return await svc.create_user(username=username)
