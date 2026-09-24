"""Proves the extension contract end to end with a throwaway lens that
adds a NEW data source ("returns"), a threshold parameter, a detection
rule and prose -- without touching any core module."""

from __future__ import annotations

import sys
import types

import pandas as pd
import pytest

from commerce_lab.app.i18n import localize_decision, t
from commerce_lab.datagen.generator import generate_all
from commerce_lab.decisions.models import DecisionItem
from commerce_lab.lenses.base import DataSource, Lens, Param
from commerce_lab.lenses.registry import (
    BUILTIN_LENS_NAMES,
    data_sources,
    load_lens,
    load_lenses,
    register_lens,
    resolve_params,
    run_detection,
    unregister_lens,
)
from commerce_lab.lenses.settings import LabSettings, load_settings
from commerce_lab.pipeline.bigquery import raw_table_ddl
from commerce_lab.pipeline.snapshot import build_snapshot


def _generate_returns(rng, datasets):
    return pd.DataFrame([{"order_id": oid, "returned": rng.random() < 0.2} for oid in datasets["orders"]["order_id"]])


RETURNS = DataSource(
    name="returns",
    columns={"order_id": "STRING", "returned": "BOOL"},
    generate=_generate_returns,
)


def _compute(datasets, window, params):
    return {"return_rate": round(float(datasets["returns"]["returned"].mean()), 3)}


def _detect(section, params):
    if section["return_rate"] < params["max_return_rate"]:
        return []
    return [
        DecisionItem(
            issue_type="high_return_rate",
            headline="Return rate is high",
            severity="medium",
            supporting_kpi={"return_rate": section["return_rate"], "estimated_revenue_impact": None},
            likely_drivers=["Returns exceed the tolerated rate."],
            possible_action="Review product quality.",
            kpi_to_monitor="return_rate",
        )
    ]


def _localize(affected, kpi, lang):
    return {"headline": f"반품률 높음 ({kpi['return_rate']:.0%})"} if lang == "ko" else {}


RETURNS_LENS = Lens(
    id="returns",
    title={"ko": "Returns", "en": "Returns"},
    compute=_compute,
    detect=_detect,
    params=(Param("max_return_rate", 0.1, {"en": "Max return rate", "ko": "최대 반품률"}, 0.0, 1.0, 0.01),),
    data_sources=(RETURNS,),
    localizers={"high_return_rate": _localize},
    strings={"returns.header": {"ko": "반품", "en": "Returns"}},
)


@pytest.fixture
def returns_lens():
    register_lens(RETURNS_LENS)
    yield RETURNS_LENS
    unregister_lens("returns")


@pytest.fixture
def core_and_returns(returns_lens):
    return [*load_lenses(BUILTIN_LENS_NAMES), returns_lens]


def test_new_data_source_is_generated_without_changing_core_datasets(core_and_returns):
    baseline = generate_all()
    extended = generate_all(data_sources=data_sources(core_and_returns))

    assert set(extended) == set(baseline) | {"returns"}
    for name, df in baseline.items():
        pd.testing.assert_frame_equal(df, extended[name])
    assert list(extended["returns"].columns) == ["order_id", "returned"]
    pd.testing.assert_frame_equal(extended["returns"], generate_all(data_sources=data_sources(core_and_returns))["returns"])


def test_new_lens_flows_into_snapshot_with_its_own_section_and_lens_tag(core_and_returns):
    datasets = generate_all(data_sources=data_sources(core_and_returns))
    snapshot = build_snapshot(datasets, lenses=core_and_returns, settings=LabSettings())

    assert snapshot["lenses"] == [*BUILTIN_LENS_NAMES, "returns"]
    assert "return_rate" in snapshot["returns"]
    assert snapshot["params"]["returns"] == {"max_return_rate": 0.1}
    tagged = [d for d in snapshot["decisions"] if d["issue_type"] == "high_return_rate"]
    assert len(tagged) == 1 and tagged[0]["lens"] == "returns"
    assert all(d["lens"] for d in snapshot["decisions"])  # every item names its lens


def test_config_overrides_change_what_is_detected(core_and_returns):
    datasets = generate_all(data_sources=data_sources(core_and_returns))
    lenient = LabSettings(params={"returns": {"max_return_rate": 0.9}})
    snapshot = build_snapshot(datasets, lenses=core_and_returns, settings=lenient)
    assert not any(d["issue_type"] == "high_return_rate" for d in snapshot["decisions"])


def test_thresholds_can_be_reevaluated_from_the_snapshot_alone(core_and_returns):
    """What the app does when a viewer changes a threshold: rerun the rules
    on the stored sections, no raw data involved."""
    datasets = generate_all(data_sources=data_sources(core_and_returns))
    snapshot = build_snapshot(datasets, lenses=core_and_returns, settings=LabSettings())

    def marketing_issues(**overrides):
        params = {**snapshot["params"], "marketing": {**snapshot["params"]["marketing"], **overrides}}
        return [d for d in run_detection(core_and_returns, snapshot, params) if d.issue_type == "marketing_efficiency_decline"]

    strict = marketing_issues(decline_medium_pct=-1.0)
    relaxed = marketing_issues(decline_medium_pct=-90.0, decline_high_pct=-90.0)
    assert len(strict) > len(relaxed)


def test_default_snapshot_still_flags_the_four_planted_scenarios(datasets):
    snapshot = build_snapshot(datasets, settings=LabSettings())
    kinds = {d["issue_type"] for d in snapshot["decisions"]}
    assert {"marketing_efficiency_decline", "stockout_risk", "sales_decline", "customer_mix_shift"} <= kinds


def test_lens_prose_and_strings_are_registered(returns_lens):
    decision = {"issue_type": "high_return_rate", "supporting_kpi": {"return_rate": 0.2}, "affected": {}, "headline": "x"}
    assert localize_decision(decision, "ko")["headline"] == "반품률 높음 (20%)"
    assert t("returns.header", "ko") == "반품"


def test_unknown_parameter_in_config_fails_loudly():
    with pytest.raises(ValueError, match="Unknown parameter"):
        resolve_params(load_lens("sales"), {"decline_hgh_pct": -10})


def test_lens_can_be_loaded_from_a_dotted_module_path():
    module = types.ModuleType("acme_pkg.returns")
    module.LENS = RETURNS_LENS
    sys.modules["acme_pkg"] = types.ModuleType("acme_pkg")
    sys.modules["acme_pkg.returns"] = module
    try:
        assert load_lens("acme_pkg.returns").id == "returns"
    finally:
        del sys.modules["acme_pkg"], sys.modules["acme_pkg.returns"]
        unregister_lens("returns")


def test_module_without_lens_is_rejected():
    sys.modules["acme_pkg"] = types.ModuleType("acme_pkg")
    sys.modules["acme_pkg.plain"] = types.ModuleType("acme_pkg.plain")
    try:
        with pytest.raises(ValueError, match="LENS"):
            load_lens("acme_pkg.plain")
    finally:
        del sys.modules["acme_pkg"], sys.modules["acme_pkg.plain"]


def test_raw_table_ddl_for_a_lens_data_source():
    assert raw_table_ddl("raw", RETURNS) == (
        "CREATE TABLE IF NOT EXISTS raw.returns (\n    order_id STRING,\n    returned BOOL\n);"
    )


def test_settings_file_selects_lenses_and_overrides_params(tmp_path):
    path = tmp_path / "lab.toml"
    path.write_text(
        '[lenses]\nenabled = ["sales", "inventory"]\n\n[params.inventory]\nstockout_days = 10\n',
        encoding="utf-8",
    )
    settings = load_settings(path)
    assert settings.enabled == ("sales", "inventory")
    assert settings.params == {"inventory": {"stockout_days": 10}}
    assert load_settings(tmp_path / "missing.toml") == LabSettings()


def test_shipped_config_enables_the_builtin_lenses_with_default_params():
    settings = load_settings()
    assert settings.enabled == BUILTIN_LENS_NAMES
    assert settings.params == {}
