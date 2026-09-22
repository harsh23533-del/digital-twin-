"""
Rolling-window feature builder for the cardiac module.

The trained model expects a static 13-field clinical snapshot
(age, sex, cp, trestbps, chol, fbs, restecg, thalach, exang, oldpeak,
slope, ca, thal). A wearable only streams a couple of live signals
(heart_rate, spo2) — it can't re-run bloodwork every tick. So:

- Static fields (age, sex, cp, chol, fbs, restecg, exang, oldpeak,
  slope, ca, thal) come from the patient's EHR baseline, captured once.
- The two fields a wearable *can* keep fresh — trestbps (resting BP)
  and thalach (max heart rate achieved) — are recomputed each tick
  from a rolling window over the recent vitals stream, so the risk
  score actually reacts to incoming wearable data instead of being frozen.
"""

from collections import deque
import pandas as pd
from modules.cardiac.model import FEATURE_NAMES

# Sensible clinical defaults, used only for any EHR field a patient hasn't set.
_DEFAULT_EHR = {
    "age": 50, "sex": 1, "cp": 3, "chol": 200, "fbs": 0,
    "restecg": 0, "exang": 0, "oldpeak": 1.0, "slope": 2, "ca": 0, "thal": 3,
    "resting_trestbps": 120,  # fallback resting BP if no wearable BP reading yet
}

ROLLING_WINDOW = 10  # last N vitals readings used for trestbps/thalach


def build_feature_row(ehr_profile: dict, vitals_history: deque) -> pd.DataFrame:
    """Build the model's 13-feature row from EHR baseline + rolling vitals."""
    ehr = {**_DEFAULT_EHR, **ehr_profile}

    recent = list(vitals_history)[-ROLLING_WINDOW:]
    hr_readings = [r["heart_rate"] for r in recent if "heart_rate" in r]
    bp_readings = [r["trestbps"] for r in recent if "trestbps" in r]

    # thalach = max HR achieved in the rolling window (falls back to EHR default)
    thalach = max(hr_readings) if hr_readings else ehr.get("thalach", 150)
    # trestbps = rolling average resting BP if the wearable reports it, else baseline
    trestbps = (sum(bp_readings) / len(bp_readings)) if bp_readings else ehr["resting_trestbps"]

    row = {
        "age": ehr["age"], "sex": ehr["sex"], "cp": ehr["cp"],
        "trestbps": trestbps, "chol": ehr["chol"], "fbs": ehr["fbs"],
        "restecg": ehr["restecg"], "thalach": thalach, "exang": ehr["exang"],
        "oldpeak": ehr["oldpeak"], "slope": ehr["slope"], "ca": ehr["ca"],
        "thal": ehr["thal"],
    }
    return pd.DataFrame([row], columns=FEATURE_NAMES)
