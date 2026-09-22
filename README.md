# MediTwin — Unified Multi-Disease Digital Twin Platform

Digital Twin Challenge 2026 (Happiest Health) submission.

## Structure
- twin_engine/ — core patient-state engine and scheduler
- modules/cardiac/ — cardiac risk module
- modules/metabolic/ — metabolic risk module (rule-based reference-range scorer + trend detection, done)
- modules/dermatology/ — dermatology module (optional/stretch) — done as a placeholder classifier (no DermNet/ONNX model available; same interface a real one would expose)
- data/ — datasets and synthetic data
- dashboard/ — Streamlit dashboard tabs (cardiac_tab.py, metabolic_tab.py: done)
- docs/ — methodology, architecture docs

## Setup
```
pip install -r requirements.txt
```
