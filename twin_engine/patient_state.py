"""
Core patient state for the digital twin.

Holds one evolving patient's profile, a rolling vitals history buffer,
and the latest cardiac risk score. The cardiac module reads/writes into
this shared object.
"""

from dataclasses import dataclass, field
from collections import deque
from datetime import datetime
from typing import Any


@dataclass
class PatientState:
    patient_id: str
    ehr_profile: dict[str, Any] = field(default_factory=dict)

    # Rolling history buffer of vitals readings (bounded, most-recent-N)
    vitals_history: deque = field(default_factory=lambda: deque(maxlen=500))

    # Per-module risk scores, e.g. {"cardiac": {"score": 0.72, "explanation": {...}}}
    risk_scores: dict[str, Any] = field(default_factory=dict)

    last_updated: datetime = field(default_factory=datetime.now)

    def add_reading(self, reading_type: str, reading: dict[str, Any]) -> None:
        """Route a new reading into the correct history buffer."""
        if reading_type == "vitals":
            self.vitals_history.append(reading)
        else:
            raise ValueError(f"Unknown reading_type: {reading_type}")

        self.last_updated = datetime.now()

    def update_risk(self, module: str, score: float, explanation: dict | None = None) -> None:
        """Store the latest risk score + explanation for a module."""
        self.risk_scores[module] = {
            "score": score,
            "explanation": explanation or {},
            "updated_at": datetime.now(),
        }

    def summary(self) -> str:
        risks = ", ".join(
            f"{mod}={data['score']:.2f}" for mod, data in self.risk_scores.items()
        ) or "none yet"
        return (
            f"[{self.patient_id}] "
            f"vitals={len(self.vitals_history)} "
            f"| risk_scores: {risks} "
            f"| last_updated={self.last_updated.strftime('%H:%M:%S')}"
        )
