"""Inventory ledger generation.

Built from the already-generated order stream so demand is internally
consistent: `units_sold` per SKU/day comes directly from aggregated orders.
Plants Scenario 2 (rising demand + low remaining stock): receipts for the
targeted Aurora SKU are deliberately insufficient in the recent window while
demand for that SKU is elevated (via `orders.py`'s SKU weighting), so closing
stock and days-of-cover fall.

Every other SKU uses a reactive, periodic-review replenishment policy
(order up to roughly the demand actually realized in the prior interval)
so it stays near a stable, non-alarming days-of-cover for the whole
window -- deliberately avoiding both compounding overstock and spurious
stockouts, so the M4 inventory-risk rules fire on the planted scenario
rather than on generator noise.
"""

from __future__ import annotations

import random

import pandas as pd

from . import config
from .dates import daterange, is_recent
from .entities import Sku

NORMAL_RECEIPT_INTERVAL_DAYS = 7  # restock cadence for non-scenario SKUs
NORMAL_STARTING_DAYS_OF_COVER_RANGE = (20.0, 35.0)  # opening stock, expressed as days of baseline demand
NORMAL_REPLENISH_FACTOR_RANGE = (0.95, 1.05)  # symmetric around 1.0: avoids compounding drift over ~17 cycles
FALLBACK_DAILY_DEMAND = 0.5  # used only if a SKU had zero baseline-window orders


def _baseline_daily_demand_by_sku(orders_df: pd.DataFrame) -> dict[str, float]:
    baseline = orders_df[
        (orders_df["order_date"] >= config.BASELINE_START_DATE.isoformat())
        & (orders_df["order_date"] <= config.BASELINE_END_DATE.isoformat())
    ]
    totals = baseline.groupby("sku_id")["quantity"].sum()
    return (totals / config.BASELINE_WINDOW_DAYS).to_dict()


def generate_inventory(rng: random.Random, skus: list[Sku], orders_df: pd.DataFrame) -> pd.DataFrame:
    units_sold_by_sku_day: dict[tuple[str, str], int] = (
        orders_df.groupby(["sku_id", "order_date"])["quantity"].sum().to_dict()
    )
    baseline_demand_by_sku = _baseline_daily_demand_by_sku(orders_df)

    scenario_sku_id = None
    aurora_skus = [s for s in skus if s.brand == config.SCENARIO_INV_BRAND]
    if aurora_skus:
        scenario_sku_id = aurora_skus[config.SCENARIO_INV_SKU_INDEX].sku_id

    rows = []
    for sku in skus:
        is_scenario_sku = sku.sku_id == scenario_sku_id
        baseline_rate = baseline_demand_by_sku.get(sku.sku_id, FALLBACK_DAILY_DEMAND)

        if is_scenario_sku:
            opening = config.SCENARIO_INV_OPENING_STOCK
        else:
            # Ordinary SKUs start with a realistic ~20-35 days of cover
            # given their own observed baseline demand, instead of a flat
            # stock range that ignores per-SKU demand entirely.
            opening = max(5, round(baseline_rate * rng.uniform(*NORMAL_STARTING_DAYS_OF_COVER_RANGE)))

        stock = opening
        day_index = 0
        trailing_demand: list[int] = []
        for day in daterange(config.START_DATE, config.END_DATE):
            units_sold = int(units_sold_by_sku_day.get((sku.sku_id, day.isoformat()), 0))
            raw_demand = units_sold

            if is_scenario_sku:
                if is_recent(day):
                    receipts = config.SCENARIO_INV_RECENT_RECEIPTS_PER_DAY
                else:
                    receipts = rng.randint(*config.SCENARIO_INV_BASELINE_RECEIPTS_RANGE)
            elif day_index % NORMAL_RECEIPT_INTERVAL_DAYS == 0:
                # Reactive replenishment: order up to (roughly) whatever
                # demand was actually realized over the last interval,
                # not a fixed historical estimate. This is a periodic-
                # review, order-up-to-consumption policy, so stock stays
                # near its starting days-of-cover for the whole window
                # instead of drifting toward stockout or excess purely
                # from estimation noise.
                if trailing_demand:
                    recent_demand = sum(trailing_demand[-NORMAL_RECEIPT_INTERVAL_DAYS:])
                else:
                    recent_demand = baseline_rate * NORMAL_RECEIPT_INTERVAL_DAYS
                receipts = round(recent_demand * rng.uniform(*NORMAL_REPLENISH_FACTOR_RANGE))
            else:
                receipts = 0

            opening_stock = stock
            # Stock cannot go negative; unmet demand is simply not fulfillable
            # in this simplified model (no backorder tracking).
            units_sold = min(units_sold, opening_stock + receipts)
            closing_stock = opening_stock + receipts - units_sold

            rows.append(
                {
                    "date": day.isoformat(),
                    "sku_id": sku.sku_id,
                    "brand": sku.brand,
                    "opening_stock": opening_stock,
                    "receipts": receipts,
                    "units_sold": units_sold,
                    "closing_stock": closing_stock,
                }
            )

            stock = closing_stock
            trailing_demand.append(raw_demand)
            day_index += 1

    return pd.DataFrame.from_records(rows)
