"""Calls Gemini to produce a grounded executive summary. Never raises --
a Gemini failure (missing credentials, quota, network, model change)
degrades to `gemini_summary: None`, and the app falls back to the
deterministic summary already built in `commerce_lab.app.view_helpers`
(PROJECT.md's Definition of Done requires the app to work even when the
AI layer is unavailable; Gemini is an interpretation layer, not a
dependency of the facts themselves).
"""

from __future__ import annotations

import logging

from .config import (
    GEMINI_LOCATION,
    GEMINI_MODEL,
    MAX_OUTPUT_TOKENS,
    MAX_SUMMARY_CHARS,
    REQUEST_TIMEOUT_MS,
    TEMPERATURE,
    THINKING_BUDGET,
    gemini_enabled,
    require_project_id,
)
from .prompts import build_executive_summary_prompt

logger = logging.getLogger(__name__)


def build_client():
    from google import genai
    from google.genai import types

    project_id = require_project_id()
    return genai.Client(
        vertexai=True,
        project=project_id,
        location=GEMINI_LOCATION,
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def build_generation_config():
    from google.genai import types

    return types.GenerateContentConfig(
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=TEMPERATURE,
        thinking_config=types.ThinkingConfig(thinking_budget=THINKING_BUDGET),
    )


def generate_executive_summary(snapshot: dict, client=None) -> str | None:
    """`client` is injectable for testing; a real `google.genai.Client`
    is built (and requires live credentials + GCP_PROJECT_ID) when not
    provided."""
    if not gemini_enabled():
        logger.info("GEMINI_ENABLED is off; skipping Gemini call.")
        return None

    prompt = build_executive_summary_prompt(
        snapshot.get("sales", {}).get("summary", {}), snapshot["decisions"], snapshot["period"]
    )

    try:
        if client is None:
            client = build_client()
        response = client.models.generate_content(
            model=GEMINI_MODEL, contents=prompt, config=build_generation_config()
        )
        text = getattr(response, "text", None)
        return text.strip()[:MAX_SUMMARY_CHARS] if text else None
    except Exception:  # noqa: BLE001 -- deliberate: any Gemini failure must degrade, never crash the refresh
        logger.warning("Gemini executive summary generation failed; falling back to None.", exc_info=True)
        return None
