from __future__ import annotations

import pytest

from commerce_lab.pipeline.config import GcpConfig


def test_require_project_and_bucket_raises_when_missing(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    cfg = GcpConfig()
    with pytest.raises(RuntimeError, match="GCP_PROJECT_ID"):
        cfg.require_project_and_bucket()


def test_require_project_and_bucket_passes_when_set(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "demo-project")
    monkeypatch.setenv("GCS_BUCKET", "demo-bucket")
    cfg = GcpConfig()
    cfg.require_project_and_bucket()  # must not raise


def test_defaults(monkeypatch):
    monkeypatch.delenv("GCP_REGION", raising=False)
    cfg = GcpConfig()
    assert cfg.region == "asia-northeast3"
    assert cfg.bq_dataset_raw == "raw"
    assert cfg.bq_dataset_staging == "staging"
    assert cfg.bq_dataset_metrics == "metrics"
