from arbor.adapters.outbound.deepseek.reasoner import parse_extract


def test_parse_extract_skips_empty_and_skip_flag():
    assert parse_extract("") is None
    assert parse_extract('{"skip": true, "text": ""}') is None
    assert parse_extract("not json") is None


def test_parse_extract_reads_fact_json():
    parsed = parse_extract('前言 {"kind": "fact", "text": "林夏开始喝美式", "skip": false} 结尾')
    assert parsed == {"kind": "fact", "text": "林夏开始喝美式", "source_text": ""}


def test_parse_extract_defaults_unknown_kind_to_fact():
    parsed = parse_extract('{"kind": "gossip", "text": "林夏住杭州"}')
    assert parsed["kind"] == "fact"
    assert parsed["text"] == "林夏住杭州"
