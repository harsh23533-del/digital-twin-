"""
Dermatology Dashboard Tab — Streamlit UI for the dermatology digital twin module.

Demoable end to end for a single simulated patient:
- Latest uploaded image reference + classification result (label, confidence)
- Progression timeline: malignancy score across past images

Uses the real ONNX classifier in modules/dermatology/model.py, trained on
synthetic ABCD-rule dermoscopy images — see that file's docstring for why
(no DermNet dataset access in this build environment). Swapping in a real
DermNet-trained model later only requires replacing that one file's
training data source.

Runnable standalone for now (already wired into the unified app.py, Step 9):
    streamlit run dashboard/dermatology_tab.py
"""

import time
import streamlit as st
import plotly.graph_objects as go
from PIL import Image

from twin_engine.patient_state import PatientState
from twin_engine.scheduler import DummySimulator
from modules.dermatology.dermatology_module import DermatologyModule
from config import DERM_ALERT_THRESHOLD  # malignancy score at/above which the banner turns red

LABEL_DESCRIPTIONS = {
    "healthy": "No abnormal findings.",
    "eczema": "Inflammatory skin condition — low concern.",
    "psoriasis": "Chronic inflammatory condition — low-moderate concern.",
    "benign_nevus": "Common mole, benign — routine monitoring.",
    "basal_cell_carcinoma": "Common skin cancer, usually slow-growing — flag for review.",
    "melanoma": "Most serious skin cancer type — flag for urgent review.",
}

st.set_page_config(page_title="MediTwin — Dermatology", layout="wide")


def _init_session(patient_id: str = "patient_001") -> None:
    """Create the engine objects once per browser session."""
    if "derm_state" not in st.session_state:
        st.session_state.derm_state = PatientState(patient_id=patient_id)
        st.session_state.derm_simulator = DummySimulator()
        st.session_state.derm_module = DermatologyModule()
        st.session_state.derm_tick_count = 0
        st.session_state.derm_risk_history = []   # list of (tick, score)
        st.session_state.derm_image_log = []       # list of (tick, image_ref, label, confidence)


def _run_ticks(n: int) -> None:
    """Advance the shared patient state by n ticks; only image ticks feed this tab."""
    state = st.session_state.derm_state
    simulator = st.session_state.derm_simulator
    dermatology = st.session_state.derm_module

    for _ in range(n):
        tick_count = st.session_state.derm_tick_count
        reading_type, reading = simulator.next_reading(state.patient_id, tick_count)
        state.add_reading(reading_type, reading)

        if reading_type == "image":
            dermatology.process(state)
            latest = state.risk_scores.get("dermatology")
            if latest:
                st.session_state.derm_risk_history.append((tick_count, latest["score"]))
                st.session_state.derm_image_log.append((
                    tick_count,
                    reading.get("image_ref"),
                    latest["explanation"]["label"],
                    latest["explanation"]["confidence"],
                ))

        st.session_state.derm_tick_count += 1


def render_dermatology_tab() -> None:
    _init_session()
    state = st.session_state.derm_state

    st.title("🩹 Dermatology Twin — Skin Monitor")
    st.caption(f"Patient: {state.patient_id} | Ticks elapsed: {st.session_state.derm_tick_count}")
    st.caption(
        "Real ONNX classifier (trained on synthetic ABCD-rule dermoscopy images — "
        "no DermNet dataset access in this build environment; see modules/dermatology/model.py)."
    )

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        n_ticks = st.number_input("Ticks to advance", min_value=1, max_value=50, value=3, step=1)
    with col2:
        if st.button("▶ Advance", type="primary"):
            _run_ticks(int(n_ticks))
    with col3:
        auto = st.checkbox("Auto-run (1 tick / sec)")

    latest_risk = state.risk_scores.get("dermatology")

    # --- Latest image + classification result ---
    st.subheader("Latest Upload")
    if latest_risk:
        explanation = latest_risk["explanation"]
        label = explanation["label"]
        confidence = explanation["confidence"]
        score = latest_risk["score"]

        img_col, info_col = st.columns([1, 2])
        with img_col:
            if state.skin_history:
                img_arr = state.skin_history[-1].get("image")
                if img_arr is not None:
                    st.image(Image.fromarray(img_arr), caption=explanation.get("image_ref", ""), width=200)
        with info_col:
            c1, c2 = st.columns(2)
            c1.metric("Predicted class", label)
            c2.metric("Confidence", f"{confidence:.0%}")
            probs = explanation.get("probabilities")
            if probs:
                st.caption("Class probabilities: " + ", ".join(f"{k}={v:.2f}" for k, v in probs.items()))

        if score >= DERM_ALERT_THRESHOLD:
            st.error(f"⚠️ {label} — malignancy score {score:.2f} (threshold {DERM_ALERT_THRESHOLD})")
        else:
            st.success(f"{label} — malignancy score {score:.2f}")
        st.caption(LABEL_DESCRIPTIONS.get(label, ""))
    else:
        st.info("No skin image reading yet — click Advance to start the simulation.")

    # --- Progression timeline ---
    st.subheader("Progression Timeline")
    if st.session_state.derm_risk_history:
        xs, ys = zip(*st.session_state.derm_risk_history)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(xs), y=list(ys), mode="lines+markers", name="Malignancy score"))
        fig.add_hline(
            y=DERM_ALERT_THRESHOLD, line_dash="dash", line_color="red",
            annotation_text="Alert threshold",
        )
        fig.update_layout(
            xaxis_title="Tick", yaxis_title="Malignancy score (0-1)", yaxis_range=[0, 1], height=350,
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No image ticks yet.")

    # --- Past images log ---
    st.subheader("Image History")
    if st.session_state.derm_image_log:
        for tick, image_ref, label, confidence in reversed(st.session_state.derm_image_log[-10:]):
            st.caption(f"Tick {tick:03d} — `{image_ref}` → **{label}** ({confidence:.0%} confidence)")
    else:
        st.caption("No images processed yet.")

    if auto:
        time.sleep(1)
        _run_ticks(1)
        st.rerun()


if __name__ == "__main__":
    render_dermatology_tab()
