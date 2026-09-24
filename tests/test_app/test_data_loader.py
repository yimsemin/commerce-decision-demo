from __future__ import annotations

import json

import pytest

from commerce_lab.app.data_loader import load_snapshot_from_gcs, load_snapshot_from_local


def test_load_snapshot_from_local_raises_clear_error_when_missing(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(FileNotFoundError, match="commerce_lab.pipeline.refresh"):
        load_snapshot_from_local(missing)


def test_load_snapshot_from_local_reads_json(tmp_path):
    path = tmp_path / "app_snapshot.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    assert load_snapshot_from_local(path) == {"schema_version": 1}


class FakeBlob:
    def __init__(self, text):
        self._text = text

    def download_as_text(self):
        return self._text


class FakeBucket:
    def __init__(self, blob):
        self._blob = blob

    def blob(self, path):
        return self._blob


class FakeClient:
    def __init__(self, text):
        self._bucket = FakeBucket(FakeBlob(text))

    def bucket(self, name):
        return self._bucket


def test_load_snapshot_from_gcs_uses_injected_client():
    client = FakeClient(json.dumps({"schema_version": 1, "as_of_date": "2026-09-21"}))
    result = load_snapshot_from_gcs("gs://demo-bucket/snapshot/app_snapshot.json", client=client)
    assert result == {"schema_version": 1, "as_of_date": "2026-09-21"}
