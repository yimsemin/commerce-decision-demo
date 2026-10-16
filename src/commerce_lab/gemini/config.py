"""Gemini/Vertex AI configuration.

Model and location were chosen deliberately, not defaulted:

- Location: `us-central1`. The refresh job's service account got
  `403 PERMISSION_DENIED` on `aiplatform.endpoints.predict` for the
  `global` publisher-model resource despite `roles/aiplatform.user`, while
  the same call worked with a user account; a standard regional endpoint
  works. The root cause (likely an org-level policy) is not known --
  see docs/operations.md.
- Model: `gemini-2.5-flash`. Fast/cheap, sufficient for summarizing a
  small structured decision list; this is not a reasoning-heavy task.
"""

from __future__ import annotations

import os

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_LOCATION = "us-central1"

# Deliberately conservative limits (owner request 2026-09-24: the Gemini
# path is the most attractive abuse/cost target). Only the scheduled
# refresh job ever calls Gemini -- the public app never does, and the
# prompt is built purely from the pipeline's own structured facts, so
# there is no user-supplied input to inject into.
MAX_OUTPUT_TOKENS = 400
TEMPERATURE = 0.2
THINKING_BUDGET = 0  # 2.5-flash "thinking" tokens are billed as output
REQUEST_TIMEOUT_MS = 30_000
MAX_SUMMARY_CHARS = 1500


def gemini_enabled() -> bool:
    """Kill switch: set GEMINI_ENABLED=false on the refresh job to stop
    every Gemini call without a redeploy of code."""
    return os.environ.get("GEMINI_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def require_project_id() -> str:
    project_id = os.environ.get("GCP_PROJECT_ID")
    if not project_id:
        raise RuntimeError(
            "Missing required environment variable: GCP_PROJECT_ID "
            "(identifies the owner's GCP project; never hardcoded)."
        )
    return project_id
