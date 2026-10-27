"""FastAPI主应用"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.common.errors import ServiceError, ERROR_STATUS_MAP
from app.db.database import init_engine, init_db
from app.modules.user_storage.router import router as user_router
from app.modules.document_parser.router import router as doc_router
from app.modules.knowledge_splitter.router import router as split_router
from app.modules.ai_learning.router import router as learning_router
from app.modules.learning_plan.router import router as plan_router
from app.modules.teaching.router import router as teaching_router
from app.modules.review.router import router as review_router
from app.modules.knowledge_graph.router import router as kg_router
from app.modules.settings.router import router as settings_router
from app.modules.sync.router import router as sync_router
from app.modules.adaptive_design.router import router as aid_router
from app.modules.learning_assets.router import router as learning_assets_router
from app.modules.teaching.router_v2 import router as teaching_v2_router
from app.paths import ensure_data_dirs, ensure_default_env, get_static_dir, path_audit_snapshot

# 过滤高频轮询接口的 uvicorn 访问日志
_POLLING_PATHS = ("/learn-progress", "/split/progress", "/parse")


class PollingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(path in msg for path in _POLLING_PATHS)


logging.getLogger("uvicorn.access").addFilter(PollingFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化数据库，关闭时清理资源"""
    ensure_data_dirs()
    try:
        ensure_default_env()
    except Exception as exc:
        logging.getLogger(__name__).warning("ensure_default_env failed: %s", exc)

    init_engine(settings.DB_URL)
    await init_db()
    from app.common.llm_client import init_semaphore
    init_semaphore(settings.LLM_MAX_CONCURRENT)
    logging.getLogger(__name__).info("paths: %s", path_audit_snapshot())
    yield
    from app.common.llm_client import request_shutdown, wait_inflight
    request_shutdown()
    await wait_inflight(timeout=120.0)
    import app.deps as deps_mod
    for client in deps_mod._module_clients.values():
        await client.close()
    deps_mod._module_clients.clear()


app = FastAPI(title="学习辅助系统", version="1.0.0", lifespan=lifespan)

_cors = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
if get_static_dir() is not None or os.environ.get("APP_STATIC_DIR") or settings.APP_STATIC_DIR:
    _cors = list(dict.fromkeys(_cors + [
        "http://127.0.0.1:8765", "http://localhost:8765",
        "http://127.0.0.1:8766", "http://localhost:8766",
        "http://127.0.0.1:8767", "http://localhost:8767",
    ]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ServiceError)
async def service_error_handler(request: Request, exc: ServiceError):
    """统一ServiceError异常处理"""
    status = ERROR_STATUS_MAP.get(exc.code, 500)
    return JSONResponse(
        status_code=status,
        content={"code": exc.code.value, "message": exc.message, "details": exc.details},
    )


app.include_router(user_router)
app.include_router(doc_router)
app.include_router(split_router)
app.include_router(learning_router)
app.include_router(plan_router)
app.include_router(teaching_router)
app.include_router(review_router)
app.include_router(kg_router)
app.include_router(settings_router)
app.include_router(sync_router)
app.include_router(aid_router)
app.include_router(learning_assets_router)
app.include_router(teaching_v2_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "paths": path_audit_snapshot()}


def _mount_spa() -> None:
    """生产模式：托管前端 dist；非 /api 回退 index.html。开发模式不 mount。"""
    static = get_static_dir()
    if static is None and getattr(settings, "APP_STATIC_DIR", ""):
        p = Path(settings.APP_STATIC_DIR)
        static = p if p.is_dir() else None
    if static is None:
        return

    static = static.resolve()
    assets = static / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    index = static / "index.html"
    if not index.is_file():
        logging.getLogger(__name__).warning("SPA index.html missing under %s", static)
        return

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (static / full_path).resolve()
        try:
            candidate.relative_to(static)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)

    logging.getLogger(__name__).info("SPA static mounted from %s", static)


_mount_spa()
