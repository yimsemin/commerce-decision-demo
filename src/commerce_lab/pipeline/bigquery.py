"""BigQuery load helpers for the raw layer.

Raw tables are declared explicitly in `sql/raw/*.sql` (schema is not
autodetected, so column types are predictable and match the generator's
output). Each refresh does a full `WRITE_TRUNCATE` load per table: data
volumes are deliberately small and there is no need for incremental/append
semantics in this portfolio sample.
"""

from __future__ import annotations


def table_ref(project_id: str, dataset: str, table_name: str) -> str:
    return f"{project_id}.{dataset}.{table_name}"


def load_csv_to_table(client, gcs_uri: str, project_id: str, dataset: str, table_name: str, job_config_cls, source_format) -> None:
    """Load one CSV (already uploaded to GCS) into its raw table.

    `client` is a `google.cloud.bigquery.Client`. `job_config_cls` and
    `source_format` are passed in (rather than imported at call time) so
    this function's control flow can be unit tested with lightweight
    fakes instead of the real SDK.
    """
    destination = table_ref(project_id, dataset, table_name)
    job_config = job_config_cls(
        source_format=source_format,
        skip_leading_rows=1,
        write_disposition="WRITE_TRUNCATE",
    )
    load_job = client.load_table_from_uri(gcs_uri, destination, job_config=job_config)
    load_job.result()  # block until the load finishes or raises


def load_all_raw_tables(client, uploaded_uris: list[str], project_id: str, dataset: str, job_config_cls, source_format) -> None:
    for uri in uploaded_uris:
        table_name = uri.rsplit("/", 1)[-1].removesuffix(".csv")
        load_csv_to_table(client, uri, project_id, dataset, table_name, job_config_cls, source_format)


def raw_table_ddl(dataset: str, source) -> str:
    """CREATE TABLE IF NOT EXISTS for a lens-declared `DataSource` (the
    built-in tables are declared in sql/raw/create_raw_tables.sql)."""
    cols = ",\n    ".join(f"{name} {bq_type}" for name, bq_type in source.columns.items())
    return f"CREATE TABLE IF NOT EXISTS {dataset}.{source.name} (\n    {cols}\n);"


def ensure_extra_raw_tables(client, project_id: str, dataset: str, sources) -> None:
    for source in sources:
        client.query(raw_table_ddl(dataset, source), project=project_id).result()
