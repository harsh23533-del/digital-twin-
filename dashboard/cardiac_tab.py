"""
Cardiac Dashboard Tab — Streamlit UI for the cardiac digital twin module.

Demoable end to end for a single simulated patient:
- Live HR / SpO2 readout
- Rolling cardiac risk-score line chart (Plotly)
- SHAP bar chart of top contributing factors for the latest tick
- Alert banner when risk crosses the patient's threshold

Runnable standalone for now (Step 9 wires this into the unified app.py):
    streamlit run dashboard/cardiac_tab.py
"""

import time
import streamlit as st
import plotly.graph_objects as go

from twin_engine.patient_state import PatientState
from twin_engine.scheduler import DummySimulator
from modules.cardiac.cardiac_module import CardiacModule

from config import CARDIAC_ALERT_THRESHOLD as RISK_ALERT_THRESHOLD
# TODO: move to per-patient EHR profile once multi-patient (Step 9) lands

st.set_page_config(page_title="MediTwin — Cardiac", layout="wide")


def _init_session(patient_id: str = "patient_001") -> None:
    """Create the engine objects once per browser session."""
    if "cardiac_state" not in st.session_state:
        st.session_state.cardiac_state = PatientState(
            patient_id=patient_id,
            ehr_profile={
                "age": 52, "sex": 1, "cp": 3, "chol": 230, "fbs": 0,
                "restecg": 1, "exang": 0, "oldpeak": 1.2, "slope": 2, "ca": 0, "thal": 3,
            },
        )
        st.session_state.cardiac_simulator = DummySimulator()
        st.session_state.cardiac_module = CardiacModule()
        st.session_state.cardiac_tick_count = 0
        st.session_state.risk_history = []        # list of (tick, score)
        st.session_state.vitals_history_log = []   # list of (tick, hr, spo2)


def _run_ticks(n: int) -> None:
    """Advance the shared patient state by n ticks; log only vitals ticks for this tab's charts."""
    state = st.session_state.cardiac_state
    simulator = st.session_state.cardiac_simulator
    cardiac = st.session_state.cardiac_module

    for _ in range(n):
        tick_count = st.session_state.cardiac_tick_count
        reading_type, reading = simulator.next_reading(state.patient_id, tick_count)
        state.add_reading(reading_type, reading)

        if reading_type == "vitals":
            cardiac.process(state)
            st.session_state.vitals_history_log.append(
                (tick_count, reading["heart_rate"], reading["spo2"])
            )
            latest = state.risk_scores.get("cardiac")
            if latest:
                st.session_state.risk_history.append((tick_count, latest["score"]))

        st.session_state.cardiac_tick_count += 1


def render_cardiac_tab() -> None:
    _init_session()
    state = st.session_state.cardiac_state

    st.title("🫀 Cardiac Twin — Live Monitor")
    st.caption(f"Patient: {state.patient_id} | Ticks elapsed: {st.session_state.cardiac_tick_count}")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        n_ticks = st.number_input("Ticks to advance", min_value=1, max_value=50, value=3, step=1)
    with col2:
        if st.button("▶ Advance", type="primary"):
            _run_ticks(int(n_ticks))
    with col3:
        auto = st.checkbox("Auto-run (1 tick / sec)")

    # --- Live HR / SpO2 readout ---
    latest_vitals = st.session_state.vitals_history_log[-1] if st.session_state.vitals_history_log else None
    v1, v2 = st.columns(2)
    with v1:
        st.metric("Heart Rate (bpm)", latest_vitals[1] if latest_vitals else "—")
    with v2:
        st.metric("SpO2 (%)", latest_vitals[2] if latest_vitals else "—")

    # --- Alert banner ---
    latest_risk = state.risk_scores.get("cardiac")
    if latest_risk:
        score = latest_risk["score"]
        if score >= RISK_ALERT_THRESHOLD:
            st.error(f"⚠️ Cardiac risk elevated: {score:.2f} (threshold {RISK_ALERT_THRESHOLD})")
        else:
            st.success(f"Cardiac risk nominal: {score:.2f}")
    else:
        st.info("No cardiac reading yet — click Advance to start the simulation.")

    # --- Rolling risk-score line chart ---
    st.subheader("Rolling Cardiac Risk Score")
    if st.session_state.risk_history:
        xs, ys = zip(*st.session_state.risk_history)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(xs), y=list(ys), mode="lines+markers", name="Risk score"))
        fig.add_hline(
            y=RISK_ALERT_THRESHOLD, line_dash="dash", line_color="red",
            annotation_text="Alert threshold",
        )
        fig.update_layout(
            xaxis_title="Tick", yaxis_title="Risk (0–1)", yaxis_range=[0, 1], height=350,
        )
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No vitals ticks yet.")

    # --- SHAP bar chart for latest reading ---
    st.subheader("Top Contributing Factors (SHAP, latest reading)")
    top_factors = (latest_risk or {}).get("explanation", {}).get("top_factors") if latest_risk else None
    if top_factors:
        names = list(top_factors.keys())
        vals = list(top_factors.values())
        colors = ["crimson" if v > 0 else "seagreen" for v in vals]
        fig2 = go.Figure(go.Bar(x=vals, y=names, orientation="h", marker_color=colors))
        fig2.update_layout(xaxis_title="SHAP contribution (→ higher risk)", height=300)
        st.plotly_chart(fig2, width='stretch')
    else:
        st.info("No explanation yet — advance until a vitals tick fires.")

    # Auto-run: sleep then rerun the script (Streamlit's standard polling pattern)
    if auto:
        time.sleep(1)
        _run_ticks(1)
        st.rerun()


if __name__ == "__main__":
    render_cardiac_tab()
