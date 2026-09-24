from __future__ import annotations

import pytest

from commerce_lab.gemini.config import require_project_id


def test_require_project_id_raises_when_missing(monkeypatch):
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    with pytest.raises(RuntimeError, match="GCP_PROJECT_ID"):
        require_project_id()


def test_require_project_id_returns_value_when_set(monkeypatch):
    monkeypatch.setenv("GCP_PROJECT_ID", "demo-project")
    assert require_project_id() == "demo-project"
