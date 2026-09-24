from __future__ import annotations

from commerce_lab.pipeline.gcs import object_path, upload_dataset, upload_snapshot


def test_object_path_layout():
    assert object_path("commerce", "2026-09-22", "orders") == "raw/commerce/2026-09-22/orders.csv"


class FakeBlob:
    def __init__(self, path, sink):
        self.path = path
        self._sink = sink

    def upload_from_filename(self, local_path):
        self._sink.append((self.path, local_path))


class FakeBucket:
    def __init__(self, name, sink):
        self.name = name
        self._sink = sink

    def blob(self, path):
        return FakeBlob(path, self._sink)


class FakeClient:
    def __init__(self):
        self.uploads = []

    def bucket(self, name):
        return FakeBucket(name, self.uploads)


def test_upload_dataset_uploads_every_csv_and_returns_uris(tmp_path):
    (tmp_path / "orders.csv").write_text("order_id\nORD-000001\n")
    (tmp_path / "marketing.csv").write_text("date\n2026-09-01\n")
    (tmp_path / "notes.txt").write_text("ignored, not a csv")

    client = FakeClient()
    uris = upload_dataset(client, "demo-bucket", tmp_path, "commerce", "2026-09-22")

    assert uris == [
        "gs://demo-bucket/raw/commerce/2026-09-22/marketing.csv",
        "gs://demo-bucket/raw/commerce/2026-09-22/orders.csv",
    ]
    assert len(client.uploads) == 2
    uploaded_paths = {path for path, _local in client.uploads}
    assert uploaded_paths == {
        "raw/commerce/2026-09-22/marketing.csv",
        "raw/commerce/2026-09-22/orders.csv",
    }


def test_upload_snapshot_uses_fixed_private_path(tmp_path):
    snapshot_file = tmp_path / "app_snapshot.json"
    snapshot_file.write_text("{}")

    client = FakeClient()
    uri = upload_snapshot(client, "demo-bucket", snapshot_file)

    assert uri == "gs://demo-bucket/snapshot/app_snapshot.json"
    assert client.uploads == [("snapshot/app_snapshot.json", str(snapshot_file))]
