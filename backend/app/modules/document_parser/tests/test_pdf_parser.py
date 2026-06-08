"""PDF解析器测试"""

import pytest
from unittest.mock import MagicMock, patch

from app.modules.ai_learning.tests.mock_llm import MockLLMClient
from app.modules.document_parser.parsers.pdf_parser import PDFParser
from app.common.errors import ServiceError, ErrorCode


class TestPDFParser:
    """PDF解析器测试类"""

    def test_can_parse_pdf(self):
        """识别PDF文件"""
        parser = PDFParser()
        assert parser.can_parse("test.pdf") is True
        assert parser.can_parse("test.PDF") is True
        assert parser.can_parse("path/to/file.pdf") is True

    def test_cannot_parse_txt(self):
        """不识别TXT文件"""
        parser = PDFParser()
        assert parser.can_parse("test.txt") is False
        assert parser.can_parse("test.docx") is False
        assert parser.can_parse("test") is False

    def test_can_parse_case_insensitive(self):
        """大小写不敏感"""
        parser = PDFParser()
        assert parser.can_parse("test.Pdf") is True
        assert parser.can_parse("test.pDf") is True

    @patch('app.modules.document_parser.parsers.pdf_parser.pdfplumber')
    def test_parse_extracts_metadata(self, mock_pdfplumber, tmp_path):
        """解析提取元数据"""
        # 创建测试PDF文件
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        # Mock pdfplumber
        mock_pdf = MagicMock()
        mock_pdf.metadata = {
            'Title': '测试书籍',
            'Author': '测试作者',
            'Producer': '测试出版商',
            'CreationDate': 'D:20230101120000'
        }
        mock_pdf.pages = [MagicMock()]
        mock_pdf.pages[0].extract_text.return_value = "第一页内容"
        mock_pdfplumber.open.return_value = mock_pdf

        parser = PDFParser()
        result = parser.parse(str(pdf_file))

        assert result.metadata.title == "测试书籍"
        assert result.metadata.author == "测试作者"
        assert result.metadata.file_type == "pdf"
        assert result.metadata.total_pages == 1

    @patch('app.modules.document_parser.parsers.pdf_parser.pdfplumber')
    def test_parse_extracts_text(self, mock_pdfplumber, tmp_path):
        """解析提取文本"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        mock_pdf = MagicMock()
        mock_pdf.metadata = {'Title': '测试'}
        mock_pdf.pages = [MagicMock(), MagicMock()]
        mock_pdf.pages[0].extract_text.return_value = "第一页"
        mock_pdf.pages[1].extract_text.return_value = "第二页"
        mock_pdfplumber.open.return_value = mock_pdf

        parser = PDFParser()
        result = parser.parse(str(pdf_file))

        assert "第一页" in result.full_text
        assert "第二页" in result.full_text
        assert result.page_map is not None
        assert len(result.page_map) == 2

    @patch('app.modules.document_parser.parsers.pdf_parser.pdfplumber')
    def test_llm_fallback_when_rules_fail(self, mock_pdfplumber, tmp_path):
        """规则识别不足时使用 LLM fallback"""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")
        llm_client = MockLLMClient()

        mock_pdf = MagicMock()
        mock_pdf.metadata = {'Title': '测试'}
        mock_pdf.pages = [MagicMock()]
        mock_pdf.pages[0].extract_text.return_value = "没有明显章节格式的正文\n只是普通段落"
        mock_pdf.outline = []
        mock_pdfplumber.open.return_value = mock_pdf

        parser = PDFParser()
        result = parser.parse(str(pdf_file), llm_client=llm_client)

        assert llm_client.call_count == 1
        assert len(result.toc) >= 3
        assert result.toc[0].title == "第一章 测试章"

    @patch('app.modules.document_parser.parsers.pdf_parser.pdfplumber')
    def test_parse_empty_pdf_raises_error(self, mock_pdfplumber, tmp_path):
        """空PDF抛出错误"""
        pdf_file = tmp_path / "empty.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        mock_pdf = MagicMock()
        mock_pdf.metadata = {}
        mock_pdf.pages = [MagicMock()]
        mock_pdf.pages[0].extract_text.return_value = ""
        mock_pdfplumber.open.return_value = mock_pdf

        parser = PDFParser()
        with pytest.raises(ServiceError) as exc_info:
            parser.parse(str(pdf_file))

        assert exc_info.value.code == ErrorCode.PROCESSING_ERROR
        assert "无文本内容" in exc_info.value.message
