@echo off
chcp 65001 >nul

echo ========================================
echo       Learning Helper - Starting
echo ========================================
echo.

:: Create required directories
cd /d "%~dp0backend"
if not exist "data\files" mkdir "data\files"
if not exist "data\backups" mkdir "data\backups"

:: Start backend in new window
echo [1/2] Starting backend...
start "Learning Helper - Backend" cmd /k "cd /d "%~dp0backend" && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: Wait for backend
timeout /t 3 /nobreak >nul

:: Start frontend in new window
echo [2/2] Starting frontend...
start "Learning Helper - Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

:: Wait for frontend
timeout /t 5 /nobreak >nul

:: Open browser
echo.
echo Opening browser...
start http://localhost:3000

echo.
echo ========================================
echo  Backend: http://localhost:8000
echo  Frontend: http://localhost:3000
echo  API Docs: http://localhost:8000/docs
echo ========================================
echo.
echo Press any key to exit this window...
pause >nul
