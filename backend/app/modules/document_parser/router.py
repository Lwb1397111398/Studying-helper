"""文档解析API路由"""

import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.common.errors import ServiceError, ErrorCode
from app.config import settings
from app.db.database import get_db
from app.deps import get_llm_client as _get_llm_client
from app.db.models import BookModel, ChapterModel, KnowledgeUnitModel, MasteryRecordModel, AnnotationModel
from app.modules.document_parser.service import DocumentParserService
from app.modules.document_parser.parsers import PDFParser, TXTParser, EPUBParser
from app.modules.document_parser.schemas import TOCItem
from app.modules.knowledge_splitter.service import KnowledgeSplitterService
from app.modules.knowledge_splitter.schemas import Chapter as SplitChapter, KnowledgeUnit


router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

DEFAULT_USER_ID = "anonymous"
_executor = ThreadPoolExecutor(max_workers=4)


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


@router.post("/parse")
async def parse_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """上传并解析文档，保存到数据库"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 永久存储目录
    storage_dir = Path(settings.FILE_STORAGE_DIR)
    storage_dir.mkdir(parents=True, exist_ok=True)

    # 生成唯一文件名，保留原始扩展名
    ext = Path(file.filename).suffix
    unique_name = f"{uuid4()}{ext}"
    file_path = storage_dir / unique_name

    try:
        # 写入文件
        content = await file.read()
        file_path.write_bytes(content)

        # 获取 parser 模块专属 LLM 客户端
        parser_llm = await _get_llm_client("parser")

        # 调用服务解析（同步方法，放线程池避免阻塞事件循环）
        import asyncio
        service = _get_service(llm_client=parser_llm)
        loop = asyncio.get_event_loop()
        parsed = await loop.run_in_executor(
            _executor,
            lambda: service.parse_and_store(
                file_path=str(file_path),
                user_id=DEFAULT_USER_ID
            )
        )

        # 用原始文件名覆盖标题（去掉扩展名）
        original_title = Path(file.filename).stem
        parsed.metadata.title = original_title

        # 保存到数据库
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        book_id = parsed.id

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

        # 保存章节
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

        return {
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "file_type": book.file_type,
            "total_chapters": book.total_chapters,
            "created_at": book.created_at,
        }

    except ServiceError as e:
        # 解析失败时清理文件
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=400 if e.code == ErrorCode.VALIDATION_ERROR else 500,
            detail=e.message
        )
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/formats")
async def get_formats():
    """获取支持的文件格式"""
    service = _get_service()
    return {"formats": service.get_supported_formats()}


@router.get("/{book_id}/toc/preview")
async def get_toc_preview(book_id: str, db: AsyncSession = Depends(get_db)):
    """
    获取书籍目录预览（供用户编辑）。

    返回已解析的目录项列表，前端可展示为可编辑树形结构。
    """
    result = await db.execute(
        select(BookModel).where(BookModel.id == book_id)
    )
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="书籍不存在")

    # 重新解析文件获取目录
    service = _get_service()
    import asyncio
    loop = asyncio.get_event_loop()
    parsed = await loop.run_in_executor(
        _executor,
        lambda: service.parse_and_store(
            file_path=book.file_path,
            user_id=book.user_id
        )
    )

    # 构建树形结构
    from app.modules.document_parser.toc_detector import build_toc_tree
    toc_tree = build_toc_tree(parsed.toc)

    return {
        "book_id": book_id,
        "title": book.title,
        "toc": [item.model_dump() for item in toc_tree],
    }


@router.post("/{book_id}/toc/confirm")
async def confirm_toc(
    book_id: str,
    request: TOCConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    用户确认/编辑目录后触发重新拆分。

    流程：
    1. 删除现有 Chapter + KnowledgeUnit + 相关记录
    2. 根据用户提交的目录重建 Chapter
    3. 重新拆分知识单元
    4. 返回最终章节列表
    """
    result = await db.execute(
        select(BookModel).where(BookModel.id == book_id)
    )
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="书籍不存在")

    # 获取 parser 模块专属 LLM 客户端
    parser_llm = await _get_llm_client("parser")

    # 重新解析文件
    service = _get_service(llm_client=parser_llm)
    import asyncio
    loop = asyncio.get_event_loop()
    parsed = await loop.run_in_executor(
        _executor,
        lambda: service.parse_and_store(
            file_path=book.file_path,
            user_id=book.user_id
        )
    )

    # 构建用户确认的目录结构
    user_toc_items = [
        TOCItem(
            title=item.title,
            level=item.level,
            char_offset=item.char_offset,
        )
        for item in request.items
    ]

    # 替换解析结果的目录
    parsed.toc = user_toc_items

    # 删除旧数据
    old_units = await db.execute(
        select(KnowledgeUnitModel.id).where(KnowledgeUnitModel.book_id == book_id)
    )
    old_unit_ids = [row[0] for row in old_units.all()]
    if old_unit_ids:
        await db.execute(delete(AnnotationModel).where(AnnotationModel.knowledge_unit_id.in_(old_unit_ids)))
        await db.execute(delete(MasteryRecordModel).where(MasteryRecordModel.knowledge_unit_id.in_(old_unit_ids)))
    await db.execute(delete(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id == book_id))
    await db.execute(delete(ChapterModel).where(ChapterModel.book_id == book_id))

    # 重新拆分
    splitter = KnowledgeSplitterService()
    split_result = splitter.split(parsed, book_id)

    # 保存新数据
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    for chapter in split_result.chapters:
        db.add(ChapterModel(
            id=chapter.id,
            book_id=book_id,
            title=chapter.title,
            chapter_number=chapter.chapter_number,
            order_index=chapter.order_index,
            level=chapter.level,
            summary=chapter.summary,
        ))

    for unit in split_result.units:
        db.add(KnowledgeUnitModel(
            id=unit.id,
            book_id=book_id,
            chapter_id=unit.chapter_id,
            title=unit.title,
            content=unit.content,
            order_index=unit.order_index,
            char_offset_start=unit.char_offset_start,
            char_offset_end=unit.char_offset_end,
            summary=unit.summary,
            key_points=",".join(unit.key_points) if unit.key_points else None,
            concepts=",".join(unit.concepts) if unit.concepts else None,
            difficulty_level=unit.difficulty_level,
            importance_score=unit.importance_score,
        ))

    # 更新书籍状态
    book.parse_status = "completed"
    book.split_status = "completed"
    book.total_chapters = len(split_result.chapters)
    book.total_units = len(split_result.units)
    book.updated_at = now
    await db.flush()

    return {
        "book_id": book_id,
        "chapters_count": len(split_result.chapters),
        "units_count": len(split_result.units),
    }
