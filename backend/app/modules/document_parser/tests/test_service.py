"""文档解析服务测试"""

import pytest
from pathlib import Path

from app.modules.ai_learning.tests.mock_llm import MockLLMClient
from app.modules.document_parser.service import DocumentParserService
from app.modules.document_parser.parsers import TXTParser, PDFParser, EPUBParser
from app.common.errors import ServiceError, ErrorCode


class TestDocumentParserService:
    """文档解析服务测试类"""

    def _create_service(self):
        """创建服务实例"""
        parsers = [TXTParser(), PDFParser(), EPUBParser()]
        return DocumentParserService(
            parsers=parsers,
            storage_dir="/tmp/test_storage"
        )

    def test_auto_select_parser(self, tmp_path):
        """根据扩展名自动选择解析器"""
        file_path = tmp_path / "test.txt"
        file_path.write_text("测试内容", encoding='utf-8')

        service = self._create_service()
        result = service.parse_and_store(str(file_path), "test_user")

        assert result.metadata.file_type == "txt"
        assert result.full_text == "测试内容"

    def test_unsupported_format_raises_error(self, tmp_path):
        """不支持的格式：抛出VALIDATION_ERROR"""
        file_path = tmp_path / "test.docx"
        file_path.write_bytes(b"fake content")

        service = self._create_service()
        with pytest.raises(ServiceError) as exc_info:
            service.parse_and_store(str(file_path), "test_user")

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
        assert "不支持的文件格式" in exc_info.value.message

    def test_file_too_large_raises_error(self, tmp_path):
        """文件过大：抛出VALIDATION_ERROR"""
        file_path = tmp_path / "large.txt"
        # 创建一个超过100MB的文件（模拟）
        # 为了测试效率，我们mock文件大小检查
        file_path.write_text("a" * 100, encoding='utf-8')

        service = self._create_service()
        # 直接测试文件大小检查逻辑
        with pytest.raises(ServiceError) as exc_info:
            # 临时修改MAX_FILE_SIZE来测试
            original_max = service.MAX_FILE_SIZE
            service.MAX_FILE_SIZE = 50  # 设置为50字节
            try:
                service.parse_and_store(str(file_path), "test_user")
            finally:
                service.MAX_FILE_SIZE = original_max

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
        assert "文件过大" in exc_info.value.message

    def test_nonexistent_file_raises_error(self, tmp_path):
        """不存在的文件：抛出VALIDATION_ERROR"""
        service = self._create_service()
        with pytest.raises(ServiceError) as exc_info:
            service.parse_and_store(str(tmp_path / "nonexistent.txt"), "test_user")

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
        assert "文件不存在" in exc_info.value.message

    def test_empty_file_raises_error(self, tmp_path):
        """空文件：抛出VALIDATION_ERROR"""
        file_path = tmp_path / "empty.txt"
        file_path.write_text("", encoding='utf-8')

        service = self._create_service()
        with pytest.raises(ServiceError) as exc_info:
            service.parse_and_store(str(file_path), "test_user")

        assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
        assert "文件内容为空" in exc_info.value.message

    def test_txt_parser_uses_service_llm_fallback(self, tmp_path):
        """规则识别不足时应使用服务注入的 LLM fallback 识别目录"""
        file_path = tmp_path / "test.txt"
        file_path.write_text("没有明显章节格式的正文\n只是普通段落\n更多普通内容", encoding='utf-8')
        llm_client = MockLLMClient()
        service = DocumentParserService(
            parsers=[TXTParser()],
            storage_dir="/tmp/test_storage",
            llm_client=llm_client,
        )

        result = service.parse_and_store(str(file_path), "test_user")

        assert llm_client.call_count == 1
        assert len(result.toc) >= 3
        assert result.toc[0].title == "第一章 测试章"

    def test_get_supported_formats(self):
        """返回支持的格式列表"""
        service = self._create_service()
        formats = service.get_supported_formats()

        assert "pdf" in formats
        assert "txt" in formats
        assert "epub" in formats
        assert len(formats) == 3

    def test_parse_with_user_id(self, tmp_path):
        """解析时传递用户ID"""
        file_path = tmp_path / "test.txt"
        file_path.write_text("测试内容", encoding='utf-8')

        service = self._create_service()
        result = service.parse_and_store(str(file_path), "user_123")

        # 验证解析成功（user_id目前未在结果中使用，但不应报错）
        assert result is not None
        assert result.metadata.title == "test"
