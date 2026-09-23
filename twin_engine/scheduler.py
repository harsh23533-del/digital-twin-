"""
Scheduler / tick loop for the digital twin engine.

Advances simulated time and, on each tick, pulls a fake reading from
the dummy simulator and routes it into the patient's state. Real
module logic (cardiac risk model, lab analyzer, etc.) plugs in later
by replacing `_dummy_route_to_modules`.
"""

import random
import time
import logging
import numpy as np
from twin_engine.patient_state import PatientState
from modules.cardiac.cardiac_module import CardiacModule
from modules.metabolic.metabolic_module import MetabolicModule
from modules.dermatology.dermatology_module import DermatologyModule
from modules.dermatology.synthetic_data import generate_image, CLASSES
from modules.dermatology.model import MALIGNANCY_WEIGHT

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("twin_engine")


class DummySimulator:
    """Emits a fake reading each tick, cycling through reading types.

    Lab values are a slow, bounded random walk (not IID noise) so that
    consecutive lab readings actually drift gradually — giving the
    metabolic module's trend detector something real to pick up on.
    """

    _reading_types = ["vitals", "lab", "image"]

    # marker: (start_value, (min_bound, max_bound), max_step_per_tick)
    _LAB_WALK_SPEC = {
        "creatinine": (1.0, (0.5, 3.0), 0.05),
        "egfr": (95.0, (20.0, 120.0), 2.0),
        "alt": (25.0, (10.0, 150.0), 3.0),
        "ast": (25.0, (10.0, 150.0), 3.0),
        "glucose": (95.0, (70.0, 220.0), 4.0),
        "hba1c": (5.4, (4.5, 9.5), 0.1),
    }

    # Classes ordered by malignancy weight — used to turn a slowly-drifting
    # 0-1 "skin severity" random walk into a class to render, so successive
    # images for one patient tell a coherent progression story instead of
    # jumping randomly between unrelated conditions each tick.
    _SEVERITY_ORDER = sorted(CLASSES, key=lambda c: MALIGNANCY_WEIGHT[c])

    def __init__(self):
        self._lab_state = {m: start for m, (start, _, _) in self._LAB_WALK_SPEC.items()}
        self._skin_severity = 0.08  # starts near "healthy"
        self._img_rng = np.random.default_rng()
        self._trestbps_state = 120.0  # resting systolic BP, bounded random walk

    def next_reading(self, patient_id: str, tick_count: int) -> tuple[str, dict]:
        reading_type = self._reading_types[tick_count % len(self._reading_types)]

        if reading_type == "vitals":
            reading = self._next_vitals_reading()
        elif reading_type == "lab":
            reading = self._next_lab_reading()
        else:  # image
            reading = self._next_image_reading(patient_id, tick_count)

        return reading_type, reading

    def _next_vitals_reading(self) -> dict:
        # trestbps: slow bounded random walk, like the lab markers, so the
        # rolling-average feature in rolling_features.py actually has data
        # to average instead of always falling back to the static EHR value.
        self._trestbps_state = round(
            max(90.0, min(180.0, self._trestbps_state + random.uniform(-3.0, 3.0))), 1
        )
        # heart_rate: mostly resting range, with an occasional exertion spike
        # so the rolling-window max (thalach) reaches physiologically
        # realistic peak values instead of being capped at 100 — the
        # Cleveland dataset's thalach feature ranges up to ~202.
        if random.random() < 0.15:
            heart_rate = random.randint(110, 180)
        else:
            heart_rate = random.randint(58, 100)

        return {
            "heart_rate": heart_rate,
            "spo2": random.randint(94, 100),
            "trestbps": self._trestbps_state,
        }

    def _next_lab_reading(self) -> dict:
        for marker, (_, (lo, hi), step) in self._LAB_WALK_SPEC.items():
            value = self._lab_state[marker] + random.uniform(-step, step)
            self._lab_state[marker] = round(max(lo, min(hi, value)), 2)
        return dict(self._lab_state)

    def _next_image_reading(self, patient_id: str, tick_count: int) -> dict:
        """Render a real synthetic lesion image (see modules/dermatology/synthetic_data.py).

        `_skin_severity` random-walks in [0, 1]; the nearest class by
        malignancy weight is rendered, so the classifier is always fed a
        genuine image — never a ground-truth label — and successive images
        for a patient drift smoothly instead of jumping between conditions.
        """
        self._skin_severity = max(0.0, min(1.0, self._skin_severity + random.uniform(-0.04, 0.05)))
        cls = min(self._SEVERITY_ORDER, key=lambda c: abs(MALIGNANCY_WEIGHT[c] - self._skin_severity))

        image, _params = generate_image(cls, self._img_rng)
        return {"image_ref": f"{patient_id}_skin_{tick_count}.jpg", "image": image}


def tick(
    state: PatientState,
    simulator: DummySimulator,
    tick_count: int,
    cardiac: CardiacModule,
    metabolic: MetabolicModule,
    dermatology: DermatologyModule,
) -> None:
    """Advance one simulated time step for a single patient."""
    reading_type, reading = simulator.next_reading(state.patient_id, tick_count)
    state.add_reading(reading_type, reading)

    if reading_type == "vitals":
        cardiac.process(state)
    elif reading_type == "lab":
        metabolic.process(state)
    elif reading_type == "image":
        dermatology.process(state)

    log_reading = {k: v for k, v in reading.items() if k != "image"} if reading_type == "image" else reading
    logger.info(f"tick {tick_count:03d} | +{reading_type} {log_reading} | {state.summary()}")


def run(patient_id: str = "patient_001", n_ticks: int = 10, interval_sec: float = 0.5) -> PatientState:
    """Run the tick loop for a fixed number of ticks (demo / smoke test)."""
    state = PatientState(
        patient_id=patient_id,
        ehr_profile={
            "age": 52, "sex": 1, "cp": 3, "chol": 230, "fbs": 0,
            "restecg": 1, "exang": 0, "oldpeak": 1.2, "slope": 2, "ca": 0, "thal": 3,
        },
    )
    simulator = DummySimulator()
    cardiac = CardiacModule()
    metabolic = MetabolicModule()
    dermatology = DermatologyModule()

    logger.info(f"Starting twin engine for {patient_id} — {n_ticks} ticks")
    for i in range(n_ticks):
        tick(state, simulator, i, cardiac, metabolic, dermatology)
        time.sleep(interval_sec)

    logger.info("Engine loop finished.")
    return state


if __name__ == "__main__":
    run()
