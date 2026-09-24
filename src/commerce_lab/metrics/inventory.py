"""Inventory KPIs: on-hand stock, sales velocity, days of cover, risk flags.

Formulas (see docs/kpi_definitions.md):
    on_hand           = closing_stock on the latest available date
    velocity          = AVG(units_sold) over the trailing `velocity_window_days`
                         days ending on the latest available date
    days_of_cover     = on_hand / velocity   (None if velocity is 0 and on_hand is 0)
    stockout_risk     = days_of_cover is not None and days_of_cover < STOCKOUT_THRESHOLD_DAYS
    excess_risk       = on_hand > 0 and (velocity == 0 or days_of_cover > EXCESS_THRESHOLD_DAYS)

Thresholds are demo defaults documented alongside the formulas, not
tuned against real retail benchmarks.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

STOCKOUT_THRESHOLD_DAYS = 7
EXCESS_THRESHOLD_DAYS = 60
VELOCITY_WINDOW_DAYS = 14


def inventory_risk_by_sku(
    inventory: pd.DataFrame,
    as_of: dt.date,
    velocity_window_days: int = VELOCITY_WINDOW_DAYS,
    stockout_threshold_days: float = STOCKOUT_THRESHOLD_DAYS,
    excess_threshold_days: float = EXCESS_THRESHOLD_DAYS,
) -> pd.DataFrame:
    velocity_start = (as_of - dt.timedelta(days=velocity_window_days - 1)).isoformat()
    as_of_str = as_of.isoformat()

    on_hand = inventory[inventory["date"] == as_of_str][["sku_id", "brand", "closing_stock"]].rename(
        columns={"closing_stock": "on_hand"}
    )

    velocity_window = inventory[(inventory["date"] >= velocity_start) & (inventory["date"] <= as_of_str)]
    velocity = velocity_window.groupby("sku_id")["units_sold"].mean().rename("velocity")

    combined = on_hand.merge(velocity, on="sku_id", how="left").fillna({"velocity": 0.0})
    combined["velocity"] = combined["velocity"].round(2)
    combined["days_of_cover"] = combined.apply(
        lambda r: round(r["on_hand"] / r["velocity"], 1) if r["velocity"] > 0 else None, axis=1
    )
    combined["stockout_risk"] = combined["days_of_cover"].apply(
        lambda d: d is not None and d < stockout_threshold_days
    )
    combined["excess_risk"] = combined.apply(
        lambda r: r["on_hand"] > 0
        and (r["velocity"] == 0 or (r["days_of_cover"] is not None and r["days_of_cover"] > excess_threshold_days)),
        axis=1,
    )
    return combined.sort_values("days_of_cover", na_position="first").reset_index(drop=True)
