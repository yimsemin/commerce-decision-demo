"""Marketing lens: spend, ROAS and CAC. Rule: ROAS deterioration for a
brand/channel segment (docs/decision_rules.md)."""

from __future__ import annotations

import pandas as pd

from ..app.i18n import t
from ..decisions.models import DecisionItem
from ..formatting import number, signed_pct
from ..metrics.marketing import cac_by_channel, marketing_by_segment
from ..pipeline.serialize import records
from .base import Lens, Param


def compute(datasets, window, params) -> dict:
    return {
        "by_segment": records(marketing_by_segment(datasets["marketing"], window, ["brand", "marketing_channel"])),
        "cac_by_channel": records(cac_by_channel(datasets["marketing"], datasets["customers"], window)),
    }


def detect(section: dict, params: dict) -> list[DecisionItem]:
    issues: list[DecisionItem] = []
    for _, row in pd.DataFrame(section["by_segment"]).iterrows():
        if row["previous_spend"] < params["min_segment_spend"] or pd.isna(row["previous_roas"]) or row["previous_roas"] == 0:
            continue
        pct_change = (row["current_roas"] - row["previous_roas"]) / row["previous_roas"] * 100
        if pct_change > params["decline_medium_pct"]:
            continue
        severity = "high" if pct_change <= params["decline_high_pct"] else "medium"
        # Revenue the current spend "should" have produced at the previous
        # period's efficiency, vs. what it actually produced -- a rough but
        # directly-derivable dollar sizing of the efficiency loss.
        expected_revenue_at_previous_roas = row["current_spend"] * row["previous_roas"]
        revenue_impact = round(float(row["current_attributed_revenue"] - expected_revenue_at_previous_roas), 2)
        issues.append(
            DecisionItem(
                issue_type="marketing_efficiency_decline",
                headline=f"Marketing efficiency deteriorating for {row['brand']} / {row['marketing_channel']}",
                severity=severity,
                supporting_kpi={
                    "current_roas": round(float(row["current_roas"]), 2),
                    "previous_roas": round(float(row["previous_roas"]), 2),
                    "roas_change_pct": round(float(pct_change), 1),
                    "current_spend": round(float(row["current_spend"]), 2),
                    "estimated_revenue_impact": revenue_impact,
                },
                likely_drivers=[
                    f"Spend changed from {row['previous_spend']:.0f} to {row['current_spend']:.0f} "
                    f"while attributed revenue changed from {row['previous_attributed_revenue']:.0f} "
                    f"to {row['current_attributed_revenue']:.0f}."
                ],
                affected={"brand": row["brand"], "marketing_channel": row["marketing_channel"]},
                possible_action=(
                    f"Review targeting, creative, and bid strategy for {row['brand']} / "
                    f"{row['marketing_channel']}; consider reallocating budget to better-performing segments."
                ),
                kpi_to_monitor=f"roas[{row['brand']} / {row['marketing_channel']}]",
            )
        )
    return issues


def localize_marketing_efficiency(affected: dict, kpi: dict, lang: str) -> dict:
    brand, channel = affected["brand"], affected["marketing_channel"]
    if lang == "ko":
        return {
            "headline": f"{brand} / {channel} 마케팅 효율 악화",
            "likely_drivers": [
                f"ROAS가 {kpi['previous_roas']:.2f} → {kpi['current_roas']:.2f}로 하락({signed_pct(kpi['roas_change_pct'])}), "
                f"현재 지출은 ${number(kpi['current_spend'])}."
            ],
            "possible_action": f"{brand} / {channel}의 타겟팅·크리에이티브·입찰 전략을 재검토하고, 성과가 좋은 세그먼트로 예산 재배분을 고려하세요.",
        }
    return {
        "headline": f"Marketing efficiency deteriorating for {brand} / {channel}",
        "likely_drivers": [
            f"ROAS fell from {kpi['previous_roas']:.2f} to {kpi['current_roas']:.2f} ({signed_pct(kpi['roas_change_pct'])}); "
            f"current spend is ${number(kpi['current_spend'])}."
        ],
        "possible_action": f"Review targeting, creative, and bid strategy for {brand} / {channel}; consider reallocating budget to better-performing segments.",
    }


def kpi_lookup(section: dict, issue_type: str, affected: dict):
    for row in section["by_segment"]:
        if row["brand"] == affected.get("brand") and row["marketing_channel"] == affected.get("marketing_channel"):
            return row["current_roas"]
    return None


def render(section: dict, lang: str, params: dict) -> None:
    import streamlit as st

    st.subheader(t("marketing.header", lang))
    df = pd.DataFrame(section["by_segment"])
    st.dataframe(
        df[["brand", "marketing_channel", "current_spend", "current_roas", "previous_roas", "roas_change_pct"]],
        width="stretch",
        hide_index=True,
        column_config={
            "current_spend": st.column_config.NumberColumn(format="dollar"),
            "current_roas": st.column_config.NumberColumn(format="%.2f"),
            "previous_roas": st.column_config.NumberColumn(format="%.2f"),
            "roas_change_pct": st.column_config.NumberColumn(format="%+.1f%%"),
        },
    )
    st.bar_chart(df.set_index(df["brand"] + " / " + df["marketing_channel"])[["current_roas", "previous_roas"]])

    st.subheader(t("marketing.cac_header", lang))
    st.dataframe(
        pd.DataFrame(section["cac_by_channel"]),
        width="stretch",
        hide_index=True,
        column_config={
            "spend": st.column_config.NumberColumn(format="dollar"),
            "cac": st.column_config.NumberColumn(format="dollar"),
        },
    )


LENS = Lens(
    id="marketing",
    title={"ko": "마케팅", "en": "Marketing"},
    compute=compute,
    detect=detect,
    params=(
        Param("decline_high_pct", -40.0, {"ko": "ROAS 변화율 ≤ 이 값이면 high (%)", "en": "ROAS change ≤ this: high (%)"}, -90.0, -5.0, 1.0),
        Param("decline_medium_pct", -20.0, {"ko": "ROAS 변화율 ≤ 이 값이면 medium (%)", "en": "ROAS change ≤ this: medium (%)"}, -90.0, -5.0, 1.0),
        Param("min_segment_spend", 1000.0, {"ko": "판정 대상 최소 규모: 이전 기간 지출 ($)", "en": "Ignore segments under: prev. spend ($)"}, 0.0, 50000.0, 100.0),
    ),
    render=render,
    localizers={"marketing_efficiency_decline": localize_marketing_efficiency},
    kpi_lookup=kpi_lookup,
)
