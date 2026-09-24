"""Runs the actual Streamlit script in-process (streamlit.testing.v1) so
the app is genuinely executed, not just imported. Verifies PROJECT.md
§13's "application starts locally" without needing a browser.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

from commerce_lab.pipeline.snapshot import build_snapshot_history, write_snapshot

MAIN_PATH = str(Path(__file__).resolve().parents[2] / "src" / "commerce_lab" / "app" / "main.py")


def test_app_runs_with_no_exceptions_and_renders_all_tabs(tmp_path, datasets, monkeypatch):
    snapshot_path = tmp_path / "app_snapshot.json"
    write_snapshot(build_snapshot_history(datasets), snapshot_path)
    monkeypatch.setenv("SNAPSHOT_LOCAL_PATH", str(snapshot_path))
    monkeypatch.delenv("SNAPSHOT_SOURCE", raising=False)

    st.cache_data.clear()  # @st.cache_data on _get_history() persists across AppTest runs in-process
    at = AppTest.from_file(MAIN_PATH)
    at.session_state["lang"] = "en"
    at.run(timeout=30)

    assert not at.exception
    assert len(at.tabs) == 6
    assert at.title[0].value == "Commerce Decision Lab"
    # the top-of-page KPI metrics, plus one "Estimated revenue impact" metric
    # per decision card that has a computable dollar estimate
    overview_metric_labels = {m.label for m in at.tabs[0].metric}
    assert {"Net revenue", "Orders", "AOV", "New-customer share"} <= overview_metric_labels
    assert overview_metric_labels <= {"Net revenue", "Orders", "AOV", "New-customer share", "Estimated revenue impact"}


def test_app_period_selector_switches_language(tmp_path, datasets, monkeypatch):
    snapshot_path = tmp_path / "app_snapshot.json"
    write_snapshot(build_snapshot_history(datasets), snapshot_path)
    monkeypatch.setenv("SNAPSHOT_LOCAL_PATH", str(snapshot_path))
    monkeypatch.delenv("SNAPSHOT_SOURCE", raising=False)

    st.cache_data.clear()
    at = AppTest.from_file(MAIN_PATH)
    at.session_state["lang"] = "ko"
    at.run(timeout=30)

    assert not at.exception
    overview_metric_labels = {m.label for m in at.tabs[0].metric}
    assert {"순매출", "주문 수", "평균 주문 금액", "신규 고객 비중"} <= overview_metric_labels
    assert overview_metric_labels <= {"순매출", "주문 수", "평균 주문 금액", "신규 고객 비중", "예상 매출 영향"}


def test_app_shows_clear_error_when_snapshot_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("SNAPSHOT_LOCAL_PATH", str(tmp_path / "does_not_exist.json"))
    monkeypatch.delenv("SNAPSHOT_SOURCE", raising=False)

    st.cache_data.clear()
    at = AppTest.from_file(MAIN_PATH)
    at.run(timeout=30)

    assert at.exception
    assert "commerce_lab.pipeline.refresh" in at.exception[0].value


def _run_app(tmp_path, datasets, monkeypatch, lang="en"):
    snapshot_path = tmp_path / "app_snapshot.json"
    write_snapshot(build_snapshot_history(datasets), snapshot_path)
    monkeypatch.setenv("SNAPSHOT_LOCAL_PATH", str(snapshot_path))
    monkeypatch.delenv("SNAPSHOT_SOURCE", raising=False)
    st.cache_data.clear()
    at = AppTest.from_file(MAIN_PATH)
    at.session_state["lang"] = lang
    at.run(timeout=30)
    assert not at.exception
    return at


def _banner_shown(at) -> bool:
    return any(b.key == "params.reset_main" for b in at.button)


def _headlines(at) -> list[str]:
    """Headline line of every decision card in the Decisions tab."""
    return [m.value.split("**")[1] for m in at.tabs[-1].markdown if m.value.startswith("**")]


def test_changing_a_threshold_reevaluates_issues_in_the_session(tmp_path, datasets, monkeypatch):
    at = _run_app(tmp_path, datasets, monkeypatch)
    baseline = _headlines(at)
    assert any(h.startswith("Excess inventory risk") for h in baseline)
    assert not _banner_shown(at)  # no "adjusted thresholds" banner until something changes

    # Raise the excess-stock cutoff to a year of cover: no SKU is "excess" any more.
    excess = next(n for n in at.sidebar.slider if n.key == "param.inventory.excess_days")
    excess.set_value(365.0).run(timeout=30)

    assert not at.exception
    assert _banner_shown(at)  # visible marker with a reset button
    assert any("60 → 365" in m.value for m in at.markdown)  # ...naming what changed
    assert not any(h.startswith("Excess inventory risk") for h in _headlines(at))
    assert any(h.startswith("Stock-out risk") for h in _headlines(at))  # the planted stock-out is unaffected


def test_decisions_tab_filters_by_lens_and_severity(tmp_path, datasets, monkeypatch):
    at = _run_app(tmp_path, datasets, monkeypatch)
    baseline = _headlines(at)

    lens_filter = next(m for m in at.tabs[-1].multiselect if m.label == "Lens")
    lens_filter.set_value(["inventory"]).run(timeout=30)
    assert not at.exception
    filtered = _headlines(at)
    assert filtered and len(filtered) < len(baseline)
    assert all("SKU" in h for h in filtered)  # only inventory issues remain


def test_app_still_renders_a_pre_lens_v1_snapshot(tmp_path, datasets, monkeypatch):
    """A snapshot written before lenses existed (no `lenses`/`params`, no `lens` tag on
    decisions) must keep working while the app is redeployed ahead of the next refresh."""
    history = build_snapshot_history(datasets)
    for snap in history["snapshots"].values():
        for key in ("lenses", "params"):
            snap.pop(key)
        snap["schema_version"] = 1
        for d in snap["decisions"]:
            d.pop("lens")
    write_snapshot(history, tmp_path / "app_snapshot.json")
    monkeypatch.setenv("SNAPSHOT_LOCAL_PATH", str(tmp_path / "app_snapshot.json"))
    monkeypatch.delenv("SNAPSHOT_SOURCE", raising=False)
    st.cache_data.clear()
    at = AppTest.from_file(MAIN_PATH)
    at.session_state["lang"] = "en"
    at.run(timeout=30)
    assert not at.exception
    assert len(at.tabs) == 6

    next(m for m in at.tabs[-1].multiselect if m.label == "Lens").set_value(["inventory"]).run(timeout=30)
    assert not at.exception
    assert _headlines(at) and all("SKU" in h for h in _headlines(at))


def test_admin_config_subset_and_param_defaults_show_up_in_the_app_in_both_languages(tmp_path, datasets, monkeypatch):
    """What an operator gets from config/lab.toml: only the enabled lenses become tabs, and
    the sliders start at the configured value (not the code default), in ko and en."""
    from commerce_lab.lenses.settings import LabSettings

    settings = LabSettings(enabled=("sales", "inventory"), params={"inventory": {"stockout_days": 10}})
    write_snapshot(build_snapshot_history(datasets, settings=settings, lenses=None), tmp_path / "app_snapshot.json")
    monkeypatch.setenv("SNAPSHOT_LOCAL_PATH", str(tmp_path / "app_snapshot.json"))
    monkeypatch.delenv("SNAPSHOT_SOURCE", raising=False)

    for lang, expected_tabs in (("ko", ["개요", "성과", "재고", "의사결정"]), ("en", ["Overview", "Performance", "Inventory", "Decisions"])):
        st.cache_data.clear()
        at = AppTest.from_file(MAIN_PATH)
        at.session_state["lang"] = lang
        at.run(timeout=30)
        assert not at.exception
        assert [tab.label for tab in at.tabs] == expected_tabs
        stockout = next(s for s in at.sidebar.slider if s.key == "param.inventory.stockout_days")
        assert stockout.value == 10
        assert not any(s.key.startswith("param.marketing") for s in at.sidebar.slider)
        assert not _banner_shown(at)  # configured value is the baseline, not an "adjustment"
