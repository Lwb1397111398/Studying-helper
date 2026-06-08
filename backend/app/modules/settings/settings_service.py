"""设置服务层 — 封装 .env 文件读写逻辑"""
from pathlib import Path
import asyncio
import os
import re
import tempfile

ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"

# 异步写锁，防止并发写入损坏文件（FastAPI 异步环境下 threading.Lock 无效）
_write_lock = asyncio.Lock()


def read_env() -> dict[str, str]:
    """读取 .env 文件，返回键值对字典（支持行内注释）"""
    result: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # 去除行内注释（# 前必须有空格，避免误删 URL 中的 #）
            value = re.sub(r'\s+#.*$', '', value)
            result[key] = value
    return result


async def write_env(updates: dict[str, str | None]):
    """更新 .env 文件，合并现有配置，跳过 None 值。

    使用异步锁 + 原子写入（写临时文件后重命名）防止并发损坏。
    写入后同步更新 os.environ 和 settings 单例。
    """
    async with _write_lock:
        existing = read_env()
        existing.update({k: v for k, v in updates.items() if v is not None})
        lines = [f'{k}="{v}"' for k, v in sorted(existing.items())]
        content = "\n".join(lines) + "\n"

        # 原子写入：先写临时文件，再重命名
        fd, tmp_path = tempfile.mkstemp(
            dir=str(ENV_FILE.parent), suffix=".env.tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(ENV_FILE))
        except Exception:
            # 清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # 同步到环境变量，使当前进程生效
    os.environ.update({k: v for k, v in updates.items() if v is not None})

    # 同步 settings 单例
    from app.config import settings
    for key, value in updates.items():
        if value is not None and hasattr(settings, key):
            setattr(settings, key, value)
