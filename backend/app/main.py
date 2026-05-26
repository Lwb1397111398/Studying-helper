"""FastAPI主应用"""
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化数据库，关闭时清理资源"""
    init_engine(settings.DB_URL)
    await init_db()
    yield
    # 关闭LLM客户端
    import app.deps as deps_mod
    client = deps_mod._llm_client
    if client is not None:
        await client.close()


app = FastAPI(title="学习辅助系统", version="1.0.0", lifespan=lifespan)

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
app.include_router(user_router, prefix="/api/v1")
app.include_router(doc_router)
app.include_router(split_router)
app.include_router(learning_router)
app.include_router(plan_router)
app.include_router(teaching_router)
app.include_router(review_router)
app.include_router(kg_router)
app.include_router(settings_router)
