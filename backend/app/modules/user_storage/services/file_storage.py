"""文件存储服务"""
import os
from uuid import uuid4

from app.common.errors import ServiceError, ErrorCode


class FileStorage:
    def __init__(self, base_dir: str):
        self.base_dir = os.path.realpath(base_dir)

    def _validate_path(self, file_path: str) -> str:
        real_path = os.path.realpath(file_path)
        if not real_path.startswith(self.base_dir + os.sep) and real_path != self.base_dir:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, "非法文件路径")
        return real_path

    async def store(self, user_id: str, filename: str, content: bytes) -> str:
        safe_filename = os.path.basename(filename)
        user_dir = os.path.join(self.base_dir, user_id)
        os.makedirs(user_dir, exist_ok=True)
        unique_name = f"{uuid4()}_{safe_filename}"
        file_path = os.path.join(user_dir, unique_name)
        import aiofiles
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        return file_path

    async def retrieve(self, file_path: str) -> bytes:
        real_path = self._validate_path(file_path)
        if not os.path.exists(real_path):
            raise ServiceError(ErrorCode.NOT_FOUND, f"文件不存在: {file_path}")
        import aiofiles
        async with aiofiles.open(real_path, "rb") as f:
            return await f.read()

    async def delete(self, file_path: str) -> None:
        real_path = self._validate_path(file_path)
        if os.path.exists(real_path):
            os.remove(real_path)
