"""知识拆分测试"""

import pytest
from app.modules.document_parser.schemas import ParsedDocument, BookMetadata
from app.modules.knowledge_splitter.service import KnowledgeSplitterService


class TestKnowledgeSplitterService:
    def test_split_with_toc(self, sample_document):
        """有目录的文档：按章节正确拆分"""
        service = KnowledgeSplitterService(unit_min_length=10)
        result = service.split(sample_document, "book1")
        assert len(result.chapters) >= 2
        assert len(result.units) >= 2
        assert result.split_stats.total_chapters >= 2

    def test_split_without_toc(self, sample_document_no_toc):
        """无目录的文档：整本书作为一章"""
        service = KnowledgeSplitterService(unit_min_length=10)
        result = service.split(sample_document_no_toc, "book1")
        assert len(result.chapters) == 1
        assert len(result.units) >= 1

    def test_merge_short_units(self):
        """短单元合并：低于最小长度的单元被合并"""
        service = KnowledgeSplitterService(unit_min_length=200)
        doc = ParsedDocument(
            metadata=BookMetadata(title="test", file_type="txt", file_size_bytes=100),
            full_text="短段落一。\n\n短段落二。\n\n短段落三。",
            toc=[]
        )
        result = service.split(doc, "book1")
        assert len(result.units) <= 2

    def test_split_long_unit(self, long_text):
        """长单元拆分：超过最大长度的单元被细分"""
        service = KnowledgeSplitterService(unit_min_length=10, unit_max_length=500)
        doc = ParsedDocument(
            metadata=BookMetadata(title="test", file_type="txt", file_size_bytes=len(long_text)),
            full_text=long_text,
            toc=[]
        )
        result = service.split(doc, "book1")
        for unit in result.units:
            assert len(unit.content) <= 600  # 允许少量超出

    def test_unit_offset_tracking(self, sample_document):
        """偏移量追踪：每个单元记录在原文中的位置"""
        service = KnowledgeSplitterService(unit_min_length=10)
        result = service.split(sample_document, "book1")
        for unit in result.units:
            extracted = sample_document.full_text[unit.char_offset_start:unit.char_offset_end]
            assert len(extracted) > 0

    def test_split_stats(self, sample_document):
        """拆分统计：统计数据正确"""
        service = KnowledgeSplitterService(unit_min_length=10)
        result = service.split(sample_document, "book1")
        assert result.split_stats.total_units == len(result.units)
        assert result.split_stats.avg_unit_length > 0

    def test_unit_order_index(self, sample_document):
        """单元顺序：order_index递增"""
        service = KnowledgeSplitterService(unit_min_length=10)
        result = service.split(sample_document, "book1")
        for i, unit in enumerate(result.units):
            assert unit.order_index == i
