# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-05-26

First public release. The package covers the full analysis pipeline from raw RR
intervals to clinical reporting, across six validated physiological protocols.

### Added — Core signals

- `signals/rr.py` — `RRSeries`: typed representation of RR intervals with
  input validation (range, length), heart-rate conversion, and filtering helpers.
- `signals/ecg.py` — `ECGSignal`: ECG signal loader with R-peak detection and
  RR extraction via `scipy`.

### Added — HRV feature extraction

- `features/time_domain.py` — RMSSD, SDNN, SD1, SD2, SD1/SD2 ratio, pNN50,
  mean HR. Fully vectorised via NumPy.
- `features/frequency_domain.py` — Power spectral density (VLF, LF, HF, LF/HF
  ratio) computed by FFT and Lomb-Scargle. Named physiological band constants.
- `features/nonlinear.py` — DFA α1 (log-log slope), approximate entropy (ApEn),
  sample entropy (SampEn), Poincaré SD1/SD2.

### Added — Clinical protocols

- `protocols/resting.py` — Resting HRV analysis. Computes a multi-domain score
  and fitness category from a `RRSeries` and user demographics.
- `protocols/orthostatic.py` — Active orthostatic test (supine → standing).
  Computes HR delta, vagal reactivity index, and clinical interpretation.
- `protocols/cardiac_coherence.py` — Cardiac coherence analysis. Resonance
  frequency, peak power, coherence score (McCraty / HeartMath standard).
- `protocols/hrr.py` — Heart Rate Recovery. HRR60 and HRR120 with Cole et al.
  1999 clinical categories.
- `protocols/cardiac_drift.py` — Cardiac drift by linear regression over sliding
  windows. Drift rate (bpm/min), magnitude, R², and clinical interpretation.
- `protocols/vo2max.py` — VO2max estimation via three validated models: Uth
  (requires HRmax), Esco-Flatt (HRV-derived), and ln-RMSSD (Nunan). ACSM 2022
  fitness categories.

### Added — Visualization

- `visualization/rr_plots.py` — Time-series plot of RR intervals with ectopic
  beat markers.
- `visualization/spectral_plots.py` — Power spectral density plots (FFT /
  Lomb-Scargle) with physiological band overlays (VLF, LF, HF).
- `visualization/nonlinear_plots.py` — Poincaré scatter plot and DFA log-log
  regression.
- `visualization/resting_plots.py` — Longitudinal evolution of resting HRV
  indicators across sessions.
- `visualization/coherence_plots.py` — Coherence spectrogram and session score
  timeline.
- `visualization/hrr_plots.py` — HR recovery curve with HRR60/HRR120 markers
  and reference bands.
- `visualization/drift_plots.py` — Drift trajectory with linear regression
  overlay and magnitude annotation.
- `visualization/vo2max_plots.py` — Side-by-side comparison of three VO2max
  model estimates with ACSM category bands.
- `visualization/dashboard_plots.py` — Eight global dashboard functions and five
  per-protocol mini-dashboards (resting, orthostatic, coherence, HRR, drift,
  VO2max).

### Added — Tabular reporting

Nine `pd.Styler`-based functions exportable to HTML, Excel, or Jupyter display:

- `reporting/resting.py` — `table_resting_history`, `table_resting_session`.
- `reporting/orthostatic.py` — `table_orthostatic_comparison` (supine vs.
  standing with deltas), `table_orthostatic_history`.
- `reporting/hrr.py` — `table_hrr_history`.
- `reporting/drift.py` — `table_drift_history`.
- `reporting/coherence.py` — `table_coherence_history` (derived category column:
  low / moderate / high).
- `reporting/vo2max.py` — `table_vo2max_history`, `table_vo2max_session`.
- Shared colour helpers in `reporting/_core.py`: green-to-red gradients for
  every clinical indicator, category palette highlighting.

### Added — Database persistence

- `database/schema.py` — PostgreSQL schema creation (sessions, HRV features,
  protocol results).
- `database/repository.py` — Named-query repository pattern for all six
  protocols; insert and fetch by user / date range.

### Added — I/O and sensors

- `io/export.py` — Export protocol results to CSV and JSON.
- `sensors_tools/polar.py` — Parser for Polar RR export format (`.txt`).
- `scripts/import_rr.py` — CLI script to import RR data files into PostgreSQL.

### Added — Analytics

- `analytics/baseline.py` — User baseline computation from longitudinal history
  (rolling statistics).
- `analytics/anomaly.py` — Z-score anomaly detection on HRV indicators.
- `analytics/scoring.py` — Composite multi-domain HRV score.
- `analytics/trends.py` — Longitudinal trend analysis (slope, direction).

### Added — Quality and tooling

- **1 111 unit tests** (pytest), 2 skipped (PostgreSQL integration — requires
  live DB).
- **Zero ruff errors** — rules E, F, I, B, UP, SIM, D, N, S enforced.
- `pipeline-notebook.ipynb` — end-to-end Jupyter pipeline covering all six
  protocols: acquisition → features → analysis → visualisation → reporting.
- Full API documentation under `docs/` (signal, protocol, visualization,
  reporting layers).
- `pyproject.toml` configured for `hatchling` build, `ruff` lint, `pytest`.
