"""Customer lens: new-vs-returning mix and repeat purchase rate. Rule: a
sharp drop in the new-customer order share (docs/decision_rules.md)."""

from __future__ import annotations

import pandas as pd

from ..app.i18n import t
from ..decisions.models import DecisionItem
from ..metrics.customer import new_vs_returning_mix, repeat_purchase_rate
from ..pipeline.serialize import to_json_safe
from .base import Lens, Param, Tile


def compute(datasets, window, params) -> dict:
    return {
        "mix": to_json_safe(new_vs_returning_mix(datasets["orders"], window)),
        "repeat_purchase_rate": repeat_purchase_rate(datasets["customers"]),
    }


def detect(section: dict, params: dict) -> list[DecisionItem]:
    mix = section["mix"]
    current, previous = mix["current_new_share"], mix["previous_new_share"]
    if current is None or previous is None or previous == 0:
        return []

    pct_change = (current - previous) / previous * 100
    if pct_change > params["new_share_drop_medium_pct"]:
        return []

    severity = "high" if pct_change <= params["new_share_drop_high_pct"] else "medium"
    return [
        DecisionItem(
            issue_type="customer_mix_shift",
            headline="New-customer acquisition share dropping sharply",
            severity=severity,
            supporting_kpi={
                "current_new_share": current,
                "previous_new_share": previous,
                "pct_change": round(pct_change, 1),
                "estimated_revenue_impact": None,  # needs per-order revenue attribution not available here
            },
            likely_drivers=[f"Share of orders from new customers moved from {previous:.0%} to {current:.0%}."],
            affected={},
            possible_action="Review acquisition marketing spend/effectiveness; confirm this is not a data/tracking issue.",
            kpi_to_monitor="new_customer_share",
        )
    ]


def localize_customer_mix(affected: dict, kpi: dict, lang: str) -> dict:
    prev, cur = kpi["previous_new_share"], kpi["current_new_share"]
    if lang == "ko":
        return {
            "headline": "신규 고객 획득 비중 급감",
            "likely_drivers": [f"신규 고객 주문 비중이 {prev:.0%} → {cur:.0%}로 이동."],
            "possible_action": "획득 마케팅 지출/효율을 재검토하고, 데이터·트래킹 이슈가 아닌지 확인하세요.",
        }
    return {
        "headline": "New-customer acquisition share dropping sharply",
        "likely_drivers": [f"Share of orders from new customers moved from {prev:.0%} to {cur:.0%}."],
        "possible_action": "Review acquisition marketing spend/effectiveness; confirm this is not a data/tracking issue.",
    }


def kpi_lookup(section: dict, issue_type: str, affected: dict):
    return section["mix"]["current_new_share"]


def headline_metrics(section: dict, lang: str) -> list[Tile]:
    mix = section["mix"]
    new_share, prev = mix["current_new_share"], mix["previous_new_share"]
    delta = None if new_share is None or prev is None else f"{(new_share - prev) * 100:+.1f}pt"
    return [Tile("overview.metric.new_share", f"{new_share:.0%}" if new_share is not None else "n/a", delta)]


def render(section: dict, lang: str, params: dict) -> None:
    import streamlit as st

    mix = section["mix"]
    cols = st.columns(3)
    cols[0].metric(t("customer.new_share_current", lang), f"{mix['current_new_share']:.0%}" if mix["current_new_share"] is not None else "n/a")
    cols[1].metric(t("customer.new_share_previous", lang), f"{mix['previous_new_share']:.0%}" if mix["previous_new_share"] is not None else "n/a")
    cols[2].metric(t("customer.repeat_rate", lang), f"{section['repeat_purchase_rate']:.0%}")

    chart_df = pd.DataFrame(
        {
            "period": ["previous", "current"],
            "new_share": [mix["previous_new_share"], mix["current_new_share"]],
            "returning_share": [mix["previous_returning_share"], mix["current_returning_share"]],
        }
    ).set_index("period")
    st.bar_chart(chart_df)


LENS = Lens(
    id="customer",
    title={"ko": "고객", "en": "Customer"},
    compute=compute,
    detect=detect,
    params=(
        Param("new_share_drop_high_pct", -50.0, {"ko": "신규 고객 비중 변화율 ≤ 이 값이면 high (%)", "en": "New-customer share change ≤ this: high (%)"}, -90.0, -5.0, 1.0),
        Param("new_share_drop_medium_pct", -25.0, {"ko": "신규 고객 비중 변화율 ≤ 이 값이면 medium (%)", "en": "New-customer share change ≤ this: medium (%)"}, -90.0, -5.0, 1.0),
    ),
    render=render,
    localizers={"customer_mix_shift": localize_customer_mix},
    kpi_lookup=kpi_lookup,
    headline_metrics=headline_metrics,
)
