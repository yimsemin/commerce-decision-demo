"""Current-vs-previous period window computation.

Deliberately decoupled from `commerce_lab.datagen.config`: the metrics
layer derives its "current" period from the latest date actually present
in the data (or an explicit `as_of` override), not from generator
internals, so it works the same way against any warehouse snapshot.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class PeriodWindow:
    current_start: dt.date
    current_end: dt.date
    previous_start: dt.date
    previous_end: dt.date

    def in_current(self, date_series):
        return (date_series >= self.current_start.isoformat()) & (
            date_series <= self.current_end.isoformat()
        )

    def in_previous(self, date_series):
        return (date_series >= self.previous_start.isoformat()) & (
            date_series <= self.previous_end.isoformat()
        )


def compute_period_window(as_of: dt.date, window_days: int = 30) -> PeriodWindow:
    """Current period = the `window_days` days ending on `as_of`.
    Previous period = the `window_days` days immediately before that."""
    current_start = as_of - dt.timedelta(days=window_days - 1)
    previous_end = current_start - dt.timedelta(days=1)
    previous_start = previous_end - dt.timedelta(days=window_days - 1)
    return PeriodWindow(
        current_start=current_start,
        current_end=as_of,
        previous_start=previous_start,
        previous_end=previous_end,
    )


def latest_date(*date_series) -> dt.date:
    max_str = max(s.max() for s in date_series if len(s) > 0)
    return dt.date.fromisoformat(max_str)
