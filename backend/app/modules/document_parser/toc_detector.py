"""启发式目录识别 + LLM fallback"""

import re
import logging
from typing import List, Optional, Tuple
from app.modules.document_parser.schemas import TOCItem
from app.common.llm_client import LLMClient, LLMMessage

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 多模式正则匹配表：(level, pattern, flags)
# 按优先级排列，先匹配的优先
# ──────────────────────────────────────────────
CHAPTER_PATTERNS: List[Tuple[int, str, int]] = [
    # level 0: 顶级章节（按优先级排列，先匹配的优先）
    (0, r'^[（(][一二三四五六七八九十百千\d]+[)）]', 0),               # （一）(二) (1) (2) - 必须在"第X章"之前
    (0, r'^第[一二三四五六七八九十百千\d]+[编部册集]', 0),         # 第一编/第一部/第一册/第一集
    (0, r'^第\s*\d+\s*[编部册集]', 0),
    (0, r'^第[一二三四五六七八九十百千\d]+[章节篇部回]', 0),       # 第一章/第一篇/第一部/第一回
    (0, r'^第\s*\d+\s*[章节篇部回]', 0),
    (0, r'^(Chapter|Book|Lesson|Unit|Part)\s+\d+', re.IGNORECASE),        # Chapter 1 / Book 1 / Lesson 1 / Unit 1 / Part 1
    (0, r'^[IVXLCDM]+\.\s+', 0),                                   # I. / II. / III.

    # level 1: 节
    (1, r'^第[一二三四五六七八九十百千\d]+节', 0),                 # 第一节
    (1, r'^[一二三四五六七八九十百千]+、', 0),                      # 一、二、三、
    (1, r'^\d+\.\s+\S', 0),                                        # 1. 标题（必须有空格）

    # level 2: 小节
    (2, r'^\d+\.\d+\.\d+\s*\S', 0),                                # 1.1.1 标题（三级）
    (2, r'^\d+\.\d+\s*\S', 0),                                     # 1.1 标题
    (2, r'^\d+\.\S', 0),                                           # 1.标题（无空格）
]

# 编译正则表达式
_COMPILED_PATTERNS: List[Tuple[int, re.Pattern]] = [
    (level, re.compile(pattern, flags)) for level, pattern, flags in CHAPTER_PATTERNS
]


# ──────────────────────────────────────────────
# 一致性校验阈值
# ──────────────────────────────────────────────
MIN_TOC_ITEMS = 3          # 最少识别数，低于此值认为无效
MAX_TITLE_LENGTH = 100     # 超过此长度的行跳过（正文）
RELAXED_MAX_TITLE_LENGTH = 40  # 宽松模式最大标题长度
FORMAT_CONSISTENCY_RATIO = 0.6  # 同级格式一致率阈值


def identify_toc_items(text: str) -> List[TOCItem]:
    """
    从纯文本中识别章节标题（严格模式）。

    算法：
    1. 按行扫描，匹配章节标题正则
    2. 根据匹配的模式确定层级
    3. 记录每个标题的字符偏移量
    4. 如果识别到的标题数 < 3，返回空列表
    """
    toc_items: List[TOCItem] = []
    lines = text.split('\n')
    current_offset = 0

    for line in lines:
        stripped = line.strip()

        # 跳过空行
        if not stripped:
            current_offset += len(line) + 1
            continue

        # 跳过过长的行（可能是正文）
        if len(stripped) > MAX_TITLE_LENGTH:
            current_offset += len(line) + 1
            continue

        # 匹配章节标题
        level = _get_chapter_level(stripped)
        if level >= 0:
            toc_items.append(TOCItem(
                title=stripped,
                level=level,
                char_offset=current_offset
            ))

        current_offset += len(line) + 1

    # 一致性校验：同级格式必须一致
    toc_items = _validate_format_consistency(toc_items)

    # 如果识别到的标题数 < 3，返回空列表
    if len(toc_items) < MIN_TOC_ITEMS:
        return []

    return toc_items


def identify_toc_items_relaxed(text: str) -> List[TOCItem]:
    """
    宽松模式目录识别。

    解决"第一章里又出现第一章"场景：
    - 短文本（<40字）含多个编号 → 取第一个作为当前层级，后续同级
    - 利用否定先行断言避免重复计数
    """
    toc_items: List[TOCItem] = []
    lines = text.split('\n')
    current_offset = 0

    for line in lines:
        stripped = line.strip()

        if not stripped:
            current_offset += len(line) + 1
            continue

        # 宽松模式：允许更长的标题
        if len(stripped) > RELAXED_MAX_TITLE_LENGTH:
            current_offset += len(line) + 1
            continue

        # 宽松匹配：只要包含章节编号特征即可
        level = _get_chapter_level_relaxed(stripped)
        if level >= 0:
            toc_items.append(TOCItem(
                title=stripped,
                level=level,
                char_offset=current_offset
            ))

        current_offset += len(line) + 1

    toc_items = _validate_format_consistency(toc_items)

    if len(toc_items) < MIN_TOC_ITEMS:
        return []

    return toc_items


async def identify_toc_items_enhanced(
    text: str,
    file_type: str = "pdf",
    llm_client: Optional[LLMClient] = None
) -> List[TOCItem]:
    """
    增强版目录识别：规则 → 宽松规则 → LLM fallback。

    参数：
    - text: 全文文本
    - file_type: 文件类型（pdf/epub/txt）
    - llm_client: LLM 客户端（可选，不传则跳过 LLM fallback）

    返回：
    - 识别到的目录项列表
    """
    # 第一步：严格规则
    flat = identify_toc_items(text)
    if len(flat) >= MIN_TOC_ITEMS:
        logger.info(f"严格规则识别到 {len(flat)} 个目录项")
        return flat

    # 第二步：宽松规则
    flat = identify_toc_items_relaxed(text)
    if len(flat) >= MIN_TOC_ITEMS:
        logger.info(f"宽松规则识别到 {len(flat)} 个目录项")
        return flat

    # 第三步：LLM fallback
    if llm_client:
        logger.info("规则识别不足，触发 LLM fallback")
        flat = await identify_toc_items_with_llm(text, file_type, llm_client)
        if len(flat) >= MIN_TOC_ITEMS:
            return flat

    logger.warning(f"目录识别失败，仅识别到 {len(flat)} 个目录项")
    return flat


async def identify_toc_items_with_llm(
    text: str,
    file_type: str,
    llm_client: LLMClient
) -> List[TOCItem]:
    """
    使用 LLM 识别目录。

    策略：
    1. 取前 6000 字 + 后 2000 字作为上下文
    2. 发送 JSON mode prompt
    3. 解析返回的 JSON 数组
    4. 回写 char_offset（按原文匹配行号计算）
    """
    from app.modules.document_parser.toc_prompt import build_toc_prompt

    # 采样文本：前 6000 字 + 后 2000 字
    sample_text = _sample_text(text, head=6000, tail=2000)

    messages = [
        LLMMessage(role="system", content=build_toc_prompt(file_type)),
        LLMMessage(role="user", content=f"以下是书籍的文本片段：\n\n{sample_text}")
    ]

    try:
        result = await llm_client.chat_json(messages, temperature=0.3, max_tokens=4096)
        toc_data = result.get("toc", result.get("chapters", []))

        if not isinstance(toc_data, list):
            logger.warning(f"LLM 返回格式错误: {type(toc_data)}")
            return []

        # 构建 TOCItem 并回写 char_offset
        toc_items = []
        for item in toc_data:
            title = item.get("title", "")
            level = item.get("level", 0)
            if not title:
                continue

            # 在原文中查找标题位置
            char_offset = _find_title_offset(text, title)
            toc_items.append(TOCItem(
                title=title,
                level=level,
                char_offset=char_offset
            ))

        logger.info(f"LLM 识别到 {len(toc_items)} 个目录项")
        return toc_items

    except Exception as e:
        logger.error(f"LLM 目录识别失败: {e}")
        return []


# ──────────────────────────────────────────────
# 内部辅助函数
# ──────────────────────────────────────────────

def _get_chapter_level(text: str) -> int:
    """
    根据匹配的模式确定章节层级（严格模式）。

    返回：
    - 0: 顶级章节（第X章、Chapter X、第一部分、Book 1 等）
    - 1: 二级章节（第X节、1. 标题、一、标题）
    - 2: 三级章节（1.1 标题）
    - -1: 不匹配任何模式
    """
    for level, pattern in _COMPILED_PATTERNS:
        if pattern.match(text):
            return level

    return -1


def _get_chapter_level_relaxed(text: str) -> int:
    """
    宽松模式层级判断。

    只要文本包含章节编号特征即可，不要求行首匹配。
    """
    # 宽松匹配：允许编号前有空格或标点
    relaxed_patterns = [
        (0, r'[第][一二三四五六七八九十百千\d]+[编部册集章节篇部回]'),
        (0, r'(Book|Lesson|Unit|Part)\s+\d+'),
        (0, r'[（(][一二三四五六七八九十百千]+[)）]'),  # （一）(二)
        (1, r'[第][一二三四五六七八九十百千\d]+节'),
        (1, r'\d+\.\s*\S'),
        (1, r'[一二三四五六七八九十百千]+、'),
        (2, r'\d+\.\d+\s*\S'),
    ]

    for level, pattern in relaxed_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return level

    return -1


def _validate_format_consistency(items: List[TOCItem]) -> List[TOCItem]:
    """
    一致性校验：同级标题格式必须一致。

    策略：
    1. 按 level 分组
    2. 检测每组的格式类型（"第X章"/"1. X"/"Chapter X" 等）
    3. 如果组内格式种类 > 2，只保留数量最多的格式
    """
    if len(items) < MIN_TOC_ITEMS:
        return items

    # 按 level 分组
    by_level: dict[int, List[TOCItem]] = {}
    for item in items:
        by_level.setdefault(item.level, []).append(item)

    # 检查每组内部一致性
    result = []
    for level, group in by_level.items():
        formats = [_detect_format(item.title) for item in group]
        format_counts: dict[str, int] = {}
        for fmt in formats:
            format_counts[fmt] = format_counts.get(fmt, 0) + 1

        # 如果格式种类 <= 1，认为完全一致
        if len(format_counts) <= 1:
            result.extend(group)
            continue

        # 如果格式种类 == 2，检查 majority 是否 >= 60%
        if len(format_counts) == 2:
            most_common_count = max(format_counts.values())
            if most_common_count / len(group) >= FORMAT_CONSISTENCY_RATIO:
                # 保留 majority 格式
                most_common = max(format_counts, key=format_counts.get)
                consistent_items = [
                    item for item, fmt in zip(group, formats) if fmt == most_common
                ]
                result.extend(consistent_items)
                continue
            else:
                # 两种格式各占一半，保留原组
                result.extend(group)
                continue

        # 保留数量最多的格式
        most_common = max(format_counts, key=format_counts.get)
        consistent_items = [
            item for item, fmt in zip(group, formats) if fmt == most_common
        ]

        # 如果保留后数量足够，使用过滤后的结果
        if len(consistent_items) >= MIN_TOC_ITEMS:
            result.extend(consistent_items)
        else:
            # 否则保留原组（宁可多不可少）
            result.extend(group)

    # 按 char_offset 排序，维持原文顺序
    result.sort(key=lambda x: x.char_offset)
    return result


def _detect_format(title: str) -> str:
    """检测标题格式类型"""
    if re.match(r'^第[一二三四五六七八九十百千\d]+[编部册集章节篇部回]', title):
        return "chinese_number"
    if re.match(r'^(Chapter|Book|Lesson|Unit|Part)\s+\d+', title, re.IGNORECASE):
        return "english_word"
    if re.match(r'^\d+\.\s+', title):
        return "arabic_dot"
    if re.match(r'^[一二三四五六七八九十百千]+、', title):
        return "chinese_comma"
    if re.match(r'^[（(][一二三四五六七八九十百千\d]+[)）]', title):
        return "parenthesis"
    if re.match(r'^[IVXLCDM]+\.', title):
        return "roman"
    return "other"


def _sample_text(text: str, head: int = 6000, tail: int = 2000) -> str:
    """采样文本：前 head 字 + 后 tail 字"""
    if len(text) <= head + tail:
        return text

    head_text = text[:head]
    tail_text = text[-tail:]
    return f"{head_text}\n\n...（省略中间部分）...\n\n{tail_text}"


def _find_title_offset(text: str, title: str) -> int:
    """在原文中查找标题位置，返回字符偏移量"""
    # 精确匹配
    idx = text.find(title)
    if idx != -1:
        return idx

    # 模糊匹配：去除空格后比较
    title_clean = re.sub(r'\s+', '', title)
    for i in range(len(text) - len(title_clean)):
        chunk = re.sub(r'\s+', '', text[i:i + len(title_clean) + 10])
        if title_clean in chunk:
            return i

    return 0


# ──────────────────────────────────────────────
# 树形结构构建（保持不变）
# ──────────────────────────────────────────────

def build_toc_tree(flat_toc: List[TOCItem]) -> List[TOCItem]:
    """
    将扁平的目录列表转换为树形结构。

    参数：
    - flat_toc: 扁平的目录项列表

    返回：
    - 树形结构的顶级目录项列表
    """
    if not flat_toc:
        return []

    root_items: List[TOCItem] = []
    stack: List[TOCItem] = []

    for item in flat_toc:
        # 弹出栈中层级大于等于当前项的项
        while stack and stack[-1].level >= item.level:
            stack.pop()

        if stack:
            # 作为子项添加到栈顶项
            stack[-1].children.append(item)
        else:
            # 顶级项
            root_items.append(item)

        stack.append(item)

    return root_items
