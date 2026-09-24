from __future__ import annotations

from commerce_lab.app.view_helpers import (
    fallback_executive_summary,
    format_currency,
    format_pct,
    kpi_trend,
    severity_counts,
    top_issues,
)


def test_severity_counts():
    decisions = [{"severity": "high"}, {"severity": "high"}, {"severity": "low"}]
    assert severity_counts(decisions) == {"high": 2, "medium": 0, "low": 1}


def test_top_issues_orders_by_severity():
    decisions = [
        {"severity": "low", "headline": "a"},
        {"severity": "high", "headline": "b"},
        {"severity": "medium", "headline": "c"},
    ]
    result = top_issues(decisions, n=2)
    assert [d["headline"] for d in result] == ["b", "c"]


def test_format_pct_handles_none():
    assert format_pct(None) == "n/a"
    assert format_pct(12.3) == "+12.3%"
    assert format_pct(-5.0) == "-5.0%"


def test_format_currency_handles_none():
    assert format_currency(None) == "n/a"
    assert format_currency(1234.5) == "$1,234"


def test_format_currency_handles_negative():
    assert format_currency(-2631.28) == "-$2,631"


def test_top_issues_uses_revenue_impact_as_tiebreak_within_severity():
    decisions = [
        {"severity": "high", "headline": "small-impact-high", "supporting_kpi": {"estimated_revenue_impact": -100}},
        {"severity": "high", "headline": "big-impact-high", "supporting_kpi": {"estimated_revenue_impact": -5000}},
        {"severity": "medium", "headline": "no-impact-medium", "supporting_kpi": {}},
    ]
    result = top_issues(decisions, n=3)
    assert [d["headline"] for d in result] == ["big-impact-high", "small-impact-high", "no-impact-medium"]


def test_top_issues_severity_always_outranks_dollar_impact():
    decisions = [
        {"severity": "medium", "headline": "huge-impact-medium", "supporting_kpi": {"estimated_revenue_impact": -100000}},
        {"severity": "high", "headline": "tiny-impact-high", "supporting_kpi": {"estimated_revenue_impact": -1}},
    ]
    result = top_issues(decisions, n=2)
    assert [d["headline"] for d in result] == ["tiny-impact-high", "huge-impact-medium"]


def test_fallback_executive_summary_mentions_top_issue():
    decisions = [{"severity": "high", "headline": "Stock-out risk for SKU AUR-003"}]
    sales_summary = {"pct_change": {"net_revenue": -5.2}}
    summary = fallback_executive_summary(decisions, sales_summary)
    assert "Stock-out risk for SKU AUR-003" in summary
    assert "-5.2%" in summary


def test_fallback_executive_summary_ko_localizes_known_issue_headline():
    decisions = [
        {
            "issue_type": "stockout_risk",
            "severity": "high",
            "headline": "Stock-out risk for SKU AUR-003 (Aurora)",
            "affected": {"sku_id": "AUR-003", "brand": "Aurora"},
            "supporting_kpi": {"on_hand": 0, "velocity_per_day": 2.07, "days_of_cover": 0.0},
        }
    ]
    sales_summary = {"pct_change": {"net_revenue": -5.2}}
    summary = fallback_executive_summary(decisions, sales_summary, lang="ko")
    assert "AUR-003" in summary
    assert "-5.2%" in summary
    assert "Stock-out risk" not in summary  # localized, not the stale English headline


def _fake_history(*, roas_by_date: dict) -> dict:
    dates = sorted(roas_by_date)
    return {
        "available_as_of_dates": dates,
        "latest_as_of_date": dates[-1],
        "snapshots": {
            d: {
                "marketing": {"by_segment": [{"brand": "Kestrel", "marketing_channel": "paid_social", "current_roas": roas_by_date[d]}]},
                "inventory": {"risk_by_sku": []},
                "sales": {"by_brand_channel": []},
                "customer": {"mix": {"current_new_share": None}},
            }
            for d in dates
        },
    }


def test_kpi_trend_collects_values_across_anchors_in_order():
    history = _fake_history(roas_by_date={"2026-08-01": 2.5, "2026-08-16": 1.8, "2026-08-31": 1.1})
    decision = {"issue_type": "marketing_efficiency_decline", "affected": {"brand": "Kestrel", "marketing_channel": "paid_social"}}
    trend = kpi_trend(history, decision)
    assert [p["as_of"] for p in trend] == ["2026-08-01", "2026-08-16", "2026-08-31"]
    assert [p["value"] for p in trend] == [2.5, 1.8, 1.1]


def test_kpi_trend_skips_anchors_where_segment_is_absent():
    history = _fake_history(roas_by_date={"2026-08-01": 2.5})
    # a segment that isn't in the fake history at all
    decision = {"issue_type": "marketing_efficiency_decline", "affected": {"brand": "Aurora", "marketing_channel": "affiliate"}}
    assert kpi_trend(history, decision) == []


def test_kpi_trend_unknown_issue_type_returns_empty():
    history = _fake_history(roas_by_date={"2026-08-01": 2.5})
    decision = {"issue_type": "something_new", "affected": {}}
    assert kpi_trend(history, decision) == []
