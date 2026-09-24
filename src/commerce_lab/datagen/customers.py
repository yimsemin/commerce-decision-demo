"""Customer summary derivation.

Per `PROJECT.md`, customer behavior is derived from commerce data rather
than generated as an independent stream. This module aggregates the order
stream into a per-customer summary (first-order date, acquisition channel,
lifetime order count/value) that downstream metrics and tests can use to
observe Scenario 4 (new-vs-returning mix shift).
"""

from __future__ import annotations

import pandas as pd

from .entities import Customer


def derive_customer_summary(orders_df: pd.DataFrame, customers: list[Customer]) -> pd.DataFrame:
    acquisition_channel_by_id = {c.customer_id: c.acquisition_channel for c in customers}

    grouped = (
        orders_df.sort_values("order_date")
        .groupby("customer_id")
        .agg(
            first_order_date=("order_date", "first"),
            total_orders=("order_id", "count"),
            total_net_sales=("net_sales", "sum"),
        )
        .reset_index()
    )
    grouped["acquisition_channel"] = grouped["customer_id"].map(acquisition_channel_by_id)
    grouped["is_returning"] = grouped["total_orders"] > 1
    grouped["total_net_sales"] = grouped["total_net_sales"].round(2)

    return grouped[
        [
            "customer_id",
            "acquisition_channel",
            "first_order_date",
            "total_orders",
            "total_net_sales",
            "is_returning",
        ]
    ]
