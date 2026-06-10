# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
