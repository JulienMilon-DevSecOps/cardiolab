# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

First release. The package covers the full analysis pipeline from raw RR
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

### Added — Protocol-specific scores

Five scoring functions in `analytics/scoring.py`, each mapping a protocol's
primary metric to a normalised [0–100] scale using published clinical
thresholds. No personal baseline required.

- `hrr_score(hrr_60)` — maps HRR1 (bpm drop at 60 s) to [0–100]. Inflection
  at 18 bpm (mid-normal range). Reference: Cole et al. (1999), *NEJM* 341(18).
- `coherence_score_100(coherence_score)` — remaps the raw coherence percentage
  with amplified discrimination around 60 % (good coherence threshold).
  Reference: Lehrer & Gevirtz (2014), *Front. Psychol.* 5:756.
- `drift_score(drift_rate)` — inverted exponential score from drift rate
  (bpm/min); 0 bpm/min → 100 pts, ≥ 3 bpm/min → ~17 pts.
  Reference: Coyle & González-Alonso (2001), *Exerc. Sport Sci. Rev.* 29(2).
- `vo2max_score(vo2max)` — sigmoid centred at 43 mL/kg/min (average adult
  "Good" ACSM category). Reference: ACSM (2022), *Guidelines for Exercise
  Testing and Prescription*, 11th ed.
- `orthostatic_score(hr_response, hf_response_pct)` — composite autonomic
  score: 80 % ΔHR (U-shaped, optimal 10–25 bpm, POTS threshold at 30 bpm) +
  20 % HF vagal-withdrawal (normal range −30 % to −60 %).
  References: Brignole et al. (2018), ESC Guidelines, *Eur. Heart J.*; Sheldon
  et al. (2015), HRS expert consensus on POTS, *Heart Rhythm* 12(6);
  Task Force ESC/NASPE (1996), *Circulation* 93(5).

`score: float = 0.0` field present on all six protocol result dataclasses
(`HRVFeatures`, `HRRResult`, `CoherenceResult`, `DriftResult`, `VO2maxResult`,
`OrthostaticResult`, `OrthostaticRecord`).

### Added — Analytics

- `analytics/baseline.py` — User baseline computation from longitudinal history
  (rolling statistics).
- `analytics/anomaly.py` — Z-score anomaly detection on HRV indicators.
- `analytics/scoring.py` — Composite multi-domain HRV readiness score
  (`readiness_score_multi`, `readiness_score_nonlinear`,
  `readiness_score_composite`, `readiness_score_oura`) + five protocol-specific
  absolute scores (see above).
- `analytics/trends.py` — Longitudinal trend analysis (slope, direction).

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
- `visualization/dashboard_plots.py` — Global dashboard functions and
  per-protocol mini-dashboards (resting, orthostatic, coherence, HRR, drift,
  VO2max) plus `plot_score_evolution()`: generic [0–100] score timeline
  compatible with any protocol result carrying a `.score` attribute. Includes
  coloured zone backgrounds, per-session coloured dots, numeric annotations,
  and a rolling-average band (≥ 3 sessions).

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

- `database/repository.py` — Named-query repository pattern for all six
  protocols; upsert-safe inserts and fetch by user. Seven tables:
  `hrv_features`, `hrv_orthostatic`, `hrv_coherence`, `hrv_hrr`, `hrv_drift`,
  `hrv_vo2max`, `hrv_raw_sessions`.
- `hrv_raw_sessions` — stores the full RR interval array (PostgreSQL `FLOAT[]`)
  alongside provenance metadata (device, source file, JSONB). Unique key:
  `(user_id, session_date, protocol)`. Enables protocol reprocessing without
  original files and powers mini-dashboard visualisations from the database.

### Added — I/O and sensors

- `io/export.py` — Export protocol results to CSV and JSON.
- `sensors_tools/polar.py` — Parser for Polar RR export format (`.txt`).
- `scripts/import_rr.py` — CLI script to import RR data files into PostgreSQL.

### Fixed

- `analytics/scoring.py` — `readiness_score_multi()` now guarantees output in
  [0, 100]. The previous implementation could yield values slightly outside
  this range in pathological inputs due to unclamped sub-score arithmetic.
- `database/repository.py` — `_register_numpy_adapters()` called in
  `__enter__()` to fix a `psycopg2` serialisation failure with NumPy 2.x
  (`numpy.int64` / `numpy.float64` are no longer transparently coerced to
  Python scalars by the adapter).
- `protocols/resting.py` — `PhysiologicalWarning` raised when recording
  duration falls below the 300 s recommended minimum for resting HRV analysis
  (Task Force 1996). Consistent with similar guards in coherence, HRR, and
  drift protocols.
- `protocols/orthostatic.py` — `OrthostaticRecord.to_flat_dict()` and
  `to_reporting_row()` now mirror `OrthostaticResult` field-for-field, enabling
  duck-typed reporting and CSV/JSON export from DB-loaded records.

### Added — Quality and tooling

- **1 190 unit tests** (pytest); integration tests auto-activate when
  `DB_HOST_TEST` is set in the environment, auto-skip in GitLab CI.
- Full PostgreSQL integration test suite for all seven repository protocols:
  resting, orthostatic, coherence, HRR, drift, VO2max, and raw sessions.
  Each class exercises round-trip persistence, upsert idempotency, `score`
  preservation, and type-specific edge cases (NaN, `bool`, string categories).
- `tests/conftest.py` — `.env` loading via `python-dotenv` at pytest start-up,
  allowing integration tests to pick up database credentials without manual
  environment exports.
- **Zero ruff errors** — rules E, F, I, B, UP, SIM, D, N, S enforced.
- `pipeline-notebook.ipynb` — end-to-end Jupyter pipeline covering all six
  protocols: acquisition → features → analysis → visualisation → reporting.
- Full API documentation under `docs/` (signal, protocol, visualization,
  reporting layers).
- `pyproject.toml` configured for `hatchling` build, `ruff` lint, `pytest`.

### DevOps

- Secret detection stage added to the centralised GitLab CI pipeline.
