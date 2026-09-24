"""GCP resource configuration for the ingestion/refresh pipeline.

Every value is read from the environment so no project-specific detail
(project ID, bucket name) is hardcoded or committed. Dataset/table names
have sensible portfolio-scale defaults since they are not secrets.

Required at pipeline runtime (not at import time, so this module can be
imported and unit tested without any of these being set):
    GCP_PROJECT_ID
    GCS_BUCKET
"""

from __future__ import annotations

import os


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


class GcpConfig:
    def __init__(self) -> None:
        self.project_id = _env("GCP_PROJECT_ID")
        self.region = _env("GCP_REGION", "asia-northeast3")
        self.bucket = _env("GCS_BUCKET")
        self.bq_dataset_raw = _env("BQ_DATASET_RAW", "raw")
        self.bq_dataset_staging = _env("BQ_DATASET_STAGING", "staging")
        self.bq_dataset_metrics = _env("BQ_DATASET_METRICS", "metrics")

    def require_project_and_bucket(self) -> None:
        missing = [
            name
            for name, value in (("GCP_PROJECT_ID", self.project_id), ("GCS_BUCKET", self.bucket))
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + ". These identify the owner's GCP project/bucket and are never hardcoded."
            )


# Dataset -> local CSV file name produced by commerce_lab.datagen.generator.
RAW_TABLES = ["orders", "marketing", "inventory", "customers", "skus"]
