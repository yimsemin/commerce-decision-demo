"""Deterministic dimension builders: SKUs and the customer pool.

These are pure functions of a `random.Random` instance so callers control
reproducibility by passing a seeded RNG.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class Sku:
    sku_id: str
    brand: str
    base_price: float
    unit_cost: float


@dataclass(frozen=True)
class Customer:
    customer_id: str
    brand_affinity: str
    acquisition_channel: str


def build_skus(rng: random.Random) -> list[Sku]:
    skus: list[Sku] = []
    for brand in config.BRANDS:
        prefix = config.BRAND_PREFIX[brand]
        for i in range(1, config.SKUS_PER_BRAND + 1):
            base_price = round(rng.uniform(*config.BASE_PRICE_RANGE), 2)
            unit_cost = round(base_price * config.BASE_UNIT_COST_FRACTION, 2)
            skus.append(
                Sku(
                    sku_id=f"{prefix}-{i:03d}",
                    brand=brand,
                    base_price=base_price,
                    unit_cost=unit_cost,
                )
            )
    return skus


def skus_for_brand(skus: list[Sku], brand: str) -> list[Sku]:
    return [s for s in skus if s.brand == brand]


def build_customer_pool(rng: random.Random) -> list[Customer]:
    customers: list[Customer] = []
    for i in range(1, config.CUSTOMER_POOL_SIZE + 1):
        brand_affinity = rng.choice(config.BRANDS)
        acquisition_channel = rng.choice(config.MARKETING_CHANNELS)
        customers.append(
            Customer(
                customer_id=f"CUST-{i:05d}",
                brand_affinity=brand_affinity,
                acquisition_channel=acquisition_channel,
            )
        )
    return customers
