"""BigQuery as the metrics engine.

The KPI formulas live in `sql/metrics/*.sql` as table functions in the
`metrics` dataset; this module only calls them (one query per function per
comparison anchor) and hands the rows to the lenses. The pandas functions
next to it (`sales.py`, `marketing.py`, ...) remain as the local-development
and test reference; `commerce_lab.pipeline.parity` compares the two.
"""

from __future__ import annotations

from ..pipeline.serialize import to_json_safe
from .periods import PeriodWindow


class Warehouse:
    """Runs `metrics.<function>(...)` queries. `client` is a
    `google.cloud.bigquery.Client` (or a test double with the same
    `query(sql, job_config=...).result()` shape); `query_params` builds the
    scalar parameters so this module needs no BigQuery import itself."""

    def __init__(self, client, project_id: str, dataset: str, scalar_param, query_job_config):
        self._client = client
        self._project_id = project_id
        self._dataset = dataset
        self._scalar_param = scalar_param
        self._job_config = query_job_config

    @classmethod
    def connect(cls, project_id: str, dataset: str = "metrics") -> "Warehouse":
        from google.cloud import bigquery

        return cls(
            bigquery.Client(project=project_id),
            project_id,
            dataset,
            bigquery.ScalarQueryParameter,
            bigquery.QueryJobConfig,
        )

    def call(self, function: str, window: PeriodWindow, extra: dict | None = None, order_by: str | None = None) -> list[dict]:
        """Rows of `metrics.<function>(as_of, window_days[, extra...])`.
        `extra` values are (BigQuery type, value) pairs, in argument order."""
        params = [("as_of", "DATE", window.current_end), ("window_days", "INT64", window.days)]
        params += [(name, bq_type, value) for name, (bq_type, value) in (extra or {}).items()]
        return self._run(function, params, order_by)

    def call_inventory(self, window: PeriodWindow, velocity_window_days: int, stockout_days: float, excess_days: float) -> list[dict]:
        params = [
            ("as_of", "DATE", window.current_end),
            ("velocity_window_days", "INT64", int(velocity_window_days)),
            ("stockout_days", "FLOAT64", float(stockout_days)),
            ("excess_days", "FLOAT64", float(excess_days)),
        ]
        return self._run("inventory_risk", params, "days_of_cover ASC, sku_id")

    def view(self, name: str) -> list[dict]:
        sql = f"SELECT * FROM `{self._project_id}.{self._dataset}.{name}`"
        return [to_json_safe(dict(r)) for r in self._client.query(sql).result()]

    def _run(self, function: str, params: list[tuple[str, str, object]], order_by: str | None) -> list[dict]:
        placeholders = ", ".join(f"@{name}" for name, _, _ in params)
        sql = f"SELECT * FROM `{self._project_id}.{self._dataset}.{function}`({placeholders})"
        if order_by:
            sql += f" ORDER BY {order_by}"
        config = self._job_config(query_parameters=[self._scalar_param(n, t, v) for n, t, v in params])
        return [to_json_safe(dict(r)) for r in self._client.query(sql, job_config=config).result()]

    def row_counts(self, raw_dataset: str = "raw") -> dict[str, int]:
        """Row count per raw table, used to confirm the load before computing."""
        out = {}
        for table in ("orders", "marketing", "inventory", "customers", "skus"):
            sql = f"SELECT COUNT(*) AS n FROM `{self._project_id}.{raw_dataset}.{table}`"
            out[table] = int(next(iter(self._client.query(sql).result()))["n"])
        return out


def verify_loaded(warehouse: Warehouse, datasets: dict, raw_dataset: str = "raw") -> None:
    """Fails loudly if BigQuery does not hold exactly the rows just
    generated -- the metrics must describe this run's data, not a stale or
    partial load."""
    expected = {name: len(datasets[name]) for name in ("orders", "marketing", "inventory", "customers", "skus")}
    actual = warehouse.row_counts(raw_dataset)
    if actual != expected:
        raise RuntimeError(f"BigQuery raw tables do not match the generated data: expected {expected}, found {actual}.")
