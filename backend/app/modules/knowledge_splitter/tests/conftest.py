"""测试fixtures"""

import pytest
from app.modules.document_parser.schemas import ParsedDocument, BookMetadata, TOCItem


@pytest.fixture
def sample_document():
    """带目录的测试文档"""
    text = "第1章 绪论\n\n这是第一章的内容。" * 20 + "\n\n" + "第2章 基础\n\n这是第二章的内容。" * 20
    return ParsedDocument(
        metadata=BookMetadata(title="测试书", file_type="txt", file_size_bytes=len(text)),
        full_text=text,
        toc=[
            TOCItem(title="第1章 绪论", level=0, char_offset=0),
            TOCItem(title="第2章 基础", level=0, char_offset=text.index("第2章")),
        ]
    )


@pytest.fixture
def sample_document_no_toc():
    """无目录的测试文档"""
    text = "这是第一章的内容。" * 50 + "\n\n" + "这是第二章的内容。" * 50
    return ParsedDocument(
        metadata=BookMetadata(title="测试书", file_type="txt", file_size_bytes=len(text)),
        full_text=text,
        toc=[]
    )


@pytest.fixture
def long_text():
    """长文本用于测试拆分"""
    return "这是一个很长的段落。" * 500
