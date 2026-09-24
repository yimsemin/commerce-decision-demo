from __future__ import annotations

from commerce_lab.metrics.marketing import cac_by_channel, marketing_by_segment


def test_marketing_by_segment_roas_matches_manual_calc(datasets, window):
    marketing = datasets["marketing"]
    result = marketing_by_segment(marketing, window, ["brand", "marketing_channel"])

    row = result[(result["brand"] == "Kestrel") & (result["marketing_channel"] == "paid_social")].iloc[0]
    expected_roas = row["current_attributed_revenue"] / row["current_spend"]
    assert abs(row["current_roas"] - expected_roas) < 1e-9


def test_cac_by_channel_has_positive_values_where_defined(datasets, window):
    result = cac_by_channel(datasets["marketing"], datasets["customers"], window)
    defined = result.dropna(subset=["cac"])
    assert len(defined) > 0
    assert (defined["cac"] > 0).all()
