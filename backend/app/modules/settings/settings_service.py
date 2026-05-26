"""设置服务层 — 封装 .env 文件读写逻辑"""
from pathlib import Path
import os

ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"


def read_env() -> dict[str, str]:
    """读取 .env 文件，返回键值对字典"""
    result: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def write_env(updates: dict[str, str | None]):
    """更新 .env 文件，合并现有配置，跳过 None 值。

    写入后同步更新 os.environ，使当前进程生效。
    """
    existing = read_env()
    existing.update({k: v for k, v in updates.items() if v is not None})
    lines = [f'{k}="{v}"' for k, v in sorted(existing.items())]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # 同步到环境变量，使当前进程生效
    os.environ.update({k: v for k, v in updates.items() if v is not None})
