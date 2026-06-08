"""印刷目录检测：移除书中印刷的目录页"""

import re
import logging
from typing import List

from app.modules.document_parser.schemas import NoiseRegion

logger = logging.getLogger(__name__)

# 目录标题模式
TOC_HEADING_PATTERNS = [
    re.compile(r'^目\s*录\s*$'),
    re.compile(r'^Contents\s*$', re.IGNORECASE),
    re.compile(r'^Table\s+of\s+Contents\s*$', re.IGNORECASE),
    re.compile(r'^CONTENTS\s*$'),
]

# 目录条目模式
TOC_ENTRY_PATTERNS = [
    re.compile(r'.+\.{3,}\s*\d+'),                              # "Chapter 1 ........ 15"
    re.compile(r'.+\s{3,}\d+\s*$'),                             # "Chapter 1      15"
    re.compile(r'第[一二三四五六七八九十百千\d]+[章节目编].*\d+\s*$'),  # "第一章 xxx ... 1"
    re.compile(r'^\d+\.\d*\s+.*\d+$'),                          # "1.1 Title ... 10"
    re.compile(r'^[一二三四五六七八九十]+[、.]\s*.+\d+\s*$'),    # "一、标题 10"
]

# 最少目录条目数
MIN_TOC_ENTRIES = 3
# 连续非目录行数阈值（超过则认为目录结束）
CONSECUTIVE_NON_TOC = 3


def detect_toc_pages(full_text: str) -> List[NoiseRegion]:
    """检测并标记印刷目录区域。"""
    lines = full_text.split('\n')
    toc_start = None

    # 查找目录标题
    for i, line in enumerate(lines):
        stripped = line.strip()
        for pattern in TOC_HEADING_PATTERNS:
            if pattern.match(stripped):
                toc_start = i
                break
        if toc_start is not None:
            break

    if toc_start is None:
        return []

    # 从标题向下扫描目录条目
    toc_end = None
    non_toc_count = 0
    entry_count = 0

    for i in range(toc_start + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped:
            continue

        is_entry = any(p.match(stripped) for p in TOC_ENTRY_PATTERNS)
        if is_entry:
            non_toc_count = 0
            toc_end = i
            entry_count += 1
        else:
            non_toc_count += 1
            if non_toc_count >= CONSECUTIVE_NON_TOC:
                break

    if toc_end is None or entry_count < MIN_TOC_ENTRIES:
        return []

    start_offset = sum(len(lines[j]) + 1 for j in range(toc_start))
    end_offset = sum(len(lines[j]) + 1 for j in range(toc_end + 1))
    logger.info(f"检测到印刷目录: 第{toc_start}-{toc_end}行, {entry_count}个条目")
    return [NoiseRegion(start=start_offset, end=end_offset, noise_type="toc_page")]
