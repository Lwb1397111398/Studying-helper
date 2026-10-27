"""Studying-helper 桌面启动器（PyInstaller frozen / 本机直接跑均可）。

- 端口默认 8765，占用则递增
- 默认绑定 127.0.0.1；APP_LAN=1 时 0.0.0.0
- 启动后打开浏览器；控制台保留日志
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _ensure_sys_path() -> None:
    """开发模式下保证 backend 在 path 上。"""
    here = Path(__file__).resolve().parent
    # launcher 在 backend/ 下
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))


def find_free_port(start: int = 8765, attempts: int = 30) -> int:
    host = "127.0.0.1"
    for i in range(attempts):
        port = start + i
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"无法在 {start}–{start + attempts - 1} 找到空闲端口")


def main() -> None:
    _ensure_sys_path()

    # 在 import app 之前设好数据目录语义（frozen 时 paths 用 exe 旁 data/）
    from app.paths import (
        ensure_data_dirs,
        ensure_default_env,
        is_frozen,
        path_audit_snapshot,
    )

    ensure_data_dirs()
    env_path = ensure_default_env()
    # 让 pydantic settings 能读到（若进程尚未 load）
    os.environ.setdefault("APP_ENV_FILE", str(env_path))

    port = int(os.environ.get("APP_PORT") or find_free_port(8765))
    lan = (os.environ.get("APP_LAN") or "").strip() in ("1", "true", "TRUE", "yes")
    host = "0.0.0.0" if lan else "127.0.0.1"
    open_url = f"http://127.0.0.1:{port}"

    print("=" * 56)
    print("  Studying-helper 学习辅助系统")
    print("=" * 56)
    print(f"  访问地址: {open_url}")
    if lan:
        print(f"  局域网:   http://<本机IP>:{port}  (APP_LAN=1)")
    print(f"  数据目录: {path_audit_snapshot()['data_dir']}")
    print(f"  配置文件: {env_path}")
    print(f"  frozen:   {is_frozen()}")
    print("  关闭本窗口即停止服务。Ctrl+C 也可退出。")
    print("=" * 56)

    def _open():
        time.sleep(1.5)
        try:
            webbrowser.open(open_url)
        except Exception as exc:
            print(f"[warn] 无法自动打开浏览器: {exc}，请手动访问 {open_url}")

    if (os.environ.get("APP_NO_BROWSER") or "").strip() not in ("1", "true", "TRUE"):
        threading.Thread(target=_open, daemon=True).start()

    import uvicorn
    from app.main import app

    # 直接传 app 对象，避免 frozen 下 string import 失败
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        lifespan="on",
    )


if __name__ == "__main__":
    main()
