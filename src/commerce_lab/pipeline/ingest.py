"""End-to-end local-data -> GCS -> BigQuery raw-layer ingestion.

Usage (requires GCP_PROJECT_ID, GCS_BUCKET env vars and `gcloud auth
application-default login`, plus the buckets/datasets/tables already
provisioned via scripts/provision_gcp.sh):

    python -m commerce_lab.pipeline.ingest --data-dir data/generated

This is the M2 half of the refresh flow described in PROJECT.md §10
(steps 2-3: place source files in Cloud Storage, load/update BigQuery).
Steps 4-6 (metrics, snapshot, AI summary) are separate later modules.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from .config import GcpConfig
from .gcs import upload_dataset
from .bigquery import ensure_extra_raw_tables, load_all_raw_tables


def run_ingest(data_dir: Path, run_date: str | None = None, data_sources=()) -> list[str]:
    """Upload `data_dir`'s CSVs to GCS and load them into the raw BigQuery
    dataset. Returns the list of GCS URIs written. Raises if required GCP
    env vars are unset -- this function performs live GCP calls."""
    from google.cloud import bigquery, storage  # deferred: heavy, optional import

    cfg = GcpConfig()
    cfg.require_project_and_bucket()
    run_date = run_date or dt.date.today().isoformat()

    storage_client = storage.Client(project=cfg.project_id)
    uris = upload_dataset(storage_client, cfg.bucket, data_dir, "commerce", run_date)

    bq_client = bigquery.Client(project=cfg.project_id)
    ensure_extra_raw_tables(bq_client, cfg.project_id, cfg.bq_dataset_raw, data_sources)
    load_all_raw_tables(
        bq_client,
        uris,
        cfg.project_id,
        cfg.bq_dataset_raw,
        bigquery.LoadJobConfig,
        bigquery.SourceFormat.CSV,
    )
    return uris


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Upload generated CSVs to GCS and load BigQuery raw tables.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/generated"))
    parser.add_argument("--run-date", type=str, default=None)
    args = parser.parse_args(argv)

    uris = run_ingest(args.data_dir, args.run_date)
    for uri in uris:
        print(f"loaded {uri}")


if __name__ == "__main__":
    main()
