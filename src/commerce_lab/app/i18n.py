"""Minimal, dependency-free i18n for the Streamlit app.

Two concerns, kept separate:

1. `UI_STRINGS` -- static chrome (section headers, labels), plus
   `EXTRA_STRINGS` contributed by lenses. Plain dict lookup via `t(key, lang)`.
2. `localize_decision` -- decision-card prose (headline / likely driver /
   possible action). Decision items already carry every fact needed
   (`issue_type`, `affected`, `supporting_kpi`) as structured, language-
   neutral data (see `commerce_lab.decisions.rules`); this module is the
   only place that turns those facts into a sentence, in either language
   (the per-issue-type wording is supplied by each lens).
   Raw KPI keys (e.g. `kpi_to_monitor`, dataframe column names) are left
   untranslated on purpose -- they're metric identifiers, not prose.
"""

from __future__ import annotations

LANGS = ("ko", "en")
DEFAULT_LANG = "ko"

UI_STRINGS: dict[str, dict[str, str]] = {
    "tab.overview": {"ko": "개요", "en": "Overview"},
    "tab.decisions": {"ko": "의사결정", "en": "Decisions"},
    "params.header": {"ko": "이슈 기준 조정 (이 세션에서만 · 클릭하여 펼치기)", "en": "Adjust issue thresholds (this session only · click to expand)"},
    "params.help": {
        "ko": "슬라이더를 움직이면 저장된 지표로 이슈를 바로 다시 판정합니다. 이 화면에만 적용되며 다른 방문자와 다음 리프레시에는 영향이 없습니다.",
        "en": "Changing a threshold re-runs the rules on the stored metrics (snapshot). It does not affect other visitors or the next refresh.",
    },
    "params.active": {"ko": "조정된 기준으로 이슈를 다시 판정한 결과입니다 (기본값과 다른 항목):", "en": "Issues were re-evaluated with your adjusted thresholds (changed from default):"},
    "params.reset": {"ko": "기본값으로 되돌리기", "en": "Reset to defaults"},
    "filter.lens": {"ko": "관점", "en": "Lens"},
    "filter.severity": {"ko": "심각도", "en": "Severity"},
    "filter.count": {"ko": "{total}건 중 {shown}건 표시", "en": "Showing {shown} of {total}"},
    "filter.none": {"ko": "조건에 맞는 이슈가 없습니다.", "en": "No issues match the filters."},
    "period.caption": {
        "ko": "기준일 {as_of} · 현재 기간 {current_start} ~ {current_end} vs. 이전 기간 {previous_start} ~ {previous_end}",
        "en": "As of {as_of} · current period {current_start} to {current_end} vs. previous {previous_start} to {previous_end}",
    },
    "period.selector_label": {"ko": "비교 시점 (기준일)", "en": "Comparison point (as of)"},
    "lang.selector_label": {"ko": "언어 / Language", "en": "Language / 언어"},
    "overview.kpi_header": {"ko": "핵심 KPI 변화", "en": "Key KPI movement"},
    "overview.metric.net_revenue": {"ko": "순매출", "en": "Net revenue"},
    "overview.metric.orders": {"ko": "주문 수", "en": "Orders"},
    "overview.metric.aov": {"ko": "평균 주문 금액", "en": "AOV"},
    "overview.metric.new_share": {"ko": "신규 고객 비중", "en": "New-customer share"},
    "overview.issues_header": {"ko": "가장 중요한 이슈", "en": "Most material issues"},
    "overview.severity_caption": {"ko": "{high} high · {medium} medium · {low} low", "en": "{high} high · {medium} medium · {low} low"},
    "overview.summary_header": {"ko": "경영진 요약", "en": "Executive summary"},
    "overview.gemini_missing": {
        "ko": "이 스냅샷에는 Gemini 해석이 없어 결정적 대체 요약을 표시합니다.",
        "en": "Gemini interpretation not available in this snapshot -- showing a deterministic fallback summary.",
    },
    "overview.ko_summary_note": {
        "ko": "Gemini 요약은 영어로만 생성됩니다. 한국어 화면에서는 같은 근거로 만든 결정적 요약을 보여줍니다.",
        "en": "",
    },
    "overview.copy_header": {"ko": "다른 AI로 분석하기 (복사해서 붙여넣기 · 클릭하여 펼치기)", "en": "Analyze with your own AI (copy & paste · click to expand)"},
    "overview.copy_steps": {
        "ko": "1. 아래 프롬프트 오른쪽 위의 복사 버튼을 누릅니다.  \n2. ChatGPT, Claude, Gemini 등 사용 중인 AI 채팅창에 붙여넣습니다.  \n3. 이 화면의 사실(합성 데모 데이터)만 근거로 요약·우선순위·추가 확인사항을 답해 줍니다. 이 앱은 어떤 AI도 대신 호출하지 않습니다.",
        "en": "1. Click the copy button at the top right of the prompt below.  \n2. Paste it into ChatGPT, Claude, Gemini, or any assistant you use.  \n3. It answers only from the facts shown here (synthetic demo data). This app never calls any AI on your behalf.",
    },
    "performance.revenue_header": {"ko": "브랜드/채널별 매출 (현재 vs 이전 기간)", "en": "Revenue by brand / channel (current vs. previous period)"},
    "performance.sku_header": {"ko": "SKU별 매출", "en": "Revenue by SKU"},
    "marketing.header": {"ko": "지출, ROAS, 획득 효율", "en": "Spend, ROAS and acquisition efficiency"},
    "marketing.cac_header": {"ko": "채널별 고객 획득 비용(CAC)", "en": "Customer acquisition cost by channel"},
    "customer.new_share_current": {"ko": "신규 고객 비중 (현재)", "en": "New-customer share (current)"},
    "customer.new_share_previous": {"ko": "신규 고객 비중 (이전)", "en": "New-customer share (previous)"},
    "customer.repeat_rate": {"ko": "누적 재구매율", "en": "Lifetime repeat purchase rate"},
    "inventory.header": {"ko": "품절/과잉재고 위험 후보", "en": "Stock-out and excess-risk candidates"},
    "inventory.flagged_caption": {"ko": "전체 {total}개 SKU 중 {flagged}개 플래그됨", "en": "{flagged} of {total} SKUs flagged"},
    "inventory.all_skus_expander": {"ko": "전체 SKU 보기 ({n}개 · 클릭하여 펼치기)", "en": "All SKUs ({n} · click to expand)"},
    "decisions.header": {"ko": "우선순위가 매겨진 이슈", "en": "Prioritized issues"},
    "decision.supporting_kpi": {"ko": "근거 KPI", "en": "Supporting KPI"},
    "decision.kpi_expander": {
        "ko": "근거 KPI 보기 (지표 {n}개 · 클릭하여 펼치기)",
        "en": "Supporting KPIs ({n} metrics · click to expand)",
    },
    "decision.likely_drivers": {"ko": "유력한 원인", "en": "Likely driver(s)"},
    "decision.possible_action": {"ko": "제안 조치", "en": "Possible action"},
    "decision.kpi_to_monitor": {"ko": "모니터링할 KPI", "en": "KPI to monitor"},
    "decision.revenue_impact": {"ko": "예상 매출 영향", "en": "Estimated revenue impact"},
    "decision.trend": {"ko": "추세 (선택된 기준일까지)", "en": "Trend (through selected as-of)"},
}


EXTRA_STRINGS: dict[str, dict[str, str]] = {}  # strings contributed by lenses (Lens.strings)


def register_strings(strings: dict[str, dict[str, str]]) -> None:
    EXTRA_STRINGS.update(strings)


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    entry = UI_STRINGS.get(key) or EXTRA_STRINGS.get(key)
    if entry is None:
        return key
    template = entry.get(lang, entry.get(DEFAULT_LANG, key))
    return template.format(**kwargs) if kwargs else template


_SEVERITY_LABEL = {
    "ko": {"high": "🔴 high", "medium": "🟠 medium", "low": "🟢 low"},
    "en": {"high": "🔴 high", "medium": "🟠 medium", "low": "🟢 low"},
}


def severity_badge(severity: str, lang: str = DEFAULT_LANG) -> str:
    return _SEVERITY_LABEL.get(lang, _SEVERITY_LABEL[DEFAULT_LANG]).get(severity, severity)


def localize_decision(decision: dict, lang: str = DEFAULT_LANG) -> dict:
    """Returns a copy of `decision` with headline/likely_drivers/possible_action
    rendered in `lang`, rebuilt from the structured `affected`/`supporting_kpi`
    facts already on the item. `issue_type`, `severity`, `supporting_kpi`,
    `affected`, and `kpi_to_monitor` are left untouched -- those are facts
    and identifiers, not prose. The prose itself lives with the lens that
    raises the issue type (`Lens.localizers`); an issue type no lens
    localizes keeps the English prose it was created with."""
    from commerce_lab.lenses.registry import localizer_for

    localizer = localizer_for(decision["issue_type"])
    if localizer is None or lang not in LANGS:
        return decision
    prose = localizer(decision.get("affected", {}), decision.get("supporting_kpi", {}), lang)
    return {**decision, **prose}
