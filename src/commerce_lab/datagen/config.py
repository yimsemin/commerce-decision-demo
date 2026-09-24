"""Static configuration for the synthetic commerce data generator.

All entity lists, date ranges, and scenario parameters live here so the
generation logic (orders/marketing/inventory/customers) and the tests that
verify planted scenarios share a single source of truth.
"""

from __future__ import annotations

import datetime as dt

# ---------------------------------------------------------------------------
# Time window
# ---------------------------------------------------------------------------
# Fixed anchor date so a given seed always produces byte-identical data,
# regardless of when the generator is actually run.
END_DATE = dt.date(2026, 9, 21)
TOTAL_DAYS = 120
START_DATE = END_DATE - dt.timedelta(days=TOTAL_DAYS - 1)

# The "recent window" is where planted scenarios are concentrated, compared
# against the "baseline window" that precedes it.
RECENT_WINDOW_DAYS = 30
RECENT_START_DATE = END_DATE - dt.timedelta(days=RECENT_WINDOW_DAYS - 1)
BASELINE_WINDOW_DAYS = 30
BASELINE_START_DATE = RECENT_START_DATE - dt.timedelta(days=BASELINE_WINDOW_DAYS)
BASELINE_END_DATE = RECENT_START_DATE - dt.timedelta(days=1)

# ---------------------------------------------------------------------------
# Brands / channels
# ---------------------------------------------------------------------------
BRANDS = ["Aurora", "Kestrel", "Marlow"]

SALES_CHANNELS = ["online_dtc", "marketplace", "retail_partner"]

MARKETING_CHANNELS = ["paid_search", "paid_social", "affiliate"]

# ---------------------------------------------------------------------------
# SKUs: 8 per brand, simple deterministic id scheme
# ---------------------------------------------------------------------------
SKUS_PER_BRAND = 8
BRAND_PREFIX = {"Aurora": "AUR", "Kestrel": "KES", "Marlow": "MAR"}

BASE_PRICE_RANGE = (18.0, 120.0)
BASE_UNIT_COST_FRACTION = 0.45  # unit cost as a fraction of base price

# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
CUSTOMER_POOL_SIZE = 900

# ---------------------------------------------------------------------------
# Planted scenarios (explicit, documented, and asserted independently by
# tests/test_datagen/test_scenarios.py)
# ---------------------------------------------------------------------------

# Scenario 1: deteriorating marketing efficiency for one brand/channel pair.
# Spend ramps up through the recent window while attributed revenue stays
# flat, so ROAS falls materially.
SCENARIO_MKT_BRAND = "Kestrel"
SCENARIO_MKT_CHANNEL = "paid_social"
SCENARIO_MKT_SPEND_RAMP = 2.6  # recent daily spend multiplier vs baseline
SCENARIO_MKT_REVENUE_RAMP = 1.05  # attributed revenue stays roughly flat

# Scenario 2: rising demand + low remaining stock for one SKU.
# Units sold trend up in the recent window while receipts stay low, driving
# closing stock and days-of-cover down.
SCENARIO_INV_SKU_INDEX = 2  # 0-based index into Aurora's SKU list
SCENARIO_INV_BRAND = "Aurora"
SCENARIO_INV_DEMAND_RAMP = 2.8  # recent daily demand multiplier vs baseline
SCENARIO_INV_OPENING_STOCK = 90
# Baseline receipts trickle in just enough to roughly track ordinary
# (pre-ramp) demand for this one SKU, instead of the generic restock
# cadence used for every other SKU.
SCENARIO_INV_BASELINE_RECEIPTS_RANGE = (0, 2)
SCENARIO_INV_RECENT_RECEIPTS_PER_DAY = 0  # cut off: deliberately insufficient

# Scenario 3: material sales decline concentrated in one brand/channel.
SCENARIO_DECLINE_BRAND = "Marlow"
SCENARIO_DECLINE_CHANNEL = "retail_partner"
SCENARIO_DECLINE_FACTOR = 0.55  # recent-window order volume vs baseline

# Scenario 4: meaningful shift in new-vs-returning customer mix.
# Acquisition of new customers slows sharply in the recent window, shifting
# the order mix toward returning customers.
SCENARIO_NEW_SHARE_BASELINE = 0.55  # approx. share of orders from new customers
SCENARIO_NEW_SHARE_RECENT = 0.20

# ---------------------------------------------------------------------------
# Volume controls (kept deliberately small / bounded)
# ---------------------------------------------------------------------------
BASELINE_DAILY_ORDERS_MEAN = 14
RECENT_DAILY_ORDERS_MEAN = 14  # overall volume stays roughly flat; scenario 3
# carves out the declining segment on top of this baseline

DEFAULT_SEED = 42
