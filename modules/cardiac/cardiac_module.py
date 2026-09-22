"""
Cardiac module — plugs into the twin engine's tick loop.

On every 'vitals' reading, recomputes the rolling feature vector,
scores it with the reused XGBoost model, and attaches a SHAP-based
explanation so state.risk_scores['cardiac'] always comes with a reason.
"""

from modules.cardiac.model import load_model, FEATURE_NAMES
from modules.cardiac.rolling_features import build_feature_row


class CardiacModule:
    def __init__(self):
        self.model, self.scaler, self.explainer = load_model()

    def process(self, state) -> None:
        """Recompute cardiac risk for a patient state and store it."""
        row = build_feature_row(state.ehr_profile, state.vitals_history)
        scaled = self.scaler.transform(row)

        prob = float(self.model.predict_proba(scaled)[0][1])

        shap_values = self.explainer.shap_values(scaled)
        vals = shap_values[0] if isinstance(shap_values, list) else shap_values[0]
        contributions = dict(zip(FEATURE_NAMES, [float(v) for v in vals]))
        top_factors = dict(
            sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
        )

        state.update_risk("cardiac", prob, {"top_factors": top_factors})
