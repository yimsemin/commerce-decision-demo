from __future__ import annotations

import json

from commerce_lab.gemini.prompts import build_executive_summary_prompt


def test_prompt_embeds_only_provided_facts_as_json():
    sales_summary = {"current": {"net_revenue": 1000}, "previous": {"net_revenue": 900}, "pct_change": {"net_revenue": 11.1}}
    decisions = [{"issue_type": "sales_decline", "headline": "Material sales decline in Marlow / retail_partner"}]
    period = {"current_start": "2026-08-23", "current_end": "2026-09-21"}

    prompt = build_executive_summary_prompt(sales_summary, decisions, period)

    assert "Marlow / retail_partner" in prompt
    assert "do not invent" in prompt.lower() or "must not" in prompt.lower()

    # the embedded JSON block round-trips to exactly the facts passed in
    json_start = prompt.index("{")
    json_end = prompt.rindex("}") + 1
    embedded = json.loads(prompt[json_start:json_end])
    assert embedded == {"period": period, "sales_summary": sales_summary, "decisions": decisions}
