"""Demonstrates PROJECT.md §3 question 7 ("after an action or simulated
intervention, did the relevant KPI improve?"). There is no separate
verification feature -- the same deterministic rule that detects an
issue is re-run on fresher data to check it. This test constructs a
"before" state (issue detected) and an "after" state (the same KPI has
recovered past the rule's threshold) and asserts the issue is correctly
no longer flagged, i.e. the rule engine recognizes recovery, not just
decline. See docs/decision_rules.md.
"""

from __future__ import annotations

from commerce_lab.lenses import inventory, marketing
from commerce_lab.lenses.registry import resolve_params


def detect_inventory_issues(rows: list[dict]):
    return inventory.LENS.detect({"risk_by_sku": rows}, resolve_params(inventory.LENS))


def detect_marketing_efficiency_issues(rows: list[dict]):
    return marketing.LENS.detect({"by_segment": rows}, resolve_params(marketing.LENS))


def test_stockout_issue_resolves_after_simulated_replenishment():
    before = [
        {
                "sku_id": "AUR-003",
                "brand": "Aurora",
                "on_hand": 10,
                "velocity": 3.5,
                "days_of_cover": 2.9,
                "stockout_risk": True,
                "excess_risk": False,
        }
    ]
    before_issues = detect_inventory_issues(before)
    assert len(before_issues) == 1
    assert before_issues[0].issue_type == "stockout_risk"
    assert before_issues[0].kpi_to_monitor == "days_of_cover[AUR-003]"

    # Simulated intervention: an emergency replenishment lifts on-hand
    # stock well past the stockout threshold, demand unchanged.
    after = [{**before[0], "on_hand": 120, "days_of_cover": round(120 / 3.5, 1), "stockout_risk": False}]

    after_issues = detect_inventory_issues(after)
    assert after_issues == []


def test_marketing_efficiency_issue_resolves_after_simulated_roas_recovery():
    before = [
        {
                "brand": "Kestrel",
                "marketing_channel": "paid_social",
                "current_spend": 5000.0,
                "current_attributed_revenue": 4000.0,
                "current_roas": 0.8,
                "previous_spend": 2000.0,
                "previous_attributed_revenue": 6000.0,
                "previous_roas": 3.0,
        }
    ]
    before_issues = detect_marketing_efficiency_issues(before)
    assert len(before_issues) == 1
    assert before_issues[0].issue_type == "marketing_efficiency_decline"
    assert before_issues[0].kpi_to_monitor == "roas[Kestrel / paid_social]"

    # Simulated intervention: targeting/bid changes recover ROAS back to
    # (roughly) its previous-period level.
    after = [{**before[0], "current_attributed_revenue": 14500.0, "current_roas": 2.9}]

    after_issues = detect_marketing_efficiency_issues(after)
    assert after_issues == []
