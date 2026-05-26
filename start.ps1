<#
.SYNOPSIS
    学习辅助系统一键启动脚本
.DESCRIPTION
    同时启动后端(FastAPI)和前端(Vite)开发服务器
.EXAMPLE
    .\start.ps1
    .\start.ps1 -SkipInstall
#>

param(
    [switch]$SkipInstall,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       学习辅助系统 - 一键启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[√] Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[×] 未找到 Python，请先安装 Python 3.11+" -ForegroundColor Red
    exit 1
}

# 检查 Node.js
try {
    $nodeVersion = node --version 2>&1
    Write-Host "[√] Node.js: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[×] 未找到 Node.js，请先安装 Node.js 18+" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 安装依赖
if (-not $SkipInstall) {
    Write-Host "[1/4] 安装后端依赖..." -ForegroundColor Yellow
    Push-Location "$projectRoot\backend"
    pip install -r requirements.txt -q 2>$null
    if (-not (Test-Path "requirements.txt")) {
        pip install fastapi uvicorn sqlalchemy pydantic aiosqlite pdfplumber ebooklib chardet beautifulsoup4 httpx -q
    }
    Pop-Location
    Write-Host "      后端依赖完成" -ForegroundColor Green

    Write-Host "[2/4] 安装前端依赖..." -ForegroundColor Yellow
    Push-Location "$projectRoot\frontend"
    npm install --silent 2>$null
    Pop-Location
    Write-Host "      前端依赖完成" -ForegroundColor Green
} else {
    Write-Host "[1/4] 跳过后端依赖安装" -ForegroundColor Gray
    Write-Host "[2/4] 跳过前端依赖安装" -ForegroundColor Gray
}

Write-Host ""

# 启动后端
Write-Host "[3/4] 启动后端服务..." -ForegroundColor Yellow
$backendJob = Start-Process -FilePath "cmd" -ArgumentList "/c", "cd /d `"$projectRoot\backend`" && title 学习辅助系统-后端 && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" -WindowStyle Normal -PassThru
Write-Host "      后端已启动 (PID: $($backendJob.Id))" -ForegroundColor Green

# 等待后端启动
Start-Sleep -Seconds 3

# 启动前端
Write-Host "[4/4] 启动前端服务..." -ForegroundColor Yellow
$frontendJob = Start-Process -FilePath "cmd" -ArgumentList "/c", "cd /d `"$projectRoot\frontend`" && title 学习辅助系统-前端 && npm run dev" -WindowStyle Normal -PassThru
Write-Host "      前端已启动 (PID: $($frontendJob.Id))" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "           启动完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  后端地址: " -NoNewline; Write-Host "http://localhost:8000" -ForegroundColor Cyan
Write-Host "  前端地址: " -NoNewline; Write-Host "http://localhost:3000" -ForegroundColor Cyan
Write-Host "  API文档:  " -NoNewline; Write-Host "http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""

# 打开浏览器
if (-not $NoBrowser) {
    Write-Host "正在打开浏览器..." -ForegroundColor Yellow
    Start-Process "http://localhost:3000"
    Start-Sleep -Seconds 1
    Start-Process "http://localhost:8000/docs"
}

Write-Host ""
Write-Host "提示: 运行 stop.bat 可停止所有服务" -ForegroundColor Gray
Write-Host ""
