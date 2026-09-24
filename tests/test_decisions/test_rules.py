from __future__ import annotations

from commerce_lab.datagen import config
from commerce_lab.decisions.models import SEVERITY_ORDER
from commerce_lab.lenses import customer, inventory, marketing, sales
from commerce_lab.lenses.registry import resolve_params, run_detection


def test_marketing_rule_flags_the_planted_scenario_and_only_that_one(sections, default_params):
    issues = marketing.LENS.detect(sections["marketing"], default_params["marketing"])
    flagged = {(i.affected["brand"], i.affected["marketing_channel"]) for i in issues}
    assert (config.SCENARIO_MKT_BRAND, config.SCENARIO_MKT_CHANNEL) in flagged

    scenario_issue = next(
        i
        for i in issues
        if i.affected["brand"] == config.SCENARIO_MKT_BRAND
        and i.affected["marketing_channel"] == config.SCENARIO_MKT_CHANNEL
    )
    assert scenario_issue.severity in ("high", "medium")
    assert scenario_issue.issue_type == "marketing_efficiency_decline"
    assert scenario_issue.possible_action
    assert scenario_issue.kpi_to_monitor
    # planted scenario: spend ramps up while revenue stays flat, so the
    # dollar impact of the lost efficiency must be materially negative
    assert scenario_issue.supporting_kpi["estimated_revenue_impact"] < -500


def test_inventory_rule_flags_the_planted_sku(datasets, sections, default_params):
    skus_df = datasets["skus"]
    aurora_skus = skus_df[skus_df["brand"] == config.SCENARIO_INV_BRAND]["sku_id"].tolist()
    target_sku = aurora_skus[config.SCENARIO_INV_SKU_INDEX]

    issues = inventory.LENS.detect(sections["inventory"], default_params["inventory"])
    flagged_skus = {i.affected["sku_id"]: i for i in issues}
    assert target_sku in flagged_skus
    assert flagged_skus[target_sku].issue_type == "stockout_risk"


def test_sales_decline_rule_flags_the_planted_segment(sections, default_params):
    issues = sales.LENS.detect(sections["sales"], default_params["sales"])
    flagged = {(i.affected["brand"], i.affected["channel"]): i for i in issues}
    assert (config.SCENARIO_DECLINE_BRAND, config.SCENARIO_DECLINE_CHANNEL) in flagged

    scenario_issue = flagged[(config.SCENARIO_DECLINE_BRAND, config.SCENARIO_DECLINE_CHANNEL)]
    kpi = scenario_issue.supporting_kpi
    assert kpi["estimated_revenue_impact"] == round(kpi["current_net_revenue"] - kpi["previous_net_revenue"], 2)
    assert kpi["estimated_revenue_impact"] < 0


def test_customer_mix_rule_flags_the_shift(sections, default_params):
    issues = customer.LENS.detect(sections["customer"], default_params["customer"])
    assert len(issues) == 1
    assert issues[0].issue_type == "customer_mix_shift"
    assert issues[0].severity in ("high", "medium")


def test_detect_all_issues_sorted_by_severity(lenses, sections, default_params):
    issues = run_detection(lenses, sections, default_params)
    assert len(issues) >= 4  # at least the 4 planted scenarios
    severities = [SEVERITY_ORDER[i.severity] for i in issues]
    assert severities == sorted(severities)


def test_every_issue_has_the_required_structured_fields(lenses, sections, default_params):
    issues = run_detection(lenses, sections, default_params)
    for issue in issues:
        d = issue.to_dict()
        assert d["headline"]
        assert d["severity"] in ("high", "medium", "low")
        assert d["supporting_kpi"]
        assert "estimated_revenue_impact" in d["supporting_kpi"]  # present (possibly None) on every issue type
        assert d["likely_drivers"]
        assert d["possible_action"]
        assert d["kpi_to_monitor"]
