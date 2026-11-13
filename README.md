# cardiolab

[![PyPI version](https://img.shields.io/pypi/v/cardiolab)](https://pypi.org/project/cardiolab/)
[![Python versions](https://img.shields.io/pypi/pyversions/cardiolab)](https://pypi.org/project/cardiolab/)
[![Pipeline](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/badges/main/pipeline.svg)](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/pipelines?ref=main)
[![Coverage](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/badges/main/coverage.svg)](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/pipelines?ref=main)
[![License](https://img.shields.io/pypi/l/cardiolab)](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/LICENCE)

**Heart rate variability (HRV) analysis for athletes and researchers, in Python.**

cardiolab turns the beat-to-beat intervals recorded by a heart rate sensor (chest strap,
watch) into reliable HRV metrics, runs standard physiological tests, and follows them over
time: a daily readiness score, training load and freshness, recovery and fitness markers.
Every formula is taken from the published literature and referenced.

It is the scientific core of the **cardioanalysis** platform, and works just as well on its
own — in a notebook, a script or your own application.

> cardiolab is a sport and research tool, **not a medical device**: it makes no diagnosis.

---

## Features

* **Sensor imports** — Polar (`.txt`, `.csv`), HRV4Training (`.csv`), Garmin (`.fit` / `.csv`),
  Apple Health (`export.xml`).
* **Clean signal** — artefact correction that keeps the athlete's respiratory arrhythmia,
  and a signal quality grade for every recording.
* **23 HRV indicators** — time domain (RMSSD, SDNN, pNN50…), frequency domain (LF, HF,
  LF/HF…), non-linear (Poincaré SD1/SD2, DFA α1, entropies).
* **9 protocols** — resting, orthostatic, cardiac coherence, heart rate recovery, cardiac
  drift, VO2max estimation, DFA α1 thresholds, submaximal cycle test (LSCT), autonomic
  reflex tests (Ewing battery); each returns a typed result with its interpretation. Training zones from the thresholds.
* **Follow-up over time** — readiness score against the athlete's own history, 7-day
  lnRMSSD monitoring, trends, training load (ATL / CTL / freshness) with three load methods.
* **Outputs** — matplotlib charts and dashboards, pandas report tables (HTML / Excel),
  CSV / JSON export, English and French labels.
* **Storage** (optional) — PostgreSQL schema with versioned migrations, and reprocessing of
  the whole history when a calculation improves.
* **Sample data** — real recordings ship with the package: try everything without a sensor.

---

## Installation

cardiolab requires **Python 3.13+**.

```bash
pip install cardiolab
```

or, in a project managed with [uv](https://docs.astral.sh/uv/):

```bash
uv add cardiolab
```

The core needs only numpy, scipy and matplotlib. Optional extras add features:

| Extra | Adds | Install |
|-------|------|---------|
| `analysis` | pandas report tables, DataFrame exports | `pip install "cardiolab[analysis]"` |
| `database` | PostgreSQL storage (psycopg2) | `pip install "cardiolab[database]"` |
| `garmin` | Garmin `.fit` files (fitparse) | `pip install "cardiolab[garmin]"` |

Combine them as needed: `pip install "cardiolab[analysis,garmin]"` —
with uv: `uv add "cardiolab[analysis,garmin]"`.

---

## Quick start

Analyse a 5-minute morning recording — here one of the sample recordings shipped with the
package:

```python
from cardiolab import resting_hrv
from cardiolab.datasets import load_sample

rr = load_sample("resting", 0)             # RRSeries: Polar H10, lying down, on waking
features = resting_hrv(rr, auto_clean=True)

features.rmssd           # 41.1 ms — beat-to-beat variability
features.mean_hr         # 58.1 bpm
features.quality.grade   # 'good' — share of corrected beats below 2 %
```

With your own file:

```python
from cardiolab import RRSeries, resting_hrv
from cardiolab.sensors_tools import parse_rr_file

data = parse_rr_file("2026-10-28 07-12.txt")       # Polar export
features = resting_hrv(RRSeries(data["rr_intervals"]), auto_clean=True)
```

More: [Examples and notebooks](#examples-and-notebooks).

---

## How it works — the analysis workflow

In cardiolab, the *pipeline* is the chain of steps that turns a sensor recording into
interpreted results. Each step is a sub-package that can be used on its own:

```
 Sensor file ─► 1. Import ─► 2. Clean ─► 3. Measure ─► 4. Protocol ─► 5. Follow up ─► 6. Present / store
                sensors_tools  signals     features     protocols     analytics       visualization, reporting,
                                                                                       io, database
```

| Step | What happens | Sub-package |
|------|--------------|-------------|
| 1. Import | Read a sensor export into an `RRSeries` — the intervals between heartbeats, in ms | `cardiolab.sensors_tools` |
| 2. Clean | Flag implausible intervals, correct artefacts (missed, extra or ectopic beats), grade the signal quality | `cardiolab.signals` |
| 3. Measure | Compute the 23 HRV indicators | `cardiolab.features` |
| 4. Protocol | Apply a test (resting, orthostatic…) and interpret it: categories, score | `cardiolab.protocols` |
| 5. Follow up | Compare with the athlete's own history: readiness, trends, training load | `cardiolab.analytics` |
| 6. Present / store | Charts, tables, CSV / JSON, PostgreSQL | `visualization`, `reporting`, `io`, `database` |

Every step is deterministic and covered by tests; the metrics are documented in
[`docs/features/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/cardiolab/docs/features).

---

## Protocols

| Protocol | What it tells you | Recording | Function |
|----------|-------------------|-----------|----------|
| [Resting](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/protocols/resting.md) | Daily recovery — basis of the readiness score | 5 min lying down, on waking | `resting_hrv()` |
| [Orthostatic](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/protocols/orthostatic.md) | Response of the nervous system to standing up | 5 min lying + 5 min standing | `orthostatic_hrv()` |
| [Cardiac coherence](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/protocols/cardiac_coherence.md) | Share of the variability concentrated at the breathing rhythm | 5 min paced breathing, 6 breaths/min | `cardiac_coherence()` |
| [Heart rate recovery](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/protocols/hrr.md) | How fast the heart slows down after an effort (HRR1, HRR2) | From peak effort, ≥ 2 min | `heart_rate_recovery()` |
| [Cardiac drift](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/protocols/cardiac_drift.md) | Heart rate rise at a constant pace — endurance | ≥ 20 min of steady effort | `cardiac_drift()` |
| [VO2max](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/protocols/vo2max.md) | Estimated aerobic capacity, percentile by age and sex | Resting recording + HRmax or age | `vo2max_from_hrv()` |
| [DFA α1 thresholds](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/protocols/dfa_thresholds.md) | Aerobic and anaerobic thresholds (HRVT1, HRVT2) — heart rate, and power or speed | Incremental test to exhaustion, chest strap | `dfa_thresholds()` |
| [Submaximal cycle test (LSCT)](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/protocols/lsct.md) | Fitness and fatigue week after week: power at a fixed heart rate | 17 min on the bike, heart rate + power | `lsct()` |
| [Autonomic reflex tests](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/protocols/autonomic_tests.md) | Check-up of the nervous control of the heart, against reference values by age: deep breathing, Valsalva, 30:15 | 1 min paced breathing · 15 s strain on a manometer · the orthostatic test; chest strap | `deep_breathing_test()`, `valsalva_ratio()`, `ratio_30_15()` |

Each linked page describes how to record the test, how the result is computed and how to
read it. What comes next: see the
[roadmap](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/ROADMAP.md).

### Example — the orthostatic test

Lie down for 5 minutes, stand up, stay standing for 5 minutes. cardiolab detects the
moment you stood up and analyses each phase:

```python
from cardiolab import orthostatic_hrv, orthostatic_score
from cardiolab.datasets import load_sample

result = orthostatic_hrv(load_sample("orthostatic", 0), auto_clean=True)

result.hr_response        # 25.1 bpm — heart rate rise once stabilised standing
result.interpretation     # 'normal' (5–30 bpm)
result.phases.supine.features.rmssd     # 96 ms lying…
result.phases.standing.features.rmssd   # …14 ms standing: normal vagal withdrawal
orthostatic_score(result.hr_response, result.hf_response_pct)   # 51 / 100
```

The other protocols follow the same pattern: one function, one result dataclass with
`to_dict()`, a category and a score.

---

## Scores and follow-up over time

* **Readiness score** (0–100, 50 = your usual state) — `readiness_score_multi()` compares
  today's recording with your previous 28 days: lnRMSSD 45 %, resting heart rate 25 %,
  7-day trend 20 %, DFA α1 10 %. It stays at 50 until about a week of history exists
  (two weeks for the trend component).
  → [`docs/analytics/monitoring.md`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/analytics/monitoring.md)
* **Training adaptation** — 7-day rolling lnRMSSD, its coefficient of variation and the
  smallest worthwhile change (Plews, Buchheit): `monitoring_series()`.
* **Trends** — slope and significance over a window of days, sustained declines:
  `linear_trend()`, `detect_sustained_decline()`; trend line with its 95 % confidence band:
  `trend_line()`, chart `plot_trend_overlay()`.
  → [`docs/analytics/trends.md`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/analytics/trends.md)
* **Unusual days** — sessions that differ from your previous 90 days on several metrics at
  once (lnRMSSD, resting heart rate, DFA α1, SD1/SD2), with the metric that deviates most:
  `is_multivariate_anomaly()`, `anomaly_report()` (robust Mahalanobis distance, from 40
  sessions); chart `plot_anomaly_timeline()`.
  → [`docs/analytics/anomaly.md`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/analytics/anomaly.md)
* **Training load** — the load of each session (session RPE, heart rate or readiness
  based), then fatigue (ATL, 7 days), fitness (CTL, 42 days) and freshness in % of fitness,
  with zones: `TrainingLoad.from_sessions()`.
  → [`docs/training_load/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/cardiolab/docs/training_load)

---

## Visualization

`cardiolab.visualization` returns matplotlib figures (`fig.savefig(...)`), with English or
French labels:

| Module | Charts |
|--------|--------|
| `rr_plots` | Tachogram, interval distribution, raw vs corrected signal, 2×2 summary |
| `spectral_plots`, `nonlinear_plots` | Power spectrum, LF/HF, radar; Poincaré, DFA α1 |
| `resting_plots`, `monitoring_plots` | RMSSD and readiness over time; 7-day lnRMSSD monitoring |
| `orthostatic_plots`, `coherence_plots`, `hrr_plots`, `drift_plots`, `vo2max_plots` | One set per protocol: single test and evolution |
| `training_load_plots` | ATL / CTL / freshness, load per sport |
| `dashboard_plots` | One-page dashboards: per session, per protocol, heatmap over time |

For the orthostatic test, for example:

```python
from cardiolab.labels import LABELS_FR
from cardiolab.visualization.nonlinear_plots import plot_poincare_comparison
from cardiolab.visualization.orthostatic_plots import plot_orthostatic_phases_evolution

# One test: Poincaré plot lying vs standing, on the same axes
fig = plot_poincare_comparison(result.phases.supine.rr, result.phases.standing.rr)

# Several tests: RMSSD, heart rate and autonomic response per phase, session by session
fig = plot_orthostatic_phases_evolution(results, session_labels=dates, labels=LABELS_FR)
fig.savefig("orthostatic.png", dpi=150, bbox_inches="tight")
```

How to read each chart:
[`docs/visualization/reading_charts.md`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/visualization/reading_charts.md).

---

## Reports and export

* **Tables** (`analysis` extra) — `cardiolab.reporting` builds colour-coded pandas tables
  for every protocol and for the training load, ready for a notebook or
  `styler.to_html()`: `table_orthostatic_comparison(results, dates=dates)`.
  → [`docs/reporting/tables.md`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/docs/reporting/tables.md)
* **Export** — every result has `to_dict()`; `cardiolab.io` writes CSV and JSON for every
  protocol (`orthostatic_to_json(result, "test.json")`).
* **Labels** — `LABELS_EN` (default) and `LABELS_FR` translate column headers, legends and
  zone names in tables and charts.

---

## Storage — PostgreSQL

With the `database` extra, `HRVRepository` stores every protocol, the raw intervals,
training sessions and athlete profiles (12 tables, versioned SQL migrations):

```python
from cardiolab.database import HRVRepository

with HRVRepository.from_env() as repo:     # connection settings from environment variables
    repo.run_migrations()
    repo.save_orthostatic(result, user_id=user_id, date="2026-10-28")
    history = repo.load_orthostatic(user_id=user_id)
```

Raw intervals are kept, so when a release improves a calculation, `reprocess_sessions()`
recomputes the whole history (dry run first).
→ [`docs/database/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/cardiolab/docs/database)

---

## Supported sensors

| Source | File | Function | Extra |
|--------|------|----------|-------|
| Polar H10 and apps recording beat intervals (Polar Flow, Elite HRV…) | `.txt`, `.rr`, `.csv` | `parse_rr_file()` | — |
| HRV4Training | `.csv` | `parse_hrv4training_csv()` | — |
| Garmin | `.fit`, `.csv` | `parse_garmin_fit()`, `parse_garmin_csv()` | `garmin` |
| Apple Health | `export.xml` (SDNN only — Apple does not export beat intervals) | `parse_apple_health_export()` | — |

A chest strap gives the most accurate intervals. Recording guides per sensor:
[`docs/sensors/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/cardiolab/docs/sensors).

---

## Examples and notebooks

* **[`examples/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/examples)**
  — 16 runnable scripts, from validating a signal to a full daily workflow: protocols,
  plots, training load, database, reprocessing.
* **[`notebooks/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/notebooks)**
  — 10 thematic Jupyter notebooks (signal, protocols, analytics, training load, sensors).
* **Sample data** — 7 real Polar H10 recordings (6 resting, 1 orthostatic) in
  `cardiolab.datasets`: `list_samples()`, `load_sample()`. Data licence CC BY 4.0, see
  [`datasets/README.md`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/cardiolab/datasets/README.md).

---

## Documentation

| Topic | Where |
|-------|-------|
| HRV metrics, artefact correction, signal quality | [`docs/features/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/cardiolab/docs/features) |
| The eight protocols | [`docs/protocols/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/cardiolab/docs/protocols) |
| Readiness, monitoring, trends | [`docs/analytics/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/cardiolab/docs/analytics) |
| Training load, load methods, RPE guide, sports | [`docs/training_load/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/cardiolab/docs/training_load) |
| Reading the charts | [`docs/visualization/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/cardiolab/docs/visualization) |
| Report tables | [`docs/reporting/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/cardiolab/docs/reporting) |
| Database, migrations, reprocessing | [`docs/database/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/cardiolab/docs/database) |
| Sensors and recording | [`docs/sensors/`](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/tree/main/cardiolab/docs/sensors) |

---

## Versions and upgrades

cardiolab follows semantic versioning while in `0.x`: a release that **changes computed
values** is always a minor version (`0.x.0`) and comes with a migration note and a way to
reprocess the history.

* What changed in each release, and how to upgrade:
  [CHANGELOG.md](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/CHANGELOG.md)
* What comes next:
  [ROADMAP.md](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/ROADMAP.md)

---

## Development

Contributors work from the lock file with [uv](https://docs.astral.sh/uv/):

```bash
git clone https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab.git
cd cardiolab
uv sync --all-extras          # .venv with Python 3.13, all extras + dev tools
uv run ruff check . && uv run ruff format --check .
uv run pytest                 # coverage ≥ 80 %; integration tests need DB_HOST_TEST
uv run pre-commit install     # ruff hooks on commit
```

* Dependencies change through uv only (`uv add <pkg>`, `uv add --optional garmin <pkg>`,
  `uv add --dev <pkg>`); commit `uv.lock` with `pyproject.toml` — the CI runs
  `uv sync --frozen` and fails on a stale lock.
* Ruff is pinned to the version of the CI image (`ruff==0.15.17` in the `dev` group, same
  `rev` in `.pre-commit-config.yaml`): bump the three together.
* CI: GitLab
  [centralised Python pipeline](https://gitlab.com/project-jmilon-devsecops/ci-cd/pipeline-python-centralisee)
  — secret detection, Ruff (lint, format, security rules), pytest with a throwaway
  PostgreSQL, dependency audit and SBOM, build and `twine check`. A `V-x.y.z` tag publishes
  to PyPI, `V-x.y.z-rcN` to TestPyPI (Trusted Publishing).

---

## Scientific references

The main sources are below; each documentation page lists the references of its formulas.

<details>
<summary>Show the references</summary>

#### HRV — Standards and general reviews

* Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Standards of measurement, physiological interpretation and clinical use of Heart Rate Variability. *Circulation*, 93(5), 1043–1065.
* Shaffer, F., & Ginsberg, J. P. (2017). An overview of heart rate variability metrics and norms. *Frontiers in Public Health*, 5, 258. https://doi.org/10.3389/fpubh.2017.00258
* Camm, A. J., et al. (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. *European Heart Journal*, 17(3), 354–381.

#### Non-linear features

* Pincus, S. M. (1991). Approximate entropy as a measure of system complexity. *Proceedings of the National Academy of Sciences*, 88(6), 2297–2301. https://doi.org/10.1073/pnas.88.6.2297
* Richman, J. S., & Moorman, J. R. (2000). Physiological time-series analysis using approximate entropy and sample entropy. *American Journal of Physiology — Heart and Circulatory Physiology*, 278(6), H2039–H2049. https://doi.org/10.1152/ajpheart.2000.278.6.H2039
* Peng, C. K., Havlin, S., Stanley, H. E., & Goldberger, A. L. (1995). Quantification of scaling exponents and crossover phenomena in nonstationary heartbeat time series. *Chaos*, 5(1), 82–87. https://doi.org/10.1063/1.166141
* Gronwald, T., & Hoos, O. (2020). Correlation properties of heart rate variability during endurance exercise: A systematic review. *Annals of Noninvasive Electrocardiology*, 25(1), e12697. https://doi.org/10.1111/anec.12697

#### Cardiac coherence

* Lehrer, P. M., & Gevirtz, R. (2014). Heart rate variability biofeedback: how and why does it work? *Frontiers in Psychology*, 5, 756. https://doi.org/10.3389/fpsyg.2014.00756
* McCraty, R., & Shaffer, F. (2015). Heart rate variability: new perspectives on physiological mechanisms, assessment of self-regulatory capacity, and health risk. *Global Advances in Health and Medicine*, 4(1), 46–61. https://doi.org/10.7453/gahmj.2014.073
* Shaffer, F., McCraty, R., & Zerr, C. L. (2014). A healthy heart is not a metronome: an integrative review of the heart's anatomy and heart rate variability. *Frontiers in Psychology*, 5, 1040. https://doi.org/10.3389/fpsyg.2014.01040

#### Heart Rate Recovery

* Cole, C. R., Blackstone, E. H., Pashkow, F. J., Snader, C. E., & Lauer, M. S. (1999). Heart-rate recovery immediately after exercise as a predictor of mortality. *New England Journal of Medicine*, 341(18), 1351–1357. https://doi.org/10.1056/NEJM199910283411804
* Imai, K., Sato, H., Hori, M., et al. (1994). Vagally mediated heart rate recovery after exercise is accelerated in athletes but blunted in patients with chronic heart failure. *Journal of the American College of Cardiology*, 24(6), 1529–1535. https://doi.org/10.1016/0735-1097(94)90150-3
* Jouven, X., Empana, J. P., Schwartz, P. J., Desnos, M., Courbon, D., & Ducimetière, P. (2005). Heart-rate profile during exercise as a predictor of sudden death. *New England Journal of Medicine*, 352(19), 1951–1958. https://doi.org/10.1056/NEJMoa043012
* Morshedi-Meibodi, A., Larson, M. G., Levy, D., O'Donnell, C. J., & Vasan, R. S. (2002). Heart rate recovery after treadmill exercise testing and risk of cardiovascular disease events (The Framingham Heart Study). *American Journal of Cardiology*, 90(8), 848–852. https://doi.org/10.1016/S0002-9149(02)02801-1

#### Cardiac drift

* Coyle, E. F., & González-Alonso, J. (2001). Cardiovascular drift during prolonged exercise: new perspectives. *Exercise and Sport Sciences Reviews*, 29(2), 88–92. https://doi.org/10.1097/00003677-200104000-00009
* Wingo, J. E., & Cureton, K. J. (2006). Cardiovascular responses to exercise with and without hydration. *Medicine & Science in Sports & Exercise*, 38(4), 739–748. https://doi.org/10.1249/01.mss.0000191765.30569.03
* González-Alonso, J., Calbet, J. A., & Nielsen, B. (1999). Metabolic and thermodynamic responses to dehydration-induced reductions in muscle blood flow in exercising humans. *Journal of Physiology*, 520(2), 577–589. https://doi.org/10.1111/j.1469-7793.1999.00577.x

#### VO2max estimation

* Uth, N., Sørensen, H., Overgaard, K., & Pedersen, P. K. (2004). Estimation of VO2max from the ratio between HRmax and HRrest — the Heart Rate Ratio Method. *European Journal of Applied Physiology*, 91(1), 111–115. https://doi.org/10.1007/s00421-003-0988-y
* Grant, C. C., Murray, C., Janse van Rensburg, D. C., & Fletcher, L. (2013). A comparison between heart rate and heart rate variability as indicators of cardiac health and fitness. *Frontiers in Physiology*, 4, 337. https://doi.org/10.3389/fphys.2013.00337
* Tanaka, H., Monahan, K. D., & Seals, D. R. (2001). Age-predicted maximal heart rate revisited. *Journal of the American College of Cardiology*, 37(1), 153–156. https://doi.org/10.1016/S0735-1097(00)01054-8
* American College of Sports Medicine. (2022). *ACSM's Guidelines for Exercise Testing and Prescription* (11th ed.). Lippincott Williams & Wilkins.

#### Monitoring, training load and fitness norms

* Lipponen, J. A., & Tarvainen, M. P. (2019). A robust algorithm for heart rate variability time series artefact correction using novel beat classification. *Journal of Medical Engineering & Technology*, 43(3), 173–181.
* Plews, D. J., Laursen, P. B., Kilding, A. E., & Buchheit, M. (2012). Heart rate variability in elite triathletes: is variation in variability the key to effective training? *European Journal of Applied Physiology*, 112(11), 3729–3741.
* Foster, C., et al. (2001). A new approach to monitoring exercise training. *Journal of Strength and Conditioning Research*, 15(1), 109–115.
* Gabbett, T. J. (2016). The training—injury prevention paradox: should athletes be training smarter and harder? *British Journal of Sports Medicine*, 50(5), 273–280.
* Kaminsky, L. A., Arena, R., & Myers, J. (2015). Reference standards for cardiorespiratory fitness measured with cardiopulmonary exercise testing: data from the Fitness Registry and the Importance of Exercise National Database. *Mayo Clinic Proceedings*, 90(11), 1515–1523.

</details>

---

## Licence

* Code: [GNU AGPL v3 or later](https://gitlab.com/project-jmilon-devsecops/cardioanalysis/core/cardiolab/-/blob/main/LICENCE).
* Sample recordings (`cardiolab.datasets`): CC BY 4.0.

cardiolab is developed by Julien MILON as the scientific core of the **cardioanalysis**
platform (web application and API in separate repositories).
