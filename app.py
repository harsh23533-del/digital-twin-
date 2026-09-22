"""
MediTwin — Unified multi-disease digital twin dashboard.

Ties the cardiac, metabolic, and dermatology modules into one Streamlit
app (Step 9): a patient selector supporting 2+ simulated patients, a
shared chronological alert log across all active modules, and one
consistent header/layout instead of three standalone scripts.

Run:
    streamlit run app.py
"""

import time
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from twin_engine.patient_state import PatientState
from twin_engine.scheduler import DummySimulator
from modules.cardiac.cardiac_module import CardiacModule
from modules.metabolic.metabolic_module import MetabolicModule
from modules.metabolic.model import REFERENCE_RANGES, DOMAIN_MARKERS
from modules.dermatology.dermatology_module import DermatologyModule

from config import CARDIAC_ALERT_THRESHOLD, DOMAIN_ALERT_THRESHOLD, DERM_ALERT_THRESHOLD

st.set_page_config(page_title="MediTwin", layout="wide", page_icon="🩺")

MARKER_UNITS = {
    "creatinine": "mg/dL", "egfr": "mL/min/1.73m²", "alt": "U/L",
    "ast": "U/L", "glucose": "mg/dL", "hba1c": "%",
}

# Two starter patients so the selector has something real to switch between.
DEFAULT_PATIENTS = {
    "patient_001": {
        "age": 52, "sex": 1, "cp": 3, "chol": 230, "fbs": 0,
        "restecg": 1, "exang": 0, "oldpeak": 1.2, "slope": 2, "ca": 0, "thal": 3,
    },
    "patient_002": {
        "age": 61, "sex": 0, "cp": 1, "chol": 260, "fbs": 1,
        "restecg": 0, "exang": 1, "oldpeak": 2.1, "slope": 1, "ca": 1, "thal": 2,
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
                "risk_history": {"cardiac": [], "metabolic": [], "dermatology": []},
                "lab_ticks": [],
            }
        # Models/explainers are stateless w.r.t. patient identity, so one
        # instance per module is shared across all patients (cheaper: the
        # cardiac model only loads/trains once).
        st.session_state.cardiac_module = CardiacModule()
        st.session_state.metabolic_module = MetabolicModule()
        st.session_state.dermatology_module = DermatologyModule()
        st.session_state.alert_log = []  # chronological, across all patients+modules


def _log_alert(patient_id: str, module: str, message: str) -> None:
    st.session_state.alert_log.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "patient": patient_id,
        "module": module,
        "message": message,
    })


def _check_alerts(patient_id: str, state: PatientState) -> None:
    """After a tick, compare the latest risk scores to thresholds and log new alerts."""
    cardiac = state.risk_scores.get("cardiac")
    if cardiac and cardiac["score"] >= CARDIAC_ALERT_THRESHOLD:
        _log_alert(patient_id, "cardiac", f"Cardiac risk elevated: {cardiac['score']:.2f}")

    metabolic = state.risk_scores.get("metabolic")
    if metabolic:
        for domain, score in metabolic["explanation"]["domain_scores"].items():
            if score >= DOMAIN_ALERT_THRESHOLD:
                _log_alert(patient_id, "metabolic", f"{domain.title()} domain elevated: {score:.2f}")

    derm = state.risk_scores.get("dermatology")
    if derm and derm["score"] >= DERM_ALERT_THRESHOLD:
        label = derm["explanation"]["label"]
        _log_alert(patient_id, "dermatology", f"Concerning skin finding: {label} ({derm['score']:.2f})")


def _run_ticks(patient_id: str, n: int) -> None:
    p = st.session_state.patients[patient_id]
    state, simulator = p["state"], p["simulator"]
    cardiac = st.session_state.cardiac_module
    metabolic = st.session_state.metabolic_module
    dermatology = st.session_state.dermatology_module

    for _ in range(n):
        tick_count = p["tick_count"]
        reading_type, reading = simulator.next_reading(patient_id, tick_count)
        state.add_reading(reading_type, reading)

        if reading_type == "vitals":
            cardiac.process(state)
            latest = state.risk_scores.get("cardiac")
            if latest:
                p["risk_history"]["cardiac"].append((tick_count, latest["score"]))
        elif reading_type == "lab":
            metabolic.process(state)
            p["lab_ticks"].append(tick_count)
            latest = state.risk_scores.get("metabolic")
            if latest:
                p["risk_history"]["metabolic"].append((tick_count, latest["score"]))
        elif reading_type == "image":
            dermatology.process(state)
            latest = state.risk_scores.get("dermatology")
            if latest:
                p["risk_history"]["dermatology"].append((tick_count, latest["score"]))

        _check_alerts(patient_id, state)
        p["tick_count"] += 1


# --------------------------------------------------------------------- UI

_init_engine()

st.title("🩺 MediTwin — Unified Multi-Disease Digital Twin")
st.caption("Digital Twin Challenge 2026 (Happiest Health)")

with st.sidebar:
    st.header("Patient")
    patient_id = st.selectbox("Active patient", list(st.session_state.patients.keys()))
    n_ticks = st.number_input("Ticks to advance", min_value=1, max_value=50, value=3, step=1)
    if st.button("▶ Advance", type="primary", width="stretch"):
        _run_ticks(patient_id, int(n_ticks))
    auto = st.checkbox("Auto-run (1 tick / sec)")

    st.divider()
    st.subheader("🔔 Alert Log — all patients")
    if st.session_state.alert_log:
        for a in reversed(st.session_state.alert_log[-15:]):
            st.caption(f"`{a['time']}` **{a['patient']}** [{a['module']}] {a['message']}")
    else:
        st.caption("No alerts yet.")

p = st.session_state.patients[patient_id]
state = p["state"]
st.caption(f"Patient: **{patient_id}** | Ticks elapsed: {p['tick_count']}")

tab_cardiac, tab_metabolic, tab_derm = st.tabs(["🫀 Cardiac", "🧪 Metabolic", "🩹 Dermatology"])

# --- Cardiac tab ---
with tab_cardiac:
    latest_risk = state.risk_scores.get("cardiac")
    if latest_risk:
        score = latest_risk["score"]
        if score >= CARDIAC_ALERT_THRESHOLD:
            st.error(f"⚠️ Cardiac risk elevated: {score:.2f} (threshold {CARDIAC_ALERT_THRESHOLD})")
        else:
            st.success(f"Cardiac risk nominal: {score:.2f}")

        history = p["risk_history"]["cardiac"]
        if history:
            xs, ys = zip(*history)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=list(xs), y=list(ys), mode="lines+markers", name="Risk score"))
            fig.add_hline(y=CARDIAC_ALERT_THRESHOLD, line_dash="dash", line_color="red")
            fig.update_layout(xaxis_title="Tick", yaxis_title="Risk (0-1)", yaxis_range=[0, 1], height=320)
            st.plotly_chart(fig, width="stretch")

        top_factors = latest_risk["explanation"].get("top_factors")
        if top_factors:
            names, vals = list(top_factors.keys()), list(top_factors.values())
            colors = ["crimson" if v > 0 else "seagreen" for v in vals]
            fig2 = go.Figure(go.Bar(x=vals, y=names, orientation="h", marker_color=colors))
            fig2.update_layout(xaxis_title="SHAP contribution", height=260, title="Top contributing factors")
            st.plotly_chart(fig2, width="stretch")
    else:
        st.info("No cardiac reading yet — click Advance.")

# --- Metabolic tab ---
with tab_metabolic:
    latest_risk = state.risk_scores.get("metabolic")
    if latest_risk:
        domain_scores = latest_risk["explanation"]["domain_scores"]
        d1, d2, d3 = st.columns(3)
        for col, domain in zip((d1, d2, d3), ("kidney", "liver", "glucose")):
            score = domain_scores.get(domain, 0.0)
            with col:
                banner = st.error if score >= DOMAIN_ALERT_THRESHOLD else st.success
                banner(f"{domain.title()}: {score:.2f}")
        st.caption(f"Overall metabolic risk: **{latest_risk['score']:.2f}**")

        explanation = latest_risk["explanation"]
        latest_reading = explanation["latest_reading"]
        marker_scores = explanation["marker_scores"]
        trends = explanation.get("trends", {})
        domain_of = {m: d for d, markers in DOMAIN_MARKERS.items() for m in markers}
        rows = []
        for m in REFERENCE_RANGES:
            if m not in latest_reading:
                continue
            s = marker_scores.get(m, 0.0)
            status = "high" if s >= 1.0 else ("normal" if s <= 0.0 else "borderline")
            rows.append({
                "Marker": m, "Value": latest_reading[m], "Unit": MARKER_UNITS[m],
                "Domain": domain_of.get(m, "—"), "Status": status, "Trend": trends.get(m, "stable"),
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        if p["lab_ticks"]:
            markers = list(REFERENCE_RANGES.keys())
            fig = make_subplots(rows=2, cols=3, subplot_titles=markers, vertical_spacing=0.14)
            for idx, marker in enumerate(markers):
                row, col = idx // 3 + 1, idx % 3 + 1
                ys = [r.get(marker) for r in state.lab_history]
                fig.add_trace(
                    go.Scatter(x=p["lab_ticks"], y=ys, mode="lines+markers", showlegend=False),
                    row=row, col=col,
                )
                ref = REFERENCE_RANGES[marker]
                fig.add_hline(y=ref["normal"], line_dash="dot", line_color="gray", row=row, col=col)
                fig.add_hline(y=ref["high"], line_dash="dash", line_color="red", row=row, col=col)
            fig.update_layout(height=480)
            st.plotly_chart(fig, width="stretch")
    else:
        st.info("No lab reading yet — click Advance.")

# --- Dermatology tab ---
with tab_derm:
    latest_risk = state.risk_scores.get("dermatology")
    if latest_risk:
        score = latest_risk["score"]
        label = latest_risk["explanation"]["label"]
        confidence = latest_risk["explanation"]["confidence"]
        if score >= DERM_ALERT_THRESHOLD:
            st.error(f"⚠️ {label} (malignancy score {score:.2f}, confidence {confidence:.0%})")
        else:
            st.success(f"{label} (malignancy score {score:.2f}, confidence {confidence:.0%})")
        st.caption(
            "ONNX MLP classifier trained on synthetic ABCD-rule dermoscopy images "
            "(no DermNet dataset access in this build environment — see docs/methodology.md)."
        )

        history = p["risk_history"]["dermatology"]
        if history:
            xs, ys = zip(*history)
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=list(xs), y=list(ys), mode="lines+markers", name="Malignancy score"))
            fig.add_hline(y=DERM_ALERT_THRESHOLD, line_dash="dash", line_color="red")
            fig.update_layout(
                xaxis_title="Tick", yaxis_title="Score (0-1)", yaxis_range=[0, 1],
                height=320, title="Progression timeline",
            )
            st.plotly_chart(fig, width="stretch")
    else:
        st.info("No skin image reading yet — click Advance.")

if auto:
    time.sleep(1)
    _run_ticks(patient_id, 1)
    st.rerun()
