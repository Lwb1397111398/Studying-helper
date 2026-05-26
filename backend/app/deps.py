"""FastAPI依赖注入"""
import asyncio
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.config import settings
from app.common.llm_client import OpenAIClient
from app.modules.user_storage.services import (
    UserService, BookService, LearningRecordService, CacheService, FileStorage,
)
from app.modules.user_storage.auth import get_current_user_id

# 全局LLM客户端实例（延迟初始化）
_llm_client: OpenAIClient | None = None
_llm_lock = asyncio.Lock()


async def get_llm_client() -> OpenAIClient:
    """获取LLM客户端单例（线程安全）"""
    global _llm_client
    if _llm_client is None:
        async with _llm_lock:
            if _llm_client is None:
                _llm_client = OpenAIClient(
                    api_key=settings.LLM_API_KEY,
                    model=settings.LLM_MODEL,
                    base_url=settings.LLM_BASE_URL,
                )
    return _llm_client


async def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


async def get_book_service(db: AsyncSession = Depends(get_db)) -> BookService:
    return BookService(db)


async def get_record_service(db: AsyncSession = Depends(get_db)) -> LearningRecordService:
    return LearningRecordService(db)


async def get_cache_service(db: AsyncSession = Depends(get_db)) -> CacheService:
    return CacheService(db)


async def get_file_storage() -> FileStorage:
    return FileStorage(settings.FILE_STORAGE_DIR)


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> str:
    """
    验证 user_id 对应的用户存在，返回 user_id。
    anonymous 直接放行（向后兼容）。
    """
    if user_id == "anonymous":
        return user_id
    from app.modules.user_storage.services.user_service import UserService
    await UserService(db).get_user(user_id)
    return user_id
