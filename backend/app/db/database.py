"""数据库引擎和会话管理"""
import logging
from pathlib import Path
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
    engine = create_async_engine(db_url, echo=False)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    logger.info(f"数据库引擎初始化: {db_url}")


async def get_db():
    """FastAPI依赖注入用的异步数据库session生成器"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.warning("数据库事务回滚")
            raise


async def init_db():
    """创建所有表"""
    from app.db.models import (
        UserModel, BookModel, ChapterModel, KnowledgeUnitModel,
        MasteryRecordModel, AnnotationModel, LearningRecordModel,
        KGNodeModel, KGEdgeModel, CacheEntryModel, DailyStatsModel,
        ReviewSessionModel, TeachingSessionModel, TeachingMessageModel,
        UserQuestionModel, SessionTestModel,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表初始化完成")
