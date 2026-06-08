"""数据库引擎和会话管理"""
import logging
from pathlib import Path
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = None
async_session_factory = None


def init_engine(db_url: str):
    """初始化数据库引擎"""
    global engine, async_session_factory
    if "sqlite" in db_url:
        db_path = db_url.split("///")[-1]
        if db_path.startswith("./"):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(
        db_url,
        echo=False,
        connect_args={"timeout": 30} if "sqlite" in db_url else {},
    )
    # SQLite WAL 模式：允许读写并发，减少锁冲突
    if "sqlite" in db_url:
        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    logger.info(f"数据库引擎初始化: {db_url}")


async def get_db():
    """FastAPI依赖注入用的异步数据库session生成器"""
    if async_session_factory is None:
        raise RuntimeError("数据库未初始化，请先调用 init_engine()")
    async with async_session_factory() as session:
        try:
            yield session
            # 正常结束时自动提交
            await session.commit()
        except Exception:
            await session.rollback()
            logger.warning("数据库事务回滚")
            raise


async def init_db():
    """创建所有表"""
    if engine is None:
        raise RuntimeError("数据库引擎未初始化，请先调用 init_engine()")
    from app.db.models import (
        UserModel, BookModel, ChapterModel, KnowledgeUnitModel,
        MasteryRecordModel, AnnotationModel, LearningRecordModel,
        KGNodeModel, KGEdgeModel, CacheEntryModel, DailyStatsModel,
        ReviewSessionModel, TeachingSessionModel, TeachingMessageModel,
        UserQuestionModel, SessionTestModel, LearningEfficiencyModel,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 增量迁移：给已有表添加新列
        await _run_migrations(conn)
    logger.info("数据库表初始化完成")

    # 确保默认用户存在（单机模式，无需登录）
    from sqlalchemy import select
    from app.common.time_utils import utc_now
    async with async_session_factory() as session:
        result = await session.execute(select(UserModel).where(UserModel.id == "anonymous"))
        if result.scalar_one_or_none() is None:
            now = utc_now()
            session.add(UserModel(
                id="anonymous", username="本地用户",
                daily_goal_minutes=30, preferred_language="zh",
                created_at=now, updated_at=now,
            ))
            await session.commit()
            logger.info("已创建默认用户 anonymous")


async def _run_migrations(conn):
    """增量迁移：给已有表添加新列（安全，已存在则跳过）"""
    import sqlalchemy as sa

    async def _add_column_if_missing(table: str, column: str, col_type):
        try:
            await conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            logger.info(f"迁移：已添加 {table}.{column}")
        except Exception as exc:
            if "duplicate column" in str(exc).lower():
                return
            logger.exception("迁移失败：%s.%s", table, column)
            raise

    await _add_column_if_missing("knowledge_units", "explanation", "TEXT")
    # Task #10: 结构化笔记 - 给 annotations 表添加新列
    await _add_column_if_missing("annotations", "related_concepts_json", "TEXT DEFAULT '[]'")
    await _add_column_if_missing("annotations", "example", "TEXT")
    await _add_column_if_missing("annotations", "cornell_cues", "TEXT")
    await _add_column_if_missing("annotations", "cornell_summary", "TEXT")
    await _add_column_if_missing("teaching_messages", "assessment_json", "TEXT")
    # 书籍阅读动机
    await _add_column_if_missing("books", "reading_motivation", "TEXT")
