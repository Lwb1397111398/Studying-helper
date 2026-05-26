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

# 模块级 LLM 客户端缓存 {module_name: OpenAIClient}
_module_clients: dict[str, OpenAIClient] = {}
_llm_lock = asyncio.Lock()


async def get_llm_client(module: str = "default") -> OpenAIClient:
    """获取指定模块的 LLM 客户端。

    相同 module 复用同一实例，不同 module 使用各自的配置和实例。
    module="default" 时向后兼容原有行为。
    """
    if module in _module_clients:
        return _module_clients[module]

    async with _llm_lock:
        if module in _module_clients:
            return _module_clients[module]
        cfg = settings.get_llm_config(module)
        client = OpenAIClient(
            api_key=cfg["api_key"],
            model=cfg["model"],
            base_url=cfg["base_url"],
        )
        _module_clients[module] = client
        return client


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
