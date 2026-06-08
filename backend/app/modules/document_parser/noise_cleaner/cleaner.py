"""内容清洗主协调器：统一调度四个子清洗器"""

import logging
from typing import List

from app.modules.document_parser.schemas import (
    NoiseRegion, PageTextInfo, PageInfo,
)
from app.modules.document_parser.noise_cleaner.header_footer import detect_header_footer, detect_header_footer_lines
from app.modules.document_parser.noise_cleaner.front_matter import detect_front_matter
from app.modules.document_parser.noise_cleaner.back_matter import detect_back_matter
from app.modules.document_parser.noise_cleaner.toc_cleaner import detect_toc_pages

logger = logging.getLogger(__name__)


def _apply_removal(full_text: str, regions: List[NoiseRegion]) -> str:
    """从全文中移除所有噪声区域。"""
    if not regions:
        return full_text

    # 合并重叠区域
    sorted_r = sorted(regions, key=lambda r: r.start)
    merged = [sorted_r[0]]
    for r in sorted_r[1:]:
        if r.start <= merged[-1].end:
            merged[-1] = NoiseRegion(
                start=merged[-1].start,
                end=max(merged[-1].end, r.end),
                noise_type=merged[-1].noise_type,
            )
        else:
            merged.append(r)

    # 从后往前移除（避免偏移量变化）
    result = full_text
    for r in reversed(merged):
        result = result[:r.start] + result[r.end:]

    return result


def clean_full_text(full_text: str) -> tuple[str, List[NoiseRegion]]:
    """清洗全文（EPUB/TXT 路径，无页面结构）。

    返回 (cleaned_text, noise_regions)。
    """
    regions: List[NoiseRegion] = []
    regions.extend(detect_front_matter(full_text))
    regions.extend(detect_toc_pages(full_text))
    regions.extend(detect_back_matter(full_text))

    if not regions:
        return full_text, []

    cleaned = _apply_removal(full_text, regions)
    logger.info(f"内容清洗完成: 移除 {len(regions)} 个噪声区域, "
                f"文本从 {len(full_text)} 字符减至 {len(cleaned)} 字符")
    return cleaned, regions


def clean_with_pages(pages: List[PageTextInfo]) -> tuple[str, List[PageInfo], List[NoiseRegion]]:
    """清洗 PDF 逐页文本。

    返回 (cleaned_full_text, cleaned_page_map, noise_regions)。
    """
    # Phase 1: 检测页眉页脚（返回行文本集合，避免偏移量问题）
    hf_lines = detect_header_footer_lines(pages)

    # Phase 2: 全文级噪声检测
    regions: List[NoiseRegion] = []
    full_text_raw = "\n".join(p.text for p in pages)
    regions.extend(detect_front_matter(full_text_raw))
    regions.extend(detect_toc_pages(full_text_raw))
    regions.extend(detect_back_matter(full_text_raw))

    if not hf_lines and not regions:
        # 无噪声，直接拼接
        parts = []
        page_map = []
        offset = 0
        for page in pages:
            start = offset
            end = start + len(page.text)
            page_map.append(PageInfo(
                page_number=page.page_number,
                start_offset=start,
                end_offset=end,
            ))
            parts.append(page.text)
            offset = end + 1
        return "\n".join(parts), page_map, []

    # Phase 3: 按页面重建
    return _rebuild_from_pages(pages, regions, hf_lines)


def _rebuild_from_pages(
    pages: List[PageTextInfo],
    regions: List[NoiseRegion],
    hf_lines: set[str] | None = None,
) -> tuple[str, List[PageInfo], List[NoiseRegion]]:
    """从清洗后的页面重建全文和 page_map。"""
    skip_types = {"front_matter", "back_matter", "toc_page"}
    skip_regions = [r for r in regions if r.noise_type in skip_types]

    # 计算原始全文中每页的偏移量
    page_offsets = []
    offset = 0
    for page in pages:
        page_offsets.append(offset)
        offset += len(page.text) + 1

    # 确定要整页跳过的页面
    skip_pages = set()
    for r in skip_regions:
        for i, page in enumerate(pages):
            page_start = page_offsets[i]
            page_end = page_start + len(page.text)
            if page_end <= r.start or page_start >= r.end:
                continue
            overlap_start = max(r.start, page_start)
            overlap_end = min(r.end, page_end)
            overlap = overlap_end - overlap_start
            if len(page.text) > 0 and overlap / len(page.text) > 0.5:
                skip_pages.add(i)

    # 重建
    cleaned_parts = []
    page_map = []
    current_offset = 0

    for i, page in enumerate(pages):
        if i in skip_pages:
            continue

        page_text = page.text

        # 应用页眉页脚移除（按行文本匹配，不受偏移量影响）
        if hf_lines:
            lines = page_text.split('\n')
            new_lines = [line for line in lines if line.strip() not in hf_lines]
            page_text = '\n'.join(new_lines)

        if not page_text.strip():
            continue

        start = current_offset
        end = start + len(page_text)
        page_map.append(PageInfo(
            page_number=page.page_number,
            start_offset=start,
            end_offset=end,
        ))
        cleaned_parts.append(page_text)
        current_offset = end + 1

    full_text = "\n".join(cleaned_parts)
    logger.info(f"PDF 内容清洗完成: {len(pages)} 页 -> {len(page_map)} 页, "
                f"跳过 {len(skip_pages)} 页, 文本从 {sum(len(p.text) for p in pages)} "
                f"字符减至 {len(full_text)} 字符")
    return full_text, page_map, regions
