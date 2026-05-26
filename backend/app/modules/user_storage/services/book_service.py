"""书籍服务"""
import logging
import os
from uuid import uuid4

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.errors import ServiceError, ErrorCode
from app.common.time_utils import utc_now
from app.db.models import (
    BookModel, ChapterModel, KnowledgeUnitModel,
    AnnotationModel, MasteryRecordModel, LearningRecordModel,
    KGNodeModel, KGEdgeModel,
)

logger = logging.getLogger(__name__)


class BookService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_book(self, user_id: str, title: str, file_path: str,
                          file_type: str, file_size_bytes: int,
                          author: str | None = None) -> BookModel:
        now = utc_now()
        book = BookModel(
            id=str(uuid4()),
            user_id=user_id,
            title=title,
            author=author,
            file_path=file_path,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            created_at=now,
            updated_at=now,
        )
        self.db.add(book)
        await self.db.flush()
        return book

    async def get_book(self, book_id: str) -> BookModel:
        result = await self.db.execute(select(BookModel).where(BookModel.id == book_id))
        book = result.scalar_one_or_none()
        if book is None:
            raise ServiceError(ErrorCode.NOT_FOUND, f"书籍 {book_id} 不存在")
        return book

    async def list_books(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        count_result = await self.db.execute(
            select(func.count()).select_from(BookModel).where(BookModel.user_id == user_id)
        )
        total = count_result.scalar() or 0
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(BookModel)
            .where(BookModel.user_id == user_id)
            .order_by(BookModel.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        books = list(result.scalars().all())
        return {
            "items": books,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": offset + page_size < total,
        }

    async def update_status(self, book_id: str, **kwargs) -> BookModel:
        book = await self.get_book(book_id)
        for key, value in kwargs.items():
            if value is not None and hasattr(book, key):
                setattr(book, key, value)
        book.updated_at = utc_now()
        await self.db.flush()
        return book

    async def delete_book(self, book_id: str) -> None:
        """
        两阶段删除：
        1. DB 事务内：级联删除关联数据，file_path 置 NULL 后删除书籍记录
        2. 事务提交后：删除物理文件（失败只打 warning）
        """
        book = await self.get_book(book_id)
        file_path = book.file_path  # 提前取出，置 NULL 后就没了

        # 1. 收集所有关联 ID（2次查询）
        chapter_ids_result = await self.db.execute(
            select(ChapterModel.id).where(ChapterModel.book_id == book_id)
        )
        chapter_ids = [row[0] for row in chapter_ids_result.all()]

        ku_ids_result = await self.db.execute(
            select(KnowledgeUnitModel.id).where(KnowledgeUnitModel.book_id == book_id)
        )
        ku_ids = [row[0] for row in ku_ids_result.all()]

        # 2. 批量删除知识单元相关数据（2次查询）
        if ku_ids:
            await self.db.execute(
                delete(AnnotationModel).where(AnnotationModel.knowledge_unit_id.in_(ku_ids))
            )
            await self.db.execute(
                delete(MasteryRecordModel).where(MasteryRecordModel.knowledge_unit_id.in_(ku_ids))
            )
        await self.db.execute(
            delete(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id == book_id)
        )

        # 3. 删除章节（1次）
        await self.db.execute(
            delete(ChapterModel).where(ChapterModel.book_id == book_id)
        )

        # 4. 删除学习记录（1次）
        await self.db.execute(
            delete(LearningRecordModel).where(LearningRecordModel.book_id == book_id)
        )

        # 5. 删除知识图谱（2次查询 + 2次删除）
        node_ids_result = await self.db.execute(
            select(KGNodeModel.id).where(KGNodeModel.book_id == book_id)
        )
        node_ids = [row[0] for row in node_ids_result.all()]
        if node_ids:
            await self.db.execute(
                delete(KGEdgeModel).where(KGEdgeModel.source_id.in_(node_ids))
            )
            await self.db.execute(
                delete(KGEdgeModel).where(KGEdgeModel.target_id.in_(node_ids))
            )
        await self.db.execute(
            delete(KGNodeModel).where(KGNodeModel.book_id == book_id)
        )

        # 6. file_path 置 NULL，删除书籍记录
        book.file_path = None
        await self.db.delete(book)
        await self.db.flush()

        # 7. 事务提交后删除物理文件（失败不回滚 DB）
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                logger.warning(f"文件删除失败: {file_path}, 原因: {e}")
