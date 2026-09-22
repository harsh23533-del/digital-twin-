"""
Dermatology risk model — placeholder classifier.

No DermNet dataset or existing ONNX/MobileNetV2 Skin Disease Analyzer
was available to reuse for this challenge (same situation as the
metabolic module vs. its "existing Lab Report Analyzer"). This keeps
the interface a real classifier would expose —
`classify(patient_id, image_ref) -> {label, confidence, malignancy_score}`
— backed by a deterministic, patient-seeded progression instead of
real pixels, so the rest of the pipeline (module -> risk score ->
dashboard) is fully wired and a real ONNX model can be dropped in
later by replacing only this file.
"""

import random

CLASSES = ["healthy", "eczema", "psoriasis", "benign_nevus", "basal_cell_carcinoma", "melanoma"]

# Rough concern/malignancy weight per class (0 = benign, 1 = most concerning),
# used both to pick a label from the simulated risk position and as the
# single risk score stored on the patient state.
MALIGNANCY_WEIGHT = {
    "healthy": 0.0, "eczema": 0.15, "psoriasis": 0.25,
    "benign_nevus": 0.35, "basal_cell_carcinoma": 0.7, "melanoma": 1.0,
}


class PlaceholderSkinClassifier:
    """Deterministic, patient-seeded pseudo-classifier standing in for the ONNX model."""

    def __init__(self):
        self._risk_position: dict[str, float] = {}  # patient_id -> current simulated risk (0-1)

    def classify(self, patient_id: str, image_ref: str) -> dict:
        # Seeded on patient_id + image_ref so results are reproducible per image,
        # while still drifting patient-to-patient over successive images.
        rng = random.Random(f"{patient_id}:{image_ref}")
        current = self._risk_position.get(patient_id, 0.05)
        current = max(0.0, min(1.0, current + rng.uniform(-0.05, 0.07)))
        self._risk_position[patient_id] = current

        label = min(MALIGNANCY_WEIGHT, key=lambda c: abs(MALIGNANCY_WEIGHT[c] - current))
        confidence = round(0.6 + rng.uniform(0, 0.35), 3)
        return {"label": label, "confidence": confidence, "malignancy_score": round(current, 3)}
