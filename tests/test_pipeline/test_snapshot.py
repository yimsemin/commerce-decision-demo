from __future__ import annotations

import datetime as dt
import json

from commerce_lab.pipeline.snapshot import build_snapshot, build_snapshot_history, default_history_anchors, write_snapshot


def test_snapshot_has_expected_top_level_shape(datasets):
    snapshot = build_snapshot(datasets)

    assert snapshot["schema_version"] == 2
    assert snapshot["as_of_date"] == "2026-09-21"
    assert set(snapshot["period"].keys()) == {
        "current_start",
        "current_end",
        "previous_start",
        "previous_end",
    }
    assert set(snapshot.keys()) >= {
        "sales",
        "marketing",
        "customer",
        "inventory",
        "decisions",
        "gemini_summary",
        "lenses",
        "params",
    }
    assert snapshot["gemini_summary"] is None


def test_snapshot_is_json_serializable_with_no_nan_or_numpy_types(datasets):
    snapshot = build_snapshot(datasets)
    text = json.dumps(snapshot)  # must not raise (numpy/NaN would break this)
    reloaded = json.loads(text)
    assert reloaded["schema_version"] == 2


def test_snapshot_decisions_include_all_four_planted_scenarios(datasets):
    snapshot = build_snapshot(datasets)
    issue_types = {d["issue_type"] for d in snapshot["decisions"]}
    assert issue_types >= {
        "marketing_efficiency_decline",
        "stockout_risk",
        "sales_decline",
        "customer_mix_shift",
    }
    severities_of_high = {d["issue_type"] for d in snapshot["decisions"] if d["severity"] == "high"}
    assert severities_of_high == {
        "marketing_efficiency_decline",
        "stockout_risk",
        "sales_decline",
        "customer_mix_shift",
    }


def test_write_snapshot_round_trips(tmp_path, datasets):
    snapshot = build_snapshot(datasets)
    path = tmp_path / "nested" / "app_snapshot.json"
    write_snapshot(snapshot, path)

    assert path.exists()
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["as_of_date"] == snapshot["as_of_date"]


def test_build_snapshot_with_explicit_as_of(datasets):
    as_of = dt.date(2026, 8, 22)
    snapshot = build_snapshot(datasets, as_of=as_of)
    assert snapshot["as_of_date"] == "2026-08-22"
    assert snapshot["period"]["current_end"] == "2026-08-22"


def test_default_history_anchors_are_ascending_and_bounded(datasets):
    anchors = default_history_anchors(datasets)
    assert anchors == sorted(anchors)
    assert anchors[-1].isoformat() == "2026-09-21"
    assert len(anchors) == 61  # every day with a full 60-day history: day 60..120
    assert all((b - a).days == 1 for a, b in zip(anchors, anchors[1:]))
    # every anchor must have a full 60 days of history behind it
    for a in anchors:
        assert (a - dt.date(2026, 5, 25)).days >= 59


def test_build_snapshot_history_shape_and_latest_entry(datasets):
    history = build_snapshot_history(datasets)

    assert history["schema_version"] == 2
    assert history["available_as_of_dates"] == sorted(history["available_as_of_dates"])
    assert history["latest_as_of_date"] == history["available_as_of_dates"][-1]
    assert history["latest_as_of_date"] == "2026-09-21"
    assert set(history["snapshots"].keys()) == set(history["available_as_of_dates"])

    latest = history["snapshots"][history["latest_as_of_date"]]
    issue_types = {d["issue_type"] for d in latest["decisions"]}
    assert issue_types >= {
        "marketing_efficiency_decline",
        "stockout_risk",
        "sales_decline",
        "customer_mix_shift",
    }
    assert latest["gemini_summary"] is None

    text = json.dumps(history)  # must stay JSON-serializable (no NaN/numpy leaking through)
    assert json.loads(text)["latest_as_of_date"] == history["latest_as_of_date"]


def test_history_records_the_data_seed_and_where_each_lens_was_computed(datasets):
    history = build_snapshot_history(datasets, data_seed=99)
    assert history["data_seed"] == 99
    latest = history["snapshots"][history["latest_as_of_date"]]
    assert latest["metrics_source"] == {lens: "pandas" for lens in latest["lenses"]}
