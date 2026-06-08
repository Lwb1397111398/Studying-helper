"""文档解析数据模型"""

from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import uuid4


class BookMetadata(BaseModel):
    """书籍元数据"""
    title: str
    author: Optional[str] = None
    publisher: Optional[str] = None
    publish_date: Optional[str] = None
    language: str = "zh"
    total_pages: Optional[int] = None
    file_type: str  # "pdf" | "txt" | "epub"
    file_size_bytes: int


class TOCItem(BaseModel):
    """目录项"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    level: int  # 从0开始
    page_number: Optional[int] = None
    char_offset: int  # 在全文中的字符偏移
    children: List['TOCItem'] = []


class PageInfo(BaseModel):
    """页面信息"""
    page_number: int
    start_offset: int
    end_offset: int


class PageTextInfo(BaseModel):
    """PDF 逐页原始文本（清洗前）"""
    page_number: int
    text: str
    height: float = 0


class NoiseRegion(BaseModel):
    """检测到的噪声区域"""
    start: int
    end: int
    noise_type: str  # "header_footer" | "front_matter" | "toc_page" | "back_matter"


class ParsedDocument(BaseModel):
    """解析后的文档"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    metadata: BookMetadata
    full_text: str
    toc: List[TOCItem]
    page_map: Optional[List[PageInfo]] = None
