"""知识拆分服务"""

from typing import List, Dict, Optional
from app.modules.document_parser.schemas import ParsedDocument, TOCItem
from app.modules.knowledge_splitter.schemas import (
    KnowledgeUnit, Chapter, SplitResult, SplitStats, Section, SubTitle
)
from app.modules.knowledge_splitter.splitter import TextSplitter


class SplitError(Exception):
    """拆分异常基类"""
    pass


class NoTOCError(SplitError):
    """无目录异常"""
    pass


class KnowledgeSplitterService:
    """知识拆分服务"""

    def __init__(self, unit_min_length: int = 100, unit_max_length: int = 5000):
        self.splitter = TextSplitter(unit_min_length, unit_max_length)

    def split(self, document: ParsedDocument, book_id: str) -> SplitResult:
        """
        将文档拆分为章节和知识单元。

        流程：
        1. 校验目录是否存在，不存在则抛出 NoTOCError
        2. 根据目录层级递归提取章节和小节（Section）
        3. 按层级结构逐层切块：章 → 小节 → 知识单元
        4. 统计拆分结果

        参数：
        - document: 解析后的文档（来自模块一）
        - book_id: 书籍ID

        返回：SplitResult

        异常：
        - NoTOCError: 书本导入模块未识别到目录
        """
        # 步骤1：校验目录
        if not document.toc:
            raise NoTOCError(
                "书本导入模块未能识别目录结构。可能原因："
                "① 上传的是扫描版PDF（无文字层）"
                "② 文件格式异常或损坏"
                "③ 书本本身无目录"
                "建议：检查文件是否可复制文字，或尝试其他格式。"
            )

        # 步骤2：按层级提取章节和小节
        flat_toc = self._flatten_toc(document.toc)
        sorted_offsets = sorted(item.char_offset for item in flat_toc)
        chapters, sections = self._extract_hierarchy(flat_toc, document.full_text, book_id, sorted_offsets)

        # 步骤3：层级切块
        all_units: List[KnowledgeUnit] = []
        for chapter in chapters:
            chapter_sections = [s for s in sections if s.chapter_id == chapter.id]
            if chapter_sections:
                # 有小节 → 按小节切，传入子标题辅助切分
                for section in chapter_sections:
                    text = section.text
                    if text.strip():
                        units = self.splitter.split_text(
                            text, chapter.id, book_id,
                            parent_title=section.title,
                            sub_titles=section.sub_titles,
                            base_offset=section.char_offset_start,
                            section_id=section.id,
                        )
                        all_units.extend(units)
            else:
                # 无小节 → 整章切
                chapter_text = self._get_chapter_text(chapter, document.full_text, flat_toc)
                if chapter_text.strip():
                    # 计算章节在全文中的起始偏移
                    chapter_offset = self._get_chapter_start_offset(chapter, flat_toc)
                    units = self.splitter.split_text(
                        chapter_text, chapter.id, book_id,
                        parent_title=chapter.title,
                        base_offset=chapter_offset,
                        section_id=None,
                    )
                    all_units.extend(units)

        # 重新设置全局order_index
        for i, unit in enumerate(all_units):
            unit.order_index = i

        # 步骤4：计算统计信息
        stats = self._calculate_stats(all_units, len(chapters))

        return SplitResult(
            book_id=book_id,
            chapters=chapters,
            sections=sections,
            units=all_units,
            split_stats=stats,
        )

    def _extract_hierarchy(
        self, flat_toc: List[TOCItem], full_text: str, book_id: str,
        sorted_offsets: list[int],
    ) -> tuple[List[Chapter], List[Section]]:
        """
        从扁平化目录提取层级结构。

        level=0 → Chapter（章）
        level=1 → Section（小节）
        level≥2 → 归入父 Section 的 sub_titles

        返回: (chapters, sections)
        """
        chapters: List[Chapter] = []
        sections: List[Section] = []
        chapter_number = 0
        current_chapter_id = ""
        last_section: Optional[Section] = None

        for item in flat_toc:
            if item.level == 0:
                chapter_number += 1
                chapter = Chapter(
                    book_id=book_id,
                    title=item.title,
                    chapter_number=chapter_number,
                    order_index=len(chapters),
                )
                chapters.append(chapter)
                current_chapter_id = chapter.id
                last_section = None

            elif item.level == 1:
                section_text = self._get_node_text(item, full_text, sorted_offsets)
                section = Section(
                    chapter_id=current_chapter_id,
                    title=item.title,
                    level=item.level,
                    order_index=len(sections),
                    text=section_text,
                    char_offset_start=item.char_offset,
                )
                sections.append(section)
                last_section = section

            elif item.level >= 2:
                # 归入当前章最后一个 Section（O(1) 直接取 last_section）
                if last_section is not None:
                    extra_text = self._get_node_text(item, full_text, sorted_offsets)
                    last_section.text += "\n\n" + extra_text
                    last_section.sub_titles.append(
                        SubTitle(char_offset=item.char_offset, title=item.title)
                    )

        return chapters, sections

    def _flatten_toc(self, toc: List[TOCItem]) -> List[TOCItem]:
        """将树形目录扁平化为列表"""
        result = []
        for item in toc:
            result.append(item)
            if item.children:
                result.extend(self._flatten_toc(item.children))
        return result

    def _get_node_text(self, node: TOCItem, full_text: str, sorted_offsets: list[int]) -> str:
        """
        获取某个目录节点对应的文本范围。
        sorted_offsets: 按 char_offset 排序的所有目录项偏移列表（用于二分查找）
        """
        import bisect
        start = node.char_offset
        idx = bisect.bisect_right(sorted_offsets, start)
        end = sorted_offsets[idx] if idx < len(sorted_offsets) else len(full_text)
        return full_text[start:end].strip()

    def _get_chapter_start_offset(self, chapter: Chapter, flat_toc: List[TOCItem]) -> int:
        """获取章节在全文中的起始偏移"""
        for item in flat_toc:
            if item.level == 0 and item.title == chapter.title:
                return item.char_offset
        return 0

    def _get_chapter_text(self, chapter: Chapter, full_text: str, flat_toc: List[TOCItem]) -> str:
        """获取章节文本（无小节时使用）"""
        top_items = [item for item in flat_toc if item.level == 0]
        for i, item in enumerate(top_items):
            if item.title == chapter.title:
                start = item.char_offset
                end = top_items[i + 1].char_offset if i + 1 < len(top_items) else len(full_text)
                return full_text[start:end].strip()
        return ""

    def _calculate_stats(self, units: List[KnowledgeUnit], total_chapters: int) -> SplitStats:
        """计算拆分统计"""
        if not units:
            return SplitStats(
                total_chapters=total_chapters,
                total_units=0,
                avg_unit_length=0.0,
                min_unit_length=0,
                max_unit_length=0,
                units_without_title=0,
            )

        lengths = [len(u.content) for u in units]
        return SplitStats(
            total_chapters=total_chapters,
            total_units=len(units),
            avg_unit_length=sum(lengths) / len(lengths),
            min_unit_length=min(lengths),
            max_unit_length=max(lengths),
            units_without_title=sum(1 for u in units if not u.title),
        )
