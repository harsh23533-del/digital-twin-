"""
Step 10 — Testing & Validation.

Plain assert-based test suite (no pytest dependency) covering the four
checks the build plan calls for:

1. Parity: each module's output vs. the underlying model called directly
   on the same input.
2. Multi-day consistency: the tick loop runs over a long simulated
   timeline without state corruption.
3. Threshold-breach alerts: extreme inputs push scores past the alert
   thresholds used in app.py / the dashboard tabs.
4. Multi-patient personalization: two distinct patients produce
   distinct outputs from the same engine.

Run:
    python3 tests/test_engine.py
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from twin_engine.patient_state import PatientState  # noqa: E402
from twin_engine.scheduler import DummySimulator, tick  # noqa: E402
from modules.cardiac.cardiac_module import CardiacModule  # noqa: E402
from modules.cardiac.model import load_model as load_cardiac_model  # noqa: E402
from modules.cardiac.rolling_features import build_feature_row  # noqa: E402
from modules.metabolic.metabolic_module import MetabolicModule  # noqa: E402
from modules.metabolic.model import score_all, domain_scores  # noqa: E402
from modules.dermatology.dermatology_module import DermatologyModule  # noqa: E402
from modules.dermatology.model import OnnxSkinClassifier  # noqa: E402
from modules.dermatology.synthetic_data import generate_image  # noqa: E402
from config import (  # noqa: E402
    CARDIAC_ALERT_THRESHOLD, DOMAIN_ALERT_THRESHOLD, DERM_ALERT_THRESHOLD,
)

_results = []


def check(name: str, fn) -> None:
    try:
        fn()
        _results.append((name, True, None))
        print(f"  PASS  {name}")
    except AssertionError as e:
        _results.append((name, False, str(e)))
        print(f"  FAIL  {name}: {e}")
    except Exception as e:
        _results.append((name, False, f"{type(e).__name__}: {e}"))
        print(f"  ERROR {name}: {type(e).__name__}: {e}")
        traceback.print_exc()


# ------------------------------------------------------------- 1. Parity

def test_cardiac_parity():
    ehr = {
        "age": 58, "sex": 1, "cp": 2, "chol": 245, "fbs": 1,
        "restecg": 1, "exang": 1, "oldpeak": 1.8, "slope": 1, "ca": 1, "thal": 2,
    }
    state = PatientState(patient_id="parity_cardiac", ehr_profile=ehr)
    state.add_reading("vitals", {"heart_rate": 95, "spo2": 96})

    cardiac = CardiacModule()
    cardiac.process(state)
    via_module = state.risk_scores["cardiac"]["score"]

    model, scaler, _ = load_cardiac_model()
    row = build_feature_row(ehr, state.vitals_history)
    direct = float(model.predict_proba(scaler.transform(row))[0][1])

    assert abs(via_module - direct) < 1e-9, f"module={via_module} direct={direct}"


def test_metabolic_parity():
    reading = {"creatinine": 1.6, "egfr": 55.0, "alt": 90.0, "ast": 88.0, "glucose": 140.0, "hba1c": 7.2}
    state = PatientState(patient_id="parity_metabolic")
    state.add_reading("lab", reading)

    metabolic = MetabolicModule()
    metabolic.process(state)
    via_module = state.risk_scores["metabolic"]["score"]

    marker_scores = score_all(reading)
    domains = domain_scores(marker_scores)
    direct = sum(domains.values()) / len(domains)

    assert abs(via_module - direct) < 1e-9, f"module={via_module} direct={direct}"


def test_dermatology_parity():
    rng = np.random.default_rng(7)
    img, _ = generate_image("melanoma", rng)

    state = PatientState(patient_id="parity_derm")
    state.add_reading("image", {"image_ref": "parity.jpg", "image": img})

    dermatology = DermatologyModule()
    dermatology.process(state)
    via_module = state.risk_scores["dermatology"]["score"]
    via_module_label = state.risk_scores["dermatology"]["explanation"]["label"]

    classifier = OnnxSkinClassifier()
    direct = classifier.classify(img)

    assert abs(via_module - direct["malignancy_score"]) < 1e-9, \
        f"module={via_module} direct={direct['malignancy_score']}"
    assert via_module_label == direct["label"], f"module={via_module_label} direct={direct['label']}"


# ------------------------------------------------------ 2. Multi-day run

def test_multi_day_consistency():
    n_ticks = 60  # ~20 readings per module type over the simulated timeline
    state = PatientState(
        patient_id="multiday",
        ehr_profile={"age": 50, "sex": 1, "cp": 1, "chol": 200, "fbs": 0,
                     "restecg": 0, "exang": 0, "oldpeak": 0.5, "slope": 2, "ca": 0, "thal": 2},
    )
    simulator = DummySimulator()
    cardiac, metabolic, dermatology = CardiacModule(), MetabolicModule(), DermatologyModule()

    prev_updated = state.last_updated
    for i in range(n_ticks):
        tick(state, simulator, i, cardiac, metabolic, dermatology)
        assert state.last_updated >= prev_updated, "last_updated went backwards"
        prev_updated = state.last_updated

    assert len(state.vitals_history) == 20, f"expected 20 vitals readings, got {len(state.vitals_history)}"
    assert len(state.lab_history) == 20, f"expected 20 lab readings, got {len(state.lab_history)}"
    assert len(state.skin_history) == 20, f"expected 20 skin readings, got {len(state.skin_history)}"
    assert set(state.risk_scores.keys()) == {"cardiac", "metabolic", "dermatology"}, \
        f"missing modules in risk_scores: {state.risk_scores.keys()}"

    # History buffers are bounded (maxlen) rather than growing unboundedly.
    assert state.vitals_history.maxlen == 500
    assert state.lab_history.maxlen == 200
    assert state.skin_history.maxlen == 100


# ------------------------------------------------- 3. Threshold-breach alerts

def test_cardiac_alert_fires_on_extreme_input():
    ehr_high_risk = {
        "age": 70, "sex": 1, "cp": 3, "chol": 320, "fbs": 1,
        "restecg": 2, "exang": 1, "oldpeak": 3.5, "slope": 0, "ca": 3, "thal": 3,
    }
    state = PatientState(patient_id="alert_cardiac", ehr_profile=ehr_high_risk)
    state.add_reading("vitals", {"heart_rate": 140, "trestbps": 180, "spo2": 90})

    CardiacModule().process(state)
    score = state.risk_scores["cardiac"]["score"]
    assert score >= CARDIAC_ALERT_THRESHOLD, \
        f"expected high-risk profile to breach threshold, got {score:.3f}"

    ehr_low_risk = {
        "age": 30, "sex": 0, "cp": 0, "chol": 160, "fbs": 0,
        "restecg": 0, "exang": 0, "oldpeak": 0.0, "slope": 2, "ca": 0, "thal": 2,
    }
    state2 = PatientState(patient_id="no_alert_cardiac", ehr_profile=ehr_low_risk)
    state2.add_reading("vitals", {"heart_rate": 65, "spo2": 99})
    CardiacModule().process(state2)
    score2 = state2.risk_scores["cardiac"]["score"]
    assert score2 < CARDIAC_ALERT_THRESHOLD, \
        f"expected low-risk profile to stay under threshold, got {score2:.3f}"


def test_metabolic_alert_fires_on_extreme_input():
    state = PatientState(patient_id="alert_metabolic")
    state.add_reading("lab", {
        "creatinine": 2.8, "egfr": 25.0, "alt": 140.0,
        "ast": 135.0, "glucose": 210.0, "hba1c": 9.0,
    })
    MetabolicModule().process(state)
    domains = state.risk_scores["metabolic"]["explanation"]["domain_scores"]
    assert any(v >= DOMAIN_ALERT_THRESHOLD for v in domains.values()), \
        f"expected at least one domain to breach threshold, got {domains}"


def test_dermatology_alert_fires_on_melanoma():
    rng = np.random.default_rng(3)
    img, _ = generate_image("melanoma", rng)
    state = PatientState(patient_id="alert_derm")
    state.add_reading("image", {"image_ref": "alert.jpg", "image": img})
    DermatologyModule().process(state)
    score = state.risk_scores["dermatology"]["score"]
    assert score >= DERM_ALERT_THRESHOLD, f"expected melanoma sample to breach threshold, got {score:.3f}"


# ------------------------------------------------ 4. Multi-patient personalization

def test_multi_patient_personalization():
    ehr_a = {"age": 72, "sex": 1, "cp": 3, "chol": 300, "fbs": 1,
             "restecg": 2, "exang": 1, "oldpeak": 3.0, "slope": 0, "ca": 3, "thal": 3}
    ehr_b = {"age": 28, "sex": 0, "cp": 0, "chol": 150, "fbs": 0,
             "restecg": 0, "exang": 0, "oldpeak": 0.0, "slope": 2, "ca": 0, "thal": 2}

    state_a = PatientState(patient_id="patient_A", ehr_profile=ehr_a)
    state_b = PatientState(patient_id="patient_B", ehr_profile=ehr_b)
    state_a.add_reading("vitals", {"heart_rate": 100, "spo2": 94})
    state_b.add_reading("vitals", {"heart_rate": 70, "spo2": 99})

    cardiac = CardiacModule()  # same shared model instance for both, like app.py does
    cardiac.process(state_a)
    cardiac.process(state_b)

    score_a = state_a.risk_scores["cardiac"]["score"]
    score_b = state_b.risk_scores["cardiac"]["score"]
    assert score_a != score_b, f"expected different patients to get different scores, both={score_a}"
    assert score_a > score_b, \
        f"expected higher-risk profile (A) to score above lower-risk (B): A={score_a} B={score_b}"


def main():
    print("=" * 70)
    print("1. Parity checks (module output vs. model called directly)")
    check("cardiac parity", test_cardiac_parity)
    check("metabolic parity", test_metabolic_parity)
    check("dermatology parity", test_dermatology_parity)

    print()
    print("2. Multi-day tick loop consistency")
    check("60-tick multi-day run stays consistent", test_multi_day_consistency)

    print()
    print("3. Threshold-breach alerts")
    check(
        "cardiac alert fires on high-risk / stays quiet on low-risk",
        test_cardiac_alert_fires_on_extreme_input,
    )
    check("metabolic alert fires on extreme labs", test_metabolic_alert_fires_on_extreme_input)
    check("dermatology alert fires on melanoma sample", test_dermatology_alert_fires_on_melanoma)

    print()
    print("4. Multi-patient personalization")
    check(
        "two distinct patients get distinct, correctly-ordered risk scores",
        test_multi_patient_personalization,
    )

    print("=" * 70)
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    print(f"{passed}/{total} checks passed")
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
