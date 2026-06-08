"""智能启动脚本 - 自动检测可用端口"""
import socket
import subprocess
import sys
import os
import time

def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """查找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"无法找到可用端口（尝试了 {start_port}-{start_port + max_attempts - 1}）")

def main():
    # 默认端口
    backend_port = 8000
    frontend_port = 3000

    # 检测可用端口
    try:
        backend_port = find_available_port(8000)
        frontend_port = find_available_port(3000)
    except RuntimeError as e:
        print(f"错误: {e}")
        sys.exit(1)

    print("=" * 50)
    print("      学习辅助系统 - 启动中...")
    print("=" * 50)
    print()

    # 创建必要目录
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    os.makedirs(os.path.join(backend_dir, "data", "files"), exist_ok=True)
    os.makedirs(os.path.join(backend_dir, "data", "backups"), exist_ok=True)

    # 启动后端
    print(f"[1/2] 启动后端服务 (端口: {backend_port})...")
    backend_cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", str(backend_port),
    ]
    backend_process = subprocess.Popen(
        backend_cmd,
        cwd=backend_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0,
    )

    # 等待后端启动
    time.sleep(3)

    # 启动前端
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    print(f"[2/2] 启动前端服务 (端口: {frontend_port})...")
    frontend_cmd = ["npm", "run", "dev"]
    env = os.environ.copy()
    env["PORT"] = str(frontend_port)
    frontend_process = subprocess.Popen(
        frontend_cmd,
        cwd=frontend_dir,
        env=env,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0,
    )

    # 等待前端启动
    time.sleep(5)

    # 打开浏览器
    url = f"http://localhost:{frontend_port}"
    print()
    print("=" * 50)
    print(f"  后端: http://localhost:{backend_port}")
    print(f"  前端: {url}")
    print(f"  API:  http://localhost:{backend_port}/docs")
    print("=" * 50)
    print()

    import webbrowser
    webbrowser.open(url)

    print("按 Ctrl+C 停止服务...")
    try:
        backend_process.wait()
    except KeyboardInterrupt:
        print("\n正在停止服务...")
        backend_process.terminate()
        frontend_process.terminate()
        print("服务已停止")

if __name__ == "__main__":
    main()
