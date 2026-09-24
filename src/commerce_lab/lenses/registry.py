"""Loads lenses by name and runs them.

A lens name is either a built-in (`"sales"` -> `commerce_lab.lenses.sales`)
or a dotted module path (`"my_package.returns"`) whose module exposes a
module-level `LENS`. Which lenses are active is decided by
`config/lab.toml` (see `settings.py`) and recorded in every snapshot, so
the app renders exactly the lenses the refresh computed.
"""

from __future__ import annotations

import dataclasses
import importlib

import pandas as pd

from ..decisions.models import SEVERITY_ORDER, DecisionItem
from ..metrics.periods import PeriodWindow
from .base import DataSource, Lens

BUILTIN_LENS_NAMES = ("sales", "marketing", "customer", "inventory")

_LOADED: dict[str, Lens] = {}  # lens id -> Lens


def register_lens(lens: Lens) -> Lens:
    """Registers `lens` (e.g. from a test or a notebook) and merges its
    UI strings. Loading by module name calls this for you."""
    from ..app import i18n

    i18n.register_strings(lens.strings)
    _LOADED[lens.id] = lens
    return lens


def unregister_lens(lens_id: str) -> None:
    _LOADED.pop(lens_id, None)


def load_lens(name: str) -> Lens:
    module_path = name if "." in name else f"{__package__}.{name}"
    module = importlib.import_module(module_path)
    lens = getattr(module, "LENS", None)
    if not isinstance(lens, Lens):
        raise ValueError(f"Module '{module_path}' must expose a module-level LENS = Lens(...).")
    return register_lens(lens)


def load_lenses(names) -> list[Lens]:
    return [load_lens(n) for n in names]


def _ensure_builtins_loaded() -> None:
    for name in BUILTIN_LENS_NAMES:
        if name not in _LOADED:
            load_lens(name)


def localizer_for(issue_type: str):
    """The prose localizer registered for `issue_type`, or None. Built-in
    lenses are loaded on first use so `localize_decision` works standalone."""
    _ensure_builtins_loaded()
    for lens in _LOADED.values():
        if issue_type in lens.localizers:
            return lens.localizers[issue_type]
    return None


def lens_for_decision(decision: dict) -> Lens | None:
    """The lens that raised `decision`. Items from older snapshots carry no
    `lens` tag, so fall back to whichever lens localizes its issue type."""
    _ensure_builtins_loaded()
    if decision.get("lens") in _LOADED:
        return _LOADED[decision["lens"]]
    return next((lens for lens in _LOADED.values() if decision["issue_type"] in lens.localizers), None)


def data_sources(lenses: list[Lens]) -> list[DataSource]:
    return [ds for lens in lenses for ds in lens.data_sources]


def resolve_params(lens: Lens, overrides: dict | None = None) -> dict:
    """Lens defaults with `overrides` on top. Unknown keys are rejected so
    a typo in the config file fails loudly instead of being ignored."""
    params = lens.default_params()
    for key, value in (overrides or {}).items():
        if key not in params:
            raise ValueError(f"Unknown parameter '{key}' for lens '{lens.id}'. Known: {sorted(params)}.")
        params[key] = value
    return params


def compute_sections(
    lenses: list[Lens],
    datasets: dict[str, pd.DataFrame],
    window: PeriodWindow,
    params: dict[str, dict] | None = None,
) -> tuple[dict[str, dict], dict[str, dict]]:
    """(sections, resolved_params), both keyed by lens id."""
    resolved = {lens.id: resolve_params(lens, (params or {}).get(lens.id)) for lens in lenses}
    sections = {lens.id: lens.compute(datasets, window, resolved[lens.id]) for lens in lenses}
    return sections, resolved


def run_detection(lenses: list[Lens], sections: dict[str, dict], params: dict[str, dict]) -> list[DecisionItem]:
    """Runs every lens's rules and returns the items sorted by severity.
    Each item is stamped with the lens that raised it."""
    items: list[DecisionItem] = []
    for lens in lenses:
        lens_params = resolve_params(lens, params.get(lens.id))
        items.extend(dataclasses.replace(item, lens=lens.id) for item in lens.detect(sections[lens.id], lens_params))
    return sorted(items, key=lambda d: SEVERITY_ORDER[d.severity])
