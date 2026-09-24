"""End-to-end refresh: the manual local-dev equivalent of the full
PROJECT.md §10 automation flow (generate -> GCS -> BigQuery -> metrics ->
snapshot -> AI summary).

Local mode (default): generate synthetic data, compute metrics/decisions,
write `app_snapshot.json` locally. No GCP calls, no credentials needed --
this is what M5's local app dev server reads.

    python -m commerce_lab.pipeline.refresh

Cloud mode (--upload): additionally uploads the generated CSVs to GCS,
loads BigQuery raw tables, and uploads the snapshot to its private GCS
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
    seed: int, data_dir: Path, snapshot_path: Path, summarize: bool = False
) -> dict:
    """Generate data, build the snapshot history (one entry per comparison-
    period anchor), write both locally. Returns the snapshot dict (mainly
    so callers/tests can inspect it without a second file read).

    Only the latest anchor gets a live Gemini call when `summarize=True` --
    older anchors keep `gemini_summary: None` and fall back to the app's
    deterministic summary, so this doesn't multiply Gemini cost/latency."""
    lenses, _ = resolve_lenses(None, None)  # enabled lenses from config/lab.toml
    datasets = generate_all(seed=seed, data_sources=data_sources(lenses))
    write_datasets(datasets, data_dir)
    history = build_snapshot_history(datasets, lenses=lenses)

    if summarize:
        from ..gemini.summarize import generate_executive_summary

        latest = history["snapshots"][history["latest_as_of_date"]]
        latest["gemini_summary"] = generate_executive_summary(latest)

    write_snapshot(history, snapshot_path)
    return history


def run_cloud_upload(data_dir: Path, snapshot_path: Path, data_sources=()) -> list[str]:
    """Upload generated CSVs to GCS + load BigQuery raw tables, then
    upload the snapshot to its fixed private object. Performs live GCP
    calls; requires GCP_PROJECT_ID/GCS_BUCKET and credentials."""
    from google.cloud import storage

    from .config import GcpConfig
    from .gcs import upload_snapshot
    from .ingest import run_ingest

    cfg = GcpConfig()
    cfg.require_project_and_bucket()

    uris = run_ingest(data_dir, data_sources=data_sources)

    storage_client = storage.Client(project=cfg.project_id)
    snapshot_uri = upload_snapshot(storage_client, cfg.bucket, snapshot_path)
    uris.append(snapshot_uri)
    return uris


def main(argv: list[str] | None = None) -> None:
    from ..datagen import config as datagen_config

    parser = argparse.ArgumentParser(description="Run the local (and optionally cloud) refresh workflow.")
    parser.add_argument("--seed", type=int, default=datagen_config.DEFAULT_SEED)
    parser.add_argument("--data-dir", type=Path, default=Path("data/generated"))
    parser.add_argument("--snapshot-path", type=Path, default=Path("data/generated/app_snapshot.json"))
    parser.add_argument("--upload", action="store_true", help="also upload to GCS and load BigQuery (requires GCP access)")
    parser.add_argument("--summarize", action="store_true", help="also call Gemini for the executive summary (requires GCP access)")
    args = parser.parse_args(argv)

    history = run_local_refresh(args.seed, args.data_dir, args.snapshot_path, summarize=args.summarize)
    latest = history["snapshots"][history["latest_as_of_date"]]
    print(
        f"local refresh complete: {len(history['available_as_of_dates'])} period anchor(s), "
        f"{len(latest['decisions'])} decision item(s) at latest ({history['latest_as_of_date']}), "
        f"snapshot -> {args.snapshot_path}"
    )
    if args.summarize and not latest["gemini_summary"]:
        print("warning: Gemini summary generation failed or was unavailable; gemini_summary is null.")

    if args.upload:
        lenses, _ = resolve_lenses(None, None)
        uris = run_cloud_upload(args.data_dir, args.snapshot_path, data_sources(lenses))
        for uri in uris:
            print(f"uploaded {uri}")


if __name__ == "__main__":
    main()
