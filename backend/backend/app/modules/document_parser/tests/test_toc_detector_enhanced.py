"""增强版目录识别测试"""

import pytest
from app.modules.document_parser.toc_detector import (
    identify_toc_items,
    identify_toc_items_relaxed,
    identify_toc_items_enhanced,
    _validate_format_consistency,
    _detect_format,
)
from app.modules.ai_learning.tests.mock_llm import MockLLMClient


# ──────────────────────────────────────────────
# 严格模式测试（至少 3 个标题）
# ──────────────────────────────────────────────

class TestStrictMode:
    """严格模式目录识别测试"""

    def test_chinese_number_chapter(self):
        """测试中文数字章节"""
        text = "第一章 绪论\n这是正文\n第二章 方法\n这是正文\n第三章 结论\n这是正文"
        result = identify_toc_items(text)
        assert len(result) == 3
        assert result[0].title == "第一章 绪论"
        assert result[0].level == 0

    def test_arabic_number_chapter(self):
        """测试阿拉伯数字章节"""
        text = "第 1 章 导论\n这是正文\n第 2 章 方法\n这是正文\n第 3 章 结论\n这是正文"
        result = identify_toc_items(text)
        assert len(result) == 3
        assert result[0].level == 0

    def test_bian_level0(self):
        """测试'第一编'格式"""
        text = "第一编 历史篇\n这是正文\n第二编 理论篇\n这是正文\n第三编 实践篇\n这是正文"
        result = identify_toc_items(text)
        assert len(result) == 3
        assert "第一编" in result[0].title
        assert result[0].level == 0

    def test_part_level0(self):
        """测试'第一部分'格式 - Part 1/2/3"""
        text = "Part 1 Basics\nThis is text\nPart 2 Methods\nThis is text\nPart 3 Conclusion\nThis is text"
        result = identify_toc_items(text)
        assert len(result) == 3
        assert result[0].level == 0

    def test_book_level0(self):
        """测试'Book 1'格式"""
        text = "Book 1 Introduction\nThis is text\nBook 2 Methods\nThis is text\nBook 3 Conclusion\nThis is text"
        result = identify_toc_items(text)
        assert len(result) == 3
        assert result[0].level == 0

    def test_unit_level0(self):
        """测试'Unit 1'格式"""
        text = "Unit 1 Basics\nThis is text\nUnit 2 Advanced\nThis is text\nUnit 3 Expert\nThis is text"
        result = identify_toc_items(text)
        assert len(result) == 3
        assert result[0].level == 0

    def test_parenthesis_level0(self):
        """测试'（一）'格式"""
        text = "（一）引言\n这是正文\n（二）方法\n这是正文\n（三）结论\n这是正文"
        result = identify_toc_items(text)
        assert len(result) == 3
        assert result[0].level == 0

    def test_sub_level1(self):
        """测试二级节"""
        text = "第一章 绪论\n1.1 背景\n这是正文\n1.2 意义\n这是正文\n1.3 目标\n这是正文"
        result = identify_toc_items(text)
        level1_items = [r for r in result if r.level == 1]
        assert len(level1_items) == 3

    def test_sub_level2(self):
        """测试三级小节"""
        text = "第一章 绪论\n1.1 背景\n1.1.1 细节\n这是正文\n1.1.2 补充\n这是正文"
        result = identify_toc_items(text)
        level2_items = [r for r in result if r.level == 2]
        assert len(level2_items) == 2

    def test_duplicate_chapter(self):
        """测试'第一章里又出现第一章'场景 - 至少 3 个标题"""
        text = "第一章 绪论\n这是正文\n第二章 方法\n这是正文\n第一章 绪论\n这是正文"
        result = identify_toc_items(text)
        # 三个标题都应该被识别
        assert len(result) == 3
        level0_items = [r for r in result if r.level == 0]
        assert len(level0_items) == 3

    def test_less_than_3_returns_empty(self):
        """测试少于3个标题时返回空"""
        text = "第一章 绪论\n这是正文\n第二章 方法\n这是正文"
        result = identify_toc_items(text)
        assert result == []

    def test_long_line_skipped(self):
        """测试过长行被跳过"""
        text = "第一章 绪论\n" + "这是一段很长的正文" * 100 + "\n第二章 方法\n这是正文\n第三章 结论"
        result = identify_toc_items(text)
        # 应该只识别到三个章节，长正文行被跳过
        assert len(result) == 3


# ──────────────────────────────────────────────
# 宽松模式测试
# ──────────────────────────────────────────────

class TestRelaxedMode:
    """宽松模式目录识别测试"""

    def test_short_text_with_multiple_numbers(self):
        """测试短文本含多个编号"""
        text = "第一章 绪论 1.1 背景\n这是正文\n第二章 方法 2.1 实验\n这是正文\n第三章 结论 3.1 总结\n这是正文"
        result = identify_toc_items_relaxed(text)
        # 宽松模式应该能识别
        assert len(result) >= 3

    def test_chinese_comma_format(self):
        """测试'一、二、三、'格式"""
        text = "一、引言\n这是正文\n二、方法\n这是正文\n三、结论\n这是正文"
        result = identify_toc_items_relaxed(text)
        assert len(result) == 3


# ──────────────────────────────────────────────
# 格式一致性校验测试
# ──────────────────────────────────────────────

class TestFormatConsistency:
    """格式一致性校验测试"""

    def test_consistent_format_kept(self):
        """测试格式一致的保留"""
        from app.modules.document_parser.schemas import TOCItem
        items = [
            TOCItem(title="第一章 绪论", level=0, char_offset=0),
            TOCItem(title="第二章 方法", level=0, char_offset=100),
            TOCItem(title="第三章 结论", level=0, char_offset=200),
        ]
        result = _validate_format_consistency(items)
        assert len(result) == 3

    def test_inconsistent_format_filtered(self):
        """测试格式不一致的过滤 - 多数一致时过滤少数"""
        from app.modules.document_parser.schemas import TOCItem
        items = [
            TOCItem(title="第一章 绪论", level=0, char_offset=0),
            TOCItem(title="第二章 方法", level=0, char_offset=100),
            TOCItem(title="第三章 结论", level=0, char_offset=200),
            TOCItem(title="Random Title", level=0, char_offset=300),
            TOCItem(title="Another Random", level=0, char_offset=400),
        ]
        result = _validate_format_consistency(items)
        # 应该保留 3 个一致的，过滤掉 2 个不一致的
        assert len(result) == 3

    def test_detect_format_chinese_number(self):
        """测试格式检测：中文数字"""
        assert _detect_format("第一章 绪论") == "chinese_number"

    def test_detect_format_english_word(self):
        """测试格式检测：英文单词"""
        assert _detect_format("Book 1 Introduction") == "english_word"

    def test_detect_format_parenthesis(self):
        """测试格式检测：括号编号"""
        assert _detect_format("（一）引言") == "parenthesis"


# ──────────────────────────────────────────────
# LLM Fallback 测试
# ──────────────────────────────────────────────

class TestLLMFallback:
    """LLM fallback 测试"""

    @pytest.mark.asyncio
    async def test_llm_fallback_triggered(self):
        """测试 LLM fallback 被触发"""
        mock_llm = MockLLMClient()
        # 构造一个规则无法识别的文本
        text = "Some random text\nAnother line\nThird line\nFourth line\nFifth line"
        result = await identify_toc_items_enhanced(text, "pdf", mock_llm)
        # LLM 应该返回模拟的 TOC
        assert len(result) >= 3
        assert result[0].title == "第一章 测试章"

    @pytest.mark.asyncio
    async def test_llm_fallback_skipped_when_rule_works(self):
        """测试规则有效时跳过 LLM"""
        mock_llm = MockLLMClient()
        text = "第一章 绪论\n这是正文\n第二章 方法\n这是正文\n第三章 结论\n这是正文"
        result = await identify_toc_items_enhanced(text, "pdf", mock_llm)
        # 应该走规则，不走 LLM
        assert len(result) == 3
        assert mock_llm.call_count == 0  # LLM 未被调用

    @pytest.mark.asyncio
    async def test_no_llm_client_returns_empty(self):
        """测试无 LLM 客户端时返回空"""
        text = "Some random text\nAnother line"
        result = await identify_toc_items_enhanced(text, "pdf", None)
        assert result == []
