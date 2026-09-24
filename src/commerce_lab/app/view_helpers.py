"""Pure, Streamlit-free helpers for rendering the snapshot. Kept separate
from main.py so this logic is unit-testable without a Streamlit runtime.
"""

from __future__ import annotations

from commerce_lab.formatting import format_currency, format_pct  # noqa: F401  (re-exported)

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def severity_counts(decisions: list[dict]) -> dict:
    counts = {"high": 0, "medium": 0, "low": 0}
    for d in decisions:
        counts[d["severity"]] = counts.get(d["severity"], 0) + 1
    return counts


def top_issues(decisions: list[dict], n: int = 5) -> list[dict]:
    """Sorted by severity first (the deterministic rule's own judgment,
    never overridden here), then -- within the same severity tier -- by
    the magnitude of `estimated_revenue_impact` when a rule was able to
    compute one, largest first. Issues without a dollar estimate (`None`)
    sort last within their tier, not first."""

    def key(d: dict) -> tuple[int, float]:
        impact = d.get("supporting_kpi", {}).get("estimated_revenue_impact")
        magnitude = abs(impact) if impact is not None else -1
        return (SEVERITY_ORDER.get(d["severity"], 99), -magnitude)

    return sorted(decisions, key=key)[:n]


def kpi_trend(history: dict, decision: dict) -> list[dict]:
    """The `decision`'s primary KPI across every precomputed as-of anchor
    in `history` (oldest first) -- lets the app show a trend, not just a
    single current-vs-previous comparison, without ever recomputing
    anything live. Anchors where the segment/SKU has no data (e.g. too
    early in the history) are skipped rather than shown as zero. The
    lookup itself belongs to the lens that raised the issue."""
    from commerce_lab.lenses.registry import lens_for_decision

    lens = lens_for_decision(decision)
    if lens is None or lens.kpi_lookup is None:
        return []

    points: list[dict] = []
    for as_of in history["available_as_of_dates"]:
        section = history["snapshots"][as_of].get(lens.id)
        value = lens.kpi_lookup(section, decision["issue_type"], decision.get("affected", {})) if section else None
        if value is not None:
            points.append({"as_of": as_of, "value": value})
    return points


def fallback_executive_summary(decisions: list[dict], sales_summary: dict, lang: str = "en") -> str:
    """Deterministic stand-in used whenever `gemini_summary` is null (M6
    not run, or the call failed -- or the viewer picked a language Gemini
    doesn't generate, since only one English summary is generated per
    snapshot) -- never blocks the page from rendering."""
    counts = severity_counts(decisions)
    revenue_change = sales_summary.get("pct_change", {}).get("net_revenue")
    top = top_issues(decisions, n=3)

    if lang == "ko":
        from .i18n import localize_decision

        parts = [
            f"이전 기간 대비 순매출 변화: {format_pct(revenue_change)}.",
            f"high {counts['high']}건, medium {counts['medium']}건, low {counts['low']}건.",
        ]
        if top:
            headlines = [localize_decision(d, lang="ko")["headline"] for d in top]
            parts.append("주요 이슈: " + "; ".join(headlines) + ".")
        return " ".join(parts)

    parts = [
        f"Net revenue change vs. prior period: {format_pct(revenue_change)}.",
        f"{counts['high']} high-severity issue(s), {counts['medium']} medium, {counts['low']} low.",
    ]
    if top:
        parts.append("Top issues: " + "; ".join(d["headline"] for d in top) + ".")
    return " ".join(parts)
