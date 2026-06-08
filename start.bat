@echo off
chcp 65001 >nul
title 学习辅助系统 - 启动中...

echo ========================================
echo       学习辅助系统 - 启动中...
echo ========================================
echo.

:: 清理端口
echo 正在清理端口...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
timeout /t 2 /nobreak >nul

:: 创建必要目录
if not exist "%~dp0backend\data\files" mkdir "%~dp0backend\data\files"
if not exist "%~dp0backend\data\backups" mkdir "%~dp0backend\data\backups"

:: 启动后端（使用 start /D 指定工作目录，避免引号嵌套问题）
:: 注意：不使用 --reload，避免文件监控在 AI 学习过程中重启服务器导致请求中断
:: 开发时如需热重载，手动运行: cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
echo [1/2] 启动后端服务...
start "学习辅助系统-后端" /D "%~dp0backend" cmd /k "uvicorn app.main:app --host 0.0.0.0 --port 8000"

:: 等待后端启动
timeout /t 3 /nobreak >nul

:: 启动前端
echo [2/2] 启动前端服务...
start "学习辅助系统-前端" /D "%~dp0frontend" cmd /k "npm run dev"

:: 等待前端启动
timeout /t 5 /nobreak >nul

:: 打开浏览器
echo.
echo 正在打开浏览器...
start http://localhost:3000

echo.
echo ========================================
echo  启动完成！
echo  后端: http://localhost:8000
echo  前端: http://localhost:3000
echo  API:  http://localhost:8000/docs
echo ========================================
echo.
echo 按任意键关闭此窗口...
pause >nul
