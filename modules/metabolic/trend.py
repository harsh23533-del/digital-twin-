"""
Trend detection across consecutive lab readings.

Compares the newest lab reading to the rolling average of the previous
readings (a short baseline window, excluding the newest) for each
marker, and classifies it as worsening / improving / stable — direction
-aware, so e.g. a falling eGFR is "worsening" while a falling glucose is
"improving".
"""

from collections import deque
from modules.metabolic.model import REFERENCE_RANGES

TREND_WINDOW = 5             # how many prior readings define the recent baseline
CHANGE_THRESHOLD_PCT = 0.05  # ignore moves smaller than this as noise


def _direction_sign(marker: str) -> int:
    """+1 if an increase in this marker means the patient is getting worse, else -1."""
    return -1 if REFERENCE_RANGES[marker]["direction"] == "low_is_bad" else 1


def detect_trends(lab_history: deque) -> dict[str, str]:
    """Return {marker: 'worsening' | 'improving' | 'stable'} for the latest reading."""
    readings = list(lab_history)
    if len(readings) < 2:
        return {marker: "stable" for marker in REFERENCE_RANGES if readings and marker in readings[-1]}

    latest = readings[-1]
    baseline_window = readings[max(0, len(readings) - 1 - TREND_WINDOW):-1]

    trends = {}
    for marker in REFERENCE_RANGES:
        if marker not in latest:
            continue
        baseline_vals = [r[marker] for r in baseline_window if marker in r]
        if not baseline_vals:
            trends[marker] = "stable"
            continue

        baseline_avg = sum(baseline_vals) / len(baseline_vals)
        if baseline_avg == 0:
            trends[marker] = "stable"
            continue

        pct_change = (latest[marker] - baseline_avg) / abs(baseline_avg)
        signed_change = pct_change * _direction_sign(marker)

        if signed_change > CHANGE_THRESHOLD_PCT:
            trends[marker] = "worsening"
        elif signed_change < -CHANGE_THRESHOLD_PCT:
            trends[marker] = "improving"
        else:
            trends[marker] = "stable"
    return trends
