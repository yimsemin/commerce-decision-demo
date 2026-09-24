from __future__ import annotations

import pytest

from commerce_lab.datagen.generator import generate_all
from commerce_lab.metrics.periods import compute_period_window, latest_date


@pytest.fixture(scope="session")
def datasets():
    return generate_all()


@pytest.fixture(scope="session")
def window(datasets):
    as_of = latest_date(datasets["orders"]["order_date"], datasets["marketing"]["date"], datasets["inventory"]["date"])
    return compute_period_window(as_of, window_days=30)
