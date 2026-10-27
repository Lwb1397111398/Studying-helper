"""文档解析API路由"""

import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.common.llm_client import LLMClient
from app.common.time_utils import utc_now
from app.config import settings
from app.db.database import get_db
from app.deps import get_parser_llm_client
from app.db.models import BookModel, ChapterModel
from app.modules.document_parser.service import DocumentParserService, rebuild_book_from_toc
from app.modules.document_parser.parsers import PDFParser, TXTParser, EPUBParser
from app.modules.document_parser.schemas import TOCItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

DEFAULT_USER_ID = "anonymous"
_executor = ThreadPoolExecutor(max_workers=4)

# ── 解析进度内存存储 ──
_parse_progress: dict[str, dict] = {}
_PROGRESS_TTL = timedelta(hours=1)


def _cleanup_parse_progress():
    now = utc_now()
    expired = [
        uid for uid, prog in _parse_progress.items()
        if prog.get("done") and prog.get("updated_at")
        and now - datetime.fromisoformat(prog["updated_at"]) > _PROGRESS_TTL
    ]
    for uid in expired:
        del _parse_progress[uid]


def _update_parse_progress(upload_id: str, stage: str, percent: int, message: str,
                           done: bool = False, error: str = None, book: dict = None):
    _cleanup_parse_progress()
    entry = {
        "upload_id": upload_id,
        "stage": stage,
        "percent": percent,
        "message": message,
        "done": done,
        "error": error,
        "updated_at": utc_now().isoformat(),
    }
    if book is not None:
        entry["book"] = book
    _parse_progress[upload_id] = entry


class TOCConfirmItem(BaseModel):
    """用户确认的目录项"""
    title: str
    level: int = 0
    char_offset: int = 0


class TOCConfirmRequest(BaseModel):
    """目录确认请求"""
    items: list[TOCConfirmItem]


def _get_service(llm_client=None) -> DocumentParserService:
    """获取文档解析服务实例"""
    parsers = [PDFParser(), TXTParser(), EPUBParser()]
    return DocumentParserService(
        parsers=parsers,
        storage_dir=settings.FILE_STORAGE_DIR,
        llm_client=llm_client,
    )


async def _parse_in_executor(service: DocumentParserService, file_path: str, user_id: str):
    """在线程池中执行同步解析，避免阻塞事件循环"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: service.parse_and_store(file_path=file_path, user_id=user_id),
    )


# ── 异步解析：启动 + SSE 进度 ──

async def _execute_parse(upload_id: str, file_path: str, original_title: str,
                         parser_llm: LLMClient):
    """后台执行文档解析，分阶段推送进度"""
    from app.db.database import async_session_factory
    try:
        _update_parse_progress(upload_id, "reading", 5, "正在读取文件...")

        service = _get_service(llm_client=parser_llm)

        _update_parse_progress(upload_id, "reading", 15, "正在校验文件格式...")

        parsed = await _parse_in_executor(service, str(file_path), DEFAULT_USER_ID)

        _update_parse_progress(upload_id, "parsing", 50, "正在解析文档结构...")
        parsed.metadata.title = original_title

        _update_parse_progress(upload_id, "parsing", 70, f"已识别 {len(parsed.toc)} 个目录项")

        # 保存到数据库
        _update_parse_progress(upload_id, "saving", 80, "正在保存到数据库...")
        now = utc_now()
        book_id = parsed.id

        async with async_session_factory() as db:
            try:
                book = BookModel(
                    id=book_id,
                    user_id=DEFAULT_USER_ID,
                    title=parsed.metadata.title,
                    author=parsed.metadata.author,
                    file_path=str(file_path),
                    file_type=parsed.metadata.file_type,
                    file_size_bytes=parsed.metadata.file_size_bytes,
                    parse_status="completed",
                    total_chapters=len([t for t in parsed.toc if t.level == 0]),
                    created_at=now,
                    updated_at=now,
                )
                db.add(book)

                for i, toc_item in enumerate(parsed.toc):
                    if toc_item.level == 0:
                        chapter = ChapterModel(
                            id=toc_item.id,
                            book_id=book_id,
                            title=toc_item.title,
                            chapter_number=i + 1,
                            order_index=i,
                            level=toc_item.level,
                        )
                        db.add(chapter)

                await db.flush()
                await db.commit()

                book_data = {
                    "id": book.id,
                    "title": book.title,
                    "author": book.author,
                    "file_type": book.file_type,
                    "total_chapters": book.total_chapters,
                    "parse_status": book.parse_status,
                    "split_status": book.split_status,
                    "learn_status": book.learn_status,
                    "total_units": book.total_units,
                    "learned_units": book.learned_units,
                    "created_at": str(book.created_at),
                }

                _update_parse_progress(upload_id, "done", 100, "解析完成！", done=True, book=book_data)

            except Exception:
                await db.rollback()
                raise

    except Exception:
        logger.error(f"解析失败: {upload_id}", exc_info=True)
        # 清理文件
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        _update_parse_progress(upload_id, "error", 0, "文档解析失败，请检查文件格式", done=True, error="文档解析失败")


@router.post("/parse/start")
async def start_parse(
    file: UploadFile = File(...),
    parser_llm: LLMClient = Depends(get_parser_llm_client),
):
    """上传文件并启动异步解析，立即返回 upload_id"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    storage_dir = Path(settings.FILE_STORAGE_DIR)
    storage_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename).suffix
    unique_name = f"{uuid4()}{ext}"
    file_path = storage_dir / unique_name

    with file_path.open("wb") as out_file:
        while chunk := await file.read(1024 * 1024):
            out_file.write(chunk)

    original_title = Path(file.filename).stem
    upload_id = str(uuid4())

    # 初始化进度
    _update_parse_progress(upload_id, "uploading", 0, "文件上传完成，准备解析...")

    # 后台启动解析任务
    asyncio.create_task(
        _execute_parse(
            upload_id=upload_id,
            file_path=str(file_path),
            original_title=original_title,
            parser_llm=parser_llm,
        )
    )

    return {"upload_id": upload_id}


@router.get("/parse/{upload_id}/progress")
async def parse_progress_stream(upload_id: str):
    """SSE 流式推送解析进度"""

    async def event_generator() -> AsyncGenerator[str, None]:
        last_percent = -1
        while True:
            prog = _parse_progress.get(upload_id)

            if prog is None:
                data = json.dumps({"upload_id": upload_id, "stage": "waiting", "percent": 0,
                                   "message": "等待任务启动...", "done": False})
                yield f"data: {data}\n\n"
                await asyncio.sleep(1)
                continue

            current_percent = prog.get("percent", 0)
            if current_percent != last_percent or prog.get("done"):
                last_percent = current_percent
                yield f"data: {json.dumps(prog, ensure_ascii=False)}\n\n"

            if prog.get("done"):
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{book_id}/toc/preview")
async def get_toc_preview(book_id: str, db: AsyncSession = Depends(get_db)):
    """
    获取书籍目录预览（供用户编辑）。

    从数据库已存储的章节构建树形结构，避免重复解析文件。
    """
    result = await db.execute(
        select(BookModel).where(BookModel.id == book_id)
    )
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="书籍不存在")

    chapters_result = await db.execute(
        select(ChapterModel)
        .where(ChapterModel.book_id == book_id)
        .order_by(ChapterModel.order_index)
    )
    chapters = chapters_result.scalars().all()

    # 如果没有章节记录，回退到重新解析文件
    if not chapters:
        service = _get_service()
        parsed = await _parse_in_executor(service, book.file_path, book.user_id)
        from app.modules.document_parser.toc_detector import build_toc_tree
        toc_tree = build_toc_tree(parsed.toc)
        return {
            "book_id": book_id,
            "title": book.title,
            "toc": [item.model_dump() for item in toc_tree],
        }

    # 从章节列表构建树形结构（使用 stack 算法根据 level 构建层级）
    # 如果所有章节 level 都是 0，尝试从标题推断层级
    all_level_zero = all((ch.level or 0) == 0 for ch in chapters)
    import re

    def _infer_level(title: str) -> int:
        """从标题推断层级：第X编=0, 第X章=1, 第X节=2, 其他=0"""
        if re.search(r'第[一二三四五六七八九十百千\d]+编', title):
            return 0
        if re.search(r'第[一二三四五六七八九十百千\d]+章', title):
            return 1
        if re.search(r'第[一二三四五六七八九十百千\d]+节', title):
            return 2
        return 0

    toc_tree = []
    stack = []
    for ch in chapters:
        level = _infer_level(ch.title) if all_level_zero else (ch.level or 0)
        node = {
            "id": ch.id,
            "title": ch.title,
            "level": level,
            "char_offset": 0,
            "children": [],
        }
        # 弹出栈中层级大于等于当前项的项
        while stack and stack[-1]["level"] >= node["level"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(node)
        else:
            toc_tree.append(node)
        stack.append(node)

    return {
        "book_id": book_id,
        "title": book.title,
        "toc": toc_tree,
    }


@router.post("/{book_id}/toc/confirm")
async def confirm_toc(
    book_id: str,
    request: TOCConfirmRequest,
    db: AsyncSession = Depends(get_db),
    parser_llm: LLMClient = Depends(get_parser_llm_client),
):
    """用户确认/编辑目录后触发重新拆分"""
    result = await db.execute(
        select(BookModel).where(BookModel.id == book_id)
    )
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="书籍不存在")

    if not request.items:
        raise HTTPException(status_code=400, detail="目录不能为空")

    # 重新解析文件（获取全文，用于按目录切分）
    service = _get_service(llm_client=parser_llm)
    parsed = await _parse_in_executor(service, book.file_path, book.user_id)

    user_toc_items = [
        TOCItem(
            title=item.title,
            level=item.level,
            char_offset=item.char_offset,
        )
        for item in request.items
    ]

    return await rebuild_book_from_toc(db, book, parsed, user_toc_items)
