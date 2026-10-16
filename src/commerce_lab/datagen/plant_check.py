"""Checks that the four planted business scenarios came out clearly
detectable in a generated dataset.

With a random seed the planted effects ride on top of sampling noise: a
planted decline can land just short of the "high" threshold, or noise can
push an unrelated segment past it. `generate_all` uses this check to
redraw (deterministically, from the same seed) until the story holds, so
every seed yields exactly the four planted issues at high severity.

Planted effects must clear the default lens high-severity thresholds
(sales -35%, marketing -40%, new share -50%, stock-out < 3 days) with a
margin; unplanted segments must stay on the right side of them. Lower
severities from sampling noise are fine -- real data has those too.
"""

from __future__ import annotations

import pandas as pd

from ..metrics.customer import new_vs_returning_mix
from ..metrics.inventory import inventory_risk_by_sku
from ..metrics.marketing import marketing_by_segment
from ..metrics.periods import compute_period_window
from ..metrics.sales import sales_by_segment
from . import config

PLANTED_SALES_MAX_PCT = -40.0  # planted segment must fall at least this much
PLANTED_MARKETING_MAX_ROAS_PCT = -45.0
PLANTED_NEW_SHARE_MAX_PCT = -55.0
PLANTED_STOCKOUT_MAX_DAYS = 2.5
OTHER_SALES_MIN_PCT = -35.0  # unplanted segments must stay above the high thresholds
OTHER_ROAS_MIN_PCT = -40.0
OTHER_SKU_MIN_DAYS = 3.0  # = lens high_severity_days
MIN_SALES_BASE = 500.0
MIN_MARKETING_SPEND = 1000.0


def planted_scenario_failures(datasets: dict[str, pd.DataFrame]) -> list[str]:
    """Human-readable reasons the scenarios are not cleanly planted; empty
    when the dataset is good."""
    window = compute_period_window(config.END_DATE, window_days=config.RECENT_WINDOW_DAYS)
    failures: list[str] = []

    sales = sales_by_segment(datasets["orders"], window, ["brand", "channel"])
    for _, r in sales[sales["previous_net_revenue"] >= MIN_SALES_BASE].iterrows():
        planted = r["brand"] == config.SCENARIO_DECLINE_BRAND and r["channel"] == config.SCENARIO_DECLINE_CHANNEL
        pct = r["pct_change"]
        if planted and not (pct is not None and pct <= PLANTED_SALES_MAX_PCT):
            failures.append(f"sales decline too shallow ({pct})")
        if not planted and pct is not None and pct <= OTHER_SALES_MIN_PCT:
            failures.append(f"unplanted sales decline {r['brand']}/{r['channel']} ({pct})")

    mkt = marketing_by_segment(datasets["marketing"], window, ["brand", "marketing_channel"])
    for _, r in mkt[mkt["previous_spend"] >= MIN_MARKETING_SPEND].iterrows():
        planted = r["brand"] == config.SCENARIO_MKT_BRAND and r["marketing_channel"] == config.SCENARIO_MKT_CHANNEL
        pct = r["roas_change_pct"]
        if planted and not (pct is not None and pct <= PLANTED_MARKETING_MAX_ROAS_PCT):
            failures.append(f"ROAS decline too shallow ({pct})")
        if not planted and pct is not None and pct <= OTHER_ROAS_MIN_PCT:
            failures.append(f"unplanted ROAS decline {r['brand']}/{r['marketing_channel']} ({pct})")

    mix = new_vs_returning_mix(datasets["orders"], window)
    cur, prev = mix["current_new_share"], mix["previous_new_share"]
    if not prev or cur is None or (cur - prev) / prev * 100 > PLANTED_NEW_SHARE_MAX_PCT:
        failures.append(f"new-customer share drop too shallow ({prev} -> {cur})")

    risk = inventory_risk_by_sku(datasets["inventory"], as_of=config.END_DATE)
    planted_sku = datasets["skus"][datasets["skus"]["brand"] == config.SCENARIO_INV_BRAND]["sku_id"].iloc[config.SCENARIO_INV_SKU_INDEX]
    for _, r in risk.iterrows():
        days = r["days_of_cover"]
        if r["sku_id"] == planted_sku:
            if days is None or pd.isna(days) or days >= PLANTED_STOCKOUT_MAX_DAYS:
                failures.append(f"planted SKU {planted_sku} not near stock-out (cover {days})")
        elif days is not None and not pd.isna(days) and days < OTHER_SKU_MIN_DAYS:
            failures.append(f"unplanted stock-out risk {r['sku_id']} ({days})")
    return failures
