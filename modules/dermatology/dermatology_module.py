"""
Dermatology module — plugs into the twin engine's tick loop.

On every 'image' reading, runs the real ONNX skin-lesion classifier
(modules/dermatology/model.py) on the rendered lesion image and tracks
progression across the rolling skin-image history, so
state.risk_scores['dermatology'] comes with a label, confidence, and a
probability-weighted malignancy score.

Stretch-goal module (Step 7). Only wired in once Steps 1-6 were done,
per the build plan's "a polished 2-module twin beats a shallow 3-module
one" guidance.
"""

from modules.dermatology.model import OnnxSkinClassifier


class DermatologyModule:
    def __init__(self):
        self.classifier = OnnxSkinClassifier()

    def process(self, state) -> None:
        """Recompute dermatology risk for a patient state and store it."""
        if not state.skin_history:
            return

        latest = state.skin_history[-1]
        image = latest.get("image")
        if image is None:
            return  # reading has no image payload yet

        result = self.classifier.classify(image)

        state.update_risk("dermatology", result["malignancy_score"], {
            "label": result["label"],
            "confidence": result["confidence"],
            "probabilities": result["probabilities"],
            "image_ref": latest.get("image_ref"),
        })
