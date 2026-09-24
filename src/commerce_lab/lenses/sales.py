"""Sales lens: net revenue vs. the previous period, by brand/channel/SKU.
Rule: material sales decline in a brand/channel (docs/decision_rules.md)."""

from __future__ import annotations

import pandas as pd

from ..app.i18n import t
from ..decisions.models import DecisionItem
from ..formatting import format_currency, format_pct, number, signed_pct
from ..metrics.sales import sales_by_segment, sales_summary
from ..pipeline.serialize import records, to_json_safe
from .base import Lens, Param, Tile


def compute(datasets, window, params) -> dict:
    orders = datasets["orders"]
    return {
        "summary": to_json_safe(sales_summary(orders, window)),
        "by_brand_channel": records(sales_by_segment(orders, window, ["brand", "channel"])),
        "by_sku": records(sales_by_segment(orders, window, ["sku_id", "brand"])),
    }


def detect(section: dict, params: dict) -> list[DecisionItem]:
    issues: list[DecisionItem] = []
    for _, row in pd.DataFrame(section["by_brand_channel"]).iterrows():
        if row["previous_net_revenue"] < params["min_segment_previous_revenue"] or pd.isna(row["pct_change"]):
            continue
        if row["pct_change"] > params["decline_medium_pct"]:
            continue
        severity = "high" if row["pct_change"] <= params["decline_high_pct"] else "medium"
        issues.append(
            DecisionItem(
                issue_type="sales_decline",
                headline=f"Material sales decline in {row['brand']} / {row['channel']}",
                severity=severity,
                supporting_kpi={
                    "current_net_revenue": round(float(row["current_net_revenue"]), 2),
                    "previous_net_revenue": round(float(row["previous_net_revenue"]), 2),
                    "pct_change": round(float(row["pct_change"]), 1),
                    "estimated_revenue_impact": round(float(row["current_net_revenue"] - row["previous_net_revenue"]), 2),
                },
                likely_drivers=[
                    f"Net revenue moved from {row['previous_net_revenue']:.0f} to "
                    f"{row['current_net_revenue']:.0f} ({row['pct_change']:.1f}%)."
                ],
                affected={"brand": row["brand"], "channel": row["channel"]},
                possible_action=f"Investigate demand/pricing/assortment for {row['brand']} / {row['channel']}.",
                kpi_to_monitor=f"net_revenue[{row['brand']} / {row['channel']}]",
            )
        )
    return issues


def localize_sales_decline(affected: dict, kpi: dict, lang: str) -> dict:
    brand, channel = affected["brand"], affected["channel"]
    if lang == "ko":
        return {
            "headline": f"{brand} / {channel} 매출 실질 하락",
            "likely_drivers": [
                f"순매출이 ${number(kpi['previous_net_revenue'])} → ${number(kpi['current_net_revenue'])}로 변화"
                f"({signed_pct(kpi['pct_change'])})."
            ],
            "possible_action": f"{brand} / {channel}의 수요·가격·구색을 조사하세요.",
        }
    return {
        "headline": f"Material sales decline in {brand} / {channel}",
        "likely_drivers": [
            f"Net revenue moved from ${number(kpi['previous_net_revenue'])} to ${number(kpi['current_net_revenue'])} "
            f"({signed_pct(kpi['pct_change'])})."
        ],
        "possible_action": f"Investigate demand/pricing/assortment for {brand} / {channel}.",
    }


def kpi_lookup(section: dict, issue_type: str, affected: dict):
    for row in section["by_brand_channel"]:
        if row["brand"] == affected.get("brand") and row["channel"] == affected.get("channel"):
            return row["current_net_revenue"]
    return None


def headline_metrics(section: dict, lang: str) -> list[Tile]:
    cur, chg = section["summary"]["current"], section["summary"]["pct_change"]
    return [
        Tile("overview.metric.net_revenue", format_currency(cur["net_revenue"]), format_pct(chg["net_revenue"])),
        Tile("overview.metric.orders", str(cur["orders"]), format_pct(chg["orders"])),
        Tile("overview.metric.aov", format_currency(cur["aov"]), format_pct(chg["aov"])),
    ]


def render(section: dict, lang: str, params: dict) -> None:
    import streamlit as st

    revenue_config = {
        "current_net_revenue": st.column_config.NumberColumn(format="dollar"),
        "previous_net_revenue": st.column_config.NumberColumn(format="dollar"),
        "change": st.column_config.NumberColumn(format="dollar"),
        "pct_change": st.column_config.NumberColumn(format="%+.1f%%"),
    }
    st.subheader(t("performance.revenue_header", lang))
    df = pd.DataFrame(section["by_brand_channel"])
    st.dataframe(
        df[["brand", "channel", "current_net_revenue", "previous_net_revenue", "change", "pct_change"]],
        width="stretch",
        hide_index=True,
        column_config=revenue_config,
    )
    st.bar_chart(df.set_index(df["brand"] + " / " + df["channel"])[["current_net_revenue", "previous_net_revenue"]])

    st.subheader(t("performance.sku_header", lang))
    st.dataframe(pd.DataFrame(section["by_sku"]), width="stretch", hide_index=True, column_config=revenue_config)


LENS = Lens(
    id="sales",
    title={"ko": "성과", "en": "Performance"},
    compute=compute,
    detect=detect,
    params=(
        Param("decline_high_pct", -35.0, {"ko": "매출 변화율 ≤ 이 값이면 high (%)", "en": "Sales change ≤ this: high (%)"}, -90.0, -5.0, 1.0),
        Param("decline_medium_pct", -20.0, {"ko": "매출 변화율 ≤ 이 값이면 medium (%)", "en": "Sales change ≤ this: medium (%)"}, -90.0, -5.0, 1.0),
        Param("min_segment_previous_revenue", 500.0, {"ko": "판정 대상 최소 규모: 이전 기간 매출 ($)", "en": "Ignore segments under: prev. revenue ($)"}, 0.0, 50000.0, 100.0),
    ),
    render=render,
    localizers={"sales_decline": localize_sales_decline},
    kpi_lookup=kpi_lookup,
    headline_metrics=headline_metrics,
)
