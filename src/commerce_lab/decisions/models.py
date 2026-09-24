"""The structured decision-item shape used by every rule in
`commerce_lab.decisions.rules`.

Per PROJECT.md §7: a decision item states the issue, the supporting
fact/KPI, likely driver(s), the affected brand/channel/SKU, a severity
computed by a deterministic rule, a possible action, and the KPI to watch
afterward. Gemini (M6) may narrate this structure but never invents its
facts or severity.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DecisionItem:
    issue_type: str  # stable machine-readable category, e.g. "marketing_efficiency_decline"
    headline: str  # short human-readable summary
    severity: str  # "high" | "medium" | "low"
    supporting_kpi: dict = field(default_factory=dict)
    likely_drivers: list[str] = field(default_factory=list)
    affected: dict = field(default_factory=dict)  # e.g. {"brand": ..., "channel": ..., "sku_id": ...}
    possible_action: str = ""
    kpi_to_monitor: str = ""
    lens: str = ""  # id of the lens that raised it; stamped by lenses.registry.run_detection

    def to_dict(self) -> dict:
        return {
            "issue_type": self.issue_type,
            "headline": self.headline,
            "severity": self.severity,
            "supporting_kpi": self.supporting_kpi,
            "likely_drivers": self.likely_drivers,
            "affected": self.affected,
            "possible_action": self.possible_action,
            "kpi_to_monitor": self.kpi_to_monitor,
            "lens": self.lens,
        }


SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
