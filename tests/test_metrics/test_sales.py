from __future__ import annotations

from commerce_lab.metrics.sales import sales_by_segment, sales_summary


def test_sales_summary_matches_raw_aggregation(datasets, window):
    orders = datasets["orders"]
    summary = sales_summary(orders, window)

    current_orders = orders[window.in_current(orders["order_date"])]
    assert summary["current"]["orders"] == current_orders["order_id"].nunique()
    assert summary["current"]["net_revenue"] == round(float(current_orders["net_sales"].sum()), 2)
    assert summary["current"]["units_sold"] == int(current_orders["quantity"].sum())

    expected_aov = round(summary["current"]["net_revenue"] / summary["current"]["orders"], 2)
    assert summary["current"]["aov"] == expected_aov


def test_sales_by_segment_sorted_by_absolute_change(datasets, window):
    orders = datasets["orders"]
    result = sales_by_segment(orders, window, ["brand", "channel"])

    assert list(result.columns[:2]) == ["brand", "channel"]
    changes = result["change"].abs().tolist()
    assert changes == sorted(changes, reverse=True)
