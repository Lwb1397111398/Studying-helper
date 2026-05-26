"""文件存储服务"""
import os
from uuid import uuid4

from app.common.errors import ServiceError, ErrorCode


class FileStorage:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    async def store(self, user_id: str, filename: str, content: bytes) -> str:
        user_dir = os.path.join(self.base_dir, user_id)
        os.makedirs(user_dir, exist_ok=True)
        unique_name = f"{uuid4()}_{filename}"
        file_path = os.path.join(user_dir, unique_name)
        # 用异步写文件避免阻塞事件循环
        import aiofiles
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        return file_path

    async def retrieve(self, file_path: str) -> bytes:
        if not os.path.exists(file_path):
            raise ServiceError(ErrorCode.NOT_FOUND, f"文件不存在: {file_path}")
        import aiofiles
        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def delete(self, file_path: str) -> None:
        if os.path.exists(file_path):
            os.remove(file_path)
