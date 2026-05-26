"""EPUB解析器"""

import re
from pathlib import Path
from typing import List

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from app.common.errors import ServiceError, ErrorCode
from app.modules.document_parser.schemas import ParsedDocument, BookMetadata, TOCItem
from app.modules.document_parser.toc_detector import identify_toc_items


class EPUBParser:
    """EPUB文档解析器"""

    extensions = ['epub']

    def can_parse(self, file_path: str) -> bool:
        """识别EPUB文件"""
        return file_path.lower().endswith('.epub')

    def parse(self, file_path: str) -> ParsedDocument:
        """
        解析EPUB文件。

        实现：
        1. 用ebooklib读取EPUB
        2. 元数据：从OPF元数据提取（标题、作者、语言等）
        3. 目录：从NCX/navigation文档提取 → spine文件名推断 → 文本规则兜底
        4. 文本：按spine顺序遍历章节HTML，用BeautifulSoup提取纯文本
        5. 拼接所有章节文本为full_text
        """
        try:
            book = epub.read_epub(file_path)
        except Exception as e:
            raise ServiceError(
                code=ErrorCode.PROCESSING_ERROR,
                message=f"无法打开EPUB文件: {str(e)}"
            )

        # 提取元数据
        metadata = self._extract_metadata(book, file_path)

        # 提取全文（先提取，目录识别可能用到）
        full_text = self._extract_full_text(book)

        if not full_text.strip():
            raise ServiceError(
                code=ErrorCode.PROCESSING_ERROR,
                message="EPUB文件无文本内容"
            )

        # 提取目录（多层降级）
        toc = self._extract_toc_with_fallback(book, full_text)

        return ParsedDocument(
            metadata=metadata,
            full_text=full_text,
            toc=toc,
            page_map=None  # EPUB没有固定页面概念
        )

    def _extract_metadata(self, book, file_path: str) -> BookMetadata:
        """提取EPUB元数据"""
        file_size = Path(file_path).stat().st_size

        # 获取标题
        title_list = book.get_metadata('DC', 'title')
        title = title_list[0][0] if title_list else Path(file_path).stem

        # 获取作者
        creator_list = book.get_metadata('DC', 'creator')
        author = creator_list[0][0] if creator_list else None

        # 获取出版商
        publisher_list = book.get_metadata('DC', 'publisher')
        publisher = publisher_list[0][0] if publisher_list else None

        # 获取日期
        date_list = book.get_metadata('DC', 'date')
        publish_date = date_list[0][0] if date_list else None

        # 获取语言
        language_list = book.get_metadata('DC', 'language')
        language = language_list[0][0] if language_list else "zh"

        return BookMetadata(
            title=title,
            author=author,
            publisher=publisher,
            publish_date=publish_date,
            language=language,
            total_pages=None,  # EPUB没有固定页数
            file_type="epub",
            file_size_bytes=file_size
        )

    def _extract_toc_with_fallback(self, book, full_text: str) -> List[TOCItem]:
        """
        多层降级目录提取：NCX → spine文件名 → 文本规则
        """
        # 第一层：NCX 内置目录
        toc = self._extract_toc_from_ncx(book)
        if toc:
            return toc

        # 第二层：spine 文件名推断
        toc = self._extract_toc_from_spine(book)
        if toc:
            return toc

        # 第三层：文本规则兜底
        toc = self._identify_toc_from_text(full_text)
        return toc

    def _extract_toc_from_ncx(self, book) -> List[TOCItem]:
        """从 NCX/navigation 文档提取目录"""
        toc_items: List[TOCItem] = []

        try:
            toc = book.toc
            self._process_toc_items(toc, toc_items, 0)
        except Exception:
            pass

        return toc_items

    def _extract_toc_from_spine(self, book) -> List[TOCItem]:
        """
        从 spine 章节文件名推断目录。

        策略：
        - 扫描 spine 中的 HTML 文件名
        - 提取文件名中的章节编号（chapter01.html → 第一章）
        - 构建 TOCItem 列表
        """
        toc_items: List[TOCItem] = []
        chapter_pattern = re.compile(r'chapter[_-]?(\d+)|ch[_-]?(\d+)', re.IGNORECASE)

        spine_items = [item[0] for item in book.spine]

        for item_id in spine_items:
            try:
                item = book.get_item_with_id(item_id)
                if item is None:
                    continue

                # 只处理 HTML 内容
                if item.get_type() != ebooklib.ITEM_DOCUMENT:
                    continue

                file_name = item.get_name()

                # 尝试从文件名提取章节编号
                match = chapter_pattern.search(file_name)
                if match:
                    chapter_num = int(match.group(1) or match.group(2))
                    title = f"第{chapter_num}章"
                    toc_items.append(TOCItem(
                        title=title,
                        level=0,
                        char_offset=0  # 后续由 _identify_toc_from_text 回写
                    ))
            except Exception:
                continue

        # 如果识别到的章节数 < 3，认为不可靠
        if len(toc_items) < 3:
            return []

        return toc_items

    def _identify_toc_from_text(self, full_text: str) -> List[TOCItem]:
        """
        文本规则兜底：调用 toc_detector 的启发式识别。

        注意：这里使用同步版本，因为 EPUB 解析是同步的。
        异步增强版（含 LLM fallback）在 knowledge_splitter 层调用。
        """
        return identify_toc_items(full_text)

    def _process_toc_items(self, items, toc_items: List[TOCItem], level: int):
        """递归处理目录项"""
        for item in items:
            if isinstance(item, tuple):
                # (Section, [items]) 格式
                section, sub_items = item
                if hasattr(section, 'title'):
                    toc_items.append(TOCItem(
                        title=section.title,
                        level=level,
                        char_offset=0  # EPUB目录不直接对应字符偏移
                    ))
                if sub_items:
                    self._process_toc_items(
                        sub_items,
                        toc_items[-1].children if toc_items else toc_items,
                        level + 1
                    )
            elif isinstance(item, epub.Link):
                toc_items.append(TOCItem(
                    title=item.title,
                    level=level,
                    char_offset=0
                ))

    def _extract_full_text(self, book) -> str:
        """提取EPUB全文"""
        text_parts: List[str] = []

        # 按spine顺序遍历章节
        spine_items = [item[0] for item in book.spine]

        for item_id in spine_items:
            try:
                item = book.get_item_with_id(item_id)
                if item is None:
                    continue

                # 只处理HTML内容
                if item.get_type() in [ebooklib.ITEM_DOCUMENT]:
                    html_content = item.get_content().decode('utf-8', errors='ignore')
                    soup = BeautifulSoup(html_content, 'html.parser')

                    # 移除script和style标签
                    for tag in soup(['script', 'style']):
                        tag.decompose()

                    # 提取文本
                    text = soup.get_text(separator='\n', strip=True)
                    if text:
                        text_parts.append(text)
            except Exception:
                continue

        return '\n'.join(text_parts)
