@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo  Studying-helper Windows exe 构建
echo ============================================

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] 未找到 python，请先安装 Python 3.11+ 并加入 PATH
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] 未找到 npm，请先安装 Node.js
  exit /b 1
)

echo [1/6] 安装后端依赖 + pyinstaller ...
python -m pip install -q -r backend\requirements.txt pyinstaller aiofiles pillow 2>nul
if errorlevel 1 (
  echo [ERROR] pip install 失败
  exit /b 1
)

echo [2/6] 生成应用图标 packaging\app.ico ...
if exist 学习助手的图标.png (
  python scripts\make_app_icon.py
  if errorlevel 1 (
    echo [WARN] 图标生成失败，沿用已有 packaging\app.ico
  )
) else (
  echo [WARN] 未找到 学习助手的图标.png，沿用已有 packaging\app.ico
)
if not exist packaging\app.ico (
  echo [ERROR] packaging\app.ico 不存在，无法打包图标
  exit /b 1
)

echo [3/6] 构建前端 dist ...
pushd frontend
call npm install
if errorlevel 1 (
  echo [ERROR] npm install 失败
  popd
  exit /b 1
)
call npm run build
if errorlevel 1 (
  echo [ERROR] npm run build 失败
  popd
  exit /b 1
)
popd

echo [4/6] 收集 frontend dist 到 packaging\frontend_dist ...
if exist packaging\frontend_dist rmdir /s /q packaging\frontend_dist
mkdir packaging\frontend_dist
xcopy /E /I /Y frontend\dist\* packaging\frontend_dist\ >nul
if not exist packaging\frontend_dist\index.html (
  echo [ERROR] packaging\frontend_dist\index.html 不存在
  exit /b 1
)

echo [5/6] PyInstaller onefile ...
if exist build rmdir /s /q build
if exist dist_exe rmdir /s /q dist_exe
python -m PyInstaller --noconfirm --clean --distpath dist_exe --workpath build studying_helper.spec
if errorlevel 1 (
  echo [ERROR] PyInstaller 失败，请根据上方缺模块提示补 hiddenimports 后重试
  exit /b 1
)

echo [6/6] 附带 README 与便携目录说明 ...
copy /Y README_EXE.txt dist_exe\README_EXE.txt >nul 2>&1
if not exist dist_exe\data mkdir dist_exe\data

echo.
echo ============================================
echo  构建完成
echo  产物: dist_exe\StudyingHelper.exe
echo  用法: 把 StudyingHelper.exe 拷到任意目录双击
echo        同级会自动生成 data\ 存放数据库与上传文件
echo ============================================
dir dist_exe\StudyingHelper.exe
endlocal
