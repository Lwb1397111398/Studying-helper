from app.modules.learning_assets.evidence_validator import (
    find_quote_offsets,
    validate_evidence_ref,
)


def test_quote_must_match_block_slice():
    block_text = "定义：光合作用是植物利用光能的过程。"
    # 定位「光合」
    start = block_text.index("光合")
    end = start + len("光合")
    ok = validate_evidence_ref(
        block_text=block_text,
        start_offset=start,
        end_offset=end,
        quote="光合",
        offset_encoding="unicode_code_point",
    )
    assert ok.valid is True

    bad = validate_evidence_ref(
        block_text=block_text,
        start_offset=0,
        end_offset=2,
        quote="错",
    )
    assert bad.valid is False
    assert bad.code == "offset_mismatch"


def test_half_open_interval():
    text = "abcdef"
    r = validate_evidence_ref(
        block_text=text, start_offset=1, end_offset=4, quote="bcd"
    )
    assert r.valid is True


def test_find_quote_offsets():
    text = "前置 目标句子 后置"
    offs = find_quote_offsets(text, "目标句子")
    assert offs is not None
    s, e = offs
    assert text[s:e] == "目标句子"
