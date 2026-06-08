"""知识拆分数据模型"""

from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import uuid4


class KnowledgeUnit(BaseModel):
    """知识单元 - 系统中最小的可学习单位"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    book_id: str
    chapter_id: str          # 所属章节（level=0）
    section_id: Optional[str] = None  # 所属小节（level=1），无小节时为 None
    title: str
    content: str
    order_index: int
    char_offset_start: int
    char_offset_end: int
    # 以下字段在AI学习阶段填充，初始为None
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None
    concepts: Optional[List[str]] = None
    difficulty_level: Optional[int] = None  # 1-5
    importance_score: Optional[float] = None  # 0-1

    def __repr__(self) -> str:
        return (
            f"KnowledgeUnit(id={self.id!r}, title={self.title!r}, "
            f"chapter_id={self.chapter_id!r}, order_index={self.order_index}, "
            f"len={len(self.content)})"
        )


class Chapter(BaseModel):
    """章节 — 支持多级层级（编>章>节）"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    book_id: str
    title: str
    chapter_number: int
    parent_id: Optional[str] = None
    level: int = 0
    order_index: int
    summary: Optional[str] = None
    text: Optional[str] = None  # 叶子节点的文本内容

    def __repr__(self) -> str:
        return (
            f"Chapter(id={self.id!r}, title={self.title!r}, "
            f"chapter_number={self.chapter_number}, order_index={self.order_index})"
        )


class SplitStats(BaseModel):
    """拆分统计"""
    total_chapters: int
    total_units: int
    avg_unit_length: float
    min_unit_length: int
    max_unit_length: int
    units_without_title: int

    def __repr__(self) -> str:
        return (
            f"SplitStats(chapters={self.total_chapters}, units={self.total_units}, "
            f"avg_len={self.avg_unit_length:.1f})"
        )


class SubTitle(BaseModel):
    """子标题 — level≥2 的目录节点，归入父小节"""
    char_offset: int
    title: str

    def __repr__(self) -> str:
        return f"SubTitle(title={self.title!r}, offset={self.char_offset})"


class Section(BaseModel):
    """小节 — level=1 的目录节点，比章小、比知识单元大"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    chapter_id: str
    title: str
    level: int = 1
    order_index: int
    text: str
    char_offset_start: int
    # level≥2 的子标题合并进来，切块时优先在这些边界处切
    sub_titles: List[SubTitle] = []

    def __repr__(self) -> str:
        return (
            f"Section(id={self.id!r}, title={self.title!r}, "
            f"chapter_id={self.chapter_id!r}, order_index={self.order_index}, "
            f"sub_titles={len(self.sub_titles)}, text_len={len(self.text)})"
        )


class SplitResult(BaseModel):
    """拆分结果"""
    book_id: str
    chapters: List[Chapter]
    sections: List[Section]
    units: List[KnowledgeUnit]
    split_stats: SplitStats

    def __repr__(self) -> str:
        return (
            f"SplitResult(book_id={self.book_id!r}, "
            f"chapters={len(self.chapters)}, sections={len(self.sections)}, "
            f"units={len(self.units)})"
        )
