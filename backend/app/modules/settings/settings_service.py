"""设置服务层 — 封装 .env 文件读写逻辑"""
from pathlib import Path
import asyncio
import os
import re
import tempfile

# 异步写锁，防止并发写入损坏文件（FastAPI 异步环境下 threading.Lock 无效）
_write_lock = asyncio.Lock()


def _env_path() -> Path:
    """运行时解析 .env 路径（支持 frozen / APP_DATA_DIR）。

    若外部显式改写了模块级 ENV_FILE（测试或旧代码），以它为准。
    """
    if ENV_FILE != _DEFAULT_ENV_FILE:
        return ENV_FILE
    try:
        from app.paths import get_env_file, ensure_data_dirs
        ensure_data_dirs()
        return get_env_file()
    except Exception:
        return _DEFAULT_ENV_FILE


# 兼容旧代码引用 ENV_FILE；被改写时 _env_path() 会优先使用它
_DEFAULT_ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"
ENV_FILE = _DEFAULT_ENV_FILE


def read_env() -> dict[str, str]:
    """读取 .env 文件，返回键值对字典（支持行内注释）"""
    result: dict[str, str] = {}
    env_file = _env_path()
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            value = re.sub(r"\s+#.*$", "", value)
            result[key] = value
    return result


async def write_env(updates: dict[str, str | None]):
    """更新 .env 文件，合并现有配置，跳过 None 值。

    使用异步锁 + 原子写入（写临时文件后重命名）防止并发损坏。
    写入后同步更新 os.environ 和 settings 单例。
    """
    async with _write_lock:
        env_file = _env_path()
        env_file.parent.mkdir(parents=True, exist_ok=True)
        existing = read_env()
        existing.update({k: v for k, v in updates.items() if v is not None})
        lines = [f'{k}="{v}"' for k, v in sorted(existing.items())]
        content = "\n".join(lines) + "\n"

        fd, tmp_path = tempfile.mkstemp(
            dir=str(env_file.parent), suffix=".env.tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(env_file))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    os.environ.update({k: v for k, v in updates.items() if v is not None})

    from app.config import settings
    for key, value in updates.items():
        if value is not None and hasattr(settings, key):
            setattr(settings, key, value)
