from __future__ import annotations

from commerce_lab.pipeline.parity import compare


def test_compare_accepts_one_rounding_step_and_rejects_more():
    assert compare({"pct_change": -42.3}, {"pct_change": -42.2}) == []
    assert compare({"pct_change": -42.3}, {"pct_change": -42.5}) != []


def test_compare_is_strict_for_unrounded_values_and_flags():
    assert compare({"current_net_revenue": 100.0}, {"current_net_revenue": 100.0000001}) == []
    assert compare({"current_net_revenue": 100.0}, {"current_net_revenue": 100.5}) != []
    assert compare({"stockout_risk": True}, {"stockout_risk": False}) != []


def test_compare_flags_missing_keys_row_counts_and_none_mismatch():
    assert compare({"a": 1}, {"b": 1}) != []
    assert compare([{"a": 1}], [{"a": 1}, {"a": 2}]) != []
    assert compare({"cac": None}, {"cac": 1.0}) != []
    assert compare({"cac": None}, {"cac": None}) == []


def test_prose_is_not_compared_but_numbers_are():
    from commerce_lab.pipeline.parity import _without_prose

    a = [{"supporting_kpi": {"x": 1}, "likely_drivers": ["moved to 4303"]}]
    b = [{"supporting_kpi": {"x": 1}, "likely_drivers": ["moved to 4304"]}]
    assert compare(_without_prose(a), _without_prose(b)) == []
    b[0]["supporting_kpi"]["x"] = 2
    assert compare(_without_prose(a), _without_prose(b)) != []
