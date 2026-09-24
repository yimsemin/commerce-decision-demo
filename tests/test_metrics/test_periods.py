from __future__ import annotations

import datetime as dt

from commerce_lab.metrics.periods import compute_period_window


def test_period_window_boundaries():
    as_of = dt.date(2026, 9, 21)
    w = compute_period_window(as_of, window_days=30)

    assert w.current_end == as_of
    assert w.current_start == dt.date(2026, 8, 23)
    assert w.previous_end == dt.date(2026, 8, 22)
    assert w.previous_start == dt.date(2026, 7, 24)

    # windows are contiguous and non-overlapping
    assert (w.current_start - w.previous_end).days == 1
    assert (w.current_end - w.current_start).days == 29
    assert (w.previous_end - w.previous_start).days == 29
