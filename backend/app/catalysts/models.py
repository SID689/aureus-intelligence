"""
app/catalysts/models.py
-------------------------
The one shape every catalyst source produces.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

Scope = Literal["company", "sector", "macro"]
Impact = Literal["high", "medium", "low"]
Direction = Literal["positive", "negative", "neutral", "unknown"]

TYPE_LABELS: dict[str, str] = {
    "earnings": "Earnings",
    "guidance": "Guidance",
    "dividend": "Dividend",
    "merger_acquisition": "M&A",
    "material_agreement": "Material agreement",
    "control_change": "Change of control",
    "financing": "Financing",
    "restructuring": "Restructuring",
    "impairment": "Impairment",
    "bankruptcy": "Bankruptcy",
    "cybersecurity_incident": "Cyber incident",
    "delisting": "Listing notice",
    "accounting_restatement": "Restatement",
    "auditor_change": "Auditor change",
    "leadership_change": "Leadership change",
    "shareholder_vote": "Shareholder vote",
    "shareholder_rights": "Shareholder rights",
    "governance": "Governance",
    "other_material_event": "Material event",
    "regulatory_fda": "FDA decision",
    "fda_advisory_committee": "FDA advisory committee",
    "legal_regulatory": "Legal / regulatory",
    "fomc": "FOMC",
}

# The timeline's filter buckets. Kept beside the labels so a new type cannot
# ship without deciding where a reader will find it.
TYPE_GROUPS: dict[str, str] = {
    "earnings": "earnings", "guidance": "earnings",
    "merger_acquisition": "deals", "material_agreement": "deals",
    "control_change": "deals", "financing": "deals",
    "regulatory_fda": "regulatory", "fda_advisory_committee": "regulatory",
    "legal_regulatory": "regulatory", "delisting": "regulatory",
    "accounting_restatement": "regulatory", "auditor_change": "regulatory",
    "cybersecurity_incident": "regulatory", "bankruptcy": "regulatory",
    "impairment": "regulatory", "restructuring": "regulatory",
    "dividend": "corporate", "leadership_change": "corporate",
    "shareholder_vote": "corporate", "shareholder_rights": "corporate",
    "governance": "corporate", "other_material_event": "corporate",
    "fomc": "macro",
}

IMPACT_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


def stable_hash(*parts: object, length: int = 16) -> str:
    """Deterministic short hash for dedupe keys built from free text."""
    raw = "␟".join("" if p is None else str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:length]


@dataclass
class Catalyst:
    dedupe_key: str
    scope: Scope
    catalyst_type: str
    title: str
    event_date: date
    impact: Impact
    source: str
    ticker: str | None = None
    sector: str | None = None
    description: str | None = None
    event_time: str | None = None
    # None = the source did not say. See migration 013.
    date_confirmed: bool | None = None
    direction: Direction = "unknown"
    source_url: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.scope == "company" and not self.ticker:
            raise ValueError(f"company catalyst without a ticker: {self.dedupe_key}")
        if self.scope != "company" and self.ticker:
            raise ValueError(f"{self.scope} catalyst must not carry a ticker: {self.dedupe_key}")
        if self.catalyst_type not in TYPE_LABELS:
            raise ValueError(f"unknown catalyst type {self.catalyst_type!r}")
        if self.ticker:
            self.ticker = self.ticker.upper().strip()

    def to_row(self) -> dict[str, Any]:
        return {
            "dedupe_key": self.dedupe_key,
            "scope": self.scope,
            "ticker": self.ticker,
            "sector": self.sector,
            "catalyst_type": self.catalyst_type,
            "title": self.title[:300],
            "description": (self.description or None) and self.description[:1000],
            "event_date": self.event_date,
            "event_time": self.event_time,
            "date_confirmed": self.date_confirmed,
            "impact": self.impact,
            "direction": self.direction,
            "source": self.source,
            "source_url": self.source_url,
            "details": json.dumps(self.details, default=str),
        }
