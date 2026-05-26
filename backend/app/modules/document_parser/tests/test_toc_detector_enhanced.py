"""Enhanced TOC detector tests"""

import pytest
from app.modules.document_parser.toc_detector import (
    identify_toc_items,
    identify_toc_items_relaxed,
    identify_toc_items_enhanced,
    _validate_format_consistency,
    _detect_format,
)
from app.modules.ai_learning.tests.mock_llm import MockLLMClient


class TestStrictMode:
    """Strict mode TOC detection tests"""

    def test_chinese_number_chapter(self):
        """Test Chinese number chapters"""
        text = "Chapter 1 Intro\nsome text\nChapter 2 Methods\nsome text\nChapter 3 Conclusion\nsome text"
        result = identify_toc_items(text)
        assert len(result) == 3
        assert result[0].level == 0

    def test_arabic_number_chapter(self):
        """Test Arabic number chapters"""
        text = "Part 1 Basics\nsome text\nPart 2 Methods\nsome text\nPart 3 Conclusion\nsome text"
        result = identify_toc_items(text)
        assert len(result) == 3
        assert result[0].level == 0

    def test_book_level0(self):
        """Test 'Book 1' format"""
        text = "Book 1 Introduction\nsome text\nBook 2 Methods\nsome text\nBook 3 Conclusion\nsome text"
        result = identify_toc_items(text)
        assert len(result) == 3
        assert result[0].level == 0

    def test_unit_level0(self):
        """Test 'Unit 1' format"""
        text = "Unit 1 Basics\nsome text\nUnit 2 Advanced\nsome text\nUnit 3 Expert\nsome text"
        result = identify_toc_items(text)
        assert len(result) == 3
        assert result[0].level == 0

    def test_parenthesis_level0(self):
        """Test '(1)' format"""
        text = "(1) Introduction\nsome text\n(2) Methods\nsome text\n(3) Conclusion\nsome text"
        result = identify_toc_items(text)
        assert len(result) == 3
        assert result[0].level == 0

    def test_sub_level1(self):
        """Test level 1 sections (X. format)"""
        text = "Chapter 1 Intro\n1. Background\nsome text\n2. Significance\nsome text\n3. Goals\nsome text"
        result = identify_toc_items(text)
        level1_items = [r for r in result if r.level == 1]
        assert len(level1_items) == 3

    def test_sub_level2(self):
        """Test level 2 subsections (X.X format)"""
        text = "Chapter 1 Intro\n1.1 Background\n1.1.1 Details\nsome text\n1.1.2 Extra\nsome text"
        result = identify_toc_items(text)
        level2_items = [r for r in result if r.level == 2]
        # 1.1 and 1.1.1 and 1.1.2 are all level 2 (X.X and X.X.X)
        assert len(level2_items) == 3

    def test_duplicate_chapter(self):
        """Test duplicate chapter scenario"""
        text = "Chapter 1 Intro\nsome text\nChapter 2 Methods\nsome text\nChapter 1 Intro\nsome text"
        result = identify_toc_items(text)
        assert len(result) == 3
        level0_items = [r for r in result if r.level == 0]
        assert len(level0_items) == 3

    def test_less_than_3_returns_empty(self):
        """Test less than 3 titles returns empty"""
        text = "Chapter 1 Intro\nsome text\nChapter 2 Methods\nsome text"
        result = identify_toc_items(text)
        assert result == []

    def test_long_line_skipped(self):
        """Test long lines are skipped"""
        text = "Chapter 1 Intro\n" + "x" * 200 + "\nChapter 2 Methods\nsome text\nChapter 3 Conclusion"
        result = identify_toc_items(text)
        assert len(result) == 3


class TestRelaxedMode:
    """Relaxed mode tests"""

    def test_short_text_with_multiple_numbers(self):
        """Test short text with multiple numbers"""
        text = "Chapter 1 Intro 1.1 Background\nsome text\nChapter 2 Methods 2.1 Experiments\nsome text\nChapter 3 Conclusion 3.1 Summary\nsome text"
        result = identify_toc_items_relaxed(text)
        assert len(result) >= 3


class TestFormatConsistency:
    """Format consistency validation tests"""

    def test_consistent_format_kept(self):
        """Test consistent format is kept"""
        from app.modules.document_parser.schemas import TOCItem
        items = [
            TOCItem(title="Chapter 1 Intro", level=0, char_offset=0),
            TOCItem(title="Chapter 2 Methods", level=0, char_offset=100),
            TOCItem(title="Chapter 3 Conclusion", level=0, char_offset=200),
        ]
        result = _validate_format_consistency(items)
        assert len(result) == 3

    def test_inconsistent_format_filtered(self):
        """Test inconsistent format is filtered"""
        from app.modules.document_parser.schemas import TOCItem
        items = [
            TOCItem(title="Chapter 1 Intro", level=0, char_offset=0),
            TOCItem(title="Chapter 2 Methods", level=0, char_offset=100),
            TOCItem(title="Chapter 3 Conclusion", level=0, char_offset=200),
            TOCItem(title="Random Title", level=0, char_offset=300),
            TOCItem(title="Another Random", level=0, char_offset=400),
        ]
        result = _validate_format_consistency(items)
        # Should keep 3 consistent, filter 2 inconsistent
        assert len(result) == 3

    def test_detect_format_english_word(self):
        """Test format detection: English word"""
        assert _detect_format("Book 1 Introduction") == "english_word"

    def test_detect_format_parenthesis(self):
        """Test format detection: parenthesis"""
        assert _detect_format("(1) Introduction") == "parenthesis"


class TestLLMFallback:
    """LLM fallback tests"""

    @pytest.mark.asyncio
    async def test_llm_fallback_triggered(self):
        """Test LLM fallback is triggered"""
        mock_llm = MockLLMClient()
        text = "Some random text\nAnother line\nThird line\nFourth line\nFifth line"
        result = await identify_toc_items_enhanced(text, "pdf", mock_llm)
        assert len(result) >= 3
        assert result[0].title == "第一章 测试章"

    @pytest.mark.asyncio
    async def test_llm_fallback_skipped_when_rule_works(self):
        """Test LLM is skipped when rules work"""
        mock_llm = MockLLMClient()
        text = "Chapter 1 Intro\nsome text\nChapter 2 Methods\nsome text\nChapter 3 Conclusion\nsome text"
        result = await identify_toc_items_enhanced(text, "pdf", mock_llm)
        assert len(result) == 3
        assert mock_llm.call_count == 0

    @pytest.mark.asyncio
    async def test_no_llm_client_returns_empty(self):
        """Test no LLM client returns empty"""
        text = "Some random text\nAnother line"
        result = await identify_toc_items_enhanced(text, "pdf", None)
        assert result == []
