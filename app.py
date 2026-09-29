"""
Digi Twin — Cardiac Digital Twin dashboard.

A patient selector supporting 2+ simulated patients, a chronological
cardiac alert log, and a persistent header above the live vitals/risk
view.

Run:
    streamlit run app.py
"""

import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from twin_engine.patient_state import PatientState
from twin_engine.scheduler import DummySimulator
from modules.cardiac.cardiac_module import CardiacModule
from twin_engine.live_heart_rate import LiveHeartRateSource
from dashboard.patient_header import render_patient_header
from dashboard.cardiac_alarm import render_cardiac_alarm

from config import CARDIAC_ALERT_THRESHOLD

st.set_page_config(page_title="Digi Twin", layout="wide", page_icon="🫀")

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap');

:root {
  --bg: #F3F4F1;
  --panel: #10262B;
  --panel-2: #0A1E21;
  --ink: #14201E;
  --ink-soft: rgba(20,32,30,0.62);
  --on-dark: #E7EFEC;
  --heart: #FF4462;
  --o2: #37D6C4;
  --bp: #FFB648;
  --safe: #33C17A;
}

.stApp { background: var(--bg); font-family: 'Space Grotesk', sans-serif; color: var(--ink); }
.block-container { padding-top: 1.1rem; padding-bottom: 1rem; max-width: 1200px; }
header[data-testid="stHeader"] { background: transparent; }

[data-testid="stSidebar"] { background: #E9ECE8; border-right: 1px solid rgba(16,38,43,0.08); }
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { font-family: 'Space Grotesk', sans-serif; font-weight: 700; }

/* Hero bar with a single looping ECG trace */
.hero {
  position: relative; overflow: hidden; border-radius: 16px; padding: 20px 26px;
  background: linear-gradient(120deg, #123037 0%, #0a1e21 70%);
  color: var(--on-dark); margin-bottom: 14px;
}
.hero h1 { margin: 0; font-size: 1.7rem; font-weight: 700; letter-spacing: -0.01em; color: var(--on-dark); padding: 0; }
.hero p { margin: 4px 0 0; font-size: 0.85rem; color: rgba(231,239,236,0.6); }
.hero svg { position: absolute; right: 0; top: 0; height: 100%; width: 55%; opacity: 0.9; }
.ecg-line {
  fill: none; stroke: var(--heart); stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round;
  stroke-dasharray: 900; stroke-dashoffset: 900; animation: ecg-draw 3.2s linear infinite;
  filter: drop-shadow(0 0 5px rgba(255,68,98,0.7));
}
@keyframes ecg-draw { 0% { stroke-dashoffset: 900; } 70% { stroke-dashoffset: 0; } 100% { stroke-dashoffset: -900; } }

/* Vital monitor tiles */
.vital {
  background: linear-gradient(145deg, var(--panel) 0%, var(--panel-2) 100%);
  border-radius: 14px; padding: 16px 20px; color: var(--on-dark);
  border-left: 5px solid var(--accent); position: relative; overflow: hidden;
}
.vital .label { font-size: 0.78rem; color: rgba(231,239,236,0.6); margin-bottom: 4px; }
.vital .value {
  font-family: 'IBM Plex Mono', monospace; font-size: 2.3rem; font-weight: 600;
  color: var(--accent); line-height: 1.1; text-shadow: 0 0 14px color-mix(in srgb, var(--accent) 45%, transparent);
}
.vital .unit { font-family: 'Space Grotesk', sans-serif; font-size: 0.85rem; color: rgba(231,239,236,0.55); margin-left: 6px; }
.vital.hr .value.beat { animation: beat var(--beat-dur, 0.8s) ease-in-out infinite; display: inline-block; transform-origin: left center; }
@keyframes beat { 0%, 100% { transform: scale(1); } 15% { transform: scale(1.09); } 30% { transform: scale(1); } }

/* Status banner */
.status {
  border-radius: 12px; padding: 13px 18px; font-weight: 600; margin: 14px 0 6px;
  display: flex; align-items: center; gap: 10px;
}
.status.ok { background: rgba(51,193,122,0.13); color: #17703f; border: 1px solid rgba(51,193,122,0.35); }
.status.idle { background: rgba(20,32,30,0.06); color: var(--ink-soft); }
.status .pip { width: 10px; height: 10px; border-radius: 50%; background: currentColor; }

/* Sidebar alert entries */
.alert-item { font-size: 0.82rem; padding: 7px 0; border-bottom: 1px solid rgba(16,38,43,0.08); }
.alert-item .t { font-family: 'IBM Plex Mono', monospace; color: var(--ink-soft); margin-right: 6px; }
.alert-item .p { font-weight: 700; }
.alert-item .m { color: #c4243f; }

/* Auto-run: blinking call-to-action until switched on */
@keyframes autorun-blink {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255,68,98,0.55); border-color: #FF4462; background: rgba(255,68,98,0.12); }
  50% { box-shadow: 0 0 0 10px rgba(255,68,98,0); border-color: #ff9aa9; background: rgba(255,68,98,0.30); }
}
@keyframes hint-blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.25; } }
.autorun-hint {
  font-weight: 700; font-size: 0.9rem; color: #c4243f; margin: 4px 0 6px;
  animation: hint-blink 1.1s ease-in-out infinite;
}
.autorun-live {
  font-weight: 700; font-size: 0.85rem; color: #17703f; margin: 4px 0 6px;
}
.autorun-live .pip {
  display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: #33C17A;
  margin-right: 6px; box-shadow: 0 0 8px #33C17A; animation: hint-blink 1s ease-in-out infinite;
}
[data-testid="stSidebar"] [data-testid="stCheckbox"] {
  border: 2px solid #FF4462; border-radius: 12px; padding: 12px 14px;
  background: rgba(255,68,98,0.12); animation: autorun-blink 1.1s ease-in-out infinite;
}
[data-testid="stSidebar"] [data-testid="stCheckbox"] label p { font-weight: 700; font-size: 1rem; }
[data-testid="stSidebar"] [data-testid="stCheckbox"]:has(input:checked) {
  animation: none; border-color: #33C17A; background: rgba(51,193,122,0.14);
}

@media (prefers-reduced-motion: reduce) {
  .ecg-line, .vital.hr .value.beat, .autorun-hint, .autorun-live .pip,
  [data-testid="stSidebar"] [data-testid="stCheckbox"] { animation: none; stroke-dashoffset: 0; }
}
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

_ECG_PATH = (
    "M0,60 L120,60 L140,60 L155,58 L165,60 L200,60 L215,62 L225,20 L240,105 L255,60 "
    "L300,60 L330,52 L350,60 L520,60 L540,60 L555,58 L565,60 L600,60 L615,62 L625,20 "
    "L640,105 L655,60 L700,60 L730,52 L750,60 L900,60"
)


def _hero_html() -> str:
    return (
        '<div class="hero"><h1>Digi Twin</h1>'
        '<p>Cardiac digital twin &nbsp;|&nbsp; Digital Twin Challenge 2026 (Happiest Health)</p>'
        '<svg viewBox="0 0 900 120" preserveAspectRatio="none">'
        f'<path class="ecg-line" d="{_ECG_PATH}"/></svg></div>'
    )


def _vital_tile(label: str, value, unit: str, accent: str, beat_bpm=None) -> str:
    cls = "vital hr" if beat_bpm else "vital"
    style = f"--accent:{accent};"
    val_cls = "value"
    if beat_bpm:
        style += f"--beat-dur:{60.0 / max(beat_bpm, 30):.2f}s;"
        val_cls += " beat"
    return (
        f'<div class="{cls}" style="{style}"><div class="label">{label}</div>'
        f'<div><span class="{val_cls}">{value}</span><span class="unit">{unit}</span></div></div>'
    )


def _style_fig(fig):
    fig.update_layout(
        font=dict(family="Space Grotesk, sans-serif", color="#14201E"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.65)",
    )
    fig.update_xaxes(gridcolor="rgba(16,38,43,0.08)")
    fig.update_yaxes(gridcolor="rgba(16,38,43,0.08)")
    return fig


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
        st.session_state.data_source = "Simulator"
        st.session_state.live_source = LiveHeartRateSource()
        st.session_state.live_bp_override = 120


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


def _next_reading(patient_id: str) -> Optional[dict]:
    """Get one vitals reading from whichever data source is active. Returns
    None when live mode has no fresh reading yet (waiting for the device) —
    unlike the simulator, a live tick can genuinely have nothing to report."""
    if st.session_state.data_source == "Live BLE heart-rate monitor":
        reading = st.session_state.live_source.get_latest()
        if reading is None:
            return None
        # The HR service carries no BP/SpO2 — merge in the manual BP override
        # so the model's rolling trestbps feature still gets real input.
        return {**reading, "trestbps": st.session_state.live_bp_override}

    p = st.session_state.patients[patient_id]
    tick_count = p["tick_count"]
    _, reading = p["simulator"].next_reading(patient_id, tick_count)
    return reading


def _run_ticks(patient_id: str, n: int) -> None:
    p = st.session_state.patients[patient_id]
    state = p["state"]
    cardiac = st.session_state.cardiac_module

    for _ in range(n):
        reading = _next_reading(patient_id)
        if reading is None:
            break  # live mode with no signal yet — nothing to record this tick

        tick_count = p["tick_count"]
        state.add_reading("vitals", reading)
        cardiac.process(state)

        latest = state.risk_scores.get("cardiac")
        if latest:
            p["risk_history"].append((tick_count, latest["score"]))

        _check_alerts(patient_id, state)
        p["tick_count"] += 1


# --------------------------------------------------------------------- UI

_init_engine()

st.markdown(_hero_html(), unsafe_allow_html=True)

with st.sidebar:
    if st.session_state.get("auto_run"):
        st.markdown(
            "<div class='autorun-live'><span class='pip'></span>Live: updating every second</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='autorun-hint'>&#9660; Click Auto-run to watch the twin update live</div>",
            unsafe_allow_html=True,
        )
    auto = st.checkbox("▶ Auto-run (1 tick / sec)", key="auto_run")

    st.divider()
    st.subheader("Data source")
    st.radio(
        "Feed vitals from", ["Simulator", "Live BLE heart-rate monitor"],
        key="data_source", label_visibility="collapsed",
    )
    if st.session_state.data_source == "Live BLE heart-rate monitor":
        live = st.session_state.live_source
        st.caption(
            "Connects to any device broadcasting the standard Bluetooth "
            "Heart Rate service (0x180D) — e.g. a chest strap. Most budget "
            "smartwatches don't expose this; see docs/live_watch.md."
        )
        name_filter = st.text_input("Device name contains (optional)", value=live.name_filter or "")
        lc1, lc2 = st.columns(2)
        if lc1.button("Connect", width="stretch", disabled=live.is_running()):
            live.name_filter = name_filter or None
            live.start()
        if lc2.button("Disconnect", width="stretch", disabled=not live.is_running()):
            live.stop()

        status_map = {
            "idle": ("idle", "idle"), "scanning": ("scanning for device…", "idle"),
            "connected": (f"connected — {live.device_name or 'device'}", "ok"),
            "error": ("error", "idle"), "stopped": ("disconnected", "idle"),
        }
        label, cls = status_map.get(live.status, (live.status, "idle"))
        st.markdown(f"<div class='status {cls}'><span class='pip'></span>{label}</div>",
                    unsafe_allow_html=True)
        if live.status == "error" and live.error:
            st.caption(live.error)

        st.session_state.live_bp_override = st.number_input(
            "Resting BP (manual — device has no BP sensor)",
            min_value=70, max_value=220, value=st.session_state.live_bp_override,
        )

    st.header("Patient")
    patient_id = st.selectbox("Select patient", list(st.session_state.patients.keys()))
    n_ticks = st.number_input("Ticks to advance", min_value=1, max_value=50, value=1)
    if st.button("▶ Advance", type="primary", width="stretch"):
        _run_ticks(patient_id, int(n_ticks))

    st.divider()
    st.subheader("🔔 Cardiac Alerts — all patients")
    if st.session_state.alert_log:
        for a in reversed(st.session_state.alert_log[-15:]):
            st.markdown(
                f"<div class='alert-item'><span class='t'>{a['time']}</span>"
                f"<span class='p'>{a['patient']}</span> "
                f"<span class='m'>{a['message']}</span></div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No cardiac alerts yet.")

p = st.session_state.patients[patient_id]
state = p["state"]
st.caption(f"Patient: **{patient_id}** | Ticks elapsed: {p['tick_count']}")

render_patient_header(patient_id, state.ehr_profile)

# --- Cardiac ---
latest_vitals = state.vitals_history[-1] if state.vitals_history else None
v1, v2, v3 = st.columns(3)
_hr = latest_vitals["heart_rate"] if latest_vitals else None
with v1:
    st.markdown(
        _vital_tile("Heart rate", _hr if _hr is not None else "—", "bpm", "#FF4462", beat_bpm=_hr),
        unsafe_allow_html=True,
    )
with v2:
    st.markdown(
        _vital_tile("SpO2", latest_vitals.get("spo2", "—") if latest_vitals else "—", "%", "#37D6C4"),
        unsafe_allow_html=True,
    )
with v3:
    st.markdown(
        _vital_tile("Resting BP (trestbps)", latest_vitals.get("trestbps", "—") if latest_vitals else "—",
                    "mmHg", "#FFB648"),
        unsafe_allow_html=True,
    )

latest_risk = state.risk_scores.get("cardiac")
if latest_risk:
    score = latest_risk["score"]
    if score >= CARDIAC_ALERT_THRESHOLD:
        render_cardiac_alarm(score, CARDIAC_ALERT_THRESHOLD)
    else:
        st.markdown(
            f"<div class='status ok'><span class='pip'></span>"
            f"Cardiac risk nominal: {score:.2f}</div>",
            unsafe_allow_html=True,
        )

    chart_col1, chart_col2 = st.columns(2)

    vitals_recent = list(state.vitals_history)[-60:]
    with chart_col1:
        if vitals_recent:
            vfig = make_subplots(specs=[[{"secondary_y": True}]])
            vfig.add_trace(
                go.Scatter(y=[v["heart_rate"] for v in vitals_recent], name="Heart rate (bpm)",
                           mode="lines+markers", line=dict(color="#FF4462", width=2.5)),
                secondary_y=False,
            )
            vfig.add_trace(
                go.Scatter(y=[v["trestbps"] for v in vitals_recent], name="Resting BP (mmHg)",
                           mode="lines+markers", line=dict(color="#FFB648", width=2.5)),
                secondary_y=True,
            )
            vfig.update_yaxes(title_text="HR (bpm)", secondary_y=False)
            vfig.update_yaxes(title_text="BP (mmHg)", secondary_y=True)
            vfig.update_layout(
                title="Recent vitals stream", xaxis_title="Recent ticks", height=280,
                margin=dict(t=40, b=30, l=10, r=10), legend=dict(orientation="h", y=-0.25),
            )
            st.plotly_chart(_style_fig(vfig), width="stretch")

    history = p["risk_history"]
    with chart_col2:
        if history:
            xs, ys = zip(*history)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=list(xs), y=list(ys), mode="lines+markers", name="Risk score",
                line=dict(color="#0f8f86", width=2.8), marker=dict(size=6),
            ))
            fig.add_hline(y=CARDIAC_ALERT_THRESHOLD, line_dash="dash", line_color="red")
            fig.update_layout(
                title="Cardiac risk trend", xaxis_title="Tick", yaxis_title="Risk (0-1)",
                yaxis_range=[0, 1], height=280, margin=dict(t=40, b=30, l=10, r=10),
            )
            st.plotly_chart(_style_fig(fig), width="stretch")

    top_factors = latest_risk["explanation"].get("top_factors")
    if top_factors:
        with st.expander("Top contributing factors (SHAP)"):
            names, vals = list(top_factors.keys()), list(top_factors.values())
            colors = ["#FF4462" if v > 0 else "#33C17A" for v in vals]
            fig2 = go.Figure(go.Bar(x=vals, y=names, orientation="h", marker_color=colors))
            fig2.update_layout(xaxis_title="SHAP contribution", height=240, margin=dict(t=10, b=10))
            st.plotly_chart(_style_fig(fig2), width="stretch")
else:
    st.markdown(
        "<div class='status idle'>No cardiac reading yet. Click Advance in the sidebar.</div>",
        unsafe_allow_html=True,
    )

if auto:
    time.sleep(1)
    _run_ticks(patient_id, 1)
    st.rerun()
