"""
MediTwin — Cardiac Digital Twin dashboard.

A patient selector supporting 2+ simulated patients, a chronological
cardiac alert log, and a persistent header above the live vitals/risk
view.

Run:
    streamlit run app.py
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from twin_engine.patient_state import PatientState
from twin_engine.scheduler import DummySimulator
from modules.cardiac.cardiac_module import CardiacModule
from dashboard.patient_header import render_patient_header
from dashboard.cardiac_alarm import render_cardiac_alarm

from config import CARDIAC_ALERT_THRESHOLD

st.set_page_config(page_title="MediTwin", layout="wide", page_icon="🩺")
st.markdown(
    """<style>
        .block-container {padding-top: 1.2rem; padding-bottom: 1rem;}
        [data-testid="stMetricValue"] {font-size: 1.5rem;}
    </style>""",
    unsafe_allow_html=True,
)

# Two starter patients so the selector has something real to switch between.
DEFAULT_PATIENTS = {
    "patient_001": {
        "age": 56, "sex": 1, "cp": 2, "chol": 255, "fbs": 1,
        "restecg": 0, "exang": 1, "oldpeak": 2.0, "slope": 1, "ca": 1, "thal": 2,
    },
    "patient_002": {
        "age": 59, "sex": 0, "cp": 1, "chol": 265, "fbs": 1,
        "restecg": 0, "exang": 1, "oldpeak": 2.0, "slope": 1, "ca": 1, "thal": 2,
    },
}


def _init_engine() -> None:
    """Create shared module instances + per-patient state, once per session."""
    if "patients" not in st.session_state:
        st.session_state.patients = {}
        for pid, ehr in DEFAULT_PATIENTS.items():
            st.session_state.patients[pid] = {
                "state": PatientState(patient_id=pid, ehr_profile=ehr),
                "simulator": DummySimulator(),
                "tick_count": 0,
                "risk_history": [],
                # Edge-trigger state: whether cardiac was already above its
                # alert threshold as of the last tick, so _check_alerts only
                # logs on the below->above transition instead of on every
                # tick the score happens to stay elevated.
                "alert_state": {"cardiac": False},
            }
        # The model/explainer is stateless w.r.t. patient identity, so one
        # instance is shared across all patients (cheaper: the cardiac
        # model only loads/trains once).
        st.session_state.cardiac_module = CardiacModule()
        st.session_state.alert_log = []  # chronological, across all patients


_IST = ZoneInfo("Asia/Kolkata")


def _log_alert(patient_id: str, message: str) -> None:
    st.session_state.alert_log.append({
        "time": datetime.now(_IST).strftime("%H:%M:%S"),
        "patient": patient_id,
        "message": message,
    })


def _check_alerts(patient_id: str, state: PatientState) -> None:
    """After a tick, log an alert only on the below->above threshold transition
    (edge-triggered) — not on every tick a score happens to stay elevated."""
    alert_state = st.session_state.patients[patient_id]["alert_state"]

    cardiac = state.risk_scores.get("cardiac")
    if cardiac:
        is_high = cardiac["score"] >= CARDIAC_ALERT_THRESHOLD
        if is_high and not alert_state["cardiac"]:
            _log_alert(patient_id, f"Cardiac risk elevated: {cardiac['score']:.2f}")
        alert_state["cardiac"] = is_high


def _run_ticks(patient_id: str, n: int) -> None:
    p = st.session_state.patients[patient_id]
    state, simulator = p["state"], p["simulator"]
    cardiac = st.session_state.cardiac_module

    for _ in range(n):
        tick_count = p["tick_count"]
        reading_type, reading = simulator.next_reading(patient_id, tick_count)
        state.add_reading(reading_type, reading)
        cardiac.process(state)

        latest = state.risk_scores.get("cardiac")
        if latest:
            p["risk_history"].append((tick_count, latest["score"]))

        _check_alerts(patient_id, state)
        p["tick_count"] += 1


# --------------------------------------------------------------------- UI

_init_engine()

st.markdown(
    "##### 🩺 MediTwin — Cardiac Digital Twin "
    "&nbsp;·&nbsp; <span style='font-weight:400;color:gray;font-size:0.85rem;'>"
    "Digital Twin Challenge 2026 (Happiest Health)</span>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Patient")
    patient_id = st.selectbox("Select patient", list(st.session_state.patients.keys()))
    n_ticks = st.number_input("Ticks to advance", min_value=1, max_value=50, value=1)
    if st.button("▶ Advance", type="primary", width="stretch"):
        _run_ticks(patient_id, int(n_ticks))
    auto = st.checkbox("Auto-run (1 tick / sec)")

    st.divider()
    st.subheader("🔔 Cardiac Alerts — all patients")
    if st.session_state.alert_log:
        for a in reversed(st.session_state.alert_log[-15:]):
            st.caption(f"`{a['time']}` **{a['patient']}** {a['message']}")
    else:
        st.caption("No cardiac alerts yet.")

p = st.session_state.patients[patient_id]
state = p["state"]
st.caption(f"Patient: **{patient_id}** | Ticks elapsed: {p['tick_count']}")

render_patient_header(patient_id, state.ehr_profile)

# --- Cardiac ---
latest_vitals = state.vitals_history[-1] if state.vitals_history else None
v1, v2, v3 = st.columns(3)
with v1:
    st.metric("Heart Rate (bpm)", latest_vitals["heart_rate"] if latest_vitals else "—")
with v2:
    st.metric("SpO2 (%)", latest_vitals["spo2"] if latest_vitals else "—")
with v3:
    st.metric(
        "Resting BP (trestbps, mmHg)",
        latest_vitals["trestbps"] if latest_vitals else "—",
    )

latest_risk = state.risk_scores.get("cardiac")
if latest_risk:
    score = latest_risk["score"]
    if score >= CARDIAC_ALERT_THRESHOLD:
        render_cardiac_alarm(score, CARDIAC_ALERT_THRESHOLD)
    else:
        st.success(f"Cardiac risk nominal: {score:.2f}")

    chart_col1, chart_col2 = st.columns(2)

    vitals_recent = list(state.vitals_history)[-60:]
    with chart_col1:
        if vitals_recent:
            vfig = make_subplots(specs=[[{"secondary_y": True}]])
            vfig.add_trace(
                go.Scatter(y=[v["heart_rate"] for v in vitals_recent], name="Heart rate (bpm)",
                           mode="lines+markers", line=dict(color="crimson")),
                secondary_y=False,
            )
            vfig.add_trace(
                go.Scatter(y=[v["trestbps"] for v in vitals_recent], name="Resting BP (mmHg)",
                           mode="lines+markers", line=dict(color="darkorange")),
                secondary_y=True,
            )
            vfig.update_yaxes(title_text="HR (bpm)", secondary_y=False)
            vfig.update_yaxes(title_text="BP (mmHg)", secondary_y=True)
            vfig.update_layout(
                title="Recent vitals stream", xaxis_title="Recent ticks", height=280,
                margin=dict(t=40, b=30, l=10, r=10), legend=dict(orientation="h", y=-0.25),
            )
            st.plotly_chart(vfig, width="stretch")

    history = p["risk_history"]
    with chart_col2:
        if history:
            xs, ys = zip(*history)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=list(xs), y=list(ys), mode="lines+markers", name="Risk score"))
            fig.add_hline(y=CARDIAC_ALERT_THRESHOLD, line_dash="dash", line_color="red")
            fig.update_layout(
                title="Cardiac risk trend", xaxis_title="Tick", yaxis_title="Risk (0-1)",
                yaxis_range=[0, 1], height=280, margin=dict(t=40, b=30, l=10, r=10),
            )
            st.plotly_chart(fig, width="stretch")

    top_factors = latest_risk["explanation"].get("top_factors")
    if top_factors:
        with st.expander("Top contributing factors (SHAP)"):
            names, vals = list(top_factors.keys()), list(top_factors.values())
            colors = ["crimson" if v > 0 else "seagreen" for v in vals]
            fig2 = go.Figure(go.Bar(x=vals, y=names, orientation="h", marker_color=colors))
            fig2.update_layout(xaxis_title="SHAP contribution", height=240, margin=dict(t=10, b=10))
            st.plotly_chart(fig2, width="stretch")
else:
    st.info("No cardiac reading yet — click Advance.")

if auto:
    time.sleep(1)
    _run_ticks(patient_id, 1)
    st.rerun()
