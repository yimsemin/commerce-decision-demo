from __future__ import annotations

from commerce_lab.app.copy_prompt import build_copy_prompt
from commerce_lab.pipeline.snapshot import build_snapshot_history


def _latest(datasets):
    history = build_snapshot_history(datasets)
    return history["snapshots"][history["latest_as_of_date"]]


def test_prompt_is_grounded_and_language_specific(datasets):
    snap = _latest(datasets)
    en = build_copy_prompt(snap, "en")
    ko = build_copy_prompt(snap, "ko")
    assert "Use ONLY these facts" in en and "Facts (JSON):" in en
    assert "이 사실만 사용" in ko
    assert snap["as_of_date"] in en
    assert snap["decisions"][0]["severity"] in en


def test_prompt_contains_no_credentials_or_urls(datasets):
    prompt = build_copy_prompt(_latest(datasets), "en")
    for needle in ("http", "@", "project", "bucket", "token"):
        assert needle not in prompt.lower().replace("project_id", "")
