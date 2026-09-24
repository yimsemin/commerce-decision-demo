from __future__ import annotations

from commerce_lab.metrics.inventory import inventory_risk_by_sku


def test_inventory_risk_flags_are_internally_consistent(datasets, window):
    result = inventory_risk_by_sku(datasets["inventory"], as_of=window.current_end)

    for _, row in result.iterrows():
        if row["velocity"] == 0:
            assert row["days_of_cover"] is None
        else:
            assert row["days_of_cover"] == round(row["on_hand"] / row["velocity"], 1)
            assert row["stockout_risk"] == (row["days_of_cover"] < 7)
