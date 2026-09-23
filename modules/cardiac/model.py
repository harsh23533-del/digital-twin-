"""
Cardiac risk model — reused from harsh23533-del/heart-disease-predictor.

Same architecture and hyperparameters as the deployed Streamlit app's
Heart_Disease.py (XGBoost on the Cleveland dataset). That original app
reported ~0.94 AUC-ROC; this rebuild's own held-out split measures
~0.92 (printed below on training) — same model family, different
train/test split, so the two numbers aren't directly comparable.
Trains once from the local CSV mirror (data/cardiac/cleveland_heart.csv)
and caches model.pkl / scaler.pkl / features.pkl under artifacts/, so
later runs load instantly instead of retraining.
"""

import os
import joblib
import shap
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_CSV = os.path.join(_HERE, "..", "..", "data", "cardiac", "cleveland_heart.csv")
_ARTIFACT_DIR = os.path.join(_HERE, "artifacts")

_MODEL_PATH = os.path.join(_ARTIFACT_DIR, "model.pkl")
_SCALER_PATH = os.path.join(_ARTIFACT_DIR, "scaler.pkl")
_FEATURES_PATH = os.path.join(_ARTIFACT_DIR, "features.pkl")

FEATURE_NAMES = [
    "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
    "thalach", "exang", "oldpeak", "slope", "ca", "thal",
]


def _load_and_preprocess():
    df = pd.read_csv(_DATA_CSV, na_values="?")
    df.dropna(inplace=True)
    df = df.astype(float)

    X = df[FEATURE_NAMES]
    y = (df["diagnosis"] > 0).astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc = scaler.transform(X_test)
    return X_train_sc, X_test_sc, y_train, y_test, scaler


def _train_and_cache():
    os.makedirs(_ARTIFACT_DIR, exist_ok=True)
    X_train, X_test, y_train, y_test, scaler = _load_and_preprocess()

    model = XGBClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
        eval_metric="logloss",
    )
    model.fit(X_train, y_train)

    auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    print(f"[cardiac model] trained — held-out AUC-ROC: {auc:.4f}")

    joblib.dump(model, _MODEL_PATH)
    joblib.dump(scaler, _SCALER_PATH)
    joblib.dump(FEATURE_NAMES, _FEATURES_PATH)
    return model, scaler


def load_model():
    """Load cached model+scaler, training once from the local CSV if missing."""
    if os.path.exists(_MODEL_PATH) and os.path.exists(_SCALER_PATH):
        model = joblib.load(_MODEL_PATH)
        scaler = joblib.load(_SCALER_PATH)
    else:
        model, scaler = _train_and_cache()

    explainer = shap.TreeExplainer(model)
    return model, scaler, explainer


if __name__ == "__main__":
    load_model()
