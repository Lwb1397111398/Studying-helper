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

    # 非内容目录项的标题关键词（匹配则过滤）
    _NON_CONTENT_KEYWORDS = [
        '扉页', '目录', '目錄', '版权', '序', '前言', '自序', '代序',
        '缩略语', '凡例', '勘误', '条文索引', '索引',
        '参考文献', '后记', '跋', '译后记', '出版说明',
    ]

    def __init__(self, unit_min_length: int = 100, unit_max_length: int = 5000):
        self.splitter = TextSplitter(unit_min_length, unit_max_length)

    def split(self, document: ParsedDocument, book_id: str) -> SplitResult:
        """
        将文档拆分为章节和知识单元。

        流程：
        1. 校验目录是否存在，不存在则抛出 NoTOCError
        2. 根据目录层级提取多级章节结构（编>章>节>...）
        3. 为叶子节点切分知识单元
        4. 统计拆分结果

        参数：
        - document: 解析后的文档（来自模块一）
        - book_id: 书籍ID

        返回：SplitResult

        异常：
        - NoTOCError: 书本导入模块未识别到目录
        """
        # 步骤1：校验目录（toc=None 表示未识别，toc=[] 表示无目录结构）
        if document.toc is None:
            raise NoTOCError(
                "书本导入模块未能识别目录结构。可能原因："
                "① 上传的是扫描版PDF（无文字层）"
                "② 文件格式异常或损坏"
                "③ 书本本身无目录"
                "建议：检查文件是否可复制文字，或尝试其他格式。"
            )

        # 步骤2：按层级提取章节结构（支持多级层级）
        if document.toc:
            flat_toc = self._flatten_toc(document.toc)
            # 过滤非内容目录项（扉页、目录、版权页、索引等）
            flat_toc = self._filter_non_content_toc(flat_toc)
            # EPUB 等格式的 char_offset 全为 0，需要根据标题搜索修正
            self._fix_toc_offsets(flat_toc, document.full_text)
            chapters, _ = self._extract_hierarchy(flat_toc, document.full_text, book_id)
        else:
            # toc=[]：无目录结构，整本书作为一章
            from uuid import uuid4
            flat_toc = []
            chapters = [Chapter(
                id=str(uuid4()), book_id=book_id, title="全文",
                chapter_number=1, level=0, order_index=0,
                text=document.full_text,
            )]

        # 步骤3：为叶子节点切分知识单元
        all_units: List[KnowledgeUnit] = []
        parent_ids = {ch.parent_id for ch in chapters if ch.parent_id}

        for chapter in chapters:
            # 只处理叶子节点（没有子节点的节点）
            if chapter.id in parent_ids:
                continue

            if chapter.text and chapter.text.strip():
                # 计算文本在全文中的偏移
                chapter_offset = self._get_leaf_offset(chapter, flat_toc)
                units = self.splitter.split_text(
                    chapter.text, chapter.id, book_id,
                    parent_title=chapter.title,
                    base_offset=chapter_offset,
                    section_id=None,
                )
                all_units.extend(units)

        # 重新设置全局order_index
        for i, unit in enumerate(all_units):
            unit.order_index = i

        # 步骤4：计算统计信息
        # 统计各级别的章节数量
        level_counts = {}
        for ch in chapters:
            level_name = {0: '编', 1: '章', 2: '节', 3: '小节'}.get(ch.level, f'Level{ch.level}')
            level_counts[level_name] = level_counts.get(level_name, 0) + 1

        stats = self._calculate_stats(all_units, len(chapters))

        return SplitResult(
            book_id=book_id,
            chapters=chapters,
            sections=[],  # 不再使用单独的 Section 列表
            units=all_units,
            split_stats=stats,
        )

    def _extract_hierarchy(
        self, flat_toc: List[TOCItem], full_text: str, book_id: str,
    ) -> tuple[List[Chapter], List[Section]]:
        """
        从扁平化目录提取多级层级结构。

        支持任意深度的层级（编>章>节>...），通过 parent_id 建立父子关系。
        所有 TOC 条目都创建为 Chapter 对象，Section 列表返回空。

        返回: (chapters, [])
        """
        chapters: List[Chapter] = []
        # 栈维护当前层级路径：[(level, chapter_id)]
        stack: List[tuple[int, str]] = []

        for item in flat_toc:
            # 弹出栈中 level >= 当前 level 的项，找到正确的父节点
            while stack and stack[-1][0] >= item.level:
                stack.pop()

            parent_id = stack[-1][1] if stack else None

            chapter = Chapter(
                book_id=book_id,
                title=item.title,
                chapter_number=len(chapters) + 1,
                parent_id=parent_id,
                level=item.level,
                order_index=len(chapters),
            )
            chapters.append(chapter)
            stack.append((item.level, chapter.id))

        # 为叶子节点提取文本内容
        parent_ids = {ch.parent_id for ch in chapters if ch.parent_id}
        for i, chapter in enumerate(chapters):
            if chapter.id not in parent_ids:
                # 叶子节点，提取文本
                chapter.text = self._get_leaf_text(chapters[i], flat_toc, full_text, chapters)

        return chapters, []  # 不再使用单独的 Section 列表

    def _flatten_toc(self, toc: List[TOCItem]) -> List[TOCItem]:
        """将树形目录扁平化为列表"""
        result = []
        for item in toc:
            result.append(item)
            if item.children:
                result.extend(self._flatten_toc(item.children))
        return result

    def _filter_non_content_toc(self, flat_toc: List[TOCItem]) -> List[TOCItem]:
        """过滤非内容目录项（扉页、目录、版权页、索引等）。

        规则：
        - 有子节点的项保留（即使标题匹配，可能是"序"作为编包含章节）
        - 独立项（无子节点）且标题匹配非内容关键词 → 移除
        """
        if not flat_toc:
            return flat_toc

        # 判断哪些项有子节点（后面紧跟 level 更大的项）
        has_children = set()
        for i, item in enumerate(flat_toc):
            if i + 1 < len(flat_toc) and flat_toc[i + 1].level > item.level:
                has_children.add(i)

        result = []
        for i, item in enumerate(flat_toc):
            # 有子节点的项保留
            if i in has_children:
                result.append(item)
                continue
            # 独立项：检查标题是否为非内容
            title = item.title.strip()
            is_non_content = any(kw in title for kw in self._NON_CONTENT_KEYWORDS)
            if not is_non_content:
                result.append(item)

        return result

    def _fix_toc_offsets(self, flat_toc: List[TOCItem], full_text: str) -> None:
        """当 TOC 项的 char_offset 全为 0 时（如 EPUB），通过标题搜索修正偏移量。

        搜索失败的项（标题不在正文中）会被移除，避免级联错位。
        直接原地修改 flat_toc。
        """
        # 只在所有偏移都为 0 时才修正
        if not flat_toc or any(item.char_offset > 0 for item in flat_toc):
            return

        search_start = 0
        failed_indices = []
        for i, item in enumerate(flat_toc):
            pos = full_text.find(item.title, search_start)
            if pos != -1:
                item.char_offset = pos
                search_start = pos + len(item.title)
            else:
                failed_indices.append(i)

        # 从后往前移除搜索失败的项（避免索引偏移）
        for i in reversed(failed_indices):
            flat_toc.pop(i)

    def _get_node_text(self, node: TOCItem, full_text: str, flat_toc: List[TOCItem]) -> str:
        """
        获取某个目录节点对应的文本范围（只含直属内容）。

        对于 level=1：返回到下一个同级节点之间的文本，但排除 level>=2 子节点的范围
        对于 level>=2：只返回到下一个同级或更高级节点之间的文本
        """
        start = node.char_offset
        end = len(full_text)
        found_current = False

        if node.level == 1:
            # 对于 level=1：先找到下一个 level<=1 的节点作为最大范围
            # 然后检查中间是否有 level>=2 的子节点，如果有则在第一个子节点处停止
            next_peer_end = len(full_text)
            found_current = False
            for item in flat_toc:
                if item is node:
                    found_current = True
                    continue
                if not found_current:
                    continue
                if item.level <= 1:
                    next_peer_end = item.char_offset
                    break
            # 检查是否有 level>=2 的子节点
            found_current = False
            for item in flat_toc:
                if item is node:
                    found_current = True
                    continue
                if not found_current:
                    continue
                if item.char_offset >= next_peer_end:
                    break
                if item.level >= 2:
                    end = item.char_offset
                    break
            else:
                end = next_peer_end
        else:
            # 对于 level>=2：在下一个同级或更高级节点处停止
            found_current = False
            for item in flat_toc:
                if item is node:
                    found_current = True
                    continue
                if not found_current:
                    continue
                if item.level <= node.level:
                    end = item.char_offset
                    break

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

    def _get_leaf_text(
        self, chapter: Chapter, flat_toc: List[TOCItem], full_text: str, all_chapters: List[Chapter]
    ) -> str:
        """获取叶子节点的文本内容"""
        # 通过 title + level 查找对应的 TOCItem（取第一个匹配项）
        toc_item = None
        for item in flat_toc:
            if item.level == chapter.level and item.title == chapter.title:
                toc_item = item
                break

        if toc_item is None:
            return ""

        start = toc_item.char_offset

        # 找到下一个同级或更高级的节点作为结束位置
        found_current = False
        end = len(full_text)
        for item in flat_toc:
            if item is toc_item:
                found_current = True
                continue
            if not found_current:
                continue
            if item.level <= chapter.level:
                end = item.char_offset
                break

        return full_text[start:end].strip()

    def _get_leaf_offset(self, chapter: Chapter, flat_toc: List[TOCItem]) -> int:
        """获取叶子节点在全文中的起始偏移"""
        # 通过 title + level 查找对应的 TOCItem
        for item in flat_toc:
            if item.level == chapter.level and item.title == chapter.title:
                return item.char_offset
        return 0

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
