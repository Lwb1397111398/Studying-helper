"""文本拆分器"""

import re
from typing import List, Optional
from app.modules.knowledge_splitter.schemas import KnowledgeUnit, SubTitle


class TextSplitter:
    """文本拆分器"""

    # 预编译正则（避免每次调用重新编译）
    _SPLIT_PARAGRAPHS = re.compile(r'\n\n+')
    _SPLIT_SENTENCES = re.compile(r'([。！？.!?])')
    _TITLE_RE = re.compile(r'^(.{1,50})[。！？.!?]')

    def __init__(self, unit_min_length: int = 100, unit_max_length: int = 5000):
        self.unit_min_length = unit_min_length
        self.unit_max_length = unit_max_length

    def split_text(
        self,
        text: str,
        chapter_id: str,
        book_id: str,
        parent_title: str = "",
        sub_titles: Optional[List[SubTitle]] = None,
        base_offset: int = 0,
        section_id: Optional[str] = None,
    ) -> List[KnowledgeUnit]:
        """
        将文本拆分为知识单元。

        算法（优先级从高到低）：
        1. 按子标题（level≥2）边界切 — 最自然，不破坏语义
        2. 按双换行符分割段落
        3. 合并连续短段落（< unit_min_length）
        4. 拆分超长段落（> unit_max_length）：先按句子，再按逗号，最后按固定长度
        5. 为每个单元计算char_offset_start和char_offset_end

        参数：
        - text: 要切分的文本
        - chapter_id: 所属章节ID（level=0）
        - book_id: 书籍ID
        - parent_title: 父级标题（用于生成单元标题）
        - sub_titles: 子标题列表，优先在这些边界处切分（char_offset 为全文绝对偏移）
        - base_offset: text 在全文中的起始偏移，用于将 sub_titles 的绝对偏移转为相对偏移
        - section_id: 所属小节ID（level=1），无小节时为 None
        """
        if not text.strip():
            return []

        # 步骤1：优先按子标题边界切分（base_offset 在步骤5中追踪）
        if sub_titles:
            chunks = self._split_by_sub_titles(text, sub_titles, base_offset=base_offset)
        else:
            # 步骤2：按双换行符分割段落
            paragraphs = self._SPLIT_PARAGRAPHS.split(text)
            # 步骤3：合并短段落
            merged = self._merge_short_paragraphs(paragraphs)
            # 步骤4：拆分超长段落
            chunks = []
            for para in merged:
                if len(para) > self.unit_max_length:
                    chunks.extend(self._split_long_paragraph(para))
                else:
                    chunks.append(para)

        # 步骤5：构建 KnowledgeUnit
        # 关键：char_offset 是相对于传入 text 的偏移。
        # 调用方（service）需要加上 base_offset 才能得到全文偏移。
        # 切块过程中 chunks 是按顺序从 text 中切出的，直接累加偏移即可，
        # 完全避免 text.find 的重复匹配问题。
        units = []
        # 先计算每个 chunk 在原文中的精确起止位置
        # 方法：按顺序在 text 中定位每个 chunk 的首次出现（从上一个匹配位置之后）
        # 对于从 text 直接切出的 chunk（段落/句子），用顺序扫描保证位置正确
        search_start = 0
        text_len = len(text)

        for chunk in chunks:
            stripped = chunk.strip()
            if not stripped:
                continue

            # 从 search_start 开始找，确保不往回匹配
            pos = text.find(stripped, search_start)
            if pos == -1:
                # 回退：从开头找（理论上不应发生，除非切块时产生了原文没有的内容）
                pos = text.find(stripped)

            if pos != -1:
                start = pos
                end = pos + len(stripped)
                search_start = end  # 下次从当前位置之后找，防止重复匹配
            else:
                # 极端 fallback：跳过
                continue

            if start > text_len:
                continue

            title = self._extract_title(stripped)
            units.append(KnowledgeUnit(
                book_id=book_id,
                chapter_id=chapter_id,
                section_id=section_id,
                title=title,
                content=stripped,
                order_index=len(units),
                char_offset_start=start + base_offset,  # 转为全文偏移
                char_offset_end=min(end, text_len) + base_offset,
            ))

        return units

    def _split_by_sub_titles(
        self, text: str, sub_titles: List[SubTitle], base_offset: int = 0
    ) -> List[str]:
        """
        按子标题边界切分文本。

        参数：
        - text: 要切分的文本片段
        - sub_titles: 子标题列表（char_offset 为全文绝对偏移）
        - base_offset: text 在全文中的起始偏移，用于将绝对偏移转为相对偏移

        策略：
        - 将子标题绝对偏移转为 text 内相对偏移
        - 按相对偏移排序，相邻子标题之间的文本作为一块
        - 每块仍超长 → 递归按句子/逗号/长度切
        """
        if not sub_titles:
            return [text]

        text_len = len(text)
        # 转为相对偏移，过滤掉不在 text 范围内的
        relative = []
        for st in sub_titles:
            rel = st.char_offset - base_offset
            if 0 < rel < text_len:
                relative.append(rel)

        relative.sort()
        # 去重（避免多个子标题同偏移导致空块）
        relative = [relative[i] for i in range(len(relative))
                    if i == 0 or relative[i] != relative[i - 1]]

        if not relative:
            return [text]

        chunks = []
        prev = 0

        for rel_offset in relative:
            if rel_offset <= prev:
                continue
            chunk = text[prev:rel_offset].strip()
            if chunk:
                if len(chunk) > self.unit_max_length:
                    chunks.extend(self._split_long_paragraph(chunk))
                else:
                    chunks.append(chunk)
            prev = rel_offset

        # 最后一块
        tail = text[prev:].strip()
        if tail:
            if len(tail) > self.unit_max_length:
                chunks.extend(self._split_long_paragraph(tail))
            else:
                chunks.append(tail)

        return chunks if chunks else [text]

    def _merge_short_paragraphs(self, paragraphs: List[str]) -> List[str]:
        """合并连续的短段落"""
        if not paragraphs:
            return []

        merged = []
        buffer = ""

        for para in paragraphs:
            stripped = para.strip()
            if not stripped:
                continue
            if not buffer:
                buffer = stripped
            elif len(buffer) + len(stripped) + 2 <= self.unit_min_length:
                buffer += "\n\n" + stripped
            else:
                merged.append(buffer)
                buffer = stripped

        if buffer:
            merged.append(buffer)
        return merged

    def _split_long_paragraph(self, paragraph: str) -> List[str]:
        """拆分超长段落：先按句子，再按逗号，最后按固定长度"""
        # 按句子拆分
        sentences = self._SPLIT_SENTENCES.split(paragraph)
        merged_sents = []
        for i in range(0, len(sentences) - 1, 2):
            merged_sents.append(sentences[i] + sentences[i + 1])
        if len(sentences) % 2 == 1:
            merged_sents.append(sentences[-1])

        # 单句仍超长则按逗号拆
        final_sents = []
        for sent in merged_sents:
            if len(sent) > self.unit_max_length:
                final_sents.extend(self._split_by_comma(sent))
            else:
                final_sents.append(sent)

        # 按 unit_max_length 分组
        result = []
        buffer = ""
        for sent in final_sents:
            if len(buffer) + len(sent) <= self.unit_max_length:
                buffer += sent
            else:
                if buffer:
                    result.append(buffer)
                if len(sent) > self.unit_max_length:
                    result.extend(self._split_by_length(sent))
                else:
                    buffer = sent
        if buffer:
            result.append(buffer)

        return result if result else [paragraph]

    def _split_by_comma(self, text: str) -> List[str]:
        """按逗号拆分"""
        parts = re.split(r'([，,；;：:])', text)
        merged = []
        for i in range(0, len(parts) - 1, 2):
            merged.append(parts[i] + parts[i + 1])
        if len(parts) % 2 == 1:
            merged.append(parts[-1])

        result = []
        buffer = ""
        for part in merged:
            if len(buffer) + len(part) <= self.unit_max_length:
                buffer += part
            else:
                if buffer:
                    result.append(buffer)
                buffer = part
        if buffer:
            result.append(buffer)
        return result if result else [text]

    def _split_by_length(self, text: str) -> List[str]:
        """按固定长度截断"""
        step = self.unit_max_length
        return [text[i:i + step] for i in range(0, len(text), step)]

    def _extract_title(self, text: str) -> str:
        """从文本中提取标题：取第一句话"""
        match = self._TITLE_RE.match(text)
        if match:
            return match.group(1).strip()
        return text[:50].strip()
