from __future__ import annotations

from commerce_lab.gemini.summarize import generate_executive_summary

SNAPSHOT = {
    "period": {"current_start": "2026-08-23", "current_end": "2026-09-21"},
    "sales": {"summary": {"current": {"net_revenue": 1000}, "pct_change": {"net_revenue": -5.0}}},
    "decisions": [{"issue_type": "sales_decline", "headline": "Material sales decline in Marlow / retail_partner"}],
}


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, text=None, raise_exc=None):
        self._text = text
        self._raise_exc = raise_exc
        self.calls = []

    def generate_content(self, *, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self._raise_exc:
            raise self._raise_exc
        return FakeResponse(self._text)


class FakeClient:
    def __init__(self, text=None, raise_exc=None):
        self.models = FakeModels(text=text, raise_exc=raise_exc)


def test_generate_executive_summary_returns_stripped_text():
    client = FakeClient(text="  Revenue is down 5%, driven by Marlow / retail_partner.  ")
    result = generate_executive_summary(SNAPSHOT, client=client)
    assert result == "Revenue is down 5%, driven by Marlow / retail_partner."
    assert client.models.calls[0]["model"] == "gemini-2.5-flash"


def test_generate_executive_summary_returns_none_on_empty_text():
    client = FakeClient(text=None)
    assert generate_executive_summary(SNAPSHOT, client=client) is None


def test_generate_executive_summary_never_raises_on_client_failure():
    client = FakeClient(raise_exc=RuntimeError("quota exceeded"))
    result = generate_executive_summary(SNAPSHOT, client=client)  # must not raise
    assert result is None


def test_generate_executive_summary_passes_conservative_limits():
    client = FakeClient(text="ok")
    generate_executive_summary(SNAPSHOT, client=client)
    config = client.models.calls[0]["config"]
    assert config.max_output_tokens == 400
    assert config.thinking_config.thinking_budget == 0


def test_generate_executive_summary_truncates_overlong_output():
    client = FakeClient(text="x" * 5000)
    assert len(generate_executive_summary(SNAPSHOT, client=client)) == 1500


def test_kill_switch_skips_call_entirely(monkeypatch):
    monkeypatch.setenv("GEMINI_ENABLED", "false")
    client = FakeClient(text="should not be used")
    assert generate_executive_summary(SNAPSHOT, client=client) is None
    assert client.models.calls == []
