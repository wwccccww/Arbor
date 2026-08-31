from __future__ import annotations

from arbor.adapters.outbound.benchmarks.bfcl_loader import (
    _call_matches_ground_truth_item,
    _missing_arg_allowed,
    score_against_ground_truth,
)
from arbor.adapters.outbound.benchmarks.multihop_loader import answer_em, compact_retrieve_query


def test_missing_arg_allowed_accepts_empty_or_zero_options():
    assert _missing_arg_allowed(["", 0]) is True
    assert _missing_arg_allowed([4, 5]) is False


def test_simple_2_omitted_optional_z_matches_ground_truth():
    gt_item = {
        "math.hypot": {
            "x": [4],
            "y": [5],
            "z": ["", 0],
        }
    }
    actual = {"name": "math.hypot", "arguments": {"x": 4, "y": 5}}
    fn_ok, arg_ok = _call_matches_ground_truth_item(actual, gt_item)
    assert fn_ok is True
    assert arg_ok is True


def test_score_against_ground_truth_simple_2():
    ground_truth = [
        {
            "math.hypot": {
                "x": [4],
                "y": [5],
                "z": ["", 0],
            }
        }
    ]
    actual_calls = [{"name": "math.hypot", "arguments": {"x": 4, "y": 5}}]
    ok, scores = score_against_ground_truth(
        actual_calls=actual_calls,
        ground_truth=ground_truth,
        expect_no_tool=False,
    )
    assert ok is True
    assert scores["argument_match"] == 1.0


def test_multihop_answer_em_substring_match():
    assert answer_em("Paris", "The answer is Paris.") == 1.0
    assert answer_em("1998", "1998") == 1.0


def test_compact_retrieve_query_prefers_entities():
    question = "When did 'Acme Corp' acquire Beta Labs in Europe?"
    query = compact_retrieve_query(question)
    assert "Acme Corp" in query
    assert "Beta Labs" in query
