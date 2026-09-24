"""Executive Decision App -- Streamlit, Cloud Run.

Reads only the app-ready snapshot (never BigQuery or Gemini directly on
page load). Run locally with:

    python -m commerce_lab.pipeline.refresh   # writes data/generated/app_snapshot.json
    streamlit run src/commerce_lab/app/main.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from commerce_lab.app.copy_prompt import build_copy_prompt
from commerce_lab.app.data_loader import load_snapshot
from commerce_lab.app.i18n import DEFAULT_LANG, LANGS, localize_decision, severity_badge, t
from commerce_lab.app.view_helpers import (
    fallback_executive_summary,
    format_currency,
    kpi_trend,
    severity_counts,
    top_issues,
)
from commerce_lab.decisions.models import SEVERITY_ORDER
from commerce_lab.lenses.registry import BUILTIN_LENS_NAMES, lens_for_decision, load_lenses, resolve_params, run_detection

st.set_page_config(page_title="Commerce Decision Lab", layout="wide")


@st.cache_data(ttl=300)
def _get_history() -> dict:
    return load_snapshot()


def render_decision_card(decision: dict, lang: str, history: dict) -> None:
    decision = localize_decision(decision, lang=lang)
    with st.container(border=True):
        st.markdown(f"**{decision['headline']}**  \n{severity_badge(decision['severity'], lang)}")

        impact = decision["supporting_kpi"].get("estimated_revenue_impact")
        if impact is not None:
            st.metric(t("decision.revenue_impact", lang), format_currency(impact))

        cols = st.columns(2)
        with cols[0]:
            with st.expander(t("decision.kpi_expander", lang, n=len(decision["supporting_kpi"]))):
                st.json(decision["supporting_kpi"], expanded=True)
            if decision["likely_drivers"]:
                st.caption(t("decision.likely_drivers", lang))
                for driver in decision["likely_drivers"]:
                    st.write(f"- {driver}")
        with cols[1]:
            st.caption(t("decision.possible_action", lang))
            st.write(decision["possible_action"])
            st.caption(t("decision.kpi_to_monitor", lang))
            st.write(decision["kpi_to_monitor"])

        trend = kpi_trend(history, decision)
        if len(trend) >= 2:
            st.caption(t("decision.trend", lang))
            trend_df = pd.DataFrame(trend).set_index("as_of")
            st.line_chart(trend_df)


def render_overview(snapshot: dict, lang: str, history: dict, lenses: list) -> None:
    st.subheader(t("overview.kpi_header", lang))
    tiles = [
        tile
        for lens in lenses
        if lens.headline_metrics and lens.id in snapshot
        for tile in lens.headline_metrics(snapshot[lens.id], lang)
    ]
    for col, tile in zip(st.columns(max(len(tiles), 1)), tiles):
        col.metric(t(tile.label_key, lang), tile.value, tile.delta)

    st.subheader(t("overview.issues_header", lang))
    counts = severity_counts(snapshot["decisions"])
    st.caption(t("overview.severity_caption", lang, high=counts["high"], medium=counts["medium"], low=counts["low"]))
    for decision in top_issues(snapshot["decisions"], n=5):
        render_decision_card(decision, lang, history)

    st.subheader(t("overview.summary_header", lang))
    # Gemini only ever generates an English summary (one call per refresh);
    # Korean always gets the deterministic fallback so it's never mistranslated.
    if lang == "en" and snapshot.get("gemini_summary"):
        st.write(snapshot["gemini_summary"])
    else:
        if lang == "en":
            st.info(t("overview.gemini_missing", lang))
        elif snapshot.get("gemini_summary"):
            st.caption(t("overview.ko_summary_note", lang))
        st.write(fallback_executive_summary(snapshot["decisions"], snapshot.get("sales", {}).get("summary", {}), lang=lang))

    with st.expander(t("overview.copy_header", lang)):
        st.markdown(t("overview.copy_steps", lang))
        st.code(build_copy_prompt(snapshot, lang), language=None)


def render_decisions(snapshot: dict, lang: str, history: dict, lenses: list) -> None:
    st.subheader(t("decisions.header", lang))
    cols = st.columns(2)
    lens_ids = cols[0].multiselect(
        t("filter.lens", lang),
        options=[lens.id for lens in lenses],
        format_func=lambda i: next(_title(lens, lang) for lens in lenses if lens.id == i),
    )
    severities = cols[1].multiselect(t("filter.severity", lang), options=list(SEVERITY_ORDER))
    shown = [
        d
        for d in top_issues(snapshot["decisions"], n=len(snapshot["decisions"]))  # same order as Overview
        if (not lens_ids or getattr(lens_for_decision(d), "id", None) in lens_ids) and (not severities or d["severity"] in severities)
    ]
    st.caption(t("filter.count", lang, shown=len(shown), total=len(snapshot["decisions"])))
    if not shown:
        st.info(t("filter.none", lang))
    for decision in shown:
        render_decision_card(decision, lang, history)


def _title(lens, lang: str) -> str:
    return lens.title.get(lang, lens.title["en"])


def _reset_thresholds(lenses: list) -> None:
    for lens in lenses:
        for p in lens.params:
            st.session_state.pop(f"param.{lens.id}.{p.key}", None)


def _threshold_controls(lenses: list, snapshot: dict, lang: str) -> dict:
    """Sidebar sliders for every runtime-tunable lens parameter (a slider
    applies as soon as it is released, unlike a number box that needs
    Enter). Returns the overrides that differ from the snapshot's own
    values ({} if untouched)."""
    baseline = {lens.id: resolve_params(lens, snapshot.get("params", {}).get(lens.id)) for lens in lenses}
    tunable = [(lens, [p for p in lens.params if p.runtime]) for lens in lenses]
    tunable = [(lens, params) for lens, params in tunable if params]
    if not tunable:
        return {}

    overrides: dict = {}
    with st.sidebar.expander(t("params.header", lang)):
        st.caption(t("params.help", lang))
        for lens, params in tunable:
            st.markdown(f"**{_title(lens, lang)}**")
            for p in params:
                default = baseline[lens.id][p.key]
                cast = type(default)
                value = st.slider(
                    p.label.get(lang, p.label["en"]),
                    min_value=cast(p.min),
                    max_value=cast(p.max),
                    value=default,
                    step=cast(p.step),
                    key=f"param.{lens.id}.{p.key}",
                )
                if value != default:
                    overrides.setdefault(lens.id, {})[p.key] = value
        st.button(t("params.reset", lang), on_click=_reset_thresholds, args=(lenses,), key="params.reset_sidebar")
    return overrides


def _describe_overrides(lenses: list, overrides: dict, snapshot: dict, lang: str) -> str:
    lines = []
    for lens in lenses:
        for key, value in overrides.get(lens.id, {}).items():
            p = next(p for p in lens.params if p.key == key)
            base = resolve_params(lens, snapshot.get("params", {}).get(lens.id))[key]
            lines.append(f"- {_title(lens, lang)} · {p.label.get(lang, p.label['en'])}: {base:g} → {value:g}")
    return "\n".join(lines)


def main() -> None:
    history = _get_history()

    lang = st.sidebar.selectbox(
        t("lang.selector_label", st.session_state.get("lang", DEFAULT_LANG)),
        options=list(LANGS),
        format_func=lambda code: {"ko": "한국어", "en": "English"}[code],
        key="lang",
    )

    available_dates = history["available_as_of_dates"]
    selected_date = st.sidebar.select_slider(
        t("period.selector_label", lang),
        options=available_dates,
        value=st.session_state.get("as_of", history["latest_as_of_date"]),
        key="as_of",
    )
    snapshot = history["snapshots"][selected_date]

    lenses = load_lenses(snapshot.get("lenses") or BUILTIN_LENS_NAMES)
    overrides = _threshold_controls(lenses, snapshot, lang)
    if overrides:
        params = {lens.id: resolve_params(lens, {**snapshot.get("params", {}).get(lens.id, {}), **overrides.get(lens.id, {})}) for lens in lenses}
        redetected = run_detection(lenses, snapshot, params)
        snapshot = {**snapshot, "decisions": [d.to_dict() for d in redetected]}
        banner = _describe_overrides(lenses, overrides, snapshot, lang)

    st.title("Commerce Decision Lab")
    st.caption(
        t(
            "period.caption",
            lang,
            as_of=snapshot["as_of_date"],
            current_start=snapshot["period"]["current_start"],
            current_end=snapshot["period"]["current_end"],
            previous_start=snapshot["period"]["previous_start"],
            previous_end=snapshot["period"]["previous_end"],
        )
    )

    if overrides:
        with st.container(border=True):
            st.markdown(f"**{t('params.active', lang)}**\n\n{banner}")
            st.button(t("params.reset", lang), on_click=_reset_thresholds, args=(lenses,), key="params.reset_main")

    tab_names = [t("tab.overview", lang), *(_title(lens, lang) for lens in lenses), t("tab.decisions", lang)]
    tabs = st.tabs(tab_names)
    with tabs[0]:
        render_overview(snapshot, lang, history, lenses)
    for tab, lens in zip(tabs[1:-1], lenses):
        with tab:
            if lens.render is not None:
                lens.render(snapshot[lens.id], lang, resolve_params(lens, snapshot.get("params", {}).get(lens.id)) | overrides.get(lens.id, {}))
    with tabs[-1]:
        render_decisions(snapshot, lang, history, lenses)


main()
