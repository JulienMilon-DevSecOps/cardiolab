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
| [v0.3.2](#v032--fixes-and-hygiene-p1) | P1 | Readiness consistency fix, hygiene, entropy speed-up | — | TRIMP only |
| [v0.3.3](#v033--generic-repository-p1) | P1 | Generic `HRVRepository` (prerequisite for new tables) | — | No |
| [v0.4.0](#v040--signal-reliability-p1) | P1 | Artefact correction, spectral fixes, signal quality, reprocessing | V005 | **Yes** |
| [v0.5.0](#v050--athlete-longitudinal-monitoring-p2) | P2 | 7-day lnRMSSD + CV + SWC, trend analysis | — | No (new metrics) |
| [v0.6.0](#v060--exercise-protocols-p2) | P2 | DFA α1 thresholds (VT1/VT2), submaximal test | V006 | No (new protocols) |
| [v0.7.0](#v070--statistical-intelligence-p3) | P3 | Multivariate anomaly, statistical plots | — | No |
| [v0.8.0](#v080--autonomic-function-tests-p3) | P3 | Ewing battery (E/I, Valsalva, 30:15) | V007 | No (new protocol) |
| [v0.9.0](#v090--ppg--prv-p3) | P3 | PPG signals / pulse rate variability | — | No |

---

## v0.3.1 — CI pipeline 0.9.0 (P0)

Released 2026-10-12. No functional change.

* **CI — Pipeline 0.9.0 and publication 0.3.1rc1 → 0.3.1**: `ref: 0.9.0`, integration tests on a throwaway PostgreSQL, Trusted Publishing, `V-0.3.1-rc1` on TestPyPI then `V-0.3.1` on PyPI, revoke the old `PYPI_TOKEN`.

## v0.3.2 — Fixes and hygiene (P1)

No schema change. Only the TRIMP values change (bug fix).

* ✅ **Bug — `load_readiness_for_date` uses the legacy score**: it calls `readiness_score_oura` (RMSSD 70 % + HR 30 %), whereas the score stored and displayed for resting comes from `readiness_score_multi`, and orthostatic has a dedicated `orthostatic_readiness_score`. The TRIMP is therefore built from a different score than the one the athlete sees.
* **Hygiene — single source of version, dead code, test isolation**: ✅ `__version__` from `importlib.metadata`; ✅ the Supabase auto-start in `conftest.py` only when `DB_HOST_TEST` is local; ⏳ `cardiolab/scripts/import_rr.py` (no entry point, 0 % covered) — still referenced by examples 02 / 11 (JSON intermediate format) and `docs/sensors/polar.md`, whose snippet is broken (`compute_time_domain` does not exist, `parse_rr_file` returns a `dict`).
* ✅ **Performance — SampEn / ApEn with a KD-tree**: replace the O(N²) Python loops with `scipy.spatial.KDTree` (Chebyshev metric); identical results, speed-up for long recordings (drift, HRR).

## v0.3.3 — Generic repository (P1)

No API change. Prerequisite for v0.4.0, v0.6.0 and v0.8.0, which all add tables or columns.

* **Refactor — Generic `HRVRepository`**: `repository.py` is 2 590 lines with a near-identical create / save / load trio per protocol. Drive it with one table specification per protocol; public methods stay as thin wrappers. The 55 integration tests now running in CI are the safety net.

## v0.4.0 — Signal reliability (P1)

**Changes computed values** — the most important scientific version. DB: migration V005 (signal quality).

* **Artefact correction by replacement (Lipponen & Tarvainen 2019)**: `remove_outliers` deletes beats, which creates spurious successive differences and biases RMSSD, pNN50, SD1 and DFA α1. Detect ectopic / missed / extra beats from dRR and replace them by interpolation; `auto_clean=True` uses it.
* **Entropy convention**: `sampen` counts B over the N−m+1 m-length templates, whereas Richman & Moorman (2000) use the first N−m templates for both A and B. Small bias, but values change: align with the reference definition here (kept identical in v0.3.2, where only speed changed).
* **Spectral analysis — Welch window, single interpolation, Lomb-Scargle**: Welch window 64 s → 256 s with 50 % overlap (resolution 0.016 → 0.004 Hz); merge `RRSeries.interpolate` and `frequency_domain._interpolate` (cubic spline, 4 Hz); add `method="lomb"` (no interpolation, suited to irregular / PPG data).
* **Signal quality index per session**: share of corrected beats, effective duration, quality grade; stored (V005), shown in reports, and low-quality sessions excluded from the baseline by default.
* **Reprocess history from `hrv_raw_sessions`**: recompute features and scores of past sessions with the new pipeline, plus a migration note for users.

## v0.5.0 — Athlete longitudinal monitoring (P2)

No schema change — computed from the existing history.

* **7-day rolling lnRMSSD, CV and smallest worthwhile change (Plews, Buchheit)**: the reference approach for monitoring training adaptation. Rolling mean lnRMSSD, coefficient of variation, SWC band (±0.5 SD of the baseline) and interpretation (coping / maladaptation / overreaching).
* **Trend analysis**: refactor `trends.py` — slope, r², p-value over a sliding window, relative threshold, sustained-decline detection, trend report.

## v0.6.0 — Exercise protocols (P2)

DB: migration V006 (exercise test results). Requires v0.4.0 (DFA α1 is very sensitive to artefacts).

* **DFA α1 during exercise — ventilatory thresholds (VT1 / VT2)**: windowed DFA α1 (2 min, rolling) on an incremental test; HR and power at α1 = 0.75 (aerobic threshold) and α1 = 0.5 (anaerobic threshold). Garmin `.fit` and Polar H10 already provide the RR data.
* **Submaximal fitness test (LSCT, Lamberts 2011)**: standardised 3-stage test; HR at each stage + HRR60; weekly monitoring without a maximal test.

## v0.7.0 — Statistical intelligence (P3)

Most useful with ~100+ sessions per user.

* **Multivariate anomaly (Mahalanobis)**: `mahalanobis_distance`, `is_multivariate_anomaly`, `anomaly_report`; guard `n < 30 → insufficient_data`.
* **Statistical plots**: `visualization/statistical_plots.py` — anomaly timeline, trend overlay with 95 % CI.

## v0.8.0 — Autonomic function tests (P3)

DB: migration V007.

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
* Rogers, B., Giles, D., Draper, N., Hoos, O., & Gronwald, T. (2021). A new detection method defining the aerobic threshold for endurance exercise and training prescription based on fractal correlation properties of heart rate variability. *Frontiers in Physiology*, 11, 596567.
* Lamberts, R. P., Swart, J., Noakes, T. D., & Lambert, M. I. (2011). A novel submaximal cycle test to monitor fatigue and predict cycling performance. *British Journal of Sports Medicine*, 45(10), 797–804.
* Ewing, D. J., Martyn, C. N., Young, R. J., & Clarke, B. F. (1985). The value of cardiovascular autonomic function tests: 10 years experience in diabetes. *Diabetes Care*, 8(5), 491–498.
* Lomb, N. R. (1976). Least-squares frequency analysis of unequally spaced data. *Astrophysics and Space Science*, 39(2), 447–462.
