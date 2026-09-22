"""
Metabolic module — plugs into the twin engine's tick loop.

On every 'lab' reading, scores kidney/liver/glucose markers against
reference ranges and layers trend detection across the rolling lab
history, so state.risk_scores['metabolic'] always comes with a score
plus a per-marker worsening/improving/stable read — the metabolic
counterpart to the cardiac module's SHAP explanation.
"""

from modules.metabolic.model import REFERENCE_RANGES, score_all, domain_scores
from modules.metabolic.trend import detect_trends


class MetabolicModule:
    def process(self, state) -> None:
        """Recompute metabolic risk for a patient state and store it."""
        if not state.lab_history:
            return

        latest = state.lab_history[-1]
        marker_scores = score_all(latest)
        domains = domain_scores(marker_scores)
        overall = sum(domains.values()) / len(domains) if domains else 0.0
        trends = detect_trends(state.lab_history)

        state.update_risk("metabolic", overall, {
            "domain_scores": {k: round(v, 3) for k, v in domains.items()},
            "marker_scores": {k: round(v, 3) for k, v in marker_scores.items()},
            "trends": trends,
            "latest_reading": latest,
        })
