from __future__ import annotations

from commerce_lab.app.i18n import localize_decision, severity_badge, t


def test_t_falls_back_to_default_lang_for_unknown_lang():
    assert t("tab.overview", "fr") == t("tab.overview", "ko")


def test_t_formats_with_kwargs():
    result = t("period.selector_label", "ko")
    assert isinstance(result, str) and result


def test_severity_badge_known_and_unknown():
    assert "high" in severity_badge("high", "en")
    assert severity_badge("weird", "en") == "weird"


def test_localize_decision_marketing_efficiency_ko_and_en():
    decision = {
        "issue_type": "marketing_efficiency_decline",
        "headline": "Marketing efficiency deteriorating for Kestrel / paid_social",
        "severity": "high",
        "supporting_kpi": {
            "current_roas": 1.14,
            "previous_roas": 2.84,
            "roas_change_pct": -59.9,
            "current_spend": 11668.07,
        },
        "likely_drivers": ["stale english sentence"],
        "affected": {"brand": "Kestrel", "marketing_channel": "paid_social"},
        "possible_action": "stale",
        "kpi_to_monitor": "roas[Kestrel / paid_social]",
    }

    ko = localize_decision(decision, lang="ko")
    assert "Kestrel" in ko["headline"] and "악화" in ko["headline"]
    assert ko["kpi_to_monitor"] == decision["kpi_to_monitor"]  # identifiers untouched
    assert ko["supporting_kpi"] == decision["supporting_kpi"]  # facts untouched

    en = localize_decision(decision, lang="en")
    assert en["headline"] == "Marketing efficiency deteriorating for Kestrel / paid_social"


def test_localize_decision_unknown_issue_type_returns_unchanged():
    decision = {"issue_type": "something_new", "headline": "as-is"}
    assert localize_decision(decision, lang="ko") == decision


def test_localize_decision_all_known_issue_types_do_not_raise():
    fixtures = [
        {
            "issue_type": "stockout_risk",
            "affected": {"sku_id": "AUR-003", "brand": "Aurora"},
            "supporting_kpi": {"on_hand": 0, "velocity_per_day": 2.07, "days_of_cover": 0.0},
        },
        {
            "issue_type": "excess_inventory_risk",
            "affected": {"sku_id": "AUR-006", "brand": "Aurora"},
            "supporting_kpi": {"on_hand": 57, "velocity_per_day": 0.86, "days_of_cover": 66.3},
        },
        {
            "issue_type": "sales_decline",
            "affected": {"brand": "Marlow", "channel": "retail_partner"},
            "supporting_kpi": {"current_net_revenue": 3593.36, "previous_net_revenue": 6224.64, "pct_change": -42.3},
        },
        {
            "issue_type": "customer_mix_shift",
            "affected": {},
            "supporting_kpi": {"current_new_share": 0.196, "previous_new_share": 0.545, "pct_change": -64.0},
        },
    ]
    for base in fixtures:
        for lang in ("ko", "en"):
            out = localize_decision({**base, "headline": "x", "likely_drivers": [], "possible_action": "x", "severity": "high", "kpi_to_monitor": "k"}, lang=lang)
            assert out["headline"]
            assert out["possible_action"]
            assert out["likely_drivers"]
