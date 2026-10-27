"""EvidenceRef 程序校验：半开区间 + unicode code point（Python str 索引）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


OffsetEncoding = Literal["unicode_code_point"]


@dataclass
class EvidenceValidationResult:
    valid: bool
    code: str = "ok"
    message: str = ""
    normalized_quote: str = ""


def slice_by_code_points(text: str, start: int, end: int) -> str:
    """[start, end) unicode code point 切片（CPython str ≈ code point）。"""
    if start < 0 or end < start:
        raise ValueError("invalid offsets")
    return text[start:end]


def validate_evidence_ref(
    *,
    block_text: str,
    start_offset: int,
    end_offset: int,
    quote: str,
    offset_encoding: OffsetEncoding = "unicode_code_point",
    allow_whitespace_normalize: bool = True,
) -> EvidenceValidationResult:
    if offset_encoding != "unicode_code_point":
        return EvidenceValidationResult(
            valid=False,
            code="unsupported_encoding",
            message=f"unsupported offset_encoding={offset_encoding}",
        )
    if start_offset < 0 or end_offset < start_offset:
        return EvidenceValidationResult(
            valid=False,
            code="invalid_offsets",
            message="start_offset/end_offset must satisfy 0 <= start <= end",
        )
    if end_offset > len(block_text):
        return EvidenceValidationResult(
            valid=False,
            code="offset_out_of_range",
            message=f"end_offset {end_offset} > block length {len(block_text)}",
        )
    sliced = slice_by_code_points(block_text, start_offset, end_offset)
    if sliced == quote:
        return EvidenceValidationResult(valid=True, normalized_quote=quote)
    if allow_whitespace_normalize:
        if "".join(sliced.split()) == "".join(quote.split()):
            return EvidenceValidationResult(
                valid=True,
                code="ok_whitespace_normalized",
                normalized_quote=sliced,
            )
    return EvidenceValidationResult(
        valid=False,
        code="offset_mismatch",
        message="quote does not match block slice",
        normalized_quote=sliced,
    )


def find_quote_offsets(block_text: str, quote: str) -> Optional[tuple[int, int]]:
    """在 block 中定位 quote，返回 [start, end)；找不到返回 None。"""
    if not quote:
        return None
    idx = block_text.find(quote)
    if idx >= 0:
        return idx, idx + len(quote)
    # 空白折叠弱匹配：逐字符扫描代价高，第一版仅精确 find
    return None
