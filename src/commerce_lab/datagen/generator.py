"""Orchestrates synthetic data generation and writes CSV output.

Usage:
    python -m commerce_lab.datagen.generator [--seed 42] [--out data/generated]
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import pandas as pd

from . import config
from .customers import derive_customer_summary
from .entities import build_customer_pool, build_skus
from .inventory import generate_inventory
from .marketing import generate_marketing
from .orders import generate_orders


def generate_all(seed: int = config.DEFAULT_SEED, data_sources=()) -> dict[str, pd.DataFrame]:
    """Generate every dataset from a single seed. Pure function: same seed
    in, byte-identical DataFrames out. `data_sources` are extra
    `lenses.base.DataSource`s (declared by lenses); each draws from its own
    RNG so adding one never changes the core datasets."""
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
    parser.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=Path("data/generated"))
    args = parser.parse_args(argv)

    datasets = generate_all(seed=args.seed)
    write_datasets(datasets, args.out)

    for name, df in datasets.items():
        print(f"{name}: {len(df)} rows -> {args.out / f'{name}.csv'}")


if __name__ == "__main__":
    main()
