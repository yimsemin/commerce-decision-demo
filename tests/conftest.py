from __future__ import annotations

import os

import pytest

# Pin the rolling window before any commerce_lab import reads it, so tests are
# independent of the day they run.
os.environ.setdefault("COMMERCE_END_DATE", "2026-09-21")

from commerce_lab.datagen.generator import generate_all
from commerce_lab.metrics.periods import compute_period_window, latest_date


@pytest.fixture(scope="session")
def datasets():
    return generate_all()


@pytest.fixture(scope="session")
def window(datasets):
    as_of = latest_date(datasets["orders"]["order_date"], datasets["marketing"]["date"], datasets["inventory"]["date"])
    return compute_period_window(as_of, window_days=30)
