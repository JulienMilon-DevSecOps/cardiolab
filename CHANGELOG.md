# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — v0.2.0 Phase 3 — ATL / CTL / TSB model

- `analytics/training_load.py` — additions to the training load module:
  - `compute_atl(trimp, tau=7) → np.ndarray` — 7-day EMA of TRIMP (acute fatigue). Initial condition: 0. Converges to TRIMP at steady state.
  - `compute_ctl(trimp, tau=42) → np.ndarray` — 42-day EMA of TRIMP (chronic fitness). Decays ~6× slower than ATL.
  - `compute_tsb(ctl, atl) → np.ndarray` — TSB = CTL − ATL (form / freshness). Negative = accumulated fatigue.
  - `class TrainingLoad` — end-to-end container built from session dicts:
    - `from_sessions(sessions, tau_atl=7, tau_ctl=42) → TrainingLoad` — builds a dense daily date range from the first to last session; gaps filled with TRIMP=0; `trimp=None` treated as 0.
    - `to_dataframe() → pd.DataFrame` — columns: `date | trimp | atl | ctl | tsb` (requires `pip install cardiolab[analysis]`).
- `analytics/__init__.py` — exports `compute_atl`, `compute_ctl`, `compute_tsb`, `TrainingLoad`
- Unit tests `TestComputeAtl` (8), `TestComputeCtl` (5), `TestComputeTsb` (5), `TestTrainingLoad` (12) in `tests/analytics/test_training_load.py`

---

### Added — v0.2.0 Phase 2 — TRIMP calculation

- `analytics/training_load.py` — new module for training load computation
  - `trimp_hrv_based(duration_min, readiness_score) → float` — primary TRIMP: `duration × (1 − readiness/100)`. Validates input strictly (raises `ValueError` on invalid range). Reference: Manzi V et al. (2009).
  - `trimp_banister(duration_min, hr_mean, hr_max, hr_rest, sex) → float` — Banister (1991) HR-reserve formula; `b=1.92` (male) / `b=1.67` (female); HRR clamped to [0, 1]. Fallback for HR-sensor data.
  - `load_readiness_for_date(user_id, date, repo, baseline, protocol) → float | None` — strict single-protocol lookup; `"resting"` reads resting table, `"orthostatic"` reads orthostatic table and uses the **supine phase** RMSSD. Returns `None` when no session found for the date. Never falls back to the other protocol.
- `analytics/__init__.py` — exports `trimp_hrv_based`, `trimp_banister`, `load_readiness_for_date`
- Unit tests `TestTrimpHrvBased` (12 tests) and `TestTrimpBanister` (10 tests) in `tests/analytics/test_training_load.py`
- Integration tests `TestLoadReadinessForDateIntegration` (6 tests: resting round-trip, neutral baseline, date not found, orthostatic round-trip, date not found, protocol isolation)

---

### Added — v0.2.0 Documentation — Training load

- `docs/training_load/index.md` — overview and navigation for the training load module
- `docs/training_load/training_sessions.md` — purpose, DB schema, repository API (`create`, `save`, `load`), daily workflow, custom table name
- `docs/training_load/atl_ctl_tsb.md` — full model documentation: TRIMP formulas (HRV-based and Banister), protocol consistency rule, ATL/CTL/TSB EMA formulas with tau constants, TSB zones table, rest-day handling, numerical example, data requirements, references (Banister 1975/1991, Morton 1990, Manzi 2009, Plews 2013)

---

### Added — v0.2.0 Phase 1 — Training sessions (DB layer)

- `database/repository.py` — `_TRAINING_SESSIONS_COLUMNS` column registry for the new `training_sessions` table (`user_id | date | duration_min | sport_type | trimp | notes`, UNIQUE `(user_id, date)`)
- `HRVRepository.create_training_sessions_table()` — idempotent table creation (`CREATE TABLE IF NOT EXISTS`)
- `HRVRepository.save_training_session(user_id, date, duration_min, sport_type, trimp, notes)` — upsert on `(user_id, date)`; `trimp` nullable (computed later when readiness is available)
- `HRVRepository.load_training_sessions(user_id) → list[dict]` — sessions sorted ascending by date; keys: `date`, `duration_min`, `sport_type`, `trimp`, `notes`
- `training_sessions_table_name` parameter added to `HRVRepository.__init__()` and `HRVRepository.from_env()` (default `"hrv_training_sessions"`)
- Integration tests `TestTrainingSessionsIntegration` (4 tests: round-trip, upsert, date ordering, `trimp=None` accepted)

---

### Planned — v0.2.0 Training load (ATL / CTL / TSB)

**DB change:** one new table `training_sessions` — zero modification to the existing 7 tables.

**Protocol consistency rule:** the readiness score feeding TRIMP is drawn from a single primary protocol chosen at setup (`"resting"` or `"orthostatic"`), never mixed. Switching protocol resets the readiness series; the two series are never crossed in baseline or TRIMP computation. When `"orthostatic"` is chosen, the supine-phase HRV (not the ΔHR score) feeds the baseline.

#### Phase 2 — TRIMP calculation
- `analytics/training_load.py`
  - `trimp_hrv_based(duration_min, readiness_score) → float` — `duration × (1 − readiness/100)`. References: Manzi V et al. (2009)
  - `trimp_banister(duration_min, hr_mean, hr_max, hr_rest) → float` — classical Banister 1991 formula for sensors providing effort HR
- `load_readiness_for_date(user_id, date, repo, baseline, protocol: Literal["resting", "orthostatic"]) → float | None` — strict, no cross-protocol fallback

#### Phase 3 — ATL / CTL / TSB
- `compute_atl(sessions_df, tau=7) → pd.Series` — 7-day EMA (acute fatigue). References: Banister EW et al. (1991); Morton RH et al. (1990)
- `compute_ctl(sessions_df, tau=42) → pd.Series` — 42-day EMA (chronic fitness)
- `compute_tsb(ctl, atl) → pd.Series` — TSB = CTL − ATL (form)
- `class TrainingLoad` with `.from_sessions()` and `.to_dataframe()` — `date | trimp | atl | ctl | tsb`
- Rest days contribute TRIMP = 0 — ATL decays faster than CTL naturally

#### Phase 4 — Visualization
- `visualization/training_load_plots.py`
  - `plot_atl_ctl_tsb()` — dual-axis: CTL + ATL top, TSB zones bottom
  - `plot_trimp_history()` — TRIMP bars coloured by sport type
  - `plot_tsb_zones()` — coloured zone bands (overload / optimal / fresh / detraining)

#### Phase 5 — Reporting
- `reporting/training_load_report.py` — `table_training_load_history()`, `summary_training_load()`

#### Phase 6 — Local scripts
- `local/main_training_load.py` — log session → TRIMP → save → refresh chart
- `local/main_training_load_report.py` — training load report over a period

---

### Planned — v0.3.0 Additional sensors

**DB change:** none — new data maps to existing `training_sessions` and `hrv_raw_sessions`.

#### Phase 1 — Garmin
- `sensors_tools/garmin.py` — `parse_garmin_fit()`, `parse_garmin_csv()`, `extract_training_session_garmin()`
- Optional dependency: `fitparse` as `[garmin]` extra in `pyproject.toml`

#### Phase 2 — Apple Health
- `sensors_tools/apple_health.py` — `parse_apple_health_export()`, `extract_hrv_samples()`

#### Phase 3 — HRV4Training
- `sensors_tools/hrv4training.py` — `parse_hrv4training_csv()`, `to_rrseries()`

#### Phase 4 — Sensor documentation
- `docs/sensors/polar.md`, `garmin.md`, `apple_health.md`, `hrv4training.md`

---

### Planned — v0.4.0 Statistical intelligence

**DB change:** optional `anomaly_score FLOAT` column on protocol tables via `ALTER TABLE` — not required.

> GMM / HMM and ARIMA excluded: biological variance of HRV makes short-term prediction unreliable; clustering requires data volumes unlikely before 100+ longitudinal sessions.

#### Phase 1 — Multivariate anomaly detection (Mahalanobis)
- `analytics/anomaly.py` additions — `mahalanobis_distance()`, `is_multivariate_anomaly()`, `anomaly_report()`

#### Phase 2 — Trend analysis
- `analytics/trends.py` — `linear_trend()`, `detect_sustained_decline()`, `trend_report()`

#### Phase 3 — Statistical visualisation
- `visualization/statistical_plots.py` — `plot_anomaly_timeline()`, `plot_trend_overlay()`

---

### Out of scope — parallel repositories

| Project | Depends on | Can start |
|---------|-----------|-----------|
| `cardioanalysis-api` (FastAPI, new repo) | cardiolab ≥ v0.2.0 via PyPI | After v0.2.0 published |
| Web interface (new repo) | `cardioanalysis-api` stable | After API v1 stable |

---

## [0.1.0] - 2026-05-28

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
