"""Checks that the BigQuery metrics functions and the pandas reference code
agree on the same data.

    python -m commerce_lab.pipeline.parity --seed 123

Generates the dataset for `--seed`, loads it into BigQuery exactly as the
refresh job does (this replaces the raw tables and today's GCS folder), then
builds every comparison anchor's snapshot twice -- KPIs from BigQuery and
from pandas -- and compares every KPI and every decision item. Exits 1 on
any difference. Rounded values may differ by one rounding step (see ROUNDING_STEP).
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

# One rounding step per KPI name (the size of the last rounded digit);
# anything not listed must agree to 1e-6. BigQuery rounds half away from
# zero and numpy half to even, and the two sum floats in different orders,
# so a value sitting exactly on a .5 boundary can land one step apart.
ROUNDING_STEP = {
    "pct_change": 0.1,
    "roas_change_pct": 0.1,
    "days_of_cover": 0.1,
    "velocity": 0.01,
    "aov": 0.01,
    "net_revenue": 0.01,
    "cac": 0.01,
    "current_new_share": 0.001,
    "previous_new_share": 0.001,
    "current_returning_share": 0.001,
    "previous_returning_share": 0.001,
    "repeat_purchase_rate": 0.001,
}

# Prose built from the numbers above (formatted to whole units), so a
# boundary value can differ by 1 there too; the numbers themselves are
# compared in `supporting_kpi`.
PROSE_FIELDS = {"likely_drivers"}


def _close(key: str, a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        step = ROUNDING_STEP.get(key, 0.0)
        return math.isclose(a, b, rel_tol=1e-6, abs_tol=step * 1.01 + 1e-9)
    return a == b


def compare(a, b, path: str = "") -> list[str]:
    """Differences between two snapshot sections (nested dict/list/scalars),
    as readable strings; empty when they agree."""
    if isinstance(a, dict) and isinstance(b, dict):
        diffs = [f"{path}.{k}: missing on one side" for k in a.keys() ^ b.keys()]
        for k in a.keys() & b.keys():
            diffs += compare(a[k], b[k], f"{path}.{k}")
        return diffs
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: {len(a)} rows vs {len(b)} rows"]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in compare(x, y, f"{path}[{i}]")]
    key = path.rsplit(".", 1)[-1].split("[")[0]
    return [] if _close(key, a, b) else [f"{path}: {a!r} vs {b!r}"]


def _without_prose(decisions: list[dict]) -> list[dict]:
    return [{k: v for k, v in d.items() if k not in PROSE_FIELDS} for d in decisions]


def main(argv: list[str] | None = None) -> None:
    from ..datagen.generator import generate_all, write_datasets
    from ..lenses.registry import data_sources
    from .refresh import resolve_lenses, run_cloud_ingest
    from .snapshot import build_snapshot_history

    parser = argparse.ArgumentParser(description="Compare BigQuery and pandas KPIs on the same data.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data/generated"))
    args = parser.parse_args(argv)

    lenses, _ = resolve_lenses(None, None)
    sources = data_sources(lenses)
    datasets = generate_all(seed=args.seed, data_sources=sources)
    write_datasets(datasets, args.data_dir)
    warehouse = run_cloud_ingest(args.data_dir, args.seed, sources)(datasets)

    from_bq = build_snapshot_history(datasets, lenses=lenses, warehouse=warehouse, data_seed=args.seed)
    from_pandas = build_snapshot_history(datasets, lenses=lenses, data_seed=args.seed)

    total = 0
    for as_of, bq_snap in from_bq["snapshots"].items():
        pd_snap = from_pandas["snapshots"][as_of]
        diffs = []
        for lens in lenses:
            diffs += compare(bq_snap[lens.id], pd_snap[lens.id], f"{as_of}.{lens.id}")
        diffs += compare(_without_prose(bq_snap["decisions"]), _without_prose(pd_snap["decisions"]), f"{as_of}.decisions")
        total += len(diffs)
        print(f"{as_of}: {'OK' if not diffs else f'{len(diffs)} difference(s)'}")
        for d in diffs[:20]:
            print(f"  {d}")
    print(f"seed {args.seed}: {'BigQuery and pandas agree' if total == 0 else f'{total} difference(s)'}")
    raise SystemExit(1 if total else 0)


if __name__ == "__main__":
    main()
