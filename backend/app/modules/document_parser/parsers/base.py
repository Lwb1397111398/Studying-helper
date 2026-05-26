"""解析器协议定义"""

from typing import Protocol
from app.modules.document_parser.schemas import ParsedDocument


class DocumentParser(Protocol):
    """文档解析器协议"""

    def can_parse(self, file_path: str) -> bool:
        """检查是否能解析该文件"""
        ...

    def parse(self, file_path: str) -> ParsedDocument:
        """解析文件并返回ParsedDocument"""
        ...
