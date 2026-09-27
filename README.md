# MediTwin — Cardiac Digital Twin

Submission for the **Digital Twin Challenge 2026** (Happiest Health).

## Problem

Most risk-prediction tools score a patient once from a single snapshot.
MediTwin instead keeps one evolving **digital twin** per patient — a
`PatientState` that gets re-scored on every new vitals reading — for
the **cardiac** organ system, behind a multi-patient Streamlit app.

See [`docs/methodology.md`](docs/methodology.md) for data sources, model
details, and limitations.

## Architecture

A shared **Twin Engine** (`twin_engine/`) advances simulated time and
routes each new vitals reading to the cardiac module, which keeps
`risk_scores["cardiac"]` up to date; a persistent header (patient EHR
summary + a low-poly 3D humanoid highlighting the heart) sits above the
live vitals/risk view; `app.py` unifies everything behind a patient
selector and a chronological cardiac alert log.

## Structure

```
twin_engine/          core patient-state engine + tick scheduler (incl. occasional
                       cardiac stress episodes — see Cardiac Alarm below)
modules/cardiac/       XGBoost (AUC ≈ 0.92 on this build's own held-out split) + SHAP explainer, rolling vitals features
dashboard/             patient_header.py (persistent EHR + 3D heart-highlight model),
                        cardiac_alarm.py (flashing/beeping high-risk alert),
                        cardiac_tab.py (standalone single-patient view)
app.py                 unified multi-patient app; sidebar alert log
config.py               shared alert thresholds (single source of truth)
data/cardiac/          Cleveland Heart Disease CSV
tests/test_engine.py   parity, multi-day, alert-threshold, multi-patient checks
docs/                  methodology.md
.github/workflows/     CI: lint (flake8) + test suite on every push/PR
```

## Persistent Patient Header

Above the live vitals view, a header shows the active patient's EHR
baseline (age, sex, cholesterol, resting BP) alongside a low-poly 3D
humanoid (Three.js, embedded via `st.iframe`) with the heart highlighted.

## Cardiac: live vitals + alarm

The Cardiac view shows the patient's current heart rate, SpO2, and resting
BP as live metrics, plus a recent-vitals chart (last 60 readings). The
simulator occasionally runs a short "stress episode" — elevated resting BP
paired with a heart rate that fails to rise with it (chronotropic
incompetence, a real risk marker also reflected in the underlying Cleveland
training data) — so cardiac risk genuinely fluctuates rather than sitting
flat. When it does, a flashing red banner with a best-effort audio beep
(hospital-monitor style) replaces the normal status banner. The sidebar
alert log is chronological across all patients.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

First run trains and caches the cardiac model locally (`artifacts/`
folder, gitignored) — a few seconds, then instant on later runs.

## Testing

```bash
python3 tests/test_engine.py
```

Runs 4 checks (parity vs. the underlying model, 60-tick multi-day
consistency, threshold-breach alerts, multi-patient personalization)
with no pytest dependency required.

## Status

Cardiac-only build — metabolic and dermatology modules (previously
present as a stretch goal) have been removed to keep the twin focused
on a single organ system. See `docs/methodology.md` for known
limitations (hackathon-scope prototype — not for clinical use).
