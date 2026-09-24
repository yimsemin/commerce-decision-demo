"""Marketing KPIs: spend, attributed revenue, ROAS, CAC.

Formulas (see docs/kpi_definitions.md):
    spend               = SUM(spend)
    attributed_revenue  = SUM(attributed_revenue)
    roas                = attributed_revenue / spend
    cac(channel)        = spend(channel) / new_customers_acquired(channel)

CAC is computed at the marketing-channel grain only (not brand x channel):
the synthetic customer model assigns `acquisition_channel` per customer,
independent of brand, so a brand-level CAC split would not be a defensible
calculation from this data (PROJECT.md §6 explicitly scopes CAC to "where
the synthetic model supports a defensible calculation").
"""

from __future__ import annotations

import pandas as pd

from .periods import PeriodWindow


def _pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def marketing_by_segment(marketing: pd.DataFrame, window: PeriodWindow, group_cols: list[str]) -> pd.DataFrame:
    """Current-vs-previous spend/attributed_revenue/ROAS by an arbitrary
    segment (e.g. ["brand", "marketing_channel"])."""
    current_df = marketing[window.in_current(marketing["date"])]
    previous_df = marketing[window.in_previous(marketing["date"])]

    def _agg(df: pd.DataFrame) -> pd.DataFrame:
        g = df.groupby(group_cols).agg(spend=("spend", "sum"), attributed_revenue=("attributed_revenue", "sum"))
        g["roas"] = g["attributed_revenue"] / g["spend"]
        return g

    current_agg = _agg(current_df).add_prefix("current_")
    previous_agg = _agg(previous_df).add_prefix("previous_")

    combined = pd.concat([current_agg, previous_agg], axis=1).fillna(0.0).reset_index()
    combined["roas_change_pct"] = combined.apply(
        lambda r: _pct_change(r["current_roas"], r["previous_roas"]), axis=1
    )
    combined = combined.sort_values("roas_change_pct", ascending=True, na_position="last").reset_index(drop=True)
    return combined


def cac_by_channel(marketing: pd.DataFrame, customers: pd.DataFrame, window: PeriodWindow) -> pd.DataFrame:
    """Current-period customer acquisition cost per marketing channel."""
    spend_current = (
        marketing[window.in_current(marketing["date"])]
        .groupby("marketing_channel")["spend"]
        .sum()
        .rename("spend")
    )

    new_customers = customers[window.in_current(customers["first_order_date"])]
    acquired_current = new_customers.groupby("acquisition_channel").size().rename("new_customers")

    combined = pd.concat([spend_current, acquired_current], axis=1).fillna(0.0).reset_index()
    combined = combined.rename(columns={"index": "marketing_channel"})
    combined["cac"] = combined.apply(
        lambda r: round(r["spend"] / r["new_customers"], 2) if r["new_customers"] else None, axis=1
    )
    return combined
