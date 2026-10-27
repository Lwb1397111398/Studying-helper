"""文档解析服务"""

import logging
from pathlib import Path
from typing import List, Optional

from app.common.errors import ServiceError, ErrorCode
from app.common.llm_client import LLMClient
from app.modules.document_parser.schemas import ParsedDocument
from app.modules.document_parser.parsers.base import DocumentParser

logger = logging.getLogger(__name__)

# 文件头魔数校验
MAGIC_BYTES = {
    b'%PDF': 'pdf',
    b'PK': 'epub',  # EPUB 是 ZIP 格式
}


class DocumentParserService:
    """文档解析服务"""

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

    def __init__(self, parsers: List[DocumentParser], storage_dir: str, llm_client: Optional[LLMClient] = None):
        self.parsers = parsers
        self.storage_dir = storage_dir
        self.llm_client = llm_client

    def parse_and_store(self, file_path: str, user_id: str) -> ParsedDocument:
        """
        解析文件并返回结果。

        流程：
        1. 验证文件存在
        2. 检查文件大小（< 100MB）
        3. 魔数校验文件类型
        4. 选择合适的解析器
        5. 调用解析器
        6. 返回ParsedDocument

        异常：
        - ServiceError(VALIDATION_ERROR): 文件不存在、格式不支持、文件为空、文件过大、类型不匹配
        - ServiceError(PROCESSING_ERROR): 解析失败
        """
        path = Path(file_path)

        # 验证文件存在
        if not path.exists():
            raise ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"文件不存在: {file_path}"
            )

        # 检查文件大小
        file_size = path.stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            raise ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"文件过大，最大支持100MB，当前文件大小: {file_size / 1024 / 1024:.2f}MB"
            )

        # 检查文件是否为空
        if file_size == 0:
            raise ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="文件内容为空"
            )

        # 魔数校验（至少 8 字节）
        self._validate_magic_bytes(path)

        # 选择合适的解析器
        parser = self._select_parser(file_path)
        if parser is None:
            supported_formats = ", ".join(self.get_supported_formats())
            raise ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"不支持的文件格式，支持的格式: {supported_formats}"
            )

        # 调用解析器
        try:
            return parser.parse(file_path, llm_client=self.llm_client)
        except ServiceError:
            raise
        except Exception as e:
            logger.error(f"解析文件失败: {file_path}", exc_info=True)
            raise ServiceError(
                code=ErrorCode.PROCESSING_ERROR,
                message=f"解析文件失败: {str(e)}"
            )

    def _validate_magic_bytes(self, path: Path) -> None:
        """通过文件头魔数校验真实文件类型"""
        ext = path.suffix.lower().lstrip('.')
        if ext == 'txt':
            return  # TXT 无固定魔数，跳过
        try:
            header = path.read_bytes()[:8]
        except OSError as e:
            raise ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"无法读取文件: {e}"
            )
        expected = None
        for magic, fmt in MAGIC_BYTES.items():
            if header.startswith(magic):
                expected = fmt
                break
        if expected and ext != expected:
            raise ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"文件类型不匹配：扩展名为 .{ext}，实际内容为 {expected.upper()} 格式"
            )

    def _select_parser(self, file_path: str) -> DocumentParser | None:
        """根据文件扩展名选择合适的解析器"""
        for parser in self.parsers:
            if parser.can_parse(file_path):
                return parser
        return None

    def get_supported_formats(self) -> List[str]:
        """动态聚合支持的文件格式列表"""
        formats = []
        for parser in self.parsers:
            # 每个解析器通过 can_parse 隐式声明支持的扩展名
            # 这里用一个小技巧：用空扩展名探测
            if hasattr(parser, 'extensions'):
                formats.extend(parser.extensions)
            else:
                # 回退：用常见扩展名测试
                for ext in ['pdf', 'txt', 'epub']:
                    if parser.can_parse(f"test.{ext}"):
                        formats.append(ext)
        return sorted(set(formats))


def resolve_user_toc_offsets(items, full_text: str) -> None:
    """逐项修正用户确认目录的 char_offset（原地修改）。

    目录预览接口和用户新增的章节 offset 可能为 0。拆分服务只在
    所有 offset 全为 0 时才做全局标题搜索，混合场景（部分有真实
    offset、部分为 0）会把 offset=0 的章节内容错位到全书开头。
    这里按列表顺序逐项解析：offset 为 0 的非首项先按标题搜索定位，
    找不到则退回前一项的偏移。
    """
    prev = 0
    for i, item in enumerate(items):
        if item.char_offset == 0 and i > 0:
            pos = full_text.find(item.title, prev)
            item.char_offset = pos if pos != -1 else prev
        prev = max(prev, item.char_offset)


async def rebuild_book_from_toc(db, book, parsed, toc_items) -> dict:
    """按用户确认的目录重建章节与知识单元。

    流程：修正目录偏移 -> 删除旧章节/单元/关联记录 -> 重新拆分 -> 入库。
    commit 由调用方的会话管理负责。
    """
    import json
    from sqlalchemy import select, delete
    from app.common.time_utils import utc_now
    from app.db.models import (
        ChapterModel, KnowledgeUnitModel, MasteryRecordModel, AnnotationModel,
    )
    from app.modules.knowledge_splitter.service import KnowledgeSplitterService

    resolve_user_toc_offsets(toc_items, parsed.full_text)
    parsed.toc = toc_items

    # 删除旧数据
    old_units = await db.execute(
        select(KnowledgeUnitModel.id).where(KnowledgeUnitModel.book_id == book.id)
    )
    old_unit_ids = [row[0] for row in old_units.all()]
    if old_unit_ids:
        await db.execute(delete(AnnotationModel).where(
            AnnotationModel.knowledge_unit_id.in_(old_unit_ids)))
        await db.execute(delete(MasteryRecordModel).where(
            MasteryRecordModel.knowledge_unit_id.in_(old_unit_ids)))
    await db.execute(delete(KnowledgeUnitModel).where(KnowledgeUnitModel.book_id == book.id))
    await db.execute(delete(ChapterModel).where(ChapterModel.book_id == book.id))

    # 重新拆分
    splitter = KnowledgeSplitterService()
    split_result = splitter.split(parsed, book.id)

    # 保存新数据
    for chapter in split_result.chapters:
        db.add(ChapterModel(
            id=chapter.id,
            book_id=book.id,
            title=chapter.title,
            chapter_number=chapter.chapter_number,
            order_index=chapter.order_index,
            level=chapter.level,
            summary=chapter.summary,
        ))

    for unit in split_result.units:
        db.add(KnowledgeUnitModel(
            id=unit.id,
            book_id=book.id,
            chapter_id=unit.chapter_id,
            title=unit.title,
            content=unit.content,
            order_index=unit.order_index,
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
    book.updated_at = utc_now()
    await db.flush()

    return {
        "book_id": book.id,
        "chapters_count": len(split_result.chapters),
        "units_count": len(split_result.units),
    }
