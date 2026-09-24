"""Builds a self-contained prompt the user can paste into any AI assistant
(ChatGPT, Claude, Gemini, ...). Deterministic and offline: no model is
called here. The facts embedded are the same pre-computed, synthetic
snapshot values the app already shows, so the assistant interprets them
but never computes them (same grounding rule as the Gemini layer).
"""

from __future__ import annotations

import json

from commerce_lab.app.i18n import DEFAULT_LANG, localize_decision
from commerce_lab.app.view_helpers import top_issues

_INSTRUCTIONS = {
    "en": (
        "You are an analyst assistant helping a commerce executive decide what to do this week.\n"
        "Below are pre-computed facts (synthetic demo data). Use ONLY these facts: do not invent "
        "numbers or causes, and say so explicitly when something is uncertain.\n\n"
        "Please:\n"
        "1. Summarize the situation in 3-5 sentences, highest severity first.\n"
        "2. Rank the issues by what to act on first and why.\n"
        "3. For the top issue, list what extra data you would want before committing to the suggested action.\n"
    ),
    "ko": (
        "당신은 커머스 경영진이 이번 주에 무엇을 해야 할지 판단하도록 돕는 분석 어시스턴트입니다.\n"
        "아래는 미리 계산된 사실(합성 데모 데이터)입니다. 반드시 이 사실만 사용하고, 숫자나 원인을 "
        "지어내지 말며, 불확실한 부분은 불확실하다고 명시하세요.\n\n"
        "요청:\n"
        "1. 상황을 3~5문장으로 요약하세요(심각도 높은 이슈부터).\n"
        "2. 무엇부터 조치해야 하는지 우선순위를 매기고 이유를 설명하세요.\n"
        "3. 가장 중요한 이슈에 대해, 제안된 조치를 확정하기 전에 추가로 필요한 데이터를 나열하세요.\n"
    ),
}


def build_copy_prompt(snapshot: dict, lang: str = DEFAULT_LANG, n: int = 5) -> str:
    facts = {
        "as_of_date": snapshot["as_of_date"],
        "period": snapshot["period"],
        "sales_summary": snapshot.get("sales", {}).get("summary", {}),
        "issues": [
            {
                "headline": d["headline"],
                "severity": d["severity"],
                "supporting_kpi": d["supporting_kpi"],
                "likely_drivers": d["likely_drivers"],
                "possible_action": d["possible_action"],
                "kpi_to_monitor": d["kpi_to_monitor"],
            }
            for d in (localize_decision(x, lang=lang) for x in top_issues(snapshot["decisions"], n=n))
        ],
    }
    header = _INSTRUCTIONS.get(lang, _INSTRUCTIONS[DEFAULT_LANG])
    return header + "\nFacts (JSON):\n" + json.dumps(facts, indent=2, ensure_ascii=False)
