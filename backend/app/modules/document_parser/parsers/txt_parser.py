"""TXT解析器"""

import asyncio
from pathlib import Path
from typing import List, Optional

import chardet

from app.common.errors import ServiceError, ErrorCode
from app.common.llm_client import LLMClient
from app.modules.document_parser.schemas import ParsedDocument, BookMetadata, TOCItem
from app.modules.document_parser.toc_detector import identify_toc_items, identify_toc_items_enhanced


class TXTParser:
    """TXT文档解析器"""

    extensions = ['txt']

    def can_parse(self, file_path: str) -> bool:
        """识别TXT文件"""
        return file_path.lower().endswith('.txt')

    def parse(self, file_path: str, llm_client: Optional[LLMClient] = None) -> ParsedDocument:
        """
        解析TXT文件。

        实现：
        1. 读取文件前10KB检测编码（chardet）
        2. 用检测到的编码读取全文
        3. 提取目录：
           a. 检查文件开头是否有目录段落（连续带编号的行）
           b. 如果没有，使用启发式规则识别章节标题
        4. 元数据：从文件名提取书名，作者为None
        5. 如果文件为空，抛出ServiceError(VALIDATION_ERROR)
        """
        file_path_obj = Path(file_path)

        # 验证文件存在
        if not file_path_obj.exists():
            raise ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"文件不存在: {file_path}"
            )

        # 检测编码
        encoding = self._detect_encoding(file_path)

        # 读取全文
        try:
            full_text = file_path_obj.read_text(encoding=encoding)
        except Exception as e:
            raise ServiceError(
                code=ErrorCode.PROCESSING_ERROR,
                message=f"读取文件失败: {str(e)}"
            )

        # 验证文件不为空
        if not full_text.strip():
            raise ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="文件内容为空"
            )

        # 内容清洗（在目录检测之前，确保偏移量一致）
        try:
            from app.modules.document_parser.noise_cleaner import clean_full_text
            full_text, _ = clean_full_text(full_text)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"内容清洗失败，使用原始文本: {e}")

        # 提取元数据
        metadata = self._extract_metadata(file_path_obj, encoding)

        # 提取目录
        toc = self._extract_toc(full_text, llm_client)

        return ParsedDocument(
            metadata=metadata,
            full_text=full_text,
            toc=toc,
            page_map=None  # TXT没有页面概念
        )

    def _detect_encoding(self, file_path: str) -> str:
        """检测文件编码"""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(10240)  # 读取前10KB

            result = chardet.detect(raw_data)
            encoding = result.get('encoding', 'utf-8')

            # 如果检测失败或置信度低，默认使用utf-8
            if not encoding or (result.get('confidence', 0) < 0.5):
                encoding = 'utf-8'

            return encoding
        except Exception:
            return 'utf-8'

    def _extract_metadata(self, file_path: Path, encoding: str) -> BookMetadata:
        """提取TXT文件元数据"""
        file_size = file_path.stat().st_size
        title = file_path.stem  # 从文件名提取书名

        return BookMetadata(
            title=title,
            author=None,
            publisher=None,
            publish_date=None,
            language="zh",
            total_pages=None,
            file_type="txt",
            file_size_bytes=file_size
        )

    def _extract_toc(self, full_text: str, llm_client: Optional[LLMClient] = None) -> List[TOCItem]:
        """提取目录"""
        # 先尝试识别文件开头的目录段落
        toc = self._extract_toc_from_header(full_text)

        if not toc:
            # 如果没有目录段落，使用启发式规则
            toc = identify_toc_items(full_text)

        if not toc and llm_client:
            # 同步解析器只在无线程事件循环中桥接异步 LLM fallback。
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                toc = asyncio.run(identify_toc_items_enhanced(full_text, "txt", llm_client))

        return toc

    def _extract_toc_from_header(self, full_text: str) -> List[TOCItem]:
        """从文件开头提取目录段落"""
        lines = full_text.split('\n')
        toc_items: List[TOCItem] = []
        in_toc_section = False
        toc_end_patterns = ['正文', '第一章', 'Chapter 1', '第一回']

        # 检查前50行是否有目录特征
        check_lines = lines[:50]
        toc_pattern_count = 0

        for line in check_lines:
            stripped = line.strip()
            if not stripped:
                continue
            # 检测目录特征：包含章节编号的行
            if any(pattern in stripped for pattern in ['第', '章', '节', '篇', 'Chapter', '目录']):
                toc_pattern_count += 1

        # 如果目录特征行少于3行，认为没有目录段落
        if toc_pattern_count < 3:
            return []

        # 提取目录
        current_offset = 0
        for line in lines[:50]:
            stripped = line.strip()
            if not stripped:
                current_offset += len(line) + 1
                continue

            # 检查是否是目录项
            is_toc_item = False
            for pattern in toc_end_patterns:
                if pattern in stripped and stripped.startswith(('第', 'Chapter')):
                    is_toc_item = True
                    break

            if is_toc_item or (len(stripped) < 50 and any(
                c in stripped for c in ['第', '章', '节', '篇']
            )):
                toc_items.append(TOCItem(
                    title=stripped,
                    level=0,
                    char_offset=current_offset
                ))

            current_offset += len(line) + 1

            # 如果遇到正文开始，停止提取
            if any(pattern in stripped for pattern in toc_end_patterns):
                if len(toc_items) >= 3:
                    break
                else:
                    return []  # 不是真正的目录

        return toc_items if len(toc_items) >= 3 else []
