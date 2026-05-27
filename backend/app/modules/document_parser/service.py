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
            return parser.parse(file_path)
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
