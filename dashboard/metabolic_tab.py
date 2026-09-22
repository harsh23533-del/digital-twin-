"""
Metabolic Dashboard Tab — Streamlit UI for the metabolic digital twin module.

Demoable end to end for a single simulated patient:
- Latest lab values table (value, domain, reference-range status)
- Per-marker trend chart over simulated time (6 small multiples)
- Risk banner per organ-system domain (kidney / liver / glucose)

Runnable standalone for now (Step 9 wires this into the unified app.py):
    streamlit run dashboard/metabolic_tab.py
"""

import time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from twin_engine.patient_state import PatientState
from twin_engine.scheduler import DummySimulator
from modules.metabolic.metabolic_module import MetabolicModule
from modules.metabolic.model import REFERENCE_RANGES, DOMAIN_MARKERS
from config import DOMAIN_ALERT_THRESHOLD  # per-domain score at/above which the banner turns red

MARKER_UNITS = {
    "creatinine": "mg/dL", "egfr": "mL/min/1.73m²", "alt": "U/L",
    "ast": "U/L", "glucose": "mg/dL", "hba1c": "%",
}
MARKER_LABELS = {m: f"{m} ({MARKER_UNITS[m]})" for m in REFERENCE_RANGES}

st.set_page_config(page_title="MediTwin — Metabolic", layout="wide")


def _init_session(patient_id: str = "patient_001") -> None:
    """Create the engine objects once per browser session."""
    if "metabolic_state" not in st.session_state:
        st.session_state.metabolic_state = PatientState(patient_id=patient_id)
        st.session_state.metabolic_simulator = DummySimulator()
        st.session_state.metabolic_module = MetabolicModule()
        st.session_state.metabolic_tick_count = 0
        st.session_state.lab_ticks = []  # tick numbers at which a lab reading landed


def _run_ticks(n: int) -> None:
    """Advance the shared patient state by n ticks; only lab ticks feed this tab."""
    state = st.session_state.metabolic_state
    simulator = st.session_state.metabolic_simulator
    metabolic = st.session_state.metabolic_module

    for _ in range(n):
        tick_count = st.session_state.metabolic_tick_count
        reading_type, reading = simulator.next_reading(state.patient_id, tick_count)
        state.add_reading(reading_type, reading)

        if reading_type == "lab":
            metabolic.process(state)
            st.session_state.lab_ticks.append(tick_count)

        st.session_state.metabolic_tick_count += 1


def _status_label(score: float) -> str:
    if score <= 0.0:
        return "normal"
    if score >= 1.0:
        return "high"
    return "borderline"


def _latest_values_table(latest_risk: dict) -> pd.DataFrame:
    explanation = latest_risk["explanation"]
    latest_reading = explanation["latest_reading"]
    marker_scores = explanation["marker_scores"]
    trends = explanation.get("trends", {})

    domain_of = {m: d for d, markers in DOMAIN_MARKERS.items() for m in markers}

    rows = []
    for marker in REFERENCE_RANGES:
        if marker not in latest_reading:
            continue
        rows.append({
            "Marker": marker,
            "Value": latest_reading[marker],
            "Unit": MARKER_UNITS[marker],
            "Domain": domain_of.get(marker, "—"),
            "Status": _status_label(marker_scores.get(marker, 0.0)),
            "Trend": trends.get(marker, "stable"),
        })
    return pd.DataFrame(rows)


def _trend_figure(lab_history, lab_ticks) -> go.Figure:
    markers = list(REFERENCE_RANGES.keys())
    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=[MARKER_LABELS[m] for m in markers],
        vertical_spacing=0.12,
    )
    for idx, marker in enumerate(markers):
        row, col = idx // 3 + 1, idx % 3 + 1
        ys = [r.get(marker) for r in lab_history]
        fig.add_trace(
            go.Scatter(x=lab_ticks, y=ys, mode="lines+markers", name=marker, showlegend=False),
            row=row, col=col,
        )
        ref = REFERENCE_RANGES[marker]
        fig.add_hline(y=ref["normal"], line_dash="dot", line_color="gray", row=row, col=col)
        fig.add_hline(y=ref["high"], line_dash="dash", line_color="red", row=row, col=col)
    fig.update_layout(height=520, title_text="Lab Marker Trends (dotted = normal cutoff, red = high cutoff)")
    return fig


def render_metabolic_tab() -> None:
    _init_session()
    state = st.session_state.metabolic_state

    st.title("🧪 Metabolic Twin — Lab Monitor")
    st.caption(
        f"Patient: {state.patient_id} | Ticks elapsed: {st.session_state.metabolic_tick_count} "
        f"| Lab readings so far: {len(state.lab_history)}"
    )

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        n_ticks = st.number_input("Ticks to advance", min_value=1, max_value=50, value=6, step=1)
    with col2:
        if st.button("▶ Advance", type="primary"):
            _run_ticks(int(n_ticks))
    with col3:
        auto = st.checkbox("Auto-run (1 tick / sec)")

    latest_risk = state.risk_scores.get("metabolic")

    # --- Domain risk banners ---
    if latest_risk:
        domain_scores = latest_risk["explanation"]["domain_scores"]
        d1, d2, d3 = st.columns(3)
        for col, domain in zip((d1, d2, d3), ("kidney", "liver", "glucose")):
            score = domain_scores.get(domain, 0.0)
            with col:
                if score >= DOMAIN_ALERT_THRESHOLD:
                    st.error(f"⚠️ {domain.title()}: {score:.2f}")
                else:
                    st.success(f"{domain.title()}: {score:.2f}")
        st.caption(f"Overall metabolic risk: **{latest_risk['score']:.2f}**")
    else:
        st.info("No lab reading yet — click Advance to start the simulation.")

    # --- Latest lab values table ---
    st.subheader("Latest Lab Values")
    if latest_risk:
        df = _latest_values_table(latest_risk)
        st.dataframe(df, width='stretch', hide_index=True)
    else:
        st.info("No lab values yet.")

    # --- Per-marker trend chart ---
    st.subheader("Marker Trends Over Time")
    if st.session_state.lab_ticks:
        fig = _trend_figure(list(state.lab_history), st.session_state.lab_ticks)
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No lab ticks yet.")

    if auto:
        time.sleep(1)
        _run_ticks(1)
        st.rerun()


if __name__ == "__main__":
    render_metabolic_tab()
