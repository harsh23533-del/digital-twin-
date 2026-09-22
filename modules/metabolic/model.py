"""
Metabolic risk model — rule-based lab report analyzer.

No existing "Lab Report Analyzer" model/repo was available to reuse for
this challenge (unlike the cardiac module, which reuses a trained
XGBoost model). Instead, this scores each lab marker against standard
clinical reference ranges (normal -> 0, borderline/high -> ramps to 1)
so the logic stays transparent and explainable, matching the SHAP-style
"reason behind the score" spirit of the cardiac module.

Markers are grouped into three organ-system domains; the domain score
is the mean of its markers, and the overall metabolic score is the
mean of the three domain scores.
"""

from typing import Any

# direction: "high_is_bad" (score rises as the value rises above `normal`)
#            "low_is_bad"  (score rises as the value falls below `normal`)
# normal: upper/lower bound of the normal range (score 0 at/inside this)
# high: value at which the marker is fully abnormal (score 1)
REFERENCE_RANGES: dict[str, dict[str, Any]] = {
    "creatinine": {"direction": "high_is_bad", "normal": 1.2, "high": 1.5},   # mg/dL
    "egfr":       {"direction": "low_is_bad",  "normal": 90,  "high": 60},   # mL/min/1.73m^2
    "alt":        {"direction": "high_is_bad", "normal": 40,  "high": 80},   # U/L
    "ast":        {"direction": "high_is_bad", "normal": 40,  "high": 80},   # U/L
    "glucose":    {"direction": "high_is_bad", "normal": 100, "high": 126},  # mg/dL, fasting
    "hba1c":      {"direction": "high_is_bad", "normal": 5.7, "high": 6.5},  # %
}

DOMAIN_MARKERS: dict[str, list[str]] = {
    "kidney": ["creatinine", "egfr"],
    "liver": ["alt", "ast"],
    "glucose": ["glucose", "hba1c"],
}


def score_reading(marker: str, value: float) -> float:
    """Map one lab value to a 0 (normal) - 1 (fully abnormal) score.

    For "low_is_bad" markers (e.g. eGFR, where lower is worse), the value
    is mirrored around `normal` so the same linear-ramp logic applies
    regardless of direction.
    """
    r = REFERENCE_RANGES[marker]
    normal, high = r["normal"], r["high"]

    if r["direction"] == "low_is_bad":
        value = normal - (value - normal)
        high = normal - (high - normal)

    if value <= normal:
        return 0.0
    if value >= high:
        return 1.0
    return (value - normal) / (high - normal)


def score_all(reading: dict[str, float]) -> dict[str, float]:
    """Score every marker present in a lab reading."""
    return {m: score_reading(m, reading[m]) for m in REFERENCE_RANGES if m in reading}


def domain_scores(marker_scores: dict[str, float]) -> dict[str, float]:
    """Aggregate marker scores into kidney / liver / glucose domain scores."""
    result = {}
    for domain, markers in DOMAIN_MARKERS.items():
        present = [marker_scores[m] for m in markers if m in marker_scores]
        if present:
            result[domain] = sum(present) / len(present)
    return result
