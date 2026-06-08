"""页眉页脚检测：PDF 专用，检测跨页重复的行和页码"""

import re
import logging
from typing import List, Set

from app.modules.document_parser.schemas import NoiseRegion, PageTextInfo

logger = logging.getLogger(__name__)

MAX_HF_LINE_LENGTH = 80
MIN_REPEAT_RATIO = 0.6
CANDIDATE_LINES = 3
MIN_PAGES = 5

# 页码模式：匹配 "- 42 -"、"42"、"— 42 —"、"Page 42"、"第42页" 等
_PAGE_NUMBER_RE = re.compile(
    r'^(?:'
    r'[-—–\s]*\d+[-—–\s]*'  # - 42 - 或 42
    r'|Page\s+\d+'           # Page 42
    r'|第\s*\d+\s*页'        # 第42页
    r'|P\.?\s*\d+'           # P42 或 P. 42
    r')$'
)


def _is_chapter_title(text: str) -> bool:
    """检查文本是否像章节标题（不应被删除）。"""
    from app.modules.document_parser.toc_detector import _get_chapter_level
    return _get_chapter_level(text) >= 0


def _is_page_number(text: str) -> bool:
    """检查文本是否是页码。"""
    return bool(_PAGE_NUMBER_RE.match(text))


def detect_header_footer_lines(pages: List[PageTextInfo]) -> Set[str]:
    """检测跨页重复的页眉页脚行和页码，返回要移除的行文本集合。"""
    if len(pages) < MIN_PAGES:
        return set()

    # 1) 检测重复行（静态页眉页脚）
    top_candidates: dict[str, list[int]] = {}
    bottom_candidates: dict[str, list[int]] = {}

    for i, page in enumerate(pages):
        lines = [l.strip() for l in page.text.split('\n') if l.strip()]
        if not lines:
            continue

        for line in lines[:CANDIDATE_LINES]:
            if len(line) <= MAX_HF_LINE_LENGTH:
                top_candidates.setdefault(line, []).append(i)

        for line in lines[-CANDIDATE_LINES:]:
            if len(line) <= MAX_HF_LINE_LENGTH:
                bottom_candidates.setdefault(line, []).append(i)

    threshold = len(pages) * MIN_REPEAT_RATIO
    result: Set[str] = set()

    for text, page_indices in top_candidates.items():
        if len(page_indices) >= threshold and not _is_chapter_title(text):
            result.add(text)

    for text, page_indices in bottom_candidates.items():
        if len(page_indices) >= threshold and not _is_chapter_title(text):
            result.add(text)

    # 2) 检测页码模式（每页不同但格式一致）
    page_number_count = 0
    for page in pages:
        lines = [l.strip() for l in page.text.split('\n') if l.strip()]
        if not lines:
            continue
        # 检查首尾行是否是页码
        for line in lines[:CANDIDATE_LINES] + lines[-CANDIDATE_LINES:]:
            if _is_page_number(line):
                page_number_count += 1
                break

    if page_number_count >= threshold:
        # 多数页面都有页码模式，标记所有匹配的行
        for page in pages:
            lines = [l.strip() for l in page.text.split('\n') if l.strip()]
            for line in lines[:CANDIDATE_LINES] + lines[-CANDIDATE_LINES:]:
                if _is_page_number(line):
                    result.add(line)

    if result:
        logger.info(f"检测到 {len(result)} 个页眉页脚行: {result}")
    return result


def detect_header_footer(pages: List[PageTextInfo]) -> List[NoiseRegion]:
    """检测 PDF 页面中跨页重复的页眉页脚行（返回偏移量区域）。"""
    hf_lines = detect_header_footer_lines(pages)
    if not hf_lines:
        return []

    regions = []
    offset = 0
    for i, page in enumerate(pages):
        lines = page.text.split('\n')
        page_start = offset

        for j, line in enumerate(lines):
            stripped = line.strip()
            if stripped not in hf_lines:
                offset += len(line) + 1
                continue

            line_start = page_start + sum(len(lines[k]) + 1 for k in range(j))
            line_end = line_start + len(line)

            if j < CANDIDATE_LINES or j >= len(lines) - CANDIDATE_LINES:
                regions.append(NoiseRegion(
                    start=line_start, end=line_end + 1,
                    noise_type="header_footer"
                ))
            offset += len(line) + 1

        # Reset offset for proper page tracking
        offset = page_start + len(page.text) + 1

    if regions:
        logger.info(f"检测到 {len(regions)} 个页眉页脚区域")
    return regions
