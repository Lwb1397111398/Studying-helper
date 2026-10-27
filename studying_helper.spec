# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Studying-helper onefile Windows exe."""

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

block_cipher = None

ROOT = Path(SPECPATH).resolve()
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "packaging" / "frontend_dist"

datas = []
binaries = []
hiddenimports = []

for pkg in (
    "chardet",
    "pdfplumber",
    "pdfminer",
    "ebooklib",
    "bs4",
    "openai",
    "httpx",
    "anyio",
    "pydantic",
    "pydantic_core",
    "sqlalchemy",
    "aiosqlite",
    "uvicorn",
    "starlette",
    "fastapi",
    "multipart",
    "aiofiles",
    "greenlet",
    "certifi",
):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:
        print(f"collect_all({pkg}) skip: {exc}")

if FRONTEND_DIST.is_dir():
    datas.append((str(FRONTEND_DIST), "frontend_dist"))
else:
    print("WARNING: packaging/frontend_dist missing")

hiddenimports += [
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "anyio._backends._asyncio",
    "sqlalchemy.dialects.sqlite",
    "app",
    "app.main",
    "app.config",
    "app.paths",
    "app.deps",
    "app.db.database",
    "app.db.models",
    "app.common.llm_client",
    "app.common.errors",
    "app.modules.user_storage.router",
    "app.modules.document_parser.router",
    "app.modules.document_parser.parsers.pdf_parser",
    "app.modules.document_parser.parsers.txt_parser",
    "app.modules.document_parser.parsers.epub_parser",
    "app.modules.knowledge_splitter.router",
    "app.modules.ai_learning.router",
    "app.modules.learning_plan.router",
    "app.modules.teaching.router",
    "app.modules.teaching.router_v2",
    "app.modules.review.router",
    "app.modules.knowledge_graph.router",
    "app.modules.settings.router",
    "app.modules.sync.router",
    "app.modules.adaptive_design.router",
    "app.modules.learning_assets.router",
    "jwt",
    "email_validator",
]
_seen = set()
hiddenimports = [x for x in hiddenimports if not (x in _seen or _seen.add(x))]

a = Analysis(
    [str(BACKEND / "launcher.py")],
    pathex=[str(BACKEND)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pandas", "scipy", "pytest", "IPython"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="StudyingHelper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "packaging" / "app.ico"),
)
