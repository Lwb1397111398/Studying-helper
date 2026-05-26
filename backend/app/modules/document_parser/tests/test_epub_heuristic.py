"""EPUB heuristic fallback tests"""

import pytest
import ebooklib
from unittest.mock import MagicMock, patch
from app.modules.document_parser.parsers.epub_parser import EPUBParser


class TestEPUBSpineInference:
    """Test EPUB spine filename inference"""

    def test_chapter_file_name_extraction(self):
        """Test chapter extraction from filenames"""
        parser = EPUBParser()

        mock_book = MagicMock()
        mock_book.spine = [
            ("ch01", "chapter01.html"),
            ("ch02", "chapter02.html"),
            ("ch03", "chapter03.html"),
        ]

        def mock_get_item(item_id):
            item = MagicMock()
            item.get_type.return_value = ebooklib.ITEM_DOCUMENT
            item.get_name.return_value = f"chapter{item_id.replace('ch', '')}.html"
            return item

        mock_book.get_item_with_id.side_effect = mock_get_item

        result = parser._extract_toc_from_spine(mock_book)
        assert len(result) == 3
        assert result[0].title == "第1章"
        assert result[0].level == 0

    def test_insufficient_chapters_returns_empty(self):
        """Test insufficient chapters returns empty"""
        parser = EPUBParser()

        mock_book = MagicMock()
        mock_book.spine = [
            ("ch01", "chapter01.html"),
        ]

        def mock_get_item(item_id):
            item = MagicMock()
            item.get_type.return_value = ebooklib.ITEM_DOCUMENT
            item.get_name.return_value = "chapter01.html"
            return item

        mock_book.get_item_with_id.side_effect = mock_get_item

        result = parser._extract_toc_from_spine(mock_book)
        assert result == []


class TestEPUBTextFallback:
    """Test EPUB text rule fallback"""

    def test_text_rule_fallback(self):
        """Test text rule fallback"""
        parser = EPUBParser()

        text = "Chapter 1 Intro\nsome text\nChapter 2 Methods\nsome text\nChapter 3 Conclusion\nsome text"

        result = parser._identify_toc_from_text(text)
        assert len(result) == 3
        assert result[0].title == "Chapter 1 Intro"

    def test_no_toc_returns_empty(self):
        """Test no TOC returns empty"""
        parser = EPUBParser()

        text = "some text\nmore text"

        result = parser._identify_toc_from_text(text)
        assert result == []
