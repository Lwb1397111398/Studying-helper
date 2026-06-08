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


async def get_default_llm_client() -> OpenAIClient:
    """获取默认 LLM 客户端。"""
    return await get_llm_client("default")


async def get_teaching_llm_client() -> OpenAIClient:
    """获取教学模块的 LLM 客户端。"""
    return await get_llm_client("teaching")


async def get_ai_analysis_llm_client() -> OpenAIClient:
    """获取 AI 分析模块的 LLM 客户端。"""
    return await get_llm_client("ai_analysis")


async def get_parser_llm_client() -> OpenAIClient:
    """获取文档解析模块的 LLM 客户端。"""
    return await get_llm_client("parser")


async def clear_llm_client_cache(module: str | None = None) -> None:
    """清除 LLM 客户端缓存，下次请求时用新配置重建。

    Args:
        module: 指定模块名，None 表示清除所有
    """
    async with _llm_lock:
        if module:
            client = _module_clients.pop(module, None)
            if client:
                await client.close()
        else:
            for client in _module_clients.values():
                await client.close()
            _module_clients.clear()


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


async def get_current_user() -> str:
    """单机模式下固定返回 anonymous"""
    return "anonymous"
