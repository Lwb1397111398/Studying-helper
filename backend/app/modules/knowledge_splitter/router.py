"""知识拆分路由"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.time_utils import utc_now
from app.db.database import get_db
from app.db.models import BookModel, ChapterModel, KnowledgeUnitModel, MasteryRecordModel, AnnotationModel
from app.modules.knowledge_splitter.service import KnowledgeSplitterService, NoTOCError
from app.modules.document_parser.schemas import ParsedDocument
from app.modules.document_parser.parsers import PDFParser, TXTParser, EPUBParser
from app.modules.document_parser.service import DocumentParserService

router = APIRouter(prefix="/api/v1/split", tags=["split"])
_executor = ThreadPoolExecutor(max_workers=4)

# 内存存储拆分进度（key: book_id）
_split_progress: dict[str, dict] = {}


# 进度记录 TTL：超过此时间的已完成/失败记录将被自动清理
_PROGRESS_TTL = timedelta(hours=1)


def _cleanup_expired_progress():
    """清理过期的进度记录，防止内存泄漏"""
    now = utc_now()
    expired = [
        bid for bid, prog in _split_progress.items()
        if prog.get("done") and prog.get("updated_at")
        and now - datetime.fromisoformat(prog["updated_at"]) > _PROGRESS_TTL
    ]
    for bid in expired:
        del _split_progress[bid]
    if expired:
        logger.debug("清理 %d 条过期进度记录", len(expired))


def _update_progress(book_id: str, stage: str, percent: int, message: str, done: bool = False, error: str = None):
    """更新拆分进度"""
    # 每次写入前清理过期记录
    _cleanup_expired_progress()
    _split_progress[book_id] = {
        "book_id": book_id,
        "stage": stage,
        "percent": percent,
        "message": message,
        "done": done,
        "error": error,
        "updated_at": utc_now().isoformat(),
    }


async def _execute_split(book_id: str, db: AsyncSession):
    """后台执行知识拆分，分阶段推送进度"""
    try:
        # ── 阶段1: 读取文件信息 (0% → 15%) ──
        _update_progress(book_id, "reading", 5, "正在读取书籍信息...")

        result = await db.execute(select(BookModel).where(BookModel.id == book_id))
        book = result.scalar_one_or_none()
        if book is None:
            _update_progress(book_id, "error", 0, "书籍不存在", done=True, error="书籍不存在")
            return

        _update_progress(book_id, "reading", 15, f"已读取: {book.title}")

        # ── 阶段2: 解析文档 (15% → 40%) ──
        _update_progress(book_id, "parsing", 20, "正在解析文档内容...")

        import tempfile
        parsers = [PDFParser(), TXTParser(), EPUBParser()]
        service = DocumentParserService(parsers=parsers, storage_dir=tempfile.gettempdir())

        loop = asyncio.get_event_loop()
        parsed = await loop.run_in_executor(
            _executor,
            lambda: service.parse_and_store(file_path=book.file_path, user_id=book.user_id)
        )

        parsed.metadata.title = book.title
        toc_count = len(parsed.toc) if parsed.toc else 0
        text_len = len(parsed.full_text) if parsed.full_text else 0
        _update_progress(book_id, "parsing", 40, f"解析完成: {toc_count} 个目录项, {text_len} 字符")

        # ── 阶段3: 拆分章节 (40% → 60%) ──
        _update_progress(book_id, "splitting_chapters", 45, "正在拆分章节...")

        splitter = KnowledgeSplitterService()

        try:
            split_result = await loop.run_in_executor(
                _executor,
                lambda: splitter.split(parsed, book_id)
            )
        except NoTOCError as e:
            book.parse_status = "failed"
            book.split_status = "failed"
            await db.commit()
            import logging
            logging.getLogger(__name__).error(f"知识拆分失败: {e}", exc_info=True)
            _update_progress(book_id, "error", 0, "知识拆分失败，请检查文件格式", done=True, error="知识拆分失败")
            return

        chapter_count = len(split_result.chapters)
        _update_progress(book_id, "splitting_chapters", 60, f"章节拆分完成: {chapter_count} 个章节")

        # ── 阶段4: 拆分知识单元 (60% → 80%) ──
        unit_count = len(split_result.units)
        _update_progress(book_id, "splitting_units", 70, f"知识单元拆分完成: {unit_count} 个单元")

        # ── 阶段5: 保存数据库 (80% → 100%) ──
        _update_progress(book_id, "saving", 80, "正在保存到数据库...")

        now = utc_now()

        # 用 SAVEPOINT 包裹删除+写入，失败可回滚到保存点
        async with db.begin_nested():
            # 删除旧数据（先删子表再删父表）
            old_units = await db.execute(
                select(KnowledgeUnitModel.id).where(KnowledgeUnitModel.book_id == book_id)
            )
            old_unit_ids = [row[0] for row in old_units.all()]
            if old_unit_ids:
                await db.execute(
                    delete(AnnotationModel)
                    .where(AnnotationModel.knowledge_unit_id.in_(old_unit_ids))
                )
                await db.execute(
                    delete(MasteryRecordModel)
                    .where(MasteryRecordModel.knowledge_unit_id.in_(old_unit_ids))
                )
            await db.execute(delete(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id == book_id))
            await db.execute(delete(ChapterModel).where(ChapterModel.book_id == book_id))

            # 写入章节（支持多级层级：编>章>节>...）
            for chapter in split_result.chapters:
                db.add(ChapterModel(
                    id=chapter.id, book_id=book_id, title=chapter.title,
                    chapter_number=chapter.chapter_number, order_index=chapter.order_index,
                    level=chapter.level, parent_id=chapter.parent_id,
                    summary=chapter.summary,
                ))

            # 写入知识单元
            for unit in split_result.units:
                db.add(KnowledgeUnitModel(
                    id=unit.id, book_id=book_id, chapter_id=unit.chapter_id,
                    section_id=unit.section_id,
                    title=unit.title, content=unit.content, order_index=unit.order_index,
                    char_offset_start=unit.char_offset_start,
                    char_offset_end=unit.char_offset_end,
                    summary=unit.summary,
                    key_points=json.dumps(unit.key_points, ensure_ascii=False) if unit.key_points else None,
                    concepts=json.dumps(unit.concepts, ensure_ascii=False) if unit.concepts else None,
                    difficulty_level=unit.difficulty_level,
                    importance_score=unit.importance_score,
                ))

            # 更新书籍状态
            book.parse_status = "completed"
            book.split_status = "completed"
            book.total_chapters = len(split_result.chapters)
            book.total_units = len(split_result.units)
            book.updated_at = now

        # SAVEPOINT 提交后，外层 commit 持久化
        await db.commit()

        _update_progress(book_id, "done", 100,
            f"拆分完成！{len(split_result.chapters)} 章节，{len(split_result.units)} 知识单元",
            done=True)

    except Exception as e:
        await db.rollback()
        # 重新查 book（rollback 后 book 对象可能失效）
        try:
            result = await db.execute(select(BookModel).where(BookModel.id == book_id))
            book = result.scalar_one_or_none()
            if book is not None:
                book.parse_status = "failed"
                book.split_status = "failed"
                await db.commit()
        except Exception:
            await db.rollback()
        _update_progress(book_id, "error", 0, "知识拆分失败", done=True, error="知识拆分失败")


@router.post("/{book_id}")
async def start_split(book_id: str, db: AsyncSession = Depends(get_db)):
    """启动知识拆分任务，立即返回 task_id"""
    # 检查书籍是否存在
    result = await db.execute(select(BookModel).where(BookModel.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="书籍不存在")

    # 检查是否已有进行中的任务
    if book_id in _split_progress and not _split_progress[book_id].get("done"):
        return {"book_id": book_id, "status": "already_running", "progress": _split_progress[book_id]}

    # 初始化进度
    _update_progress(book_id, "pending", 0, "任务已创建，等待执行...")

    # 后台启动异步任务
    from app.db.database import async_session_factory

    async def _run():
        async with async_session_factory() as session:
            await _execute_split(book_id, session)

    asyncio.create_task(_run())

    return {"book_id": book_id, "status": "started"}


@router.get("/{book_id}/progress")
async def split_progress_stream(book_id: str):
    """SSE 流式推送拆分进度"""

    async def event_generator() -> AsyncGenerator[str, None]:
        last_percent = -1
        while True:
            prog = _split_progress.get(book_id)

            if prog is None:
                # 还没有任务记录
                data = json.dumps({"book_id": book_id, "stage": "waiting", "percent": 0, "message": "等待任务启动...", "done": False})
                yield f"data: {data}\n\n"
                await asyncio.sleep(1)
                continue

            # 只在进度变化时推送（减少无效消息）
            current_percent = prog.get("percent", 0)
            if current_percent != last_percent or prog.get("done"):
                last_percent = current_percent
                data = json.dumps(prog, ensure_ascii=False)
                yield f"data: {data}\n\n"

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


@router.get("/{book_id}/result")
async def split_result(book_id: str, db: AsyncSession = Depends(get_db)):
    """获取拆分结果"""
    prog = _split_progress.get(book_id)
    if prog is None:
        raise HTTPException(status_code=404, detail="没有找到拆分任务")

    if not prog.get("done"):
        raise HTTPException(status_code=202, detail="拆分仍在进行中")

    if prog.get("error"):
        raise HTTPException(status_code=500, detail=prog["error"])

    # 返回最终结果
    from app.modules.knowledge_splitter.schemas import SplitStats

    chapters_result = await db.execute(
        select(ChapterModel).where(ChapterModel.book_id == book_id).order_by(ChapterModel.order_index)
    )
    chapters = chapters_result.scalars().all()

    units_result = await db.execute(
        select(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id == book_id).order_by(KnowledgeUnitModel.order_index)
    )
    units = units_result.scalars().all()

    return {
        "book_id": book_id,
        "chapters_count": len(chapters),
        "units_count": len(units),
        "message": "知识拆分完成",
    }


# ── 兼容旧接口：同步拆分（保留，但内部走异步） ──
@router.post("/{book_id}/sync")
async def split_document_sync(book_id: str, db: AsyncSession = Depends(get_db)):
    """同步执行知识拆分（兼容旧版，不推荐）"""
    result = await db.execute(select(BookModel).where(BookModel.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="书籍不存在")

    import tempfile
    parsers = [PDFParser(), TXTParser(), EPUBParser()]
    service = DocumentParserService(parsers=parsers, storage_dir=tempfile.gettempdir())

    try:
        loop = asyncio.get_event_loop()
        parsed = await loop.run_in_executor(
            _executor,
            lambda: service.parse_and_store(file_path=book.file_path, user_id=book.user_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析文件失败: {str(e)}")

    parsed.metadata.title = book.title

    splitter = KnowledgeSplitterService()
    try:
        split_result = splitter.split(parsed, book_id)
    except NoTOCError as e:
        raise HTTPException(status_code=422, detail=str(e))

    now = utc_now()

    async with db.begin_nested():
        old_units = await db.execute(
            select(KnowledgeUnitModel.id).where(KnowledgeUnitModel.book_id == book_id)
        )
        old_unit_ids = [row[0] for row in old_units.all()]
        if old_unit_ids:
            await db.execute(
                delete(AnnotationModel)
                .where(AnnotationModel.knowledge_unit_id.in_(old_unit_ids))
            )
            await db.execute(
                delete(MasteryRecordModel)
                .where(MasteryRecordModel.knowledge_unit_id.in_(old_unit_ids))
            )
        await db.execute(delete(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id == book_id))
        await db.execute(delete(ChapterModel).where(ChapterModel.book_id == book_id))

        for chapter in split_result.chapters:
            db.add(ChapterModel(
                id=chapter.id, book_id=book_id, title=chapter.title,
                chapter_number=chapter.chapter_number, order_index=chapter.order_index,
                level=chapter.level, parent_id=chapter.parent_id,
                summary=chapter.summary,
            ))

        for unit in split_result.units:
            db.add(KnowledgeUnitModel(
                id=unit.id, book_id=book_id, chapter_id=unit.chapter_id,
                section_id=unit.section_id,
                title=unit.title, content=unit.content, order_index=unit.order_index,
                char_offset_start=unit.char_offset_start,
                char_offset_end=unit.char_offset_end,
                summary=unit.summary,
                key_points=json.dumps(unit.key_points, ensure_ascii=False) if unit.key_points else None,
                concepts=json.dumps(unit.concepts, ensure_ascii=False) if unit.concepts else None,
                difficulty_level=unit.difficulty_level,
                importance_score=unit.importance_score,
            ))

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
        "split_stats": split_result.split_stats.model_dump(),
    }
