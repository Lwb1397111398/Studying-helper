"""文档解析器集合"""

from app.modules.document_parser.parsers.base import DocumentParser
from app.modules.document_parser.parsers.pdf_parser import PDFParser
from app.modules.document_parser.parsers.txt_parser import TXTParser
from app.modules.document_parser.parsers.epub_parser import EPUBParser

__all__ = [
    "DocumentParser",
    "PDFParser",
    "TXTParser",
    "EPUBParser",
]
