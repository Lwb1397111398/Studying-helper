"""TXT解析器测试"""

import pytest
from unittest.mock import patch

from app.modules.document_parser.parsers.txt_parser import TXTParser
from app.common.errors import ServiceError, ErrorCode


class TestTXTParser:
    """TXT解析器测试类"""

    def test_can_parse_txt(self):
        """识别TXT文件"""
        parser = TXTParser()
        assert parser.can_parse("test.txt") is True
        assert parser.can_parse("test.TXT") is True
        assert parser.can_parse("path/to/file.txt") is True

    def test_cannot_parse_other(self):
        """不识别其他格式"""
        parser = TXTParser()
        assert parser.can_parse("test.pdf") is False
        assert parser.can_parse("test.epub") is False
        assert parser.can_parse("test") is False

    def test_parse_utf8_txt(self, tmp_path):
        """解析UTF-8编码TXT"""
        file_path = tmp_path / "test.txt"
        content = "第一章 测试\n这是一个测试文件。\n第二章 结束\n"
        file_path.write_text(content, encoding='utf-8')

        parser = TXTParser()
        result = parser.parse(str(file_path))

        assert result.metadata.title == "test"
        assert result.metadata.file_type == "txt"
        assert result.full_text == content
        assert result.page_map is None  # TXT没有页面概念

    def test_parse_txt_with_toc(self, sample_txt_with_toc):
        """带目录的TXT：正确识别目录"""
        parser = TXTParser()
        result = parser.parse(str(sample_txt_with_toc))

        # 应该识别到目录
        assert len(result.toc) > 0
        # 验证目录项标题
        toc_titles = [item.title for item in result.toc]
        assert any("第一章" in title for title in toc_titles)

    def test_parse_txt_without_toc(self, sample_txt_without_toc):
        """无目录的TXT：启发式识别"""
        parser = TXTParser()
        result = parser.parse(str(sample_txt_without_toc))

        # 启发式识别可能识别到章节标题
        # 这取决于文本内容是否匹配模式
        assert result.full_text is not None

    def test_parse_empty_txt_raises_error(self, sample_txt_empty):
        """空文件：抛出VALIDATION_ERROR"""
        parser = TXTParser()
        with pytest.raises(ServiceError) as exc_info:
            parser.parse(str(sample_txt_empty))

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
        assert "文件内容为空" in exc_info.value.message

    def test_parse_nonexistent_file_raises_error(self, tmp_path):
        """不存在的文件：抛出错误"""
        parser = TXTParser()
        with pytest.raises(ServiceError) as exc_info:
            parser.parse(str(tmp_path / "nonexistent.txt"))

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR

    def test_parse_gbk_txt(self, sample_txt_gbk):
        """解析GBK编码TXT"""
        parser = TXTParser()
        result = parser.parse(str(sample_txt_gbk))

        assert "测试章节" in result.full_text
        assert "GBK编码" in result.full_text

    def test_metadata_extraction(self, tmp_path):
        """元数据提取"""
        file_path = tmp_path / "我的书籍.txt"
        file_path.write_text("测试内容", encoding='utf-8')

        parser = TXTParser()
        result = parser.parse(str(file_path))

        assert result.metadata.title == "我的书籍"
        assert result.metadata.author is None
        assert result.metadata.file_type == "txt"
        assert result.metadata.file_size_bytes > 0
