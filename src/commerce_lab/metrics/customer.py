"""Customer KPIs: new-vs-returning mix, repeat purchase rate.

Formulas (see docs/kpi_definitions.md):
    new_customer_share(period)  = AVG(is_new_customer) over orders in the period
    repeat_purchase_rate         = COUNT(customers with total_orders > 1)
                                    / COUNT(all customers), as of the latest data
"""

from __future__ import annotations

import pandas as pd

from .periods import PeriodWindow


def new_vs_returning_mix(orders: pd.DataFrame, window: PeriodWindow) -> dict:
    current = orders[window.in_current(orders["order_date"])]
    previous = orders[window.in_previous(orders["order_date"])]

    current_share = round(float(current["is_new_customer"].mean()), 3) if len(current) else None
    previous_share = round(float(previous["is_new_customer"].mean()), 3) if len(previous) else None

    return {
        "current_new_share": current_share,
        "previous_new_share": previous_share,
        "current_returning_share": round(1 - current_share, 3) if current_share is not None else None,
        "previous_returning_share": round(1 - previous_share, 3) if previous_share is not None else None,
    }


def repeat_purchase_rate(customers: pd.DataFrame) -> float:
    if len(customers) == 0:
        return 0.0
    return round(float(customers["is_returning"].mean()), 3)
