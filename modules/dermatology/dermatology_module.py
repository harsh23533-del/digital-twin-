"""
Dermatology module — plugs into the twin engine's tick loop.

On every 'image' reading, classifies the skin image (placeholder
classifier — see modules/dermatology/model.py) and tracks progression
across the rolling skin-image history, so state.risk_scores['dermatology']
comes with a label, confidence, and a malignancy-based risk score.

Stretch-goal module (Step 7). Only wired in once Steps 1-6 were done,
per the build plan's "a polished 2-module twin beats a shallow 3-module
one" guidance.
"""

from modules.dermatology.model import PlaceholderSkinClassifier


class DermatologyModule:
    def __init__(self):
        self.classifier = PlaceholderSkinClassifier()

    def process(self, state) -> None:
        """Recompute dermatology risk for a patient state and store it."""
        if not state.skin_history:
            return

        latest = state.skin_history[-1]
        image_ref = latest.get("image_ref")
        result = self.classifier.classify(state.patient_id, image_ref)

        state.update_risk("dermatology", result["malignancy_score"], {
            "label": result["label"],
            "confidence": result["confidence"],
            "image_ref": image_ref,
        })
