"""后置内容检测：附录、索引、参考文献等"""

import logging
from typing import List

from app.modules.document_parser.schemas import NoiseRegion

logger = logging.getLogger(__name__)

# 后置内容标记词
BACK_MATTER_MARKERS = [
    "附录", "Appendix", "Appendices",
    "索引", "Index",
    "参考文献", "参考书目", "References", "Bibliography",
    "参考文献列表",
    "后记", "跋", "Afterword", "Epilogue",
    "术语表", "词汇表", "Glossary",
    "名词索引", "人名索引", "主题索引",
    "编后记", "出版后记",
]

# 标记行最大长度（避免匹配正文中的引用）
MAX_MARKER_LINE_LENGTH = 50
MIN_BACK_MATTER_LINES = 3


def detect_back_matter(full_text: str) -> List[NoiseRegion]:
    """检测文本末尾的后置内容区域。"""
    lines = full_text.split('\n')

    # 从末尾反向扫描，找到最早的后置标记（尽量往前找）
    marker_line_idx = None
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if not stripped:
            continue
        if len(stripped) > MAX_MARKER_LINE_LENGTH:
            continue
        for marker in BACK_MATTER_MARKERS:
            if marker in stripped:
                remaining = len(lines) - i
                if remaining >= MIN_BACK_MATTER_LINES:
                    marker_line_idx = i  # 记录，继续往前找更早的
                break

    if marker_line_idx is None:
        return []

    start_offset = sum(len(lines[j]) + 1 for j in range(marker_line_idx))
    logger.info(f"检测到后置内容: 从第{marker_line_idx}行到文末, {len(full_text) - start_offset} 字符")
    return [NoiseRegion(start=start_offset, end=len(full_text), noise_type="back_matter")]
