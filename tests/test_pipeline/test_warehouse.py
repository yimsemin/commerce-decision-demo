from __future__ import annotations

import datetime as dt

from commerce_lab.lenses.registry import compute_sections, load_lenses, metrics_source
from commerce_lab.metrics.periods import compute_period_window
from commerce_lab.metrics.warehouse import Warehouse, verify_loaded
import pytest


class FakeClient:
    def __init__(self, rows):
        self.rows = rows
        self.queries: list[tuple[str, list]] = []

    def query(self, sql, job_config=None):
        self.queries.append((sql, job_config))
        rows = self.rows(sql) if callable(self.rows) else self.rows
        return type("Job", (), {"result": lambda _self: rows})()


def make_warehouse(rows):
    client = FakeClient(rows)
    wh = Warehouse(client, "proj", "metrics", lambda n, t, v: (n, t, v), lambda query_parameters: query_parameters)
    return wh, client


WINDOW = compute_period_window(dt.date(2026, 9, 21), 30)


def test_call_builds_a_parameterized_function_query():
    wh, client = make_warehouse([{"brand": "A", "change": 1.5}])
    rows = wh.call("sales_by_brand_channel", WINDOW, order_by="ABS(change) DESC")
    sql, params = client.queries[0]
    assert sql == "SELECT * FROM `proj.metrics.sales_by_brand_channel`(@as_of, @window_days) ORDER BY ABS(change) DESC"
    assert params == [("as_of", "DATE", dt.date(2026, 9, 21)), ("window_days", "INT64", 30)]
    assert rows == [{"brand": "A", "change": 1.5}]


def test_inventory_call_passes_lens_params():
    wh, client = make_warehouse([])
    wh.call_inventory(WINDOW, 14, 7, 60)
    sql, params = client.queries[0]
    assert "inventory_risk`(@as_of, @velocity_window_days, @stockout_days, @excess_days)" in sql
    assert ("stockout_days", "FLOAT64", 7.0) in params and ("velocity_window_days", "INT64", 14) in params


def test_period_window_days():
    assert WINDOW.days == 30


def test_lenses_with_a_warehouse_are_computed_in_bigquery_not_pandas(datasets):
    lenses = load_lenses(["sales", "customer"])

    def rows(sql):
        if "sales_summary" in sql:
            return [dict(zip(
                ["current_net_revenue", "current_orders", "current_units_sold", "current_aov",
                 "previous_net_revenue", "previous_orders", "previous_units_sold", "previous_aov",
                 "pct_net_revenue", "pct_orders", "pct_units_sold", "pct_aov"], range(12)))]
        if "customer_mix" in sql:
            return [{"current_new_share": 0.2, "previous_new_share": 0.5}]
        if "repeat_purchase_rate" in sql:
            return [{"repeat_purchase_rate": 0.4}]
        return []

    wh, client = make_warehouse(rows)
    sections, _ = compute_sections(lenses, datasets, WINDOW, warehouse=wh)

    assert sections["sales"]["summary"]["current"]["net_revenue"] == 0
    assert sections["sales"]["summary"]["pct_change"]["aov"] == 11
    assert sections["customer"]["mix"]["current_new_share"] == 0.2
    assert sections["customer"]["repeat_purchase_rate"] == 0.4
    assert all(metrics_source(lens, wh) == "bigquery" for lens in lenses)
    assert all(metrics_source(lens, None) == "pandas" for lens in lenses)


def test_verify_loaded_fails_loudly_on_a_row_count_mismatch(datasets):
    expected = {n: len(datasets[n]) for n in ("orders", "marketing", "inventory", "customers", "skus")}
    wh, _ = make_warehouse(lambda sql: [{"n": expected[sql.rsplit(".", 1)[-1].strip("`")]}])
    verify_loaded(wh, datasets)  # matches: no error

    wrong, _ = make_warehouse([{"n": 1}])
    with pytest.raises(RuntimeError, match="do not match"):
        verify_loaded(wrong, datasets)
