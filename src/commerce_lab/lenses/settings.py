"""Owner-editable settings: which lenses run, and their parameter values.

Read from `config/lab.toml` (or the path in `COMMERCE_LAB_CONFIG`); if the
file is missing, built-in defaults apply. Example:

    [lenses]
    enabled = ["sales", "marketing", "customer", "inventory", "my_package.returns"]

    [params.marketing]
    roas_decline_high_pct = -35
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .registry import BUILTIN_LENS_NAMES

DEFAULT_CONFIG_PATH = Path("config/lab.toml")


@dataclass(frozen=True)
class LabSettings:
    enabled: tuple[str, ...] = BUILTIN_LENS_NAMES
    params: dict[str, dict] = field(default_factory=dict)  # lens id -> {param key: value}


def load_settings(path: Path | None = None) -> LabSettings:
    path = path or Path(os.environ.get("COMMERCE_LAB_CONFIG", str(DEFAULT_CONFIG_PATH)))
    if not path.exists():
        return LabSettings()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    enabled = tuple(raw.get("lenses", {}).get("enabled", BUILTIN_LENS_NAMES))
    return LabSettings(enabled=enabled, params=raw.get("params", {}))
