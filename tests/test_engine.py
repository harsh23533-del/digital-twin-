"""
Testing & Validation (cardiac-only build).

Plain assert-based test suite (no pytest dependency) covering:

1. Parity: the cardiac module's output vs. the underlying model called
   directly on the same input.
2. Multi-day consistency: the tick loop runs over a long simulated
   timeline without state corruption.
3. Threshold-breach alerts: extreme inputs push scores past the alert
   threshold used in app.py.
4. Multi-patient personalization: two distinct patients produce
   distinct outputs from the same engine.

Run:
    python3 tests/test_engine.py
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from twin_engine.patient_state import PatientState  # noqa: E402
from twin_engine.scheduler import DummySimulator, tick  # noqa: E402
from modules.cardiac.cardiac_module import CardiacModule  # noqa: E402
from modules.cardiac.model import load_model as load_cardiac_model  # noqa: E402
from modules.cardiac.rolling_features import build_feature_row  # noqa: E402
from config import CARDIAC_ALERT_THRESHOLD  # noqa: E402
from twin_engine.live_heart_rate import parse_hr_measurement  # noqa: E402

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


# ------------------------------------------------------ 2. Multi-day run

def test_multi_day_consistency():
    n_ticks = 60
    state = PatientState(
        patient_id="multiday",
        ehr_profile={"age": 50, "sex": 1, "cp": 1, "chol": 200, "fbs": 0,
                     "restecg": 0, "exang": 0, "oldpeak": 0.5, "slope": 2, "ca": 0, "thal": 2},
    )
    simulator = DummySimulator()
    cardiac = CardiacModule()

    prev_updated = state.last_updated
    for i in range(n_ticks):
        tick(state, simulator, i, cardiac)
        assert state.last_updated >= prev_updated, "last_updated went backwards"
        prev_updated = state.last_updated

    assert len(state.vitals_history) == 60, f"expected 60 vitals readings, got {len(state.vitals_history)}"
    assert set(state.risk_scores.keys()) == {"cardiac"}, \
        f"unexpected modules in risk_scores: {state.risk_scores.keys()}"

    # History buffer is bounded (maxlen) rather than growing unboundedly.
    assert state.vitals_history.maxlen == 500


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


# ------------------------------------------------- 5. BLE HR measurement parsing

def test_hr_measurement_parsing():
    # 8-bit format (flags bit 0 = 0): heart rate is a single byte.
    assert parse_hr_measurement(bytes([0x00, 72])) == 72
    assert parse_hr_measurement(bytes([0x00, 255])) == 255

    # 16-bit format (flags bit 0 = 1): heart rate is little-endian bytes 1-2.
    assert parse_hr_measurement(bytes([0x01, 0x2C, 0x01])) == 300  # 0x012C
    assert parse_hr_measurement(bytes([0x01, 0x00, 0x00])) == 0

    # Other flag bits (energy expended, RR-interval, sensor contact) must
    # not affect which bytes carry the heart rate.
    assert parse_hr_measurement(bytes([0x0F, 88])) == 88


def main():
    print("=" * 70)
    print("1. Parity check (module output vs. model called directly)")
    check("cardiac parity", test_cardiac_parity)

    print()
    print("2. Multi-day tick loop consistency")
    check("60-tick multi-day run stays consistent", test_multi_day_consistency)

    print()
    print("3. Threshold-breach alerts")
    check(
        "cardiac alert fires on high-risk / stays quiet on low-risk",
        test_cardiac_alert_fires_on_extreme_input,
    )

    print()
    print("4. Multi-patient personalization")
    check(
        "two distinct patients get distinct, correctly-ordered risk scores",
        test_multi_patient_personalization,
    )

    print()
    print("5. BLE heart-rate measurement parsing (no hardware needed)")
    check("HR measurement byte-format decoding (8-bit and 16-bit)", test_hr_measurement_parsing)

    print("=" * 70)
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    print(f"{passed}/{total} checks passed")
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
