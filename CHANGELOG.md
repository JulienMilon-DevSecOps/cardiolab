# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-10-18

> **Changes computed values.** Artefacts are corrected instead of deleted, Lomb-Scargle is the
> default spectral method, every session gets a signal quality index (migration V005), SampEn
> follows the reference convention and the faulty VO2max model is removed. After upgrading:
> `repo.run_migrations()`, then `reprocess_sessions()` — see the migration note below.

### Added — Artefact correction (`cardiolab.signals.artifacts`)

- `RRSeries.correct_artifacts(method="lipponen2019", max_passes=1, min_deviation=0.20)` →
  `(RRSeries, ArtifactReport)`: classifies abnormal beats (Lipponen & Tarvainen 2019 — time-varying
  thresholds on successive differences and on the deviation from an 11-beat median) and **corrects**
  them instead of deleting them: extra beats merged with the next interval, missed beats split in
  two, ectopic and long / short beats replaced by cubic-spline interpolation. Timestamps follow
  added / removed beats; the report is stored in `metadata["artifact_correction"]`.
- **Amplitude gate** (`min_deviation=0.20`): ectopic / long-short beats are only corrected beyond
  20 % of the local median. The published rules alone also flag the sharp physiological swings of a
  strong respiratory arrhythmia (trained athletes at rest); `0` restores them unchanged.
- `ArtifactReport` (counts per type, `corrected_pct`, `is_reliable`, `to_dict()`), exported from
  `cardiolab` and `cardiolab.signals`. More than 5 % corrected → `PhysiologicalWarning`.
- Validation: 100 % of injected artefacts detected, corrected RMSSD within 3 % of the truth,
  0 correction on clean signals; classifications identical to NeuroKit2 (`signal_fixpeaks`,
  method « kubios », one pass) without the gate. On the sample recordings: 0–1 % corrected.
- `docs/features/artefact_correction.md`.

### Added — Spectral analysis

- `frequency_domain(method="lomb")`: Lomb-Scargle periodogram (`scipy.signal.lombscargle`) on the
  beat times, without interpolation, linearly detrended, scaled to a one-sided PSD in ms²/Hz.
  Accepted by `resting_hrv()` and `orthostatic_hrv()`.
- `frequency_domain(..., window_sec=256.0)`: Welch window length in seconds.
- `"VLF_reliable"` key in the `frequency_domain()` result: `False` below 5 minutes
  (`VLF_MIN_DURATION_SEC`).
- `RRSeries.beat_times()`: recorded timestamps when strictly increasing, else cumulated RR.

### Changed — Spectral analysis

- **Default spectral method: `"lomb"`** (was `"welch"`) for `frequency_domain()`, `resting_hrv()`,
  `orthostatic_hrv()` and `HRVFeatures.method`. On 5-minute synthetic recordings with a known
  spectrum, Lomb-Scargle is nearly unbiased with LF/HF ± 15 % across recordings, versus ± 33 % for
  Welch (a single 256 s window, no averaging) and a + 15 to + 57 % bias for AR (VLF leakage).
  Rows stored before 0.4.0 keep `spectral_method = "welch"`. Charts keep Welch.
- **Welch**: 256 s windows (was 256 samples = 64 s), 50 % overlap, linear detrend per window —
  resolution 0.016 → 0.004 Hz (Kubios standard).
- **Single interpolation**: `RRSeries.interpolate(fs=4.0, kind="cubic")` (cubic spline, was linear)
  on `beat_times()`; `frequency_domain._interpolate`, `cardiac_coherence()` and the dashboard PSD
  use it — three separate linear interpolations removed.
- **Computed values change**: HF power rises by 10–80 % on the sample recordings (linear
  interpolation attenuated the HF band), LF/HF changes accordingly. Before / after table in
  `docs/features/frequency_domain.md`. Time-domain, non-linear metrics and scores are unchanged.

### Added — Signal quality (`cardiolab.signals.quality`) — migration V005

- `SignalQuality` (`grade`, `artifact_pct`, `corrected`, `n_beats`, `effective_duration`) and
  `signal_quality(rr, good_max=2.0, acceptable_max=5.0)`, exported from `cardiolab` and
  `cardiolab.signals`. Corrected recordings: `good` < 2 %, `acceptable` < 5 %, `poor` ≥ 5 %
  corrected beats; uncorrected recordings: `poor` as soon as one artefact is detected (one missed
  beat in sample 2026-04-24 nearly doubles RMSSD).
- `quality` attribute on `HRVFeatures`, `OrthostaticResult`, `CoherenceResult`, `VO2maxResult`,
  set by `resting_hrv()`, `orthostatic_hrv()`, `cardiac_coherence()`, `vo2max_from_hrv()`.
  Orthostatic phases are graded on the artefacts within their own time window — a movement
  artefact when standing up does not downgrade the supine phase.
- **Migration `V005__add_signal_quality.sql`**: `quality JSONB` on `hrv_features`,
  `hrv_orthostatic` (one object per phase), `hrv_coherence`, `hrv_vo2max`; idempotent. Existing
  rows keep `NULL` = unknown. Apply with `repo.run_migrations()` **before saving new sessions**.
  HRR and cardiac drift (heart-rate based) are not graded.
- `Baseline(include_poor=False)`: `poor` sessions are left out of every statistic by default;
  `Baseline.sessions` / `Baseline.excluded`; `from_features(..., include_poor=)`. `trend_rmssd()`
  and `detect_rmssd_anomaly()` use the same sessions. Sessions without quality are kept.
- Reports: `quality_grade` column (coloured, translated, `n/a` when unknown) in the resting,
  orthostatic, coherence and VO2max history tables. Charts: red cross on `poor` sessions in the
  resting, readiness, generic score, coherence, VO2max and orthostatic dual-score evolutions.
- `to_dict()` / CSV exports: `quality_grade`, `quality_artifact_pct`, `quality_corrected`,
  `quality_n_beats`, `quality_effective_duration`. Labels `quality_*` (EN / FR).
- `docs/features/signal_quality.md`.

### Added — Reprocessing the history (`cardiolab.database.reprocess`)

- `reprocess_sessions(repo, user_id, protocol=None, since=None, dry_run=True, *, method="lomb",
  auto_clean=True, hr_max=None)` → `ReprocessReport`: recomputes stored sessions from
  `hrv_raw_sessions` with the current pipeline, in chronological order — resting readiness scores
  against the previous sessions, already reprocessed. Dry run by default; writes in the caller's
  transaction; idempotent (a second run reports every session `unchanged`). A session is rewritten
  as soon as any stored field changes (e.g. the SampEn of an orthostatic phase), not only the key
  metrics shown in the report (`SessionChange.changed_fields`). Failed analyses keep
  their stored row; sessions without raw RR are listed in `report.skipped`.
- `analyse_session(protocol, rr, *, method, auto_clean, hr_max)`: the single definition of how a
  session is computed (coherence and VO2max RR series corrected first when `auto_clean`).
- `session_score(protocol, result, baseline=None)` (`cardiolab.analytics.scoring`): the [0–100]
  score stored with a session, one entry point for the six protocols.
- `ReprocessReport` (`summary()`, `to_rows()`, `count()`, `written`, `skipped`) and
  `SessionChange` (`deltas()`), exported from `cardiolab.database`.
- `examples/16_reprocess_history.py`; `docs/database/reprocessing.md`.

### Migration note — from 0.3.x

1. `repo.run_migrations()` — applies V005 (`quality` column) before any new session is saved.
2. `reprocess_sessions(repo, user_id)` — dry run: check the before / after report.
3. `reprocess_sessions(repo, user_id, dry_run=False)` — stored values follow the 0.4.0 pipeline.

Without step 3, the history mixes two pipelines (artefact deletion vs correction, Welch vs
Lomb-Scargle) and baselines, scores and trends are distorted.

### Changed

- **Minimum dependency versions** (`pyproject.toml`): `numpy>=2.0` (`np.trapezoid`), `scipy>=1.13`
  and `matplotlib>=3.9` (numpy 2 binaries); `analysis` extra: `pandas>=2.2.2` (first release built
  for numpy 2 — pandas 2.1 crashes on import with numpy 2) and `jinja2>=3.1.2` (pandas Styler).
  Older versions installed without error, then failed at run time. Unit suite run on exactly
  these minimum versions: all tests pass. `requirements.txt` removed —
  the extras of `pyproject.toml` are the only dependency list (`pip install -e ".[dev,analysis,database,garmin]"`).
- **`auto_clean=True`** (`resting_hrv`, `orthostatic_hrv`) now runs `correct_artifacts()` then
  removes any remaining value outside 300–2000 ms; it only applied `remove_outliers()` before.
  **Computed values change** for recordings analysed with `auto_clean=True`.
- `PhysiologicalWarning` messages suggest `correct_artifacts()`.
- Documentation (features, sensors, README) recommends `correct_artifacts()` instead of
  `remove_outliers()`; example 07 compares deletion and correction. README no longer claims that
  every protocol has `auto_clean` (only resting and orthostatic).

### Fixed — Sample entropy convention

- `sampen()` counted B over the N − m + 1 m-length templates and A over N − m: both now use the
  same N − m starting points (Richman & Moorman 2000). Values are 0.05–1 % lower on the sample
  recordings; a perfectly periodic series now gives SampEn = 0 (it gave log 2). No score uses
  SampEn. Reference oracle of the tests updated accordingly.

### Fixed — VO2max (issue v0.4.0-05)

- **"Esco & Flatt (2014)" RMSSD model removed**: `18.37 + 0.054 × RMSSD` returned 20–24 mL/kg/min
  over the whole normal RMSSD range, so every user without `hr_max` was classed "poor" / "fair"
  (sample recordings of a trained athlete: ≈ 21 mL/kg/min, versus 47–54 with the other models).
  The cited paper studies ultra-short HRV recordings and contains no VO2max equation.
  `vo2max_esco_flatt` is kept for storage compatibility and is always `nan`; removed from the
  reports and charts.
- **Fitness category and score**: Uth when `hr_max` is known, otherwise the ln-RMSSD estimate,
  now documented as **indicative** — no published source could be verified for its equation
  either; resting HRV adds little to heart rate for predicting VO2max (Grant et al. 2013).
- False references removed (Esco & Flatt 2014 "Sensors", Nunan et al. 2010 as source of a VO2max
  equation); Tanaka HRmax formula corrected to `208 − 0.7 × age`.
- Tests: plausible estimates and categories without `hr_max` on the six sample recordings; Uth
  and ln-RMSSD within 25 % on an athlete profile.

### Fixed — Spectral analysis

- **AR PSD**: evaluated on a 256-point grid (0.016 Hz at 4 Hz); AR peaks are narrow and the band
  integration missed most of their power (synthetic 0.1 Hz oscillation of 800 ms² → LF 277 ms²).
  Now a 4 096-point grid (≈ 0.001 Hz) with linear detrend: 792 ms². A flat signal returns a zero
  spectrum instead of numerical noise.
- **Coherence score** (`cardiac_coherence()`, AR-based): underestimated for the same reason — a
  regular 0.1 Hz breathing pattern scored ≈ 47 %, now ≈ 88 %; spontaneous breathing at rest gives
  ≈ 50–60 % (was ≈ 30 %). Scores from earlier versions are not comparable.

### Fixed — Notebooks

- Notebooks 01, 02, 03, 05, 08, 09 use `correct_artifacts()` instead of `remove_outliers()`;
  notebook 01 section 5 presents the correction (it wrongly described `remove_outliers()` as an
  interpolation) and compares raw vs corrected signals.
- Notebook 02 stored the **cleaned** series in `hrv_raw_sessions`: the raw series is now saved
  unchanged (the raw table is the source for reprocessing), the corrected one is used for analysis.
- Notebook 05 (never executed): `vo2max_from_hrv()` was called with a non-existent `hr_rest`
  argument; the VO2max score now uses the Uth model (the RMSSD model is being fixed).
- Notebook 09 (never executed): called functions that do not exist (`compute_time_domain`,
  `compute_frequency_domain`, `RestingProtocol`, `cardiolab.storage.database`) and
  `parse_rr_file(...).remove_outliers()` on a dict. Rewritten with the real API; the Polar demo
  uses a real sample recording; saving to the database is off by default (`SAVE_TO_DB = False`).
- Notebooks 01, 05 and 09 executed end to end, outputs saved.

### Tests

- `tests/database/test_reprocess.py` (19): pipeline, dry run, writes, idempotency, chronological
  scores, `since`, sessions without raw RR, new / failed sessions, VO2max `hr_max`, report;
  PostgreSQL run (dry run → apply → second apply unchanged).
- `tests/signals/test_quality.py` (27): thresholds, uncorrected rule, serialisation, corrected /
  uncorrected series, real sample, protocols (per-phase orthostatic grading), baseline exclusion.
- Integration (PostgreSQL): quality round trips on the four tables, `NULL` = unknown, migration
  V005 re-run on pre-0.4.0 tables. Charts and tables: `test_quality_marker.py`,
  `test_quality_column.py`.
- `tests/features/test_spectral_accuracy.py` (25): default method (bias and dispersion of the
  three methods on 5-minute series with a known spectrum); peaks at 0.10 / 0.25 Hz within ±0.005 Hz and
  band powers within 10 % of theory for welch, ar and lomb; Parseval within 10 %; methods agree;
  `window_sec` resolution; `VLF_reliable`; flat AR spectrum; real sample.
- `tests/signals/test_rr.py`: `beat_times()`, cubic interpolation.
- `tests/signals/test_artifacts.py` (61): acceptance criteria, classification, corrections,
  timestamps, edge cases, report, `RRSeries` wrapper, real sample with a missed beat.
- `auto_clean` tests now compare with `correct_artifacts()` + `remove_outliers()`; new test:
  a missed beat is corrected, not deleted (RMSSD within 5 % of the truth).

---

## [0.3.4] - 2026-10-16

> Version 0.3.3 was prepared (generic repository) but not published: its changes ship in 0.3.4,
> together with the sports reference list.

### Added — Sports reference list (`cardiolab.sports`)

- `Sport` (code, English / French label, colour, family), `SPORTS`, `FAMILIES`,
  `get_sport()`, `list_sports(family=None)` and `normalize_sport(value, sub_sport=None)`,
  also exported from the package root. 17 sports in 4 families (endurance, strength & fitness,
  team & racket sports, other).
- `normalize_sport()` maps codes, English / French labels, common synonyms (« Course à pied »,
  `run`, `VTT`, `musculation`…) and Garmin FIT `sport` / `sub_sport` values to a code
  (`running` + `trail` → `trail`); unknown or empty → `"other"`. `sport_type` stays a free
  `TEXT` column — no schema change.
- `labels.py`: keys `sport_<code>` and `sport_family_<code>` in `LABELS_EN` / `LABELS_FR`.
- `validate_sport(value)`: strict variant — known names give their code, `None` / empty gives
  `None`, anything else raises `ValueError` with the closest sport suggested
  (« runing » → « Did you mean 'running'? »).
- `docs/training_load/sports.md`.

### Changed

- **`HRVRepository.save_training_session()` validates `sport_type`** and stores the reference
  code (« Course à pied » → `running`); an unknown sport raises `ValueError` before anything is
  written, so typos can no longer break charts and filters. `find_training_sessions()` accepts
  the same names for its sport filter. Sessions saved before 0.3.4 keep their text; charts
  still colour them through `normalize_sport()`.

- `extract_training_session_garmin()` also returns `"sport"` (normalised code) and
  `"sport_raw"` (FIT value), read from the FIT `session` then `sport` messages.
- `plot_trimp_history()`: colours come from the reference list (the six previous colours are
  unchanged); a stored name that is not a code (« Course à pied ») gets its sport colour, an
  unknown sport the `other` colour, a session without sport keeps the default colour;
  `sport_colors` still overrides. With `labels=LABELS_FR` the legend shows French sport names.
- Package docstring lists the `sports` and `datasets` submodules.

### Tests

- `tests/test_sports.py` (64): reference list, normalisation, strict validation, labels, chart
  colours and legend.
- `tests/database/test_repository.py`: sport validated and stored as a code on save, filter
  converted (4); the save/load round trip now expects the code.
- `tests/sensors_tools/test_garmin.py`: sport read from FIT files (10), keys of
  `extract_training_session_garmin()` updated.

No change to the public API nor to the stored data — internal refactoring of the database
layer.

### Changed — Generic `HRVRepository` (`database/repository.py`)

- The six protocol tables keyed by `UNIQUE(user_id, date)` (resting, orthostatic, coherence,
  HRR, drift, VO2max) are now described by `_ProtocolTable` specifications — column registry +
  row → result function — and handled by three generic methods (`_create`, `_upsert`,
  `_select`) built on three query builders. The 18 public `create_* / save_* / load_*`
  methods are one-line wrappers with unchanged signatures and docstrings.
- Metric columns are written and read **by name** (they match the result dataclass
  attributes) instead of hand-maintained positional tuples; `_build_ortho_row` gathers its
  73 values by column name, so a row can no longer drift out of sync with the schema.
  The 19 HRV metrics are defined once (`_HRV_METRICS`) for resting and the three orthostatic
  phases.
- Code size: 1 448 → 993 lines of code (−31 %, docstrings kept); `repository.py`
  2 590 → ~2 180 lines. Raw sessions, training sessions and user profiles (different keys)
  are unchanged.
- Verified: the SQL (statements and parameters) emitted by the 21 public table calls is
  identical before / after on PostgreSQL 17, and rows written by 0.3.2 — including NULL
  columns — are read back into identical objects.

### Documentation

- README: TSB zone table aligned with the code (5 zones: > +25 fresh / detraining, +5…+25
  optimal, −10…+5 neutral, −30…−10 accumulated fatigue, < −30 overload); it still showed
  the 4 zones of an early draft with other thresholds.
- ROADMAP: new v0.3.4 « Sports » (reference list of sports, sport read from `.fit` files);
  v0.4.0 bug — VO2max RMSSD model (Esco & Flatt) returns ~21 mL/kg/min where the other
  models give ~50; v0.5.0 session-RPE load (migration V006) and age/sex-adjusted VO2max
  categories; later migrations renumbered (V007 v0.6.0, V008 v0.8.0).
- `docs/database/migration_guide.md`: new section *Adding a protocol table*; bundled
  migrations list completed with `V004__add_user_profiles.sql`.

---

## [0.3.2] - 2026-10-13

### Added — Sample datasets (`cardiolab.datasets`)

- `list_samples(protocol=None)` and `load_sample(protocol="resting", index=0)`: seven real
  Polar H10 recordings of the author (6 resting 2026-04-24 → 04-30, 1 orthostatic
  2026-05-17), returned as raw `RRSeries` with the manifest entry in `metadata`. Usable right
  after `pip install cardiolab`, read through `importlib.resources` and `parse_rr_file()`.
- Stored as raw Polar `.txt` files (one RR interval in ms per line) + `samples.json` manifest
  (date, time, beats, duration) + `README.md` (provenance, voluntary publication, licence
  CC BY 4.0 for the data). Converted from the former JSON files with no value changed.
- `pyproject.toml`: coverage now measures `cardiolab/datasets/` (only `datasets/raw/` — your
  own files, ignored by git and never packaged — stays excluded).

### Fixed — Readiness used for the HRV TRIMP

- `load_readiness_for_date()` now scores the session with the same function as the readiness
  stored and displayed in reports: `readiness_score_multi()` for resting,
  `orthostatic_readiness_score()` (supine phase) for orthostatic. It previously used the legacy
  `readiness_score_oura()` (RMSSD 70 % + HR 30 %, no DFA α1 nor trend), so the TRIMP was built
  from a different score than the one the athlete sees (e.g. 63.0 vs 54.5 on the same session).
  **TRIMP values saved with the `hrv` method before 0.3.2 differ**; re-saving the session
  (upsert) recomputes them.
- Notebooks `02_import_pipeline` and `08_full_pipeline`, and the `reading_charts.md` example,
  scored sessions with `readiness_score_oura()` too — now `readiness_score_multi()`, consistent
  with the local pipeline. Re-run the notebooks to refresh their saved outputs.

### Changed

- `cardiolab.__version__` is read from the installed distribution metadata
  (`importlib.metadata`) — `pyproject.toml` is the single source of truth. It was hard-coded and
  still reported `0.3.0` in the published 0.3.1 package. With an editable install, run
  `pip install -e . --no-deps` after a version bump (enforced by `tests/test_version.py`).
- `apen()` / `sampen()`: template matching uses a k-d tree (`scipy.spatial.cKDTree`, Chebyshev
  metric) instead of O(N²) Python loops. **Results are identical** (checked against the former
  implementation to 1e-12, including integer-ms series with ties at `r`); ×10 faster at
  300 beats, ×30 at 3 000 beats (ApEn 1.4 s → 43 ms).
- CI: the centralised pipeline is now included as a CI/CD component
  (`python-package@0.11.1`) configured through `inputs:`; Ruff security rules (SAST) are
  blocking.

### Removed

- `cardiolab/scripts/import_rr.py` (`import_all()`): it had no entry point, so the documented
  `python cardiolab/scripts/import_rr.py` did nothing, and it only converted raw files to an
  intermediate JSON format. Raw files are now read directly with `parse_rr_file()`, as the
  local pipeline already did.
- `cardiolab/datasets/{resting,orthostatic}/*.json` (replaced by the `.txt` samples above) and
  `cardiolab/datasets/exports/` (derived CSV / JSON outputs, out of date and regenerable).
  Both were shipped in the wheel without any way to load them once installed.

### Changed — Examples and documentation

- Examples 02, 09, 10 and 11 read your raw RR files (`.txt` / `.csv` / `.rr`) from
  `cardiolab/datasets/raw/resting/` with `parse_rr_file()` instead of the intermediate JSON
  files; the session date is the file name without extension. When that folder is empty,
  09 / 10 / 11 now use the shipped sample recordings instead of synthetic data. Example 10 scores sessions with
  `readiness_score_multi()`. Examples 04 / 05 notes updated; `example/` → `examples/` paths.
- `docs/sensors/polar.md`: the import snippet called a non-existent `compute_time_domain()` and
  treated the `dict` returned by `parse_rr_file()` as an `RRSeries` — fixed and verified.
- README project structure brought up to date (no `preprocessing/` nor `scripts/`, sensors,
  9 tables, notebooks, test count).

### Tests

- `tests/conftest.py`: the local Supabase stack is never started when `CI` is set — in the
  pipeline the database is the `pytest-postgres` service (same rule as `cardioanalysis-api`).
  Locally, integration tests still start and stop it automatically.
- New: `TestLoadReadinessForDateScorer` (4, no database), `TestEntropyKDTreeEquivalence` (52),
  entropy benchmarks on 3 000 beats (2, `slow`), `tests/test_version.py` (2),
  `tests/datasets/test_datasets.py` (18 — manifest, loading, every file packaged, samples
  run through the resting and orthostatic protocols).

---

## [0.3.1] - 2026-10-12

No functional change to the `cardiolab` package — CI, packaging and test tooling only.

### Changed — CI (centralised pipeline `0.3.0` → `0.9.0`)

- `.gitlab-ci.yml` now includes `pipeline-python-centralisee` at `ref: 0.9.0`:
  - blocking `version-check` on release tags (`V-x.y.z` ↔ `[project].version`);
  - `twine check --strict` during `build-package`;
  - pre-release tags `V-x.y.z-rcN` (`V-0.3.1-rc1` ↔ `version = "0.3.1rc1"`) are
    published to **TestPyPI** only; `V-x.y.z` tags publish to PyPI + GitLab Package Registry;
  - PyPI / TestPyPI publication through **Trusted Publishing** (`PYPI_AUTH_METHOD: "trusted"`),
    no API token stored in GitLab;
  - non-blocking `dependency-scan` (pip-audit).
- `PYTHON_VERSION: "3.12"` (image `python:3.12-slim`) instead of `3.12.0`.
- `PYTHON_PROJECT_EXTRAS: "dev,analysis,database,garmin"` — cardiolab has no `test` extra
  (the pipeline default).
- `PYTEST_COV_SOURCE: "cardiolab"` — coverage measured on the package only (the pipeline
  default `.` also counted `tests/`).
- **Integration tests now run in CI**: `PYTEST_DATABASE: "postgres"` starts a throwaway
  PostgreSQL 17 service; `DB_*_TEST` variables point to it. The 55 `@pytest.mark.integration`
  tests were previously always skipped in CI.

### Fixed — Tests and packaging

- Coverage under-reported (83.6 % → 91.7 % on unit tests, no test added): the
  `filterwarnings` entries referenced `cardiolab.signals.rr.PhysiologicalWarning` by dotted
  path, which made pytest import `cardiolab` before `pytest-cov` started — every module-level
  line (imports, `def`, `class`) was counted as missed. Warnings are now filtered by message.
- sdist: `/example` → `/examples` in `[tool.hatch.build.targets.sdist]` (the folder was
  renamed in v0.2.4, so examples were silently missing from the source distribution).

### Removed

- `pystest.ini` — misspelled, never read by pytest; the configuration lives in
  `pyproject.toml`.
- Generated files untracked and ignored: `coverage.json`, `output/*.png`
  (also ignored: `coverage.xml`, `pytest-report.xml`, `.benchmarks/`).

---

## [0.3.0] - 2026-06-12

### Added — Sensor integrations (issues #42, #43, #44)

#### `sensors_tools/hrv4training.py` (issue #44)

- `parse_hrv4training_csv(filepath)` — parses HRV4Training CSV exports (semicolon-separated
  RR intervals). Returns `list[dict]` with keys `date`, `rmssd`, `rr_intervals`.
  Case-insensitive column detection via `_find_col()`. Filters zero/negative intervals.
- `to_rrseries(record)` — converts a parsed HRV4Training record to `RRSeries`.

#### `sensors_tools/apple_health.py` (issue #43)

- `parse_apple_health_export(filepath)` — parses Apple Health `export.xml` for
  `HKQuantityTypeIdentifierHeartRateVariabilitySDNN` and
  `HKQuantityTypeIdentifierRestingHeartRate` records. Returns `list[dict]` with
  `date`, `sdnn`, `rmssd` (always `None` — Apple Health does not export raw RR), `source`.
  Raises `ValueError` on malformed XML or wrong root element.
- `extract_hrv_samples(filepath)` — groups by date, averages SDNN, returns
  `list[dict]` sorted by date.

> **Note:** Apple Health XML exports contain only SDNN (pre-computed by watchOS).
> Raw RR intervals are not available; `rmssd` is always `None`.

#### `sensors_tools/garmin.py` (issue #42)

- `parse_garmin_fit(filepath)` — extracts RR intervals from Garmin FIT `hrv` messages.
  Converts seconds → milliseconds. Requires optional `fitparse` dependency
  (`pip install cardiolab[garmin]`).
- `parse_garmin_csv(filepath)` — parses beat-to-beat CSV exports (e.g. from Kubios HRV).
  Auto-detects the RR column by scanning headers for `"rr"` (case-insensitive).
- `extract_training_session_garmin(filepath)` — reads `record` messages from a FIT file
  to compute `duration_min`, `hr_mean`, and `hr_max`.

#### `pyproject.toml`

- New `[garmin]` optional extra: `fitparse>=1.2`.

#### `sensors_tools/__init__.py`

- All new functions exported: `parse_hrv4training_csv`, `to_rrseries`,
  `parse_apple_health_export`, `extract_hrv_samples`,
  `parse_garmin_fit`, `parse_garmin_csv`, `extract_training_session_garmin`.

### Added — Sensor documentation

- `cardiolab/docs/sensors/hrv4training.md` — HRV4Training measurement protocol and import guide.
- `cardiolab/docs/sensors/apple_health.md` — Apple Health export workflow and lossy-export warning.
- `cardiolab/docs/sensors/garmin.md` — Garmin FIT/CSV import guide and measurement protocol.
- `cardiolab/docs/sensors/polar.md` — Polar H10 measurement protocol and import guide (EN + FR).
- `cardiolab/docs/sensors/README.md` — sensor compatibility table and quick-start snippets.

### Added — Notebook

- `notebooks/09_sensors.ipynb` — end-to-end workflow: sensor import → RR cleaning →
  HRV feature extraction → readiness scoring → optional DB save. Covers all four
  supported sources with embedded synthetic demo data.

### Added — Dataset structure

- `cardiolab/datasets/raw/polar/` — raw Polar H10 `.txt` files.
- `cardiolab/datasets/raw/hrv4training/` — HRV4Training CSV exports.
- `cardiolab/datasets/raw/apple_health/` — Apple Health `export.xml`.
- `cardiolab/datasets/raw/garmin/` — Garmin `.fit` files and beat-to-beat CSV.

### Changed

- `visualization/plot.py` — removed (dead backward-compatibility shim; zero usages).
- `docs/` (project root) — removed; content moved to `cardiolab/docs/` inside the package.
  `docs/database/migration_guide.md` → `cardiolab/docs/database/migration_guide.md`.
- `pyproject.toml` sdist include: removed `/docs` (no longer at project root).
- `notebooks/README.md` — updated dataset structure, added notebook 09, updated sensor
  integration section.

### Tests

- `tests/sensors_tools/test_hrv4training.py` — 22 new tests (100 % pass).
- `tests/sensors_tools/test_apple_health.py` — 23 new tests.
- `tests/sensors_tools/test_garmin.py` — 24 new tests; FIT parsing uses `unittest.mock`
  (no binary FIT fixtures required).
- Additional coverage for `signals/rr.py` and `signals/ecg.py` (new edge-case tests).

---

## [0.2.4] - 2026-06-10

### Changed — Licence

- Licence changed from **MIT** to **GNU Affero General Public License v3 or later
  (AGPLv3+)**. The AGPLv3 closes the SaaS loophole present in GPLv3: when a modified
  version of cardiolab is used to power a network service, the operator must provide the
  corresponding source to users of that service. The `LICENCE` file (full AGPLv3 text) is
  included in the source distribution.

### Added — Dual orthostatic scoring (issue #16)

The orthostatic protocol now produces two complementary, independent scores for each
session:

- **`readiness_score`** (relative, baseline-dependent) — applies
  `readiness_score_multi()` to the supine-phase HRV features, compared against the
  user's personal supine baseline built from all previous sessions. Returns 50 (neutral)
  on the first session. Score interpretation: `< 35` high fatigue → `35–45` slight
  fatigue → `45–55` normal → `55–65` good recovery → `≥ 65` excellent.
- **`autonomic_score`** (absolute, no baseline required) — unchanged from v0.1.0:
  80 % ΔHR component + 20 % HF vagal-withdrawal component. Now renamed from the
  ambiguous `score` field to `autonomic_score` in all reporting outputs.

#### `analytics/scoring.py`

- `orthostatic_readiness_score(supine, baseline) → float` — new public function.
  Wraps `readiness_score_multi()` for the supine phase. Returns 50.0 when baseline is
  empty (first session).
- `orthostatic_score()` — unchanged; now explicitly documented as the *autonomic
  response* score (absolute, ΔHR + HF).
- Both functions exported in `analytics/__init__.py` and `__all__`.

#### `reporting/orthostatic.py`

- `table_orthostatic_comparison()` — gains an optional `readiness_scores` parameter
  (`list[float]`). When provided, adds `readiness_score`, `readiness_label`,
  `autonomic_score`, and `autonomic_label` columns to the `"Autonomic response"` MultiIndex
  group. Colour-coded cells: green for high readiness/autonomic score, labelled zones
  translated via `labels` dict.
- `table_orthostatic_history()` — gains an optional `readiness_scores` parameter.
  Adds `readiness_score` / `readiness_label` alongside the renamed `autonomic_score` /
  `autonomic_label` columns. Both scores use a green gradient; label cells use the
  appropriate colour palette.
- New internal helpers `_readiness_label()` and `_autonomic_label()` map raw scores to
  internal English keys translated at display time via the `labels` dict.

#### `reporting/_core.py`

- `_READINESS_LABEL_COLORS` — colour palette for the 5 readiness zones
  (red / orange / yellow / light-green / green, matching the visualization module).
- `_AUTONOMIC_LABEL_COLORS` — colour palette for the 5 autonomic zones.

#### `visualization/orthostatic_plots.py`

- `plot_orthostatic_dual_score_evolution(results, readiness_scores, ...)` — new
  function, 2-panel figure:
  - **Panel 1 — Readiness score**: 5 coloured zone bands (< 35 red, 35–45 orange,
    45–55 yellow, 55–65 light-green, ≥ 65 green); neutral reference line at 50;
    blue dashed rolling mean ± 5-point band (shown when n ≥ 3 sessions); coloured
    dots per zone; right-margin zone labels.
  - **Panel 2 — Autonomic score**: 5 zone bands (< 30 red, 30–50 orange, 50–70
    yellow, 70–85 light-green, ≥ 85 green); coloured dots (red < 30, orange < 70,
    green ≥ 70); right-margin zone labels.
  - Rolling window constant `_ROLLING_WIN = 3`.
- `plot_orthostatic_dual_score_evolution` exported in `visualization/__init__.py`
  and `__all__`.

#### `labels.py`

- Added `"ortho_dual_score_title"` key in both `LABELS_EN` and `LABELS_FR`.
- Added 5 readiness label keys (`readiness_label_high_fatigue` … `readiness_label_excellent`)
  and 5 autonomic label keys (`autonomic_label_impaired` … `autonomic_label_excellent`)
  in both language dicts.

#### Tests

- `tests/analytics/test_scoring.py` — new `TestOrthostaticReadinessScore` class
  (empty baseline → 50, non-empty baseline, delegates to `readiness_score_multi`).
- `tests/visualization/test_orthostatic_plots.py` — 36 tests for the full
  `orthostatic_plots.py` module, including `TestPlotOrthostaticDualScoreEvolution`
  (18 tests): all 5 readiness zones, all 3 autonomic dot colours, rolling mean
  activation, error paths.

---

### Added — SQL migration framework (issue #11)

- `cardiolab/database/migrations/` — versioned, idempotent SQL migration files:
  - `V001__initial_schema.sql` — all 7 base tables
  - `V002__add_apen_sampen_ortho_metrics.sql` — `apen`, `sampen`, `lf_hr_pct_change`,
    `delta_rmssd` columns
  - `V003__add_training_sessions.sql` — `hrv_training_sessions` table
  - `V004__add_user_profiles.sql` — `hrv_user_profiles` table
- `schema_migrations` tracking table (applied automatically by `main_init_db.py`).
  Migrations are idempotent: re-running `main_init_db.py` on an up-to-date DB is a no-op.

---

### Added — User profiles table (issue #9)

- `hrv_user_profiles` table — stores the primary HRV protocol per user
  (`"resting"` or `"orthostatic"`), plus optional demographic fields used for
  TRIMP computation (age, sex, HRmax, HRrest).
- `HRVRepository.create_user_profiles_table()`, `save_user_profile()`,
  `load_user_profile(user_id) → dict | None` — idempotent CRUD.
- `local/main_init_db.py` updated to create the table on first run.

---

### Added — Public API audit (issue #10)

- All previously private helpers in `analytics/anomaly.py` that were being accessed via
  `_` names from outside the module are now either promoted to public symbols or
  properly encapsulated. The public interface is stable across `analytics/`, `reporting/`,
  and `visualization/` packages.
- `cardiolab/__init__.py` — top-level imports audited; all public-API functions and
  classes are directly importable from `cardiolab` without navigating subpackages.

---

### Added — Restructured `examples/` (issue #12)

- `examples/` reorganised from a flat list to a 15-file numbered sequence covering the
  full pipeline:
  - `01_setup_database.py` → `07_auto_clean.py` — database setup, ingestion, analysis,
    protocols
  - `08_to_dict_export.py`, `09_rr_signal_plots.py` → `12_other_protocols.py` — I/O
    and visualisation
  - `13_training_load.py`, `14_user_profiles.py`, `15_full_daily_pipeline.py` — advanced
    workflows
- `examples/README.md` — index with one-line description per file.
- `examples/figures/` — pre-rendered PNG outputs for each visualisation example.

---

### Performance — `_ema()` vectorisation and `load_readiness_for_date` O(1) (issue #13)

#### `analytics/training_load.py`

- `_ema(trimp, tau)` — rewritten using `scipy.signal.lfilter([k], [1.0, -(1-k)], trimp)`.
  Mathematically identical to the original Python loop (1st-order IIR filter, initial
  condition = 0); eliminates the explicit `for` loop, vectorising computation over NumPy
  arrays.
- `load_readiness_for_date(user_id, date, repo, baseline, protocol)` — now O(1): delegates
  to `repo.load_features_for_date()` (resting) or `repo.load_orthostatic_for_date()`
  (orthostatic) instead of loading all rows and scanning in Python.

#### `database/repository.py`

- `HRVRepository.load_features_for_date(user_id, date) → HRVFeatures | None` — targeted
  `WHERE date::date = %s` query; returns the session for the specified calendar day, or `None`.
- `HRVRepository.load_orthostatic_for_date(user_id, date) → OrthostaticRecord | None` —
  same pattern for the orthostatic table.

#### Tests

- `tests/analytics/test_training_load.py` — new `TestEmaVectorised` class (8 tests):
  matches the reference Python loop for constant τ = 7 and τ = 42, variable TRIMP, sparse
  TRIMP; zero input → zero output; initial condition = 0; returns `ndarray`; length
  preserved.

---

### Fixed — `plot_trimp_history` multi-activity stacked bars

`plot_trimp_history()` previously assigned one sport colour per date, silently overwriting
earlier activities when a day contained multiple sessions. The last activity's sport type
was shown and all TRIMPs were summed into a single unsegmented bar — the individual
activities were invisible.

#### `visualization/training_load_plots.py`

- When `sessions` is provided, activities are now grouped by calendar date using
  `collections.defaultdict`. Days with a single active session render as before. Days with
  two or more active sessions render **stacked bars**: each segment represents one activity,
  height = individual TRIMP, colour = its sport type, with a thin white edge between
  segments.
- The legend now lists every unique sport type present across all sessions (not only the last
  one per day).

#### Tests

- `tests/visualization/test_training_load_plots.py` — new `TestPlotTrimpHistoryMultiActivity`
  class (7 tests): returns a Figure; 5 patches for a 5-day fixture with 2 activities on day 0;
  stacked bars have correct `y` origins (0.0 and 30.0); total height = 70.0 (sum of both
  activities); legend lists both sport types; single-activity days unaffected; rest day
  produces no bar.

---

### Improved — Test coverage and quality

- Overall coverage raised from **83.6 % → 87.6 %** (`fail_under = 80`). **1 458 tests**, 0 failures.
- `tests/visualization/test_orthostatic_plots.py` — new file, 36 tests;
  brings `orthostatic_plots.py` from 13.2 % to 100 % coverage.
- Deterministic seeds — three uses of unseeded `np.random` replaced with
  `np.random.default_rng(42)`:  `test_trends.py`, `test_baseline.py`,
  `test_frequency_domain.py`.
- Zone-boundary tests — `tests/analytics/test_scoring.py`:
  `TestOrthostaticScoreZoneBoundaries` (11 tests), `TestDriftScoreZoneBoundaries` (3),
  `TestCoherenceScore100ZoneBoundaries` (3).
- Dual-score reporting tests — `tests/reporting/test_orthostatic.py`:
  `TestDualScoreColumnsComparison` (7), `TestDualScoreColumnsHistory` (7).

---

## [0.2.3] - 2026-06-03

### Fixed — Packaging

- Fixed PyPI sdist size (was 113 MB, exceeding the 100 MB limit) by switching from an
  exclusion list to an explicit inclusion list in `[tool.hatch.build.targets.sdist]`.
  The sdist is now ~316 KB. No functional changes.

*Versions 0.2.1 and 0.2.2 were intermediate attempts to resolve the same packaging issue
and contain no functional changes relative to 0.2.0.*

---

## [0.2.2] - 2026-06-03

### Fixed — Packaging

- Partial fix for sdist size: added `[tool.hatch.build.targets.sdist]` exclusion list.
  Reduced from 113 MB to 109 MB — still above the PyPI 100 MB limit. Superseded by 0.2.3.

---

## [0.2.1] - 2026-06-03

### Fixed — Packaging

- First attempt to fix sdist size by bumping the version after identifying the root cause
  (no sdist configuration in `pyproject.toml`). Superseded by 0.2.3.

---

## [0.2.0] - 2026-06-03

### Fixed — Post-review bugfixes (2026-06-03)

- `signals/rr.py` — `remove_outliers(method="zscore")` no longer crashes when all
  intervals are identical (std = 0). Previously, dividing by zero produced NaN z-scores,
  the filter mask became all-False, and the resulting empty array raised
  `ValueError: RRSeries must contain at least 2 intervals`. The series is now returned
  unchanged when std = 0.
- `signals/rr.py` — `segment()` now propagates timestamps to each produced segment.
  Previously, segments were always created without timestamps even when the source
  `RRSeries` had an explicit timestamp array.
- `visualization/rr_plots.py` — `plot_rr_tachogram()` no longer emits
  `UserWarning: No artists with labels found` when `show_mean=False` and no coloured band
  is displayed. `ax.legend()` is now called only when at least one labelled artist exists.
- `tests/conftest.py` — `baseline_30days` fixture generated invalid date strings
  (`"2026-04-31"` through `"2026-04-42"`). Dates are now computed with `timedelta` from a
  fixed start date.

### Added — v0.2.0 Pre-release improvements

#### Bilingual label system — `cardiolab/labels.py`

A new shared module provides human-readable display strings for all metrics, clinical
zones, and protocol names, usable by both reporting and visualization layers:

- `LABELS_EN` — English labels (default in the package).
- `LABELS_FR` — French labels, intended for `local/` scripts.
- `lbl(labels, key, default)` — lookup helper with safe fallback.
- **Metrics covered:** all HRV time-domain, frequency-domain, non-linear, orthostatic
  response, coherence, HRR, drift, VO2max, training load, and protocol name keys.
- **Clinical zones covered:** readiness score bands, coherence zones, HRR zones, drift
  zones, VO2max zones, TSB zones — all translatable via `zone_*` keys.
- All 8 reporting functions (`table_*_history`) and all visualization functions accept a
  `labels: dict[str, str] | None = None` parameter; session-axis labels are now passed via
  the distinct `session_labels` parameter.
- `apply_labels()` in `reporting/_core.py` uses `Styler.format_index()` to rename column
  headers for display without touching the underlying data or breaking gradient styles.

#### Orthostatic protocol — enriched metrics and new visualisation

- `OrthostaticResult` gains two new computed fields:
  - `lf_hr_pct_change` — LF/FC relative change supine → standing (%), positive = normal
    sympathetic activation; < 10 % signals blunted response (chronic fatigue marker).
  - `delta_rmssd` — absolute RMSSD drop supine → standing (ms), complementary to
    `hf_hr_pct_change`; useful for day-to-day within-individual tracking.
- `table_orthostatic_comparison` completely redesigned:
  - Three-phase MultiIndex layout: **Supine | Transition | Standing | Autonomic response**
  - Each phase shows the same HRV indicators as a resting session table.
  - Phase group names are translatable via `_phase_*` keys in the labels dict.
  - `cols` parameter to select or exclude specific flat column names.
- `table_orthostatic_history` enriched with `delta_rmssd`, `hf_hr_pct_change`,
  `lf_hr_pct_change`; filterable via `cols`.
- `visualization/orthostatic_plots.py` — new module with:
  - `plot_orthostatic_phases_evolution(results, ...)` — 4-panel plot showing RMSSD/HR per
    phase across sessions, plus autonomic response magnitudes (ΔHR, ΔRMSSD) and balance
    indicators (HF/HR%, LF/HR%) as a function of time.
- DB: `hrv_orthostatic` gains two columns (`lf_hr_pct_change`, `delta_rmssd`); existing
  tables must be recreated (`DROP TABLE hrv_orthostatic; python local/main_init_db.py`).
- `load_orthostatic()` refactored from positional column offsets to named dict access.
- Documentation on all three new orthostatic response metrics:
  - `hf_hr_pct_change` (> 40 % = healthy vagal withdrawal),
  - `lf_hr_pct_change` (> 30 % = healthy sympathetic activation),
  - `delta_rmssd` (> 15 ms = good vagal reactivity).

#### File-based report/visualisation scripts

- `local/main_report_files.py` — read `.txt` files → HTML report without database:
  - `--protocol` is now **optional** (default: all protocols with available files).
  - Without `--protocol`, produces a single multi-section HTML report
    (`<user>_rapport_complet_<ts>.html`).
  - All tables rendered with `LABELS_FR`.
- `local/main_visualize_files.py` — read `.txt` files → PNG plots without database:
  - Corrected 4 silent bugs: missing `scores` arg for resting, missing `rr_list` for HRR
    comparison, wrong argument type for VO2max comparison, missing `rolling_rmssd` for
    rolling evolution.
  - `_process_files()` now also returns `rr_list` (RRSeries per session).
  - All plots rendered with `LABELS_FR`.

#### `training_load_report.py` — labels support

- `table_training_load_history()` accepts `labels` dict; ATL/CTL/TSB column headers are
  now translatable.

#### Robustness — test fixtures

- `_test_table_drop()` added to **all** integration test fixtures — forces DROP+recreate
  before each test class to prevent schema drift failures when column structures change.

---

### Changed — v0.2.0 Multi-activity schema refactor (training_sessions)

**Why this change?**

The initial schema (Phase 1) used a `UNIQUE(user_id, date)` constraint with an upsert on
`(user_id, date)`. This prevented recording multiple activities on the same day: if a user
went for a morning run and an evening strength session, the second insert would silently
overwrite the first — irreversible data loss.

The correct model is **one row per activity, not one row per day**. The constraint has
therefore been dropped in favour of an `activity_id TEXT PRIMARY KEY` (UUID generated in
Python via `uuid.uuid4()`, to avoid a dependency on the PostgreSQL `uuid-ossp` extension).

**Where does aggregation responsibility sit?**

Daily aggregation is handled by the analytics layer, not the database. The DB stores raw
facts (each activity as it happened); `TrainingLoad.from_sessions()` sums TRIMP values per
date before building the dense series. This is mathematically equivalent:
`(d₁ + d₂) × (1 − r/100) = d₁ × (1 − r/100) + d₂ × (1 − r/100)`. Separating the
concerns keeps the DB schema open to future uses (web interface, API) without touching the
analytics logic.

**Compatibility** — Tables created with the old schema (`UNIQUE(user_id, date)`) must be
recreated: `python local/main_init_db.py --reset` (⚠️ all existing data will be lost) or
`DROP TABLE hrv_training_sessions;` followed by `python local/main_init_db.py`.

#### DB — `database/repository.py`

- `hrv_training_sessions` schema revised:
  - `activity_id TEXT PRIMARY KEY` — UUID primary key (one row = one activity)
  - `UNIQUE(user_id, date)` removed — multiple activities on the same day are now allowed
- `save_training_session(...) → str` — pure INSERT (no more upsert), returns the generated `activity_id`
- `delete_training_session(activity_id: str) → bool` — DELETE by `activity_id`, returns `True` if deleted
- `find_training_sessions(user_id, date, sport_type=None) → list[dict]` — lookup primitive for the interactive deletion workflow
- `load_training_sessions()` — each returned dict now includes `activity_id`

#### Analytics — `analytics/training_load.py`

- `TrainingLoad.from_sessions()` — aggregates TRIMP by date (sum) instead of overwriting; activities with `trimp=None` contribute 0 to the sum

#### Local scripts

- `local/main_training_load.py` — interactive `--delete` mode added:
  - Looks up activities by `(user, date, optional sport)` via `find_training_sessions()`
  - 0 matches → error message
  - 1 match → activity details displayed + `y/N` confirmation
  - N > 1 matches → numbered table (`activity_id`, sport, duration, TRIMP) + number prompt (same interaction pattern planned for the future web interface)
- `local/main_init_db.py` — bug fix: `hrv_training_sessions` was missing from `_TABLES`; `python local/main_init_db.py` was never creating the training sessions table

#### Tests

- `tests/database/test_repository.py` — 7 new tests: two activities on the same day (allowed), `save` returns a UUID `activity_id`, `delete_activity`, `delete_only_one_of_two`, `delete_nonexistent_returns_false`, `find_by_date`, `find_by_date_and_sport`
- `tests/analytics/test_training_load.py` — 6 new multi-activity tests: single date entry for two activities, TRIMP summed (30+20=50), higher ATL with two activities, `trimp=None` contributes 0, other dates not shifted, gap between two multi-activity days

---

### Added — v0.2.0 Phase 6 — Local scripts for Training load

- `local/main_training_load.py` — log a session → TRIMP → save → ATL/CTL/TSB plots:
  - Three TRIMP methods: `hrv` (readiness from the day's HRV measurement via `load_readiness_for_date`), `banister` (HR-reserve formula, requires `--hr-mean/max/rest`), `manual` (readiness entered via `--readiness`)
  - Readiness protocol selectable from the command line (`--protocol resting|orthostatic`)
  - `--readiness` fallback when no HRV measurement exists for the target date
  - `--dry-run` — simulation with no database writes
  - `--save-plot` — saves the 3 ATL/CTL/TSB plots as PNG files under `local/reports/`
- `local/main_training_load_report.py` — HTML ATL/CTL/TSB report over a period:
  - Period filter: `--from / --to` or `--last N` days
  - KPI summary (ATL, CTL, TSB, zone, CTL trend) + history table + 3 base64-encoded plots
  - `--open` — opens the report in the browser after generation
  - Output: `local/reports/<user>_training_load_<ts>.html`

---

### Added — v0.2.0 Phase 5 — Reporting Training load

- `reporting/training_load_report.py` — new module:
  - `table_training_load_history(training_load, caption_text) → pd.Styler` — dense daily ATL/CTL/TSB history table (one row per day); columns: `date | trimp | atl | ctl | tsb | tsb_zone`; CTL gradient green (high fitness = good); ATL gradient red (high fatigue = bad); `tsb_zone` cell coloured by physiological band using `_TSB_ZONE_COLORS`. Raises `ValueError` on empty input.
  - `summary_training_load(training_load) → dict` — scalar summary of the latest state; keys: `atl`, `ctl`, `tsb` (rounded to 2 d.p.), `tsb_zone` (string label), `ctl_trend` (`"increasing"` / `"stable"` / `"decreasing"` from 7-day CTL delta; default threshold 1.0 AU).
- `reporting/_core.py` — added `_TSB_ZONE_COLORS` palette (fresh_detraining / optimal / neutral / accumulated_fatigue / overload) matching the zone colour scheme in `training_load_plots.py`.
- `reporting/__init__.py` — exports `table_training_load_history`, `summary_training_load`
- Unit tests `TestTsbZoneLabel` (12), `TestCtlTrend` (6), `TestTableTrainingLoadHistory` (15), `TestSummaryTrainingLoad` (12) in `tests/reporting/test_training_load_report.py`

---

### Added — v0.2.0 Phase 4 — Visualisation ATL / CTL / TSB

- `visualization/training_load_plots.py` — new module:
  - `plot_atl_ctl_tsb(training_load, title, figsize) → Figure` — 2-panel figure: ATL (red) + CTL (blue) with shaded fill on top; TSB (purple) with 5 coloured zone bands and zero-reference line on bottom. Raises `ValueError` on empty input.
  - `plot_trimp_history(training_load, sessions, sport_colors, title, figsize) → Figure` — daily TRIMP bar chart coloured by sport type (optional sessions lookup); 7-day rolling mean line when ≥ 7 days of data; built-in palette for running/cycling/swimming/strength/trail/rowing; fallback colour for unknown types.
  - `plot_tsb_zones(training_load, title, figsize) → Figure` — TSB line with 5 physiological zone backgrounds (Fresh / Optimal / Neutral / Accumulated fatigue / Overload) from Coggan 2003 / Plews 2013; fill between TSB and zero.
- `visualization/__init__.py` — exports `plot_atl_ctl_tsb`, `plot_trimp_history`, `plot_tsb_zones`
- Unit tests `TestPlotAtlCtlTsb` (8), `TestPlotTrimpHistory` (10), `TestPlotTsbZones` (9) in `tests/visualization/test_training_load_plots.py`

---

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

#### Phase 6 — Local scripts ✅
- `local/main_training_load.py` — log session → TRIMP → save → ATL/CTL/TSB plots
- `local/main_training_load_report.py` — HTML ATL/CTL/TSB report over a period

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
