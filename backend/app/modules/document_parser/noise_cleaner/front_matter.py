"""前置内容检测：版权页、序言、前言等"""

import re
import logging
from typing import List

from app.modules.document_parser.schemas import NoiseRegion

logger = logging.getLogger(__name__)

# 前置内容标记词
FRONT_MATTER_MARKERS = [
    "书名页", "版权页", "版权信息", "版权说明",
    "出版信息", "图书在版编目", "CIP数据",
    "ISBN", "出版社", "出版发行",
    "前言", "序言", "自序", "代序", "他序",
    "推荐序", "译者序", "作者序", "再版序",
    "第二版序", "第三版序", "修订版序",
    "Preface", "Foreword", "preface", "foreword",
    "Acknowledgments", "Acknowledgements",
    "献词", "题献", "Dedication",
    "内容简介", "内容提要", "本书简介",
    "作者简介", "关于作者", "About the Author",
    "修订说明", "凡例", "使用说明",
    "法规缩略语表", "缩略语表",
]

# 正文起始标记（匹配到这些就认为正文开始了）
# 使用前瞻断言排除 TOC 条目（如 "第一章 基础 ........ 1"）
CONTENT_START_PATTERNS = [
    r'^第[一二三四五六七八九十百千\d]+[编部册集章节篇回](?=\s+[^\d.]|[^\s\d.]|$)',
    r'^第\s*\d+\s*[编部册集章节篇回](?=\s+[^\d.]|[^\s\d.]|$)',
    r'^(Chapter|Book|Lesson|Unit|Part)\s+\d+',
    r'^[IVXLCDM]+\.\s+',
    r'^引言\b',
    r'^绪论\b',
    r'^导论\b',
    r'^绪\s*言\b',
]

_COMPILED_CONTENT_START = [re.compile(p) for p in CONTENT_START_PATTERNS]

# 最少前置行数，防止误删
MIN_FRONT_MATTER_LINES = 3


def detect_front_matter(full_text: str) -> List[NoiseRegion]:
    """检测文本开头的前置内容区域。"""
    lines = full_text.split('\n')
    content_start_idx = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        for pattern in _COMPILED_CONTENT_START:
            if pattern.match(stripped):
                content_start_idx = i
                break
        if content_start_idx is not None:
            break

    if content_start_idx is None or content_start_idx < MIN_FRONT_MATTER_LINES:
        return []

    front_text = '\n'.join(lines[:content_start_idx])
    has_marker = any(marker in front_text for marker in FRONT_MATTER_MARKERS)
    if not has_marker:
        return []

    end_offset = sum(len(lines[j]) + 1 for j in range(content_start_idx))
    logger.info(f"检测到前置内容: {content_start_idx} 行, {end_offset} 字符")
    return [NoiseRegion(start=0, end=end_offset, noise_type="front_matter")]
