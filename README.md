# MediTwin — Unified Multi-Disease Digital Twin Platform

Digital Twin Challenge 2026 (Happiest Health) submission.

## Structure
- twin_engine/ — core patient-state engine and scheduler
- modules/cardiac/ — cardiac risk module
- modules/metabolic/ — metabolic risk module (rule-based reference-range scorer + trend detection, done)
- modules/dermatology/ — dermatology module (optional/stretch, done): real ONNX MLP classifier (99% held-out accuracy) trained on synthetic ABCD-rule dermoscopy images — no DermNet dataset access in this build environment, so images are rendered from first principles (asymmetry/border/color/diameter parameters) and features are re-extracted from pixels, not handed the generation parameters. Swap in a real DermNet-trained model by replacing the training data source in `model.py`.
- data/ — datasets and synthetic data
- dashboard/ — Streamlit dashboard tabs (cardiac_tab.py, metabolic_tab.py, dermatology_tab.py — all done)
- app.py — unified multi-patient app tying all three modules together (Step 9, done)
- docs/ — methodology, architecture docs

## Setup
```
pip install -r requirements.txt
streamlit run app.py
```
