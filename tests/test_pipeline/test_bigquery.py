from __future__ import annotations

from commerce_lab.pipeline.bigquery import load_all_raw_tables, load_csv_to_table, table_ref


def test_table_ref_format():
    assert table_ref("demo-project", "raw", "orders") == "demo-project.raw.orders"


class FakeLoadJob:
    def __init__(self):
        self.result_called = False

    def result(self):
        self.result_called = True


class FakeJobConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeBqClient:
    def __init__(self):
        self.calls = []
        self.jobs = []

    def load_table_from_uri(self, uri, destination, job_config):
        job = FakeLoadJob()
        self.calls.append({"uri": uri, "destination": destination, "job_config": job_config})
        self.jobs.append(job)
        return job


def test_load_csv_to_table_uses_write_truncate_and_waits_for_result():
    client = FakeBqClient()
    load_csv_to_table(
        client,
        "gs://demo-bucket/raw/commerce/2026-09-22/orders.csv",
        "demo-project",
        "raw",
        "orders",
        FakeJobConfig,
        source_format="CSV",
    )

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["uri"] == "gs://demo-bucket/raw/commerce/2026-09-22/orders.csv"
    assert call["destination"] == "demo-project.raw.orders"
    assert call["job_config"].kwargs == {
        "source_format": "CSV",
        "skip_leading_rows": 1,
        "write_disposition": "WRITE_TRUNCATE",
    }
    assert client.jobs[0].result_called is True


def test_load_all_raw_tables_derives_table_name_from_uri():
    client = FakeBqClient()
    uris = [
        "gs://demo-bucket/raw/commerce/2026-09-22/orders.csv",
        "gs://demo-bucket/raw/commerce/2026-09-22/marketing.csv",
    ]
    load_all_raw_tables(client, uris, "demo-project", "raw", FakeJobConfig, source_format="CSV")

    destinations = [c["destination"] for c in client.calls]
    assert destinations == ["demo-project.raw.orders", "demo-project.raw.marketing"]
