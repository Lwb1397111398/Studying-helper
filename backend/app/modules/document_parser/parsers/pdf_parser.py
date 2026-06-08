"""PDF解析器"""

import asyncio
from pathlib import Path
from typing import List, Optional

import pdfplumber

from app.common.errors import ServiceError, ErrorCode
from app.common.llm_client import LLMClient
from app.modules.document_parser.schemas import ParsedDocument, BookMetadata, TOCItem, PageInfo, PageTextInfo
from app.modules.document_parser.toc_detector import identify_toc_items, identify_toc_items_enhanced


class PDFParser:
    """PDF文档解析器"""

    extensions = ['pdf']

    def can_parse(self, file_path: str) -> bool:
        """识别PDF文件"""
        return file_path.lower().endswith('.pdf')

    def parse(self, file_path: str, llm_client: Optional[LLMClient] = None) -> ParsedDocument:
        """
        解析PDF文件。

        实现：
        1. 用pdfplumber打开PDF
        2. 提取元数据（标题、作者等）
        3. 提取文本（逐页），构建page_map
        4. 提取目录：
           a. 优先使用PDF内置书签（outline）
           b. 如果没有书签，使用启发式规则识别
        5. 如果文本为空（扫描版PDF），抛出ServiceError(PROCESSING_ERROR)
        6. 如果PDF加密无法打开，抛出ServiceError(PROCESSING_ERROR)
        """
        try:
            pdf = pdfplumber.open(file_path)
        except Exception as e:
            raise ServiceError(
                code=ErrorCode.PROCESSING_ERROR,
                message=f"无法打开PDF文件: {str(e)}"
            )

        try:
            # 提取元数据
            metadata = self._extract_metadata(pdf, file_path)

            # 提取原始页面文本
            raw_pages = self._extract_raw_pages(pdf)

            # 内容清洗（在目录检测之前，确保偏移量一致）
            try:
                from app.modules.document_parser.noise_cleaner import clean_with_pages
                full_text, page_map, _ = clean_with_pages(raw_pages)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"内容清洗失败，使用原始文本: {e}")
                full_text, page_map = self._extract_text_and_page_map(pdf)

            # 验证文本不为空
            if not full_text.strip():
                raise ServiceError(
                    code=ErrorCode.PROCESSING_ERROR,
                    message="PDF文件无文本内容，可能是扫描版PDF"
                )

            # 提取目录（基于清洗后的文本）
            toc = self._extract_toc(pdf, full_text, llm_client)

            return ParsedDocument(
                metadata=metadata,
                full_text=full_text,
                toc=toc,
                page_map=page_map
            )
        finally:
            pdf.close()

    def _extract_metadata(self, pdf, file_path: str) -> BookMetadata:
        """提取PDF元数据"""
        pdf_metadata = pdf.metadata or {}
        file_size = Path(file_path).stat().st_size

        title = pdf_metadata.get('Title', '') or Path(file_path).stem
        author = pdf_metadata.get('Author', '') or None
        publisher = pdf_metadata.get('Producer', '') or None
        creation_date = pdf_metadata.get('CreationDate', '')

        # 清理日期格式（PDF日期格式如D:20230101120000）
        publish_date = None
        if creation_date and isinstance(creation_date, str) and len(creation_date) >= 8:
            date_str = creation_date.replace('D:', '')[:8]
            if date_str.isdigit():
                publish_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        return BookMetadata(
            title=title,
            author=author,
            publisher=publisher,
            publish_date=publish_date,
            language="zh",
            total_pages=len(pdf.pages),
            file_type="pdf",
            file_size_bytes=file_size
        )

    def _extract_raw_pages(self, pdf) -> List[PageTextInfo]:
        """提取逐页原始文本（清洗前）"""
        pages = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages.append(PageTextInfo(
                page_number=i + 1,
                text=text,
                height=page.height or 0,
            ))
        return pages

    def _extract_text_and_page_map(self, pdf) -> tuple:
        """提取全文和页面映射（降级方案）"""
        page_map: List[PageInfo] = []
        full_text_parts: List[str] = []
        current_offset = 0

        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            start_offset = current_offset
            end_offset = start_offset + len(page_text)

            page_map.append(PageInfo(
                page_number=i + 1,
                start_offset=start_offset,
                end_offset=end_offset
            ))

            full_text_parts.append(page_text)
            current_offset = end_offset + 1  # +1 for newline separator

        full_text = "\n".join(full_text_parts)
        return full_text, page_map

    def _extract_toc(self, pdf, full_text: str, llm_client: Optional[LLMClient] = None) -> List[TOCItem]:
        """提取目录：优先使用书签，否则规则识别，最后可用 LLM fallback。"""
        toc = self._extract_toc_from_outline(pdf)

        if not toc:
            toc = identify_toc_items(full_text)

        if not toc and llm_client:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                toc = asyncio.run(identify_toc_items_enhanced(full_text, "pdf", llm_client))

        return toc

    def _extract_toc_from_outline(self, pdf) -> List[TOCItem]:
        """从PDF书签提取目录"""
        try:
            outline = pdf.outline
            if not outline:
                return []
        except Exception:
            return []

        toc_items: List[TOCItem] = []
        self._process_outline_items(outline, toc_items, 0)
        return toc_items

    def _process_outline_items(self, items: list, toc_items: List[TOCItem], level: int):
        """递归处理书签项"""
        for item in items:
            if isinstance(item, list):
                # 嵌套列表表示子项
                if toc_items:
                    self._process_outline_items(item, toc_items[-1].children, level + 1)
            elif isinstance(item, dict):
                title = item.get('title', '')
                if title:
                    # 书签的页码信息（如果有的话）
                    page_number = None
                    # 注意：pdfplumber的outline格式可能因PDF而异

                    toc_items.append(TOCItem(
                        title=title,
                        level=level,
                        page_number=page_number,
                        char_offset=0  # 书签无法精确对应字符偏移
                    ))
