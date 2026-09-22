"""
Dermatology risk model — real trained classifier, exported to ONNX.

No DermNet dataset or existing "Skin Disease Analyzer" repo was
accessible to reuse in this build environment (no Kaggle/DermNet
network access here). Instead of faking scores, this trains a real
neural-network classifier on the ABCD-rule features extracted from
synthetic dermoscopy images (see synthetic_data.py — the images are
genuinely rendered pixels, and features are re-extracted from those
pixels, not handed the generation parameters). The model is exported
to ONNX and served through onnxruntime.InferenceSession, exactly the
inference path a real DermNet-trained MobileNetV2 export would use —
only the training data source differs. Swapping in a real model later
means replacing `_train_and_cache()`'s data source and keeping
`load_classifier()` / `classify()` as the interface.
"""

from __future__ import annotations

import os
import numpy as np
import onnxruntime as ort
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score

from modules.dermatology.synthetic_data import (
    generate_dataset, extract_features, CLASSES, FEATURE_NAMES,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_ARTIFACT_DIR = os.path.join(_HERE, "artifacts")
_ONNX_PATH = os.path.join(_ARTIFACT_DIR, "skin_classifier.onnx")
_SCALER_MEAN_PATH = os.path.join(_ARTIFACT_DIR, "scaler_mean.npy")
_SCALER_SCALE_PATH = os.path.join(_ARTIFACT_DIR, "scaler_scale.npy")

# Malignancy weight per class (0 = benign, 1 = most concerning) — used to turn
# the model's class-probability distribution into a single risk score.
MALIGNANCY_WEIGHT = {
    "healthy": 0.0, "eczema": 0.15, "psoriasis": 0.25,
    "benign_nevus": 0.35, "basal_cell_carcinoma": 0.7, "melanoma": 1.0,
}


def _train_and_cache() -> tuple[str, np.ndarray, np.ndarray]:
    os.makedirs(_ARTIFACT_DIR, exist_ok=True)

    X, y_labels, _ = generate_dataset(n_per_class=300, seed=42)
    y = np.array([CLASSES.index(c) for c in y_labels])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc = scaler.transform(X_test)

    clf = MLPClassifier(
        hidden_layer_sizes=(24,), activation="relu", max_iter=3000,
        random_state=42, early_stopping=True, alpha=0.01,
    )
    clf.fit(X_train_sc, y_train)

    acc = accuracy_score(y_test, clf.predict(X_test_sc))
    print(f"[dermatology model] trained — held-out accuracy: {acc:.4f} ({len(CLASSES)} classes)")

    # Export to ONNX.
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    onnx_model = convert_sklearn(
        clf, initial_types=[("input", FloatTensorType([None, X.shape[1]]))],
        target_opset=15,
    )
    with open(_ONNX_PATH, "wb") as f:
        f.write(onnx_model.SerializeToString())

    np.save(_SCALER_MEAN_PATH, scaler.mean_)
    np.save(_SCALER_SCALE_PATH, scaler.scale_)

    return _ONNX_PATH, scaler.mean_, scaler.scale_


def load_classifier():
    """Load the cached ONNX model + scaler, training once if missing."""
    if not (os.path.exists(_ONNX_PATH) and os.path.exists(_SCALER_MEAN_PATH)):
        _train_and_cache()

    session = ort.InferenceSession(_ONNX_PATH, providers=["CPUExecutionProvider"])
    scaler_mean = np.load(_SCALER_MEAN_PATH)
    scaler_scale = np.load(_SCALER_SCALE_PATH)
    return session, scaler_mean, scaler_scale


class OnnxSkinClassifier:
    """Real ONNX-Runtime-backed skin lesion classifier."""

    def __init__(self):
        self.session, self.scaler_mean, self.scaler_scale = load_classifier()
        self.input_name = self.session.get_inputs()[0].name

    def classify(self, image: np.ndarray) -> dict:
        """Classify a rendered lesion image (HxWx3 uint8 array).

        Returns {label, confidence, malignancy_score, probabilities}.
        malignancy_score is the probability-weighted expected severity
        across all classes (not just the argmax), so it moves smoothly
        as the predicted distribution shifts.
        """
        features = extract_features(image)
        scaled = ((features - self.scaler_mean) / self.scaler_scale).astype(np.float32)

        outputs = self.session.run(None, {self.input_name: scaled.reshape(1, -1)})
        # skl2onnx MLPClassifier output: [labels, probabilities(dict or array)]
        probs_out = outputs[1]
        if isinstance(probs_out, list):
            prob_map = probs_out[0]  # {class_index: prob}
            probs = np.array([prob_map[i] for i in range(len(CLASSES))])
        else:
            probs = np.asarray(probs_out[0])

        pred_idx = int(np.argmax(probs))
        label = CLASSES[pred_idx]
        confidence = float(probs[pred_idx])
        malignancy_score = float(sum(
            probs[i] * MALIGNANCY_WEIGHT[CLASSES[i]] for i in range(len(CLASSES))
        ))

        return {
            "label": label,
            "confidence": round(confidence, 3),
            "malignancy_score": round(malignancy_score, 3),
            "probabilities": {CLASSES[i]: round(float(probs[i]), 3) for i in range(len(CLASSES))},
        }


if __name__ == "__main__":
    load_classifier()
