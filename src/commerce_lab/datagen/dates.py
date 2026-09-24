"""Shared date-window helpers used across generators and tests."""

from __future__ import annotations

import datetime as dt

from . import config


def daterange(start: dt.date, end: dt.date):
    n_days = (end - start).days + 1
    for i in range(n_days):
        yield start + dt.timedelta(days=i)


def is_recent(day: dt.date) -> bool:
    return day >= config.RECENT_START_DATE


def is_baseline(day: dt.date) -> bool:
    return config.BASELINE_START_DATE <= day <= config.BASELINE_END_DATE
