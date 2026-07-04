"""FastAPI主应用"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    init_engine(settings.DB_URL)
    await init_db()
    # 初始化 LLM 并发信号量
    from app.common.llm_client import init_semaphore
    init_semaphore(settings.LLM_MAX_CONCURRENT)
    yield
    # 优雅关闭：先通知停止接受新请求，再等待在途请求完成
    from app.common.llm_client import request_shutdown, wait_inflight
    request_shutdown()
    await wait_inflight(timeout=120.0)
    # 关闭所有模块级 LLM 客户端
    import app.deps as deps_mod
    for client in deps_mod._module_clients.values():
        await client.close()
    deps_mod._module_clients.clear()


app = FastAPI(title="学习辅助系统", version="1.0.0", lifespan=lifespan)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
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


# 注册路由
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
