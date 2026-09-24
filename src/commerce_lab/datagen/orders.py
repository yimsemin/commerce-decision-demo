"""Commerce order generation.

Plants two of the four required business scenarios directly in the order
stream:

- Scenario 3 (sales decline): the Marlow / retail_partner segment is
  down-weighted in the recent window relative to all other brand/channel
  segments.
- Scenario 4 (new-vs-returning mix shift): the probability that an order
  comes from a brand-new customer drops sharply in the recent window.

Scenario 2 (rising demand / low inventory) is seeded here too, by boosting
demand for one specific Aurora SKU in the recent window; `inventory.py`
consumes the resulting per-SKU daily unit sales to build a consistent stock
ledger.
"""

from __future__ import annotations

import datetime as dt
import random

import pandas as pd

from . import config
from .dates import daterange, is_recent
from .entities import Customer, Sku, skus_for_brand

SEGMENTS = [(b, c) for b in config.BRANDS for c in config.SALES_CHANNELS]


def _segment_weights(day: dt.date) -> list[float]:
    weights = []
    for brand, channel in SEGMENTS:
        w = 1.0
        if (
            is_recent(day)
            and brand == config.SCENARIO_DECLINE_BRAND
            and channel == config.SCENARIO_DECLINE_CHANNEL
        ):
            w *= config.SCENARIO_DECLINE_FACTOR
        weights.append(w)
    return weights


def _sku_weights(brand_skus: list[Sku], brand: str, day: dt.date) -> list[float]:
    weights = [1.0] * len(brand_skus)
    if is_recent(day) and brand == config.SCENARIO_INV_BRAND:
        weights[config.SCENARIO_INV_SKU_INDEX] *= config.SCENARIO_INV_DEMAND_RAMP
    return weights


def _new_customer_probability(day: dt.date) -> float:
    return (
        config.SCENARIO_NEW_SHARE_RECENT
        if is_recent(day)
        else config.SCENARIO_NEW_SHARE_BASELINE
    )


def _daily_order_count(rng: random.Random) -> int:
    mean = config.BASELINE_DAILY_ORDERS_MEAN
    value = round(rng.gauss(mean, mean**0.5))
    return max(1, value)


def generate_orders(
    rng: random.Random, skus: list[Sku], customers: list[Customer]
) -> pd.DataFrame:
    skus_by_brand = {brand: skus_for_brand(skus, brand) for brand in config.BRANDS}

    customer_pool = list(customers)
    rng.shuffle(customer_pool)
    pool_iter = iter(customer_pool)
    seen_customer_ids: list[str] = []
    seen_set: set[str] = set()

    def _draw_new_customer() -> Customer | None:
        for cust in pool_iter:
            if cust.customer_id not in seen_set:
                return cust
        return None

    rows = []
    order_seq = 0

    for day in daterange(config.START_DATE, config.END_DATE):
        n_orders = _daily_order_count(rng)
        seg_weights = _segment_weights(day)
        new_prob = _new_customer_probability(day)

        for _ in range(n_orders):
            brand, channel = rng.choices(SEGMENTS, weights=seg_weights, k=1)[0]
            brand_skus = skus_by_brand[brand]
            sku_weights = _sku_weights(brand_skus, brand, day)
            sku = rng.choices(brand_skus, weights=sku_weights, k=1)[0]

            want_new = rng.random() < new_prob
            customer: Customer | None = None
            is_new_customer = False
            if want_new:
                customer = _draw_new_customer()
                if customer is not None:
                    is_new_customer = True
            if customer is None:
                if seen_customer_ids:
                    customer_id = rng.choice(seen_customer_ids)
                    customer = next(c for c in customer_pool if c.customer_id == customer_id)
                else:
                    customer = _draw_new_customer()
                    is_new_customer = True

            if customer.customer_id not in seen_set:
                seen_set.add(customer.customer_id)
                seen_customer_ids.append(customer.customer_id)

            quantity = rng.randint(1, 3)
            discount = round(rng.choice([0.0] * 4 + [0.05, 0.1, 0.15, 0.2]), 2)
            selling_price = round(sku.base_price * (1 - discount), 2)
            net_sales = round(selling_price * quantity, 2)

            order_seq += 1
            rows.append(
                {
                    "order_id": f"ORD-{order_seq:06d}",
                    "order_date": day.isoformat(),
                    "brand": brand,
                    "channel": channel,
                    "sku_id": sku.sku_id,
                    "customer_id": customer.customer_id,
                    "is_new_customer": is_new_customer,
                    "quantity": quantity,
                    "selling_price": selling_price,
                    "discount": discount,
                    "net_sales": net_sales,
                }
            )

    return pd.DataFrame.from_records(rows)
