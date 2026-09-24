"""Independently verifies that each scenario planted by the generator is
observable in the generated output, using plain aggregation rather than
any generator internals.
"""

from __future__ import annotations

from commerce_lab.datagen import config

BASELINE_START = config.BASELINE_START_DATE.isoformat()
BASELINE_END = config.BASELINE_END_DATE.isoformat()
RECENT_START = config.RECENT_START_DATE.isoformat()
RECENT_END = config.END_DATE.isoformat()


def _in_window(series, start, end):
    return (series >= start) & (series <= end)


def test_scenario1_marketing_efficiency_deteriorates_for_targeted_segment(datasets):
    df = datasets["marketing"]
    seg = df[
        (df["brand"] == config.SCENARIO_MKT_BRAND)
        & (df["marketing_channel"] == config.SCENARIO_MKT_CHANNEL)
    ]

    baseline = seg[_in_window(seg["date"], BASELINE_START, BASELINE_END)]
    recent = seg[_in_window(seg["date"], RECENT_START, RECENT_END)]

    baseline_roas = baseline["attributed_revenue"].sum() / baseline["spend"].sum()
    recent_roas = recent["attributed_revenue"].sum() / recent["spend"].sum()

    assert recent_roas < baseline_roas * 0.6, (
        f"expected ROAS to collapse for {config.SCENARIO_MKT_BRAND}/{config.SCENARIO_MKT_CHANNEL}: "
        f"baseline={baseline_roas:.2f} recent={recent_roas:.2f}"
    )

    # Sanity check: an unrelated segment should NOT show the same collapse.
    other = df[
        (df["brand"] != config.SCENARIO_MKT_BRAND)
        | (df["marketing_channel"] != config.SCENARIO_MKT_CHANNEL)
    ]
    other_baseline = other[_in_window(other["date"], BASELINE_START, BASELINE_END)]
    other_recent = other[_in_window(other["date"], RECENT_START, RECENT_END)]
    other_baseline_roas = other_baseline["attributed_revenue"].sum() / other_baseline["spend"].sum()
    other_recent_roas = other_recent["attributed_revenue"].sum() / other_recent["spend"].sum()
    assert other_recent_roas > other_baseline_roas * 0.75


def test_scenario2_rising_demand_and_low_stock_for_targeted_sku(datasets):
    skus_df = datasets["skus"]
    aurora_skus = skus_df[skus_df["brand"] == config.SCENARIO_INV_BRAND]["sku_id"].tolist()
    target_sku = aurora_skus[config.SCENARIO_INV_SKU_INDEX]

    inv = datasets["inventory"]
    seg = inv[inv["sku_id"] == target_sku]

    baseline = seg[_in_window(seg["date"], BASELINE_START, BASELINE_END)]
    recent = seg[_in_window(seg["date"], RECENT_START, RECENT_END)]

    baseline_daily_demand = baseline["units_sold"].mean()
    recent_daily_demand = recent["units_sold"].mean()
    assert recent_daily_demand > baseline_daily_demand * 1.5, (
        f"expected rising demand for {target_sku}: "
        f"baseline={baseline_daily_demand:.1f} recent={recent_daily_demand:.1f}"
    )

    final_row = seg[seg["date"] == RECENT_END].iloc[0]
    recent_avg_daily_demand = recent["units_sold"].mean()
    days_of_cover = final_row["closing_stock"] / max(recent_avg_daily_demand, 1e-6)
    assert days_of_cover < 7, (
        f"expected low days-of-cover for {target_sku} at period end, got {days_of_cover:.1f}"
    )


def test_scenario3_sales_decline_concentrated_in_targeted_segment(datasets):
    df = datasets["orders"]

    seg = df[
        (df["brand"] == config.SCENARIO_DECLINE_BRAND)
        & (df["channel"] == config.SCENARIO_DECLINE_CHANNEL)
    ]
    baseline = seg[_in_window(seg["order_date"], BASELINE_START, BASELINE_END)]
    recent = seg[_in_window(seg["order_date"], RECENT_START, RECENT_END)]

    baseline_sales = baseline["net_sales"].sum()
    recent_sales = recent["net_sales"].sum()
    assert recent_sales < baseline_sales * 0.8, (
        f"expected material decline for {config.SCENARIO_DECLINE_BRAND}/{config.SCENARIO_DECLINE_CHANNEL}: "
        f"baseline={baseline_sales:.0f} recent={recent_sales:.0f}"
    )

    # Overall (all segments) revenue should NOT show the same magnitude of decline.
    all_baseline = df[_in_window(df["order_date"], BASELINE_START, BASELINE_END)]["net_sales"].sum()
    all_recent = df[_in_window(df["order_date"], RECENT_START, RECENT_END)]["net_sales"].sum()
    assert all_recent > all_baseline * 0.85


def test_scenario4_new_vs_returning_mix_shifts(datasets):
    df = datasets["orders"]

    baseline = df[_in_window(df["order_date"], BASELINE_START, BASELINE_END)]
    recent = df[_in_window(df["order_date"], RECENT_START, RECENT_END)]

    baseline_new_share = baseline["is_new_customer"].mean()
    recent_new_share = recent["is_new_customer"].mean()

    assert baseline_new_share > 0.4
    assert recent_new_share < 0.35
    assert recent_new_share < baseline_new_share * 0.7, (
        f"expected new-customer share to fall materially: "
        f"baseline={baseline_new_share:.2f} recent={recent_new_share:.2f}"
    )
