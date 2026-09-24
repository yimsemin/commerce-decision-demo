"""Builds the grounding prompt sent to Gemini.

Per PROJECT.md §7 and CLAUDE.md: Gemini interprets structured results, it
is never the source of the facts. The prompt therefore embeds only the
M4 decision items and a small set of top-line KPI numbers -- never raw
orders/marketing/inventory rows -- and explicitly instructs the model
not to invent facts and to state uncertainty.
"""

from __future__ import annotations

import json

SYSTEM_INSTRUCTION = """You are an analyst assistant summarizing a commerce business review for an \
executive audience. You are given a fixed set of structured facts: overall sales KPIs and a list of \
already-detected decision items (issue, supporting KPI, likely driver, severity, possible action, \
KPI to monitor). These facts were computed deterministically before you were called -- you did not \
compute them and must not recompute, contradict, or add new numbers.

Rules:
- Use only the facts provided below. Do not invent additional metrics, causes, or numbers.
- If you are uncertain about the cause of something, say so explicitly rather than guessing.
- Be concise: a short executive summary (3-5 sentences), referencing the highest-severity issues first.
- Do not repeat every field verbatim; synthesize into plain business language.
"""


def build_executive_summary_prompt(sales_summary: dict, decisions: list[dict], period: dict) -> str:
    facts = {
        "period": period,
        "sales_summary": sales_summary,
        "decisions": decisions,
    }
    return (
        SYSTEM_INSTRUCTION
        + "\nFacts (JSON):\n"
        + json.dumps(facts, indent=2)
        + "\n\nWrite the executive summary now."
    )
