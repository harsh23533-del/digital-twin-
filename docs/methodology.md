# MediTwin — Methodology

## 1. Problem framing

Most disease-risk tools score a patient once, from a single snapshot of data. A
digital twin is different: it holds one evolving `PatientState` per patient and
re-scores that state every time new data arrives, so risk is a continuously
updated line rather than a single number. MediTwin implements this for three
organ systems — cardiac, metabolic, dermatology — behind one shared engine.

## 2. Architecture

See `docs/architecture.png`. In short: a `DummySimulator` emits `vitals` /
`lab` / `image` readings on each `tick()`; the twin engine (`twin_engine/`)
appends each reading to the matching history buffer on `PatientState` and
routes it to the module that owns that reading type; each module recomputes
its own `risk_scores[...]` entry; `app.py` ties all three modules together
behind a multi-patient selector and a shared, chronological alert log.

## 3. Data sources per module

| Module | Data source | Why |
|---|---|---|
| Cardiac | UCI Cleveland Heart Disease dataset (`data/cardiac/cleveland_heart.csv`) | Public, real clinical dataset; reused from the author's existing `heart-disease-predictor` project |
| Metabolic | Synthetic periodic lab readings (kidney/liver/glucose panels), generated to drift gradually tick-to-tick | No existing labeled "lab report analyzer" dataset was available to reuse; clinical reference ranges are well-defined and public, so a rule-based scorer is both accurate and fully explainable without needing training data |
| Dermatology | Synthetic dermoscopy images rendered from ABCD-rule parameters (asymmetry, border irregularity, color variegation, diameter) per class | DermNet and Kaggle skin-lesion datasets were not reachable from this build environment (network is restricted to package registries only, no dataset hosts) |

## 4. Model details

**Cardiac.** XGBoost classifier (`n_estimators=200, max_depth=5,
learning_rate=0.05`) trained on the 13 standard Cleveland features
(age, sex, cp, trestbps, chol, fbs, restecg, thalach, exang, oldpeak, slope,
ca, thal), held-out AUC-ROC ≈ 0.92 on this build's own train/test split
(the original reused app reported ~0.94 on its own split — same model
family and hyperparameters, different split, so the two aren't directly
comparable). A `shap.TreeExplainer` runs on every tick
so each score ships with its own per-feature contribution breakdown, shown as
a bar chart in `cardiac_tab.py`. Rolling wearable features (last-N-minute
heart-rate average, SpO2 trend) are blended in via
`modules/cardiac/rolling_features.py` so the score reacts to the simulated
vitals stream, not just the static EHR profile.

**Metabolic.** Six lab markers (creatinine, eGFR, ALT, AST, glucose, HbA1c)
are each scored 0 (normal) → 1 (fully abnormal) by linear interpolation
between their clinical reference range and an "abnormal" cutoff
(`modules/metabolic/model.py`). Markers are grouped into three domains —
kidney, liver, glucose — the domain score is the mean of its markers, and the
overall metabolic score is the mean of the three domains. This is
deliberately rule-based rather than a trained model: the logic is fully
transparent and auditable, matching the "reason behind the score" spirit of
the cardiac module's SHAP output without requiring a labeled training set.
`modules/metabolic/trend.py` layers worsening/improving/stable trend labels
on top by comparing consecutive readings per marker.

**Dermatology.** A small MLP classifier (`hidden_layer_sizes=(24,)`) is
trained on ABCD-rule features re-extracted from the *pixels* of synthetic
dermoscopy images (not handed the generation parameters directly, so the
model genuinely has to learn the pixel → class relationship) across six
classes (healthy, eczema, psoriasis, benign nevus, basal cell carcinoma,
melanoma), held-out accuracy ≈ 0.99 on the synthetic distribution. The model
is exported to ONNX and served through `onnxruntime.InferenceSession` —
identical inference path to what a real DermNet-trained MobileNetV2 export
would use; only the training data source differs. A malignancy score is
computed as the probability-weighted sum of a per-class severity weight
(healthy = 0.0 → melanoma = 1.0), so it moves smoothly with the predicted
distribution rather than jumping only on the argmax class.

## 5. Personalization logic

Each patient owns an independent `PatientState` (EHR profile + per-module
history buffers + risk scores). Modules read from that patient's own state
only, so two patients with different EHR profiles and reading streams
produce different, independently-evolving risk trajectories from the same
shared model instances — verified directly in
`tests/test_engine.py::test_multi_patient_personalization`. Alerts are
logged per-patient but merged into one shared, chronological log in `app.py`
so a clinician-style view can watch multiple patients at once.

## 6. Validation

`tests/test_engine.py` (run via `python3 tests/test_engine.py`, no pytest
dependency) covers four checks end to end, mirroring the challenge's testing
requirements:

1. **Parity** — each module's output matches the underlying model called
   directly on the same input (cardiac, metabolic, dermatology).
2. **Multi-day consistency** — a 60-tick simulated run keeps history buffers
   bounded and monotonically-updating with no state corruption.
3. **Threshold-breach alerts** — extreme synthetic inputs push scores past
   each module's alert threshold; low-risk inputs stay under it.
4. **Multi-patient personalization** — two distinct patients produce
   distinct, correctly-ordered risk scores from the same engine.

All 8 checks pass on a clean install of `requirements.txt`.

## 7. Limitations

- The metabolic and dermatology modules are trained/scored on synthetic data
  (reference-range logic and ABCD-rule-derived images respectively), not real
  labeled clinical datasets — they demonstrate the twin architecture and
  personalization pattern, not clinical-grade accuracy for those two organ
  systems.
- The cardiac module is the only one trained on a real clinical dataset
  (Cleveland), and that dataset itself is small (~300 rows) and from 1988.
- The simulator (`DummySimulator`) generates plausible-looking but synthetic
  time-series readings; there is no real wearable/EHR feed integration.
- Dermatology images are rendered from ABCD parameters, not real dermoscopy
  photographs — texture, lighting, and hair/artifact noise that a real
  classifier has to handle are not modeled.
- This is a hackathon-scope prototype: no authentication, no persistence
  layer (state lives only in the Streamlit session), and no real PHI/EHR
  integration — not intended for clinical use.
