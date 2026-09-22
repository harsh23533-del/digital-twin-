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
from twin_engine.patient_state import PatientState
from modules.cardiac.cardiac_module import CardiacModule
from modules.metabolic.metabolic_module import MetabolicModule

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

    def __init__(self):
        self._lab_state = {m: start for m, (start, _, _) in self._LAB_WALK_SPEC.items()}

    def next_reading(self, patient_id: str, tick_count: int) -> tuple[str, dict]:
        reading_type = self._reading_types[tick_count % len(self._reading_types)]

        if reading_type == "vitals":
            reading = {
                "heart_rate": random.randint(60, 100),
                "spo2": random.randint(94, 100),
            }
        elif reading_type == "lab":
            reading = self._next_lab_reading()
        else:  # image
            reading = {"image_ref": f"{patient_id}_skin_{tick_count}.jpg"}

        return reading_type, reading

    def _next_lab_reading(self) -> dict:
        for marker, (_, (lo, hi), step) in self._LAB_WALK_SPEC.items():
            value = self._lab_state[marker] + random.uniform(-step, step)
            self._lab_state[marker] = round(max(lo, min(hi, value)), 2)
        return dict(self._lab_state)


def tick(
    state: PatientState,
    simulator: DummySimulator,
    tick_count: int,
    cardiac: CardiacModule,
    metabolic: MetabolicModule,
) -> None:
    """Advance one simulated time step for a single patient."""
    reading_type, reading = simulator.next_reading(state.patient_id, tick_count)
    state.add_reading(reading_type, reading)

    if reading_type == "vitals":
        cardiac.process(state)
    elif reading_type == "lab":
        metabolic.process(state)
    # Later steps route other reading types into their modules here, e.g.:
    # if reading_type == "image": dermatology_module.process(state)

    logger.info(f"tick {tick_count:03d} | +{reading_type} {reading} | {state.summary()}")


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

    logger.info(f"Starting twin engine for {patient_id} — {n_ticks} ticks")
    for i in range(n_ticks):
        tick(state, simulator, i, cardiac, metabolic)
        time.sleep(interval_sec)

    logger.info("Engine loop finished.")
    return state


if __name__ == "__main__":
    run()
