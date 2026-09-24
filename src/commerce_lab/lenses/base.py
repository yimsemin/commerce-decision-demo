"""The extension contract: a **lens** is one analytical viewpoint on the
business (sales, marketing, inventory, ...). Everything a viewpoint needs
lives in one module that exposes a `Lens`:

- `data_sources` -- extra raw datasets it needs (optional)
- `compute`      -- (datasets, window, params) -> its section of the snapshot
- `detect`       -- (section, params) -> deterministic `DecisionItem`s
- `params`       -- the tunable thresholds (config file + app inputs)
- `render`       -- its app tab (optional; Streamlit imported lazily)
- `localizers`   -- issue_type -> ko/en prose (optional)
- `kpi_lookup`   -- issue_type -> trend value per snapshot (optional)
- `headline_metrics` -- KPI tiles for the Overview tab (optional)

`detect` only reads the snapshot *section*, never raw data. That is what
lets the app re-evaluate the rules with different thresholds in the
viewer's session with no BigQuery call, and keeps the "KPIs are
deterministic, Gemini only interprets" rule intact. See docs/extending.md.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from ..decisions.models import DecisionItem
from ..metrics.periods import PeriodWindow


@dataclass(frozen=True)
class Param:
    """A tunable threshold. `runtime=True` params get an input in the app
    (they only affect `detect`); `runtime=False` params change what
    `compute` produces, so they can only be set in the config file and
    take effect on the next refresh."""

    key: str
    default: float
    label: dict[str, str]
    min: float
    max: float
    step: float
    runtime: bool = True


@dataclass(frozen=True)
class DataSource:
    """An extra raw table. `columns` maps column name -> BigQuery type and
    doubles as the CSV column order and the raw-table DDL. `generate`
    receives its own RNG (seeded from the global seed + table name, so
    adding a source never changes any existing dataset) and the datasets
    generated so far."""

    name: str
    columns: dict[str, str]
    generate: Callable[[random.Random, dict[str, pd.DataFrame]], pd.DataFrame]


@dataclass(frozen=True)
class Tile:
    label_key: str
    value: str
    delta: str | None = None


@dataclass(frozen=True)
class Lens:
    id: str
    title: dict[str, str]
    compute: Callable[[dict[str, pd.DataFrame], PeriodWindow, dict], dict]
    detect: Callable[[dict, dict], list[DecisionItem]]
    params: tuple[Param, ...] = ()
    data_sources: tuple[DataSource, ...] = ()
    render: Callable[[dict, str, dict], None] | None = None  # (section, lang, params)
    localizers: dict[str, Callable[[dict, dict, str], dict]] = field(default_factory=dict)
    kpi_lookup: Callable[[dict, str, dict], float | None] | None = None  # (section, issue_type, affected)
    headline_metrics: Callable[[dict, str], list[Tile]] | None = None  # (section, lang)
    strings: dict[str, dict[str, str]] = field(default_factory=dict)  # extra UI strings, merged into i18n

    def default_params(self) -> dict:
        return {p.key: p.default for p in self.params}
