"""Inventory lens: on-hand, sales velocity, days of cover. Rules:
stock-out risk and excess-inventory risk per SKU (docs/decision_rules.md)."""

from __future__ import annotations

import pandas as pd

from ..app.i18n import t
from ..decisions.models import DecisionItem
from ..metrics.inventory import inventory_risk_by_sku
from ..metrics.periods import PeriodWindow
from ..pipeline.serialize import records
from .base import Lens, Param


def compute(datasets, window: PeriodWindow, params) -> dict:
    risk = inventory_risk_by_sku(
        datasets["inventory"],
        as_of=window.current_end,
        velocity_window_days=int(params["velocity_window_days"]),
        stockout_threshold_days=params["stockout_days"],
        excess_threshold_days=params["excess_days"],
    )
    return {"risk_by_sku": records(risk)}


def flag_risks(risk_by_sku: list[dict], params: dict) -> pd.DataFrame:
    """The per-SKU stock-out/excess flags under `params`. Recomputed from
    days-of-cover/velocity rather than read from the stored flags, so the
    app can re-flag with different thresholds without a refresh."""
    df = pd.DataFrame(risk_by_sku)
    days = pd.to_numeric(df["days_of_cover"], errors="coerce")
    df["stockout_risk"] = days.notna() & (days < params["stockout_days"])
    df["excess_risk"] = (df["on_hand"] > 0) & ((df["velocity"] == 0) | (days.notna() & (days > params["excess_days"])))
    return df


def detect(section: dict, params: dict) -> list[DecisionItem]:
    issues: list[DecisionItem] = []
    for _, row in flag_risks(section["risk_by_sku"], params).iterrows():
        days = row["days_of_cover"]
        if row["stockout_risk"]:
            severity = "high" if days < params["high_severity_days"] else "medium"
            issues.append(
                DecisionItem(
                    issue_type="stockout_risk",
                    headline=f"Stock-out risk for SKU {row['sku_id']} ({row['brand']})",
                    severity=severity,
                    supporting_kpi={
                        "on_hand": int(row["on_hand"]),
                        "velocity_per_day": round(float(row["velocity"]), 2),
                        "days_of_cover": round(float(days), 1),
                        "estimated_revenue_impact": None,  # needs unit price/cost data not available here
                    },
                    likely_drivers=[
                        f"Demand of ~{row['velocity']:.1f} units/day against on-hand stock of "
                        f"{row['on_hand']:.0f} leaves ~{days:.1f} days of cover."
                    ],
                    affected={"brand": row["brand"], "sku_id": row["sku_id"]},
                    possible_action=f"Expedite replenishment for {row['sku_id']}; consider a temporary allocation cap.",
                    kpi_to_monitor=f"days_of_cover[{row['sku_id']}]",
                )
            )
        elif row["excess_risk"]:
            issues.append(
                DecisionItem(
                    issue_type="excess_inventory_risk",
                    headline=f"Excess inventory risk for SKU {row['sku_id']} ({row['brand']})",
                    severity="low",
                    supporting_kpi={
                        "on_hand": int(row["on_hand"]),
                        "velocity_per_day": round(float(row["velocity"]), 2),
                        "days_of_cover": None if pd.isna(days) else round(float(days), 1),
                        "estimated_revenue_impact": None,  # needs unit price/cost data not available here
                    },
                    likely_drivers=[
                        f"On-hand stock of {row['on_hand']:.0f} against demand of only "
                        f"~{row['velocity']:.1f} units/day."
                    ],
                    affected={"brand": row["brand"], "sku_id": row["sku_id"]},
                    possible_action=f"Consider a promotion or markdown for {row['sku_id']} to work down excess stock.",
                    kpi_to_monitor=f"days_of_cover[{row['sku_id']}]",
                )
            )
    return issues


def localize_stockout(affected: dict, kpi: dict, lang: str) -> dict:
    sku, brand = affected["sku_id"], affected["brand"]
    if lang == "ko":
        return {
            "headline": f"SKU {sku}({brand}) 품절 위험",
            "likely_drivers": [
                f"일 수요 ~{kpi['velocity_per_day']:.1f}개 대비 보유 재고 {int(kpi['on_hand'])}개, "
                f"재고 소진까지 ~{kpi['days_of_cover']:.1f}일."
            ],
            "possible_action": f"{sku} 긴급 재입고를 진행하고, 필요시 임시 배분 상한을 고려하세요.",
        }
    return {
        "headline": f"Stock-out risk for SKU {sku} ({brand})",
        "likely_drivers": [
            f"Demand of ~{kpi['velocity_per_day']:.1f} units/day against on-hand stock of "
            f"{int(kpi['on_hand'])} leaves ~{kpi['days_of_cover']:.1f} days of cover."
        ],
        "possible_action": f"Expedite replenishment for {sku}; consider a temporary allocation cap.",
    }


def localize_excess_inventory(affected: dict, kpi: dict, lang: str) -> dict:
    sku, brand = affected["sku_id"], affected["brand"]
    if lang == "ko":
        return {
            "headline": f"SKU {sku}({brand}) 과잉재고 위험",
            "likely_drivers": [f"보유 재고 {int(kpi['on_hand'])}개 대비 일 수요는 ~{kpi['velocity_per_day']:.1f}개에 불과."],
            "possible_action": f"{sku}의 과잉 재고를 줄이기 위해 프로모션이나 가격 인하를 고려하세요.",
        }
    return {
        "headline": f"Excess inventory risk for SKU {sku} ({brand})",
        "likely_drivers": [f"On-hand stock of {int(kpi['on_hand'])} against demand of only ~{kpi['velocity_per_day']:.1f} units/day."],
        "possible_action": f"Consider a promotion or markdown for {sku} to work down excess stock.",
    }


def kpi_lookup(section: dict, issue_type: str, affected: dict):
    for row in section["risk_by_sku"]:
        if row["sku_id"] == affected.get("sku_id"):
            return row["days_of_cover"]
    return None


def render(section: dict, lang: str, params: dict) -> None:
    import streamlit as st

    st.subheader(t("inventory.header", lang))
    df = flag_risks(section["risk_by_sku"], params)
    risk_df = df[df["stockout_risk"] | df["excess_risk"]]
    st.caption(t("inventory.flagged_caption", lang, flagged=len(risk_df), total=len(df)))
    st.dataframe(risk_df, width="stretch", hide_index=True)

    with st.expander(t("inventory.all_skus_expander", lang, n=len(df))):
        st.dataframe(df, width="stretch", hide_index=True)


LENS = Lens(
    id="inventory",
    title={"ko": "재고", "en": "Inventory"},
    compute=compute,
    detect=detect,
    params=(
        Param("stockout_days", 7.0, {"ko": "재고 소진 일수 < 이 값이면 품절 위험 (일)", "en": "Days of cover < this: stock-out risk (days)"}, 1.0, 30.0, 1.0),
        Param("high_severity_days", 3.0, {"ko": "재고 소진 일수 < 이 값이면 품절 high (일)", "en": "Days of cover < this: stock-out high (days)"}, 1.0, 30.0, 1.0),
        Param("excess_days", 60.0, {"ko": "재고 소진 일수 > 이 값이면 과잉재고 (일)", "en": "Days of cover > this: excess stock (days)"}, 14.0, 365.0, 5.0),
        Param("velocity_window_days", 14, {"ko": "판매 속도 산정 기간 (일)", "en": "Velocity window (days)"}, 3, 60, 1, runtime=False),
    ),
    render=render,
    localizers={"stockout_risk": localize_stockout, "excess_inventory_risk": localize_excess_inventory},
    kpi_lookup=kpi_lookup,
)
