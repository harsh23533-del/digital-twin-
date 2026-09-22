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

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("twin_engine")


class DummySimulator:
    """Emits a fake reading each tick, cycling through reading types."""

    _reading_types = ["vitals", "lab", "image"]

    def next_reading(self, patient_id: str, tick_count: int) -> tuple[str, dict]:
        reading_type = self._reading_types[tick_count % len(self._reading_types)]

        if reading_type == "vitals":
            reading = {
                "heart_rate": random.randint(60, 100),
                "spo2": random.randint(94, 100),
            }
        elif reading_type == "lab":
            reading = {
                "glucose": random.randint(80, 140),
                "creatinine": round(random.uniform(0.6, 1.3), 2),
            }
        else:  # image
            reading = {"image_ref": f"{patient_id}_skin_{tick_count}.jpg"}

        return reading_type, reading


def tick(state: PatientState, simulator: DummySimulator, tick_count: int) -> None:
    """Advance one simulated time step for a single patient."""
    reading_type, reading = simulator.next_reading(state.patient_id, tick_count)
    state.add_reading(reading_type, reading)

    # Later steps route the reading into the matching module here, e.g.:
    # if reading_type == "vitals": cardiac_module.process(state, reading)

    logger.info(f"tick {tick_count:03d} | +{reading_type} {reading} | {state.summary()}")


def run(patient_id: str = "patient_001", n_ticks: int = 10, interval_sec: float = 0.5) -> PatientState:
    """Run the tick loop for a fixed number of ticks (demo / smoke test)."""
    state = PatientState(patient_id=patient_id, ehr_profile={"age": 45, "sex": "M"})
    simulator = DummySimulator()

    logger.info(f"Starting twin engine for {patient_id} — {n_ticks} ticks")
    for i in range(n_ticks):
        tick(state, simulator, i)
        time.sleep(interval_sec)

    logger.info("Engine loop finished.")
    return state


if __name__ == "__main__":
    run()
