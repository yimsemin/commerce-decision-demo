"""Sales KPIs: net revenue, orders, units sold, average order value.

Formulas (see docs/kpi_definitions.md for the canonical documentation):
    net_revenue  = SUM(net_sales)
    orders       = COUNT(DISTINCT order_id)
    units_sold   = SUM(quantity)
    aov          = net_revenue / orders
"""

from __future__ import annotations

import pandas as pd

from .periods import PeriodWindow


def _aggregate(orders: pd.DataFrame) -> dict:
    orders_count = orders["order_id"].nunique()
    net_revenue = round(float(orders["net_sales"].sum()), 2)
    units_sold = int(orders["quantity"].sum())
    aov = round(net_revenue / orders_count, 2) if orders_count else 0.0
    return {
        "net_revenue": net_revenue,
        "orders": orders_count,
        "units_sold": units_sold,
        "aov": aov,
    }


def _pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def sales_summary(orders: pd.DataFrame, window: PeriodWindow) -> dict:
    """Overall current-vs-previous period sales KPIs."""
    current = _aggregate(orders[window.in_current(orders["order_date"])])
    previous = _aggregate(orders[window.in_previous(orders["order_date"])])
    return {
        "current": current,
        "previous": previous,
        "pct_change": {
            key: _pct_change(current[key], previous[key]) for key in current
        },
    }


def sales_by_segment(orders: pd.DataFrame, window: PeriodWindow, group_cols: list[str]) -> pd.DataFrame:
    """Current-vs-previous net revenue by an arbitrary segment (e.g.
    ["brand", "channel"] or ["sku_id"]), for contribution analysis.
    Sorted by absolute revenue change, largest swings first."""
    current_df = orders[window.in_current(orders["order_date"])]
    previous_df = orders[window.in_previous(orders["order_date"])]

    current_agg = current_df.groupby(group_cols)["net_sales"].sum().rename("current_net_revenue")
    previous_agg = previous_df.groupby(group_cols)["net_sales"].sum().rename("previous_net_revenue")

    combined = pd.concat([current_agg, previous_agg], axis=1).fillna(0.0).reset_index()
    combined["change"] = combined["current_net_revenue"] - combined["previous_net_revenue"]
    combined["pct_change"] = combined.apply(
        lambda r: _pct_change(r["current_net_revenue"], r["previous_net_revenue"]), axis=1
    )
    combined = combined.sort_values("change", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)
    return combined
