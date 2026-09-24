"""Confirms the M3 KPI layer actually surfaces the four scenarios planted
in M1 (tests/test_datagen/test_scenarios.py verifies they exist in the raw
data; this verifies the metrics layer built on top of that data exposes
them as KPI movements an issue-detection rule (M4) could act on).
"""

from __future__ import annotations

from commerce_lab.datagen import config
from commerce_lab.metrics.customer import new_vs_returning_mix
from commerce_lab.metrics.inventory import inventory_risk_by_sku
from commerce_lab.metrics.marketing import marketing_by_segment
from commerce_lab.metrics.sales import sales_by_segment


def test_marketing_kpi_shows_roas_collapse(datasets, window):
    result = marketing_by_segment(datasets["marketing"], window, ["brand", "marketing_channel"])
    row = result[
        (result["brand"] == config.SCENARIO_MKT_BRAND)
        & (result["marketing_channel"] == config.SCENARIO_MKT_CHANNEL)
    ].iloc[0]
    assert row["current_roas"] < row["previous_roas"] * 0.6


def test_inventory_kpi_flags_stockout_risk_for_targeted_sku(datasets, window):
    skus_df = datasets["skus"]
    aurora_skus = skus_df[skus_df["brand"] == config.SCENARIO_INV_BRAND]["sku_id"].tolist()
    target_sku = aurora_skus[config.SCENARIO_INV_SKU_INDEX]

    result = inventory_risk_by_sku(datasets["inventory"], as_of=window.current_end)
    row = result[result["sku_id"] == target_sku].iloc[0]
    assert bool(row["stockout_risk"]) is True


def test_sales_kpi_shows_concentrated_decline(datasets, window):
    result = sales_by_segment(datasets["orders"], window, ["brand", "channel"])
    row = result[
        (result["brand"] == config.SCENARIO_DECLINE_BRAND) & (result["channel"] == config.SCENARIO_DECLINE_CHANNEL)
    ].iloc[0]
    assert row["pct_change"] < -20

    # This should be the largest (or near-largest) negative mover, i.e.
    # genuinely "material" and identifiable via ranking, not just present.
    worst_decline = result.sort_values("change").iloc[0]
    assert worst_decline["brand"] == config.SCENARIO_DECLINE_BRAND
    assert worst_decline["channel"] == config.SCENARIO_DECLINE_CHANNEL


def test_customer_kpi_shows_new_share_drop(datasets, window):
    mix = new_vs_returning_mix(datasets["orders"], window)
    assert mix["current_new_share"] < mix["previous_new_share"] * 0.7
