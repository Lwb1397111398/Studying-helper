@echo off
chcp 65001 >nul
title 学习辅助系统 - 停止服务

echo ========================================
echo        学习辅助系统 - 停止服务
echo ========================================
echo.

echo 正在停止后端服务...
taskkill /FI "WINDOWTITLE eq 学习辅助系统-后端*" /F >nul 2>&1

echo 正在停止前端服务...
taskkill /FI "WINDOWTITLE eq 学习辅助系统-前端*" /F >nul 2>&1

:: 停止占用端口的进程
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do taskkill /PID %%a /F >nul 2>&1

echo.
echo 服务已停止！
echo.
pause
