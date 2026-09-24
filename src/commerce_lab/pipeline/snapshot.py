"""Builds the application-ready snapshot: the *only* artifact the
executive web app reads (PROJECT.md's public-traffic-never-hits-BigQuery
revision -- see PROGRESS.md decisions log). Combines M3 metrics and M4
decision items into one small, JSON-serializable structure.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from ..lenses.base import Lens
from ..lenses.registry import compute_sections, load_lenses, run_detection
from ..lenses.settings import LabSettings, load_settings
from ..metrics.periods import PeriodWindow, compute_period_window, latest_date
from .serialize import to_json_safe

SNAPSHOT_SCHEMA_VERSION = 2  # 2: adds `lenses` + `params` + per-decision `lens`; lens sections keep their v1 shape
HISTORY_SCHEMA_VERSION = 2  # shape of the build_snapshot_history() wrapper

# How many historical as-of points to precompute so the app can offer a
# comparison-period selector without ever querying BigQuery live. Anchors
# are spaced `HISTORY_SPACING_DAYS` apart, most recent last, and each still
# uses a `window_days`-vs-`window_days` current/previous comparison -- only
# the current period's *end* moves, not the comparison methodology.
HISTORY_ANCHOR_COUNT = 5
HISTORY_SPACING_DAYS = 15


def resolve_lenses(lenses: list[Lens] | None, settings: LabSettings | None) -> tuple[list[Lens], dict]:
    settings = settings or load_settings()
    return (lenses if lenses is not None else load_lenses(settings.enabled)), settings.params


def build_snapshot(
    datasets: dict[str, pd.DataFrame],
    window_days: int = 30,
    as_of: dt.date | None = None,
    lenses: list[Lens] | None = None,
    settings: LabSettings | None = None,
) -> dict:
    """One as-of snapshot. `lenses` defaults to those enabled in
    `config/lab.toml`; `settings.params` overrides lens parameter defaults."""
    lenses, param_overrides = resolve_lenses(lenses, settings)
    if as_of is None:
        as_of = latest_date(datasets["orders"]["order_date"], datasets["marketing"]["date"], datasets["inventory"]["date"])
    window: PeriodWindow = compute_period_window(as_of, window_days=window_days)

    sections, params = compute_sections(lenses, datasets, window, param_overrides)
    decisions = run_detection(lenses, sections, params)

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "as_of_date": as_of.isoformat(),
        "period": {
            "current_start": window.current_start.isoformat(),
            "current_end": window.current_end.isoformat(),
            "previous_start": window.previous_start.isoformat(),
            "previous_end": window.previous_end.isoformat(),
        },
        "lenses": [lens.id for lens in lenses],
        "params": params,
        **sections,
        "decisions": [to_json_safe(d.to_dict()) for d in decisions],
        "gemini_summary": None,  # populated by commerce_lab.gemini (M6)
    }


def default_history_anchors(
    datasets: dict[str, pd.DataFrame],
    window_days: int = 30,
    count: int = HISTORY_ANCHOR_COUNT,
    spacing_days: int = HISTORY_SPACING_DAYS,
) -> list[dt.date]:
    """The latest date in the data, plus `count - 1` earlier anchors spaced
    `spacing_days` apart -- as far back as the data can still support a full
    current-vs-previous `window_days` comparison. Ascending order (oldest
    first, latest last)."""
    latest = latest_date(datasets["orders"]["order_date"], datasets["marketing"]["date"], datasets["inventory"]["date"])
    earliest_orders_date = dt.date.fromisoformat(datasets["orders"]["order_date"].min())
    min_as_of = earliest_orders_date + dt.timedelta(days=2 * window_days - 1)

    anchors = []
    candidate = latest
    while len(anchors) < count and candidate >= min_as_of:
        anchors.append(candidate)
        candidate = candidate - dt.timedelta(days=spacing_days)
    return sorted(anchors)


def build_snapshot_history(
    datasets: dict[str, pd.DataFrame],
    as_of_dates: list[dt.date] | None = None,
    window_days: int = 30,
    lenses: list[Lens] | None = None,
    settings: LabSettings | None = None,
) -> dict:
    """Precomputes one `build_snapshot()` per as-of anchor so the app can
    offer a comparison-period selector while still only ever reading a
    single static file (never querying BigQuery/Gemini live). Ascending
    order; the last entry is the latest/default one."""
    if as_of_dates is None:
        as_of_dates = default_history_anchors(datasets, window_days=window_days)

    lenses, _ = resolve_lenses(lenses, settings)
    snapshots = {
        as_of.isoformat(): build_snapshot(datasets, window_days=window_days, as_of=as_of, lenses=lenses, settings=settings)
        for as_of in as_of_dates
    }
    available = sorted(snapshots.keys())

    return {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "available_as_of_dates": available,
        "latest_as_of_date": available[-1],
        "snapshots": snapshots,
    }


def write_snapshot(snapshot: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
