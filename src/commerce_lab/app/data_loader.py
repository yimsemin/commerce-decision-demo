"""Loads the app-ready snapshot -- the *only* thing this app ever reads.

Per the owner-approved architecture, public app traffic never queries
BigQuery or Gemini directly. Locally this reads a file from disk; when
deployed, `SNAPSHOT_SOURCE=gs://<bucket>/snapshot/app_snapshot.json`
switches it to a GCS read instead (still just a static-object fetch, not
a query).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_LOCAL_SNAPSHOT_PATH = Path("data/generated/app_snapshot.json")


def load_snapshot() -> dict:
    source = os.environ.get("SNAPSHOT_SOURCE")
    if source and source.startswith("gs://"):
        return load_snapshot_from_gcs(source)
    return load_snapshot_from_local(Path(os.environ.get("SNAPSHOT_LOCAL_PATH", str(DEFAULT_LOCAL_SNAPSHOT_PATH))))


def load_snapshot_from_local(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"No snapshot found at {path}. Run `python -m commerce_lab.pipeline.refresh` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_snapshot_from_gcs(uri: str, client=None) -> dict:
    """`client` is injectable for testing; defaults to a real
    `google.cloud.storage.Client()` when not provided."""
    if client is None:
        from google.cloud import storage

        client = storage.Client()

    bucket_name, _, blob_path = uri.removeprefix("gs://").partition("/")
    blob = client.bucket(bucket_name).blob(blob_path)
    return json.loads(blob.download_as_text())
