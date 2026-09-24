"""Cloud Storage upload helpers.

Uses the `google-cloud-storage` Python SDK (the programmatic equivalent of
`gcloud storage`) rather than the legacy `gsutil`/boto-style API, per
project convention. Client construction is separated from path/business
logic so the logic can be unit tested without live GCP credentials.
"""

from __future__ import annotations

from pathlib import Path


def object_path(dataset_name: str, run_date: str, table_name: str) -> str:
    """Build the GCS object path for one raw CSV file.

    Layout: raw/<dataset_name>/<run_date>/<table_name>.csv
    `run_date` (YYYY-MM-DD) partitions each refresh run so old snapshots
    are not silently overwritten.
    """
    return f"raw/{dataset_name}/{run_date}/{table_name}.csv"


SNAPSHOT_OBJECT_PATH = "snapshot/app_snapshot.json"


def upload_snapshot(client, bucket_name: str, snapshot_path: Path) -> str:
    """Upload the app-ready snapshot to its fixed, private object path.
    The app always reads this one path -- no per-run partitioning, since
    only the latest snapshot is ever served."""
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(SNAPSHOT_OBJECT_PATH)
    blob.upload_from_filename(str(snapshot_path))
    return f"gs://{bucket_name}/{SNAPSHOT_OBJECT_PATH}"


def upload_dataset(client, bucket_name: str, local_dir: Path, dataset_name: str, run_date: str) -> list[str]:
    """Upload every CSV in `local_dir` to the bucket, return the GCS URIs.

    `client` is a `google.cloud.storage.Client` (or a test double exposing
    the same `.bucket(name).blob(path).upload_from_filename(path)` shape).
    """
    bucket = client.bucket(bucket_name)
    uploaded_uris = []
    for csv_path in sorted(local_dir.glob("*.csv")):
        table_name = csv_path.stem
        path = object_path(dataset_name, run_date, table_name)
        blob = bucket.blob(path)
        blob.upload_from_filename(str(csv_path))
        uploaded_uris.append(f"gs://{bucket_name}/{path}")
    return uploaded_uris
