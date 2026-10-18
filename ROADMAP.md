# cardiolab — Roadmap

Last updated: 2026-10-11 — released history is in [CHANGELOG.md](CHANGELOG.md).

Versions are ordered by **priority**: each one builds on the previous. A version only
starts once the previous one is tagged. Each item maps to one GitLab issue
(milestone = target version).

| Priority | Meaning |
|----------|---------|
| **P0** | In progress — blocks everything else |
| **P1** | Correctness of the numbers cardiolab produces, or a prerequisite for what follows |
| **P2** | New value for athletes, built on reliable P1 foundations |
| **P3** | Useful, but needs data volume or hardware not yet available |

## Guiding rules

* **Toolbox, not application** — workflows belong to the API / local scripts; cardiolab ships composable functions.
* **One schema change per version at most** — each one is a versioned SQL migration (`V00N__*.sql`).
* **A change that alters computed values is a minor version** (`0.x.0`), never a patch, and comes with a way to reprocess history from `hrv_raw_sessions`.
* Every implementation updates README + CHANGELOG + `cardiolab/docs/`.

## Overview

| Version | Priority | Theme | DB change | Changes computed values |
|---------|----------|-------|-----------|-------------------------|
| [v0.3.1](#v031--ci-pipeline-090-p0) | P0 | CI pipeline 0.9.0, TestPyPI pre-release — **released 2026-10-12** | — | No |
| [v0.3.2](#v032--fixes-and-hygiene-p1) | P1 | Readiness consistency fix, hygiene, entropy speed-up, sample datasets — **released 2026-10-13** | — | TRIMP only |
| [v0.3.3](#v033--generic-repository-p1) | P1 | Generic `HRVRepository` (prerequisite for new tables) — not published separately, **shipped in v0.3.4** | — | No |
| [v0.3.4](#v034--sports-p1) | P1 | Sports reference list, sport validated on save, sport read from `.fit` files — **released 2026-10-16** (includes v0.3.3) | — | No |
| [v0.4.0](#v040--signal-reliability-p1) | P1 | Artefact correction, spectral fixes, signal quality, reprocessing — **ready 2026-10-18** | V005 | **Yes** |
| [v0.5.0](#v050--athlete-longitudinal-monitoring-p2) | P2 | 7-day lnRMSSD + CV + SWC, trend analysis, real trend component, effort-based load (session RPE) | V006 | **Yes** (readiness trend) |
| [v0.6.0](#v060--exercise-protocols-p2) | P2 | DFA α1 thresholds (VT1/VT2), submaximal test | V007 | No (new protocols) |
| [v0.7.0](#v070--statistical-intelligence-p3) | P3 | Multivariate anomaly, statistical plots | — | No |
| [v0.8.0](#v080--autonomic-function-tests-p3) | P3 | Ewing battery (E/I, Valsalva, 30:15) | V008 | No (new protocol) |
| [v0.9.0](#v090--ppg--prv-p3) | P3 | PPG signals / pulse rate variability | — | No |

---

## v0.3.1 — CI pipeline 0.9.0 (P0)

Released 2026-10-12. No functional change.

* **CI — Pipeline 0.9.0 and publication 0.3.1rc1 → 0.3.1**: `ref: 0.9.0`, integration tests on a throwaway PostgreSQL, Trusted Publishing, `V-0.3.1-rc1` on TestPyPI then `V-0.3.1` on PyPI, revoke the old `PYPI_TOKEN`.

## v0.3.2 — Fixes and hygiene (P1)

Released 2026-10-13. No schema change. Only the TRIMP values change (bug fix).

* ✅ **Bug — `load_readiness_for_date` uses the legacy score**: it calls `readiness_score_oura` (RMSSD 70 % + HR 30 %), whereas the score stored and displayed for resting comes from `readiness_score_multi`, and orthostatic has a dedicated `orthostatic_readiness_score`. The TRIMP is therefore built from a different score than the one the athlete sees.
* **Hygiene — single source of version, dead code, test isolation**: ✅ `__version__` from `importlib.metadata`; ✅ the local Supabase auto-start in `conftest.py` is skipped in CI (`CI` set — same rule as `cardioanalysis-api`); ✅ `cardiolab/scripts/import_rr.py` removed (no entry point); examples read raw files with `parse_rr_file()`; broken `docs/sensors/polar.md` snippet fixed.
* ✅ **Performance — SampEn / ApEn with a KD-tree**: replace the O(N²) Python loops with `scipy.spatial.KDTree` (Chebyshev metric); identical results, speed-up for long recordings (drift, HRR).
* ✅ **Sample datasets — `cardiolab.datasets`**: the author's real recordings (6 resting, 1 orthostatic) as raw `.txt` + manifest, loadable after `pip install` with `list_samples()` / `load_sample()`; former JSON files and `exports/` removed (they were shipped in the wheel but unreachable).

## v0.3.3 — Generic repository (P1)

Prepared 2026-10-13, not published separately: shipped in v0.3.4. No API change. Prerequisite for v0.4.0, v0.6.0 and v0.8.0, which all add tables or columns.

* ✅ **Refactor — Generic `HRVRepository`**: one `_ProtocolTable` specification per protocol table, generic `_create` / `_upsert` / `_select`, public methods as one-line wrappers. Code −31 % (1 448 → 993 lines, docstrings kept); SQL and loaded objects verified identical before / after. Adding a table is documented in `docs/database/migration_guide.md`.

## v0.3.4 — Sports (P1)

Released 2026-10-16 — also ships v0.3.3. No schema change (`sport_type` stays a `TEXT` column, now holding normalised codes). No change to computed values. Needed by the cardioanalysis site (activity list of « Saisir une séance », colours of the weekly load chart).

* ✅ **Sports reference list**: one module (`cardiolab/sports.py`) defining each sport once — code (`running`, `cycling`, `swimming`, `trail`, `strength`, `rowing`, `hiking`, `skiing`, team sports…), FR / EN labels, colour, family (endurance, strength, team sports, other) — plus `normalize_sport()` mapping free text and import names (« Course à pied », `run`, Garmin FIT sport / sub-sport codes) to a code. `_DEFAULT_SPORT_COLORS` of `training_load_plots.py` and the labels read from it.
* ✅ **Sport validated on save**: `save_training_session()` stores the reference code and rejects unknown sports with a suggestion (`validate_sport()`), so typos never reach the database.
* ✅ **Sport read from `.fit` files**: `extract_training_session_garmin()` also returns the activity sport (FIT `sport` / `sub_sport` fields), normalised with the reference list.

## v0.4.0 — Signal reliability (P1)

Ready 2026-10-18. **Changes computed values** — the most important scientific version. DB: migration V005 (signal quality).

* ✅ **Artefact correction by replacement (Lipponen & Tarvainen 2019)**: `RRSeries.correct_artifacts()` — extra beats merged, missed beats split, ectopic / long-short beats interpolated; used by `auto_clean`. One pass (as published) and a 20 % amplitude gate on ectopic / long-short beats, so that the respiratory arrhythmia of trained athletes is not corrected. Validated against injected artefacts (100 % detected, RMSSD within 3 %), clean signals (0 correction) and NeuroKit2 (identical classifications without the gate).
* ✅ **Entropy convention**: `sampen` counted B over the N−m+1 m-length templates, whereas Richman & Moorman (2000) use the first N−m templates for both A and B. Small bias, but values change: align with the reference definition here (kept identical in v0.3.2, where only speed changed).
* ✅ **Spectral analysis — Welch window, single interpolation, Lomb-Scargle**: Welch window 64 s → 256 s with 50 % overlap (resolution 0.016 → 0.004 Hz); merge `RRSeries.interpolate` and `frequency_domain._interpolate` (cubic spline, 4 Hz); add `method="lomb"` (no interpolation, suited to irregular / PPG data); `VLF_reliable` flag. Also fixed: the AR PSD grid (0.016 Hz) missed most of the power of narrow peaks — AR band powers and the coherence score were underestimated.
* ✅ **Signal quality index per session**: share of corrected beats, effective duration, quality grade; stored (V005), shown in reports, and low-quality sessions excluded from the baseline by default. Orthostatic phases graded separately; uncorrected artefacts → `poor`; evolution charts flag `poor` sessions.
* ✅ **Bug — VO2max RMSSD model (Esco & Flatt)** — model removed (the cited paper has no VO2max equation); category / score from Uth, otherwise the indicative ln-RMSSD estimate (no verified source either — see the follow-up idea below). `vo2_ef = 18.37 + 0.054 × RMSSD` returns 19.5–23.8 mL/kg/min over the whole normal RMSSD range (20–100 ms), versus ~50 for the ln-RMSSD and Uth models on the same athlete — every user without `hr_max` is classed « poor » / « fair ». Check the coefficients against Esco & Flatt (2014) and fix (or drop the model); test that the three models agree within a plausible range on realistic profiles.
* ✅ **Reprocess history from `hrv_raw_sessions`**: recompute features and scores of past sessions with the new pipeline, plus a migration note for users. `reprocess_sessions()` (dry run by default, chronological resting scores, idempotent) and `analyse_session()` — the single analysis pipeline shared with imports.

## v0.5.0 — Athlete longitudinal monitoring (P2)

DB: migration V006 (`rpe` column on training sessions). Monitoring metrics are computed from the existing history; the real trend component changes readiness values (reprocessing note).

* ✅ **7-day rolling lnRMSSD, CV and smallest worthwhile change (Plews, Buchheit)**: the reference approach for monitoring training adaptation. Rolling mean lnRMSSD, coefficient of variation, SWC band (±0.5 SD of the baseline) and interpretation (coping / maladaptation / overreaching).
* ✅ **Readiness — a real trend component**: the 20 % « trend » of `readiness_score_multi` compares today's RMSSD with the median of the last 7 sessions — the same reference as the main RMSSD component (35 %), so RMSSD actually weighs ~55 % and no trend is measured. Replace it with the **change of the 7-day rolling mean of lnRMSSD versus the previous week**, scaled by the athlete's smallest worthwhile change (SWC): stable within ±SWC → ≈ 50, sustained rise → up to 100, sustained decline → down to 0; neutral (50) until 14 days of data. Changes readiness values → reprocessing note. Already described this way on the cardioanalysis site.
* **VO2max — age- and sex-adjusted categories**: `_fitness_category()` and `vo2max_score()` use one fixed ACSM scale for everyone; use the ACSM norms by age and sex from the user profile (`birth_year`, `sex` already stored in `user_profiles`). The site already says the categories « do not yet take age and sex into account ». Same item: **VO2max without a measured HRmax** — use the Uth model with an age-predicted HRmax (Tanaka 2001, `208 − 0.7 × age`, from `birth_year`) instead of the ln-RMSSD estimate, whose equation has no verified source (kept as indicative since v0.4.0).
* **Effort-based load — session RPE (Foster 2001)**: load = duration × perceived effort (0–10 scale), for every sport and without heart rate. Heart-rate load (`trimp_banister`) suits endurance but underestimates strength and short intervals; the HRV method needs a morning measure. Adds `trimp_session_rpe()` and an `rpe` column on training sessions (migration V006); the site's « Saisir une séance » gets an effort field.
* **Trend analysis**: refactor `trends.py` — slope, r², p-value over a sliding window, relative threshold, sustained-decline detection, trend report.

## v0.6.0 — Exercise protocols (P2)

DB: migration V007 (exercise test results). Requires v0.4.0 (DFA α1 is very sensitive to artefacts).

* **DFA α1 during exercise — ventilatory thresholds (VT1 / VT2)**: windowed DFA α1 (2 min, rolling) on an incremental test; HR and power at α1 = 0.75 (aerobic threshold) and α1 = 0.5 (anaerobic threshold). Garmin `.fit` and Polar H10 already provide the RR data.
* **Submaximal fitness test (LSCT, Lamberts 2011)**: standardised 3-stage test; HR at each stage + HRR60; weekly monitoring without a maximal test.

## v0.7.0 — Statistical intelligence (P3)

Most useful with ~100+ sessions per user.

* **Multivariate anomaly (Mahalanobis)**: `mahalanobis_distance`, `is_multivariate_anomaly`, `anomaly_report`; guard `n < 30 → insufficient_data`.
* **Statistical plots**: `visualization/statistical_plots.py` — anomaly timeline, trend overlay with 95 % CI.

## v0.8.0 — Autonomic function tests (P3)

DB: migration V008.

* **Ewing battery**: deep breathing (6 breaths/min, E/I ratio), Valsalva ratio, 30:15 ratio on standing (reuses orthostatic phase detection). Clinical reference values by age.

## v0.9.0 — PPG / PRV (P3)

* **PPG signals and pulse rate variability**: `PPGSignal` (filtering, systolic peak detection), conversion to an RR-like series, PRV vs HRV limits (documented), Lomb-Scargle by default.

---

## Out of scope — parallel repositories

| Project | Depends on |
|---------|-----------|
| `cardioanalysis-api` (FastAPI) | cardiolab via PyPI |
| `cardioanalysis-web` (interface) | `cardioanalysis-api` |

## References

* Lipponen, J. A., & Tarvainen, M. P. (2019). A robust algorithm for heart rate variability time series artefact correction using novel beat classification. *Journal of Medical Engineering & Technology*, 43(3), 173–181.
* Plews, D. J., Laursen, P. B., Kilding, A. E., & Buchheit, M. (2012). Heart rate variability in elite triathletes: is variation in variability the key to effective training? *European Journal of Applied Physiology*, 112(11), 3729–3741.
* Buchheit, M. (2014). Monitoring training status with HR measures: do all roads lead to Rome? *Frontiers in Physiology*, 5, 73.
* Foster, C., et al. (2001). A new approach to monitoring exercise training. *Journal of Strength and Conditioning Research*, 15(1), 109–115.
* Rogers, B., Giles, D., Draper, N., Hoos, O., & Gronwald, T. (2021). A new detection method defining the aerobic threshold for endurance exercise and training prescription based on fractal correlation properties of heart rate variability. *Frontiers in Physiology*, 11, 596567.
* Lamberts, R. P., Swart, J., Noakes, T. D., & Lambert, M. I. (2011). A novel submaximal cycle test to monitor fatigue and predict cycling performance. *British Journal of Sports Medicine*, 45(10), 797–804.
* Ewing, D. J., Martyn, C. N., Young, R. J., & Clarke, B. F. (1985). The value of cardiovascular autonomic function tests: 10 years experience in diabetes. *Diabetes Care*, 8(5), 491–498.
* Lomb, N. R. (1976). Least-squares frequency analysis of unequally spaced data. *Astrophysics and Space Science*, 39(2), 447–462.
