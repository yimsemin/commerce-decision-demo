"""End-to-end refresh: the manual local-dev equivalent of the full
docs/PROJECT.md §10 automation flow (generate -> GCS -> BigQuery -> metrics ->
snapshot -> AI summary).

Local mode (default): generate synthetic data (a fresh random seed each
run, printed so the dataset can be reproduced with --seed), compute
metrics/decisions with the pandas reference code, write `app_snapshot.json`
locally. No GCP calls, no credentials needed -- this is what the local app
dev server reads.

    python -m commerce_lab.pipeline.refresh

Cloud mode (--upload): uploads the generated CSVs to GCS, loads the
BigQuery raw tables, computes every KPI with the BigQuery `metrics`
functions (sql/metrics/), and uploads the snapshot to its private GCS
object. Requires GCP_PROJECT_ID/GCS_BUCKET and live credentials.

    python -m commerce_lab.pipeline.refresh --upload

AI summary (--summarize): additionally calls Gemini to fill
`gemini_summary`, grounded strictly in the decision items already
computed. Optional and never fatal -- if it fails, `gemini_summary`
stays null and the app's deterministic fallback summary is shown
instead. Requires GCP_PROJECT_ID and live credentials.

    python -m commerce_lab.pipeline.refresh --summarize
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..datagen.generator import generate_all, write_datasets
from ..lenses.registry import data_sources
from .snapshot import build_snapshot_history, resolve_lenses, write_snapshot


def run_local_refresh(
    seed: int, data_dir: Path, snapshot_path: Path, summarize: bool = False, warehouse=None, ingest=None
) -> dict:
    """Generate data, build the snapshot history (one entry per comparison-
    period anchor), write both locally. Returns the snapshot dict (mainly
    so callers/tests can inspect it without a second file read).

    `ingest`, when given, is called with the generated datasets after the
    CSVs are written and must load them into BigQuery; it returns the
    `Warehouse` to compute from (cloud mode). With neither `ingest` nor
    `warehouse`, every KPI is computed by the pandas reference code.

    Only the latest anchor gets a live Gemini call when `summarize=True` --
    older anchors keep `gemini_summary: None` and fall back to the app's
    deterministic summary, so this doesn't multiply Gemini cost/latency."""
    lenses, _ = resolve_lenses(None, None)  # enabled lenses from config/lab.toml
    datasets = generate_all(seed=seed, data_sources=data_sources(lenses))
    write_datasets(datasets, data_dir)
    if ingest is not None:
        warehouse = ingest(datasets)
    history = build_snapshot_history(datasets, lenses=lenses, warehouse=warehouse, data_seed=seed)

    if summarize:
        from ..gemini.summarize import generate_executive_summary

        latest = history["snapshots"][history["latest_as_of_date"]]
        latest["gemini_summary"] = generate_executive_summary(latest)

    write_snapshot(history, snapshot_path)
    return history


def run_cloud_ingest(data_dir: Path, seed: int, data_sources=()):
    """Returns an `ingest` callback for `run_local_refresh`: uploads the CSVs
    to GCS, loads the BigQuery raw tables, confirms the load, and returns
    the BigQuery `Warehouse` the metrics are then computed from. Performs
    live GCP calls; requires GCP_PROJECT_ID/GCS_BUCKET and credentials."""
    from ..metrics.warehouse import Warehouse, verify_loaded
    from .config import GcpConfig
    from .ingest import run_ingest

    cfg = GcpConfig()
    cfg.require_project_and_bucket()
    uploaded: list[str] = []

    def ingest(datasets):
        uploaded.extend(run_ingest(data_dir, data_sources=data_sources, seed=seed))
        warehouse = Warehouse.connect(cfg.project_id, cfg.bq_dataset_metrics)
        verify_loaded(warehouse, datasets, cfg.bq_dataset_raw)
        return warehouse

    ingest.uploaded = uploaded
    return ingest


def upload_snapshot_file(snapshot_path: Path) -> str:
    from google.cloud import storage

    from .config import GcpConfig
    from .gcs import upload_snapshot

    cfg = GcpConfig()
    cfg.require_project_and_bucket()
    return upload_snapshot(storage.Client(project=cfg.project_id), cfg.bucket, snapshot_path)


def main(argv: list[str] | None = None) -> None:
    from ..datagen.generator import random_seed

    parser = argparse.ArgumentParser(description="Run the local (and optionally cloud) refresh workflow.")
    parser.add_argument("--seed", type=int, default=None, help="reproduce a dataset; default is a fresh random seed")
    parser.add_argument("--data-dir", type=Path, default=Path("data/generated"))
    parser.add_argument("--snapshot-path", type=Path, default=Path("data/generated/app_snapshot.json"))
    parser.add_argument("--upload", action="store_true", help="upload to GCS, load BigQuery and compute the KPIs there (requires GCP access)")
    parser.add_argument("--summarize", action="store_true", help="also call Gemini for the executive summary (requires GCP access)")
    args = parser.parse_args(argv)

    seed = random_seed() if args.seed is None else args.seed
    print(f"data seed: {seed}")
    lenses, _ = resolve_lenses(None, None)
    ingest = run_cloud_ingest(args.data_dir, seed, data_sources(lenses)) if args.upload else None

    history = run_local_refresh(seed, args.data_dir, args.snapshot_path, summarize=args.summarize, ingest=ingest)
    latest = history["snapshots"][history["latest_as_of_date"]]
    sources = sorted(set(latest["metrics_source"].values()))
    print(
        f"refresh complete: {len(history['available_as_of_dates'])} period anchor(s), "
        f"{len(latest['decisions'])} decision item(s) at latest ({history['latest_as_of_date']}), "
        f"metrics from {'+'.join(sources)}, snapshot -> {args.snapshot_path}"
    )
    if args.summarize and not latest["gemini_summary"]:
        print("warning: Gemini summary generation failed or was unavailable; gemini_summary is null.")

    if args.upload:
        for uri in ingest.uploaded:
            print(f"uploaded {uri}")
        print(f"uploaded {upload_snapshot_file(args.snapshot_path)}")


if __name__ == "__main__":
    main()
