"""Orchestrates synthetic data generation and writes CSV output.

Usage:
    python -m commerce_lab.datagen.generator [--seed N] [--out data/generated]
"""

from __future__ import annotations

import argparse
import random
import secrets
from pathlib import Path

import pandas as pd

from . import config
from .customers import derive_customer_summary
from .entities import build_customer_pool, build_skus
from .inventory import generate_inventory
from .marketing import generate_marketing
from .orders import generate_orders
from .plant_check import planted_scenario_failures


MAX_PLANT_ATTEMPTS = 50


def random_seed() -> int:
    """A fresh seed for a new random dataset (the refresh job's default)."""
    return secrets.randbelow(2**31)


def generate_all(seed: int = config.DEFAULT_SEED, data_sources=()) -> dict[str, pd.DataFrame]:
    """Generate every dataset from a single seed. Pure function: same seed
    in, byte-identical DataFrames out. `data_sources` are extra
    `lenses.base.DataSource`s (declared by lenses); each draws from its own
    RNG so adding one never changes the core datasets.

    A draw is kept only if the four planted scenarios came out clearly
    detectable (`plant_check`); otherwise the next draw derived from the
    same seed is tried, so every seed -- not just a lucky one -- tells the
    same four-issue story, and a seed still reproduces its dataset."""
    for attempt in range(MAX_PLANT_ATTEMPTS):
        draw = seed if attempt == 0 else f"{seed}:{attempt}"
        datasets = _generate_draw(draw, data_sources)
        if not planted_scenario_failures(datasets):
            return datasets
    raise RuntimeError(f"No draw of seed {seed} planted the scenarios cleanly in {MAX_PLANT_ATTEMPTS} attempts.")


def _generate_draw(seed, data_sources) -> dict[str, pd.DataFrame]:
    rng = random.Random(seed)

    skus = build_skus(rng)
    customers = build_customer_pool(rng)

    orders_df = generate_orders(rng, skus, customers)
    marketing_df = generate_marketing(rng)
    inventory_df = generate_inventory(rng, skus, orders_df)
    customers_df = derive_customer_summary(orders_df, customers)

    skus_df = pd.DataFrame(
        [{"sku_id": s.sku_id, "brand": s.brand, "base_price": s.base_price, "unit_cost": s.unit_cost} for s in skus]
    )

    datasets = {
        "orders": orders_df,
        "marketing": marketing_df,
        "inventory": inventory_df,
        "customers": customers_df,
        "skus": skus_df,
    }
    for source in data_sources:
        if source.name in datasets:
            raise ValueError(f"Data source '{source.name}' clashes with an existing dataset.")
        df = source.generate(random.Random(f"{seed}:{source.name}"), datasets)
        datasets[source.name] = df[list(source.columns)]
    return datasets


def write_datasets(datasets: dict[str, pd.DataFrame], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in datasets.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic commerce data.")
    parser.add_argument("--seed", type=int, default=None, help="reproduce a dataset; default is a fresh random seed")
    parser.add_argument("--out", type=Path, default=Path("data/generated"))
    args = parser.parse_args(argv)

    seed = random_seed() if args.seed is None else args.seed
    print(f"seed: {seed}")
    datasets = generate_all(seed=seed)
    write_datasets(datasets, args.out)

    for name, df in datasets.items():
        print(f"{name}: {len(df)} rows -> {args.out / f'{name}.csv'}")


if __name__ == "__main__":
    main()
