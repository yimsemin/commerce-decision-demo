"""Marketing performance generation.

Plants Scenario 1 (deteriorating marketing efficiency): for one brand /
marketing-channel pair, daily spend ramps up sharply in the recent window
while attributed revenue is deliberately held flat, so ROAS collapses. All
other brand/channel pairs keep a stable spend-to-revenue relationship
throughout, so the deterioration is concentrated and detectable.
"""

from __future__ import annotations

import datetime as dt
import random

import pandas as pd

from . import config
from .dates import daterange, is_recent

MKT_SEGMENTS = [(b, c) for b in config.BRANDS for c in config.MARKETING_CHANNELS]


def generate_marketing(rng: random.Random) -> pd.DataFrame:
    rows = []

    for brand, channel in MKT_SEGMENTS:
        is_scenario_combo = (
            brand == config.SCENARIO_MKT_BRAND and channel == config.SCENARIO_MKT_CHANNEL
        )
        base_roas = rng.uniform(2.5, 4.5)

        for day in daterange(config.START_DATE, config.END_DATE):
            normal_spend = round(rng.uniform(80.0, 220.0), 2)

            if is_scenario_combo and is_recent(day):
                spend = round(normal_spend * config.SCENARIO_MKT_SPEND_RAMP, 2)
                revenue = round(
                    normal_spend
                    * base_roas
                    * rng.uniform(0.85, 1.15)
                    * config.SCENARIO_MKT_REVENUE_RAMP,
                    2,
                )
            else:
                spend = normal_spend
                revenue = round(normal_spend * base_roas * rng.uniform(0.85, 1.15), 2)

            impressions = int(spend * rng.uniform(18.0, 26.0))
            clicks = int(impressions * rng.uniform(0.015, 0.035))
            attributed_orders = max(1, round(revenue / rng.uniform(35.0, 55.0)))

            rows.append(
                {
                    "date": day.isoformat(),
                    "brand": brand,
                    "marketing_channel": channel,
                    "spend": spend,
                    "impressions": impressions,
                    "clicks": clicks,
                    "attributed_orders": attributed_orders,
                    "attributed_revenue": revenue,
                }
            )

    return pd.DataFrame.from_records(rows)
