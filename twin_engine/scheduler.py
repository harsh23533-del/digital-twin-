"""
Scheduler / tick loop for the digital twin engine.

Advances simulated time and, on each tick, pulls a fake vitals reading
from the dummy simulator and routes it into the patient's state, which
the cardiac module scores.
"""

import random
import time
import logging
from twin_engine.patient_state import PatientState
from modules.cardiac.cardiac_module import CardiacModule

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("twin_engine")


class DummySimulator:
    """Emits a fake vitals reading each tick."""

    def __init__(self):
        self._trestbps_state = 120.0  # resting systolic BP, bounded random walk
        self._stress_ticks_remaining = 0  # >0 while a cardiac stress episode is active

    def next_reading(self, patient_id: str, tick_count: int) -> tuple[str, dict]:
        return "vitals", self._next_vitals_reading()

    def _next_vitals_reading(self) -> dict:
        # Occasionally trigger a short "cardiac stress episode": resting BP
        # climbs and, unlike a healthy exertion spike, heart rate fails to
        # rise with it (chronotropic incompetence — a real, well-documented
        # risk marker also reflected in the Cleveland training data via
        # low thalach + high trestbps). ~2% chance per vitals tick to start
        # one, lasting 8-15 consecutive vitals ticks, so a demo session
        # sees the cardiac alert fire once or twice rather than never or
        # constantly.
        if self._stress_ticks_remaining <= 0 and random.random() < 0.02:
            self._stress_ticks_remaining = random.randint(8, 15)

        in_episode = self._stress_ticks_remaining > 0
        if in_episode:
            self._stress_ticks_remaining -= 1

        # trestbps: slow bounded random walk; biased upward toward a high
        # plateau during a stress episode, otherwise a normal small drift.
        if in_episode:
            step = random.uniform(0.5, 5.0) if self._trestbps_state < 175.0 else random.uniform(-3.0, 3.0)
        else:
            step = random.uniform(-3.0, 3.0) if self._trestbps_state <= 120.0 else random.uniform(-4.0, 1.0)
        self._trestbps_state = round(max(90.0, min(185.0, self._trestbps_state + step)), 1)

        if in_episode:
            # Suppressed heart rate under stress (can't raise HR appropriately).
            heart_rate = random.randint(55, 68)
        elif random.random() < 0.15:
            # Occasional healthy exertion spike so thalach still reaches
            # realistic peak values (Cleveland's thalach ranges up to ~202).
            heart_rate = random.randint(110, 180)
        else:
            heart_rate = random.randint(58, 100)

        return {
            "heart_rate": heart_rate,
            "spo2": random.randint(90, 100) if in_episode else random.randint(94, 100),
            "trestbps": self._trestbps_state,
        }


def tick(
    state: PatientState,
    simulator: DummySimulator,
    tick_count: int,
    cardiac: CardiacModule,
) -> None:
    """Advance one simulated time step for a single patient."""
    reading_type, reading = simulator.next_reading(state.patient_id, tick_count)
    state.add_reading(reading_type, reading)
    cardiac.process(state)

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

    logger.info(f"Starting twin engine for {patient_id} — {n_ticks} ticks")
    for i in range(n_ticks):
        tick(state, simulator, i, cardiac)
        time.sleep(interval_sec)

    logger.info("Engine loop finished.")
    return state


if __name__ == "__main__":
    run()
