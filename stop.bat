@echo off
chcp 65001 >nul
title 学习辅助系统 - 停止服务

echo ========================================
echo        学习辅助系统 - 停止服务
echo ========================================
echo.

echo 正在停止后端服务...
taskkill /F /IM uvicorn.exe 2>nul
taskkill /F /IM python.exe /FI "MODULES eq uvicorn" 2>nul

echo 正在停止前端服务...
taskkill /F /IM node.exe 2>nul

:: 停止占用端口的进程
echo 正在清理端口...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo 停止进程 %%a (端口 8000)
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do (
    echo 停止进程 %%a (端口 3000)
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo ========================================
echo  服务已停止！端口已清理！
echo ========================================
echo.
pause
