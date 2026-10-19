# cardiolab

**cardiolab** is a physiological analysis engine dedicated to heart rate and heart rate variability (HRV) analysis.

This project is the scientific core of the **cardioanalysis** product.

---

## Goal

Transform raw physiological signals (ECG, PPG, HR) into:

* reliable metrics (HR, HRV)
* physiological insights (fatigue, recovery, fitness)
* interpretable scores

---

## Pipeline

```
Raw signal (ECG / PPG / Polar HR sensor)
        ↓
Preprocessing
        ↓
RR intervals
        ↓
Features (HRV — time · frequency · non-linear)
        ↓
Protocols (resting · orthostatic · cardiac coherence · HRR · drift · VO2max)
        ↓
Scoring & Analytics
        ↓
PostgreSQL persistence
```

---

## Project structure

```
cardiolab/
│
├── signals/          → raw data structures (ECG, RR series)
├── features/         → HRV computation (time, frequency & non-linear)
├── protocols/        → physiological tests
│   ├── resting.py            → standard 5-min resting HRV
│   ├── orthostatic.py        → supine → standing with automatic phase detection
│   ├── cardiac_coherence.py  → paced-breathing resonance score
│   ├── hrr.py                → Heart Rate Recovery post-exercise
│   ├── cardiac_drift.py      → progressive HR increase at constant load
│   └── vo2max.py             → VO2max estimation (Uth, indicative ln-RMSSD)
├── analytics/        → baseline, scoring, anomaly detection, trend analysis, training load (ATL/CTL/TSB)
├── sensors_tools/    → sensor imports: Polar, HRV4Training, Apple Health, Garmin (.fit / CSV)
├── sports.py         → sports reference list: codes, FR/EN labels, colours, normalize / validate
├── database/         → PostgreSQL persistence layer (9 tables, versioned SQL migrations)
├── io/               → CSV and JSON export for all protocols
├── reporting/        → tabular reporting (pandas Styler, HTML/Excel export)
│   ├── _core.py          → shared formatters, colour palettes, gradient builders
│   ├── resting.py        → table_resting_history, table_resting_session
│   └── orthostatic.py    → table_orthostatic_comparison, table_orthostatic_history
├── datasets/         → sample recordings shipped with the package (list_samples / load_sample)
├── docs/             → protocol & feature documentation
│   ├── protocols/    → resting.md, orthostatic.md, cardiac_coherence.md,
│   │                   hrr.md, cardiac_drift.md, vo2max.md
│   ├── features/     → index.md, time_domain.md, frequency_domain.md, nonlinear.md, artefact_correction.md, signal_quality.md
│   ├── analytics/    → monitoring.md (7-day lnRMSSD, SWC, adaptation states), trends.md
│   ├── visualization/→ reading_charts.md — how to read each chart type
│   ├── reporting/    → tables.md — reporting API reference
│   └── training_load/→ index.md, training_sessions.md, atl_ctl_tsb.md, sports.md
└── visualization/    → signal and HRV plots
    ├── resting_plots.py  → RMSSD & readiness score evolution over time
    └── rr_plots.py       → raw RR: tachogram, distribution, filtered,
                            multi-session comparison, 2×2 summary

examples/             → step-by-step usage scripts (01 – 15)
notebooks/            → thematic Jupyter notebooks (00 – 09)
tests/                → unit + PostgreSQL integration tests (1 763 tests)
```

---

## Key concepts

### RR intervals

RR intervals are the time gaps between consecutive heartbeats (in milliseconds).
They are the foundation of all HRV analyses in this project.

### HRV (Heart Rate Variability)

Heart rate variability is used to assess:

* fatigue
* stress
* recovery
* aerobic fitness

### HRV indicators

23 indicators computed across protocol phases (all band powers in ms²):

| Domain | Metric | Description |
|--------|--------|-------------|
| Time | RMSSD | Short-term beat-to-beat variability (ms) |
| Time | ln(RMSSD) | Log-normalised RMSSD |
| Time | SDNN | Overall variability (ms) |
| Time | pNN50 | % of pairs > 50 ms apart |
| Time | Mean HR | Mean heart rate (bpm) |
| Frequency | VLF | Very-low-frequency band power (ms²) |
| Frequency | LF | Low-frequency band power (ms²) |
| Frequency | HF | High-frequency band power (ms²) |
| Frequency | LF/HF | Autonomic balance ratio |
| Frequency | HF% | HF as fraction of total power |
| Frequency | LF_nu | LF in normalised units |
| Frequency | HF_nu | HF in normalised units |
| Frequency | Méthode | Spectral estimation method (`welch` / `ar` / `lomb`) |
| Composite | HF/FC | HF divided by mean HR (ms²/bpm) — HR-normalised vagal activity |
| Non-linear | SD1 | Poincaré short-term variability = RMSSD / √2 (ms) |
| Non-linear | SD2 | Poincaré long-term variability (ms) |
| Non-linear | SD1/SD2 | Shape of the Poincaré ellipse — autonomic balance |
| Non-linear | DFA α1 | Short-term fractal scaling exponent (scales 4–16 beats) |
| Non-linear | ApEn | Approximate Entropy — signal regularity (Pincus 1991) |
| Non-linear | SampEn | Sample Entropy — improved ApEn, length-independent (Richman & Moorman 2000) |
| Meta | Duration | Phase duration (s) |
| Meta | Score | Performance score [0–100] (protocol-specific, see below) |

### Input validation

`RRSeries` automatically emits a `PhysiologicalWarning` when any interval
falls outside [300, 2000] ms (HR > 200 bpm or HR < 30 bpm), which almost
always indicates artefacts.

### Artefact correction

`correct_artifacts()` classifies abnormal beats (Lipponen & Tarvainen 2019)
and **corrects** them instead of deleting them — extra beats merged, missed
beats split, ectopic and long / short beats interpolated — so that successive
differences (RMSSD, pNN50, SD1, DFA α1) are not distorted. Ectopic and long /
short beats are only corrected beyond 20 % of the local median, which keeps the
strong respiratory arrhythmia of trained athletes. `resting_hrv()` and
`orthostatic_hrv()` accept `auto_clean=True` to apply it. Validation and
details: [`docs/features/artefact_correction.md`](cardiolab/docs/features/artefact_correction.md).

### Signal quality

Every session carries a `SignalQuality` (`features.quality`): share of
artefacts, whether they were corrected, and a grade — `good` (< 2 % corrected),
`acceptable` (< 5 %), `poor` (≥ 5 %, or any artefact left uncorrected).
`Baseline` leaves `poor` sessions out by default (`include_poor=True` to keep
them); history tables show a quality column and evolution charts flag `poor`
sessions. Orthostatic phases are graded separately. Stored in a `quality` JSONB
column (migration V005). Details:
[`docs/features/signal_quality.md`](cardiolab/docs/features/signal_quality.md).

### Upgrading to 0.4.0 — reprocess the history

0.4.0 changes computed values (artefact correction, Lomb-Scargle default,
signal quality). Apply the migrations, then recompute stored sessions from
their raw RR intervals (`hrv_raw_sessions`) — dry run by default:

```python
from cardiolab.database import HRVRepository, reprocess_sessions

with HRVRepository.from_env() as repo:
    repo.run_migrations()
    print(reprocess_sessions(repo, user_id).summary())          # dry run
with HRVRepository.from_env() as repo:
    reprocess_sessions(repo, user_id, dry_run=False)            # write
```

Details: [`docs/database/reprocessing.md`](cardiolab/docs/database/reprocessing.md).

```python
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries
import warnings

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    rr = RRSeries(raw_intervals)  # PhysiologicalWarning if outliers present

rr_clean, report = rr.correct_artifacts()  # or: resting_hrv(rr, auto_clean=True)
report.corrected_pct  # above 5 %: PhysiologicalWarning, measure again
```

### Sample datasets

Seven real Polar H10 recordings of the author (6 resting, 1 orthostatic, raw and
uncleaned) ship with the package, so every protocol can be tried right after
`pip install cardiolab` — no database, no sensor:

```python
from cardiolab.datasets import list_samples, load_sample
from cardiolab.protocols.resting import resting_hrv

list_samples("resting")          # manifest: id, date, beats, duration…
rr = load_sample("resting", 0)   # RRSeries, manifest entry in rr.metadata
features = resting_hrv(rr, auto_clean=True)
```

Provenance, consent and licence (data: CC BY 4.0) are described in
[`cardiolab/datasets/README.md`](cardiolab/datasets/README.md).

### Export

All result dataclasses expose `to_dict()` — a plain Python dict, JSON-ready
and pandas-compatible. Dedicated export functions cover all protocols:

```python
from cardiolab.io import (
    features_to_csv, features_to_json,
    orthostatic_to_csv, orthostatic_to_json,
    coherence_to_csv, coherence_to_json,
    hrr_to_csv, hrr_to_json,
    drift_to_csv, drift_to_json,
    vo2max_to_csv, vo2max_to_json,
)
```

---

## Protocols

### Resting HRV

Standard 5-minute supine recording. Computes all 23 HRV indicators (time,
frequency, non-linear) and an optional recovery score.

```python
from cardiolab.protocols import resting_hrv
result = resting_hrv(rr, compute_score=True)  # spectral method: "lomb" (default), "welch", "ar"
```

### Orthostatic HRV

5-minute supine + 5-minute standing recording with **automatic phase detection**:

1. **Supine phase** — resting baseline, full HRV features.
2. **Transition** — postural change window detected by a sustained HR rise
   ≥ 10 bpm above the supine baseline (causal rolling 30-second window,
   5 consecutive beats required). Captures `delta_hr`, `peak_hr`,
   `transition_start_sec`, `transition_end_sec`.
3. **Standing phase** — stabilised standing, full HRV features.

Clinical interpretation:

| Classification | Criterion |
|----------------|-----------|
| `normal` | HR rise 5–30 bpm |
| `elevated_response` | HR rise > 30 bpm (possible POTS) |
| `impaired_response` | HR rise < 5 bpm (possible autonomic dysfunction) |
| `excessive_vagal_withdrawal` | HF drop > 60 % |

```python
from cardiolab.protocols import orthostatic_hrv
result = orthostatic_hrv(rr)
```

### Cardiac coherence 5-5

Paced-breathing session at 6 cycles/min (5 s inspiration / 5 s expiration).
At 0.1 Hz the baroreflex resonates, producing a large, narrow peak in the LF band.
The **coherence score** is the share of the whole spectrum held by that peak
(McCraty & Shaffer 2015 — the HeartMath coherence ratio as a percentage, AR PSD):

```
coherence_score = peak_power (0.030 Hz window) / total_power (0.0033–0.4 Hz) × 100
```

| Score (%) | Interpretation |
|-----------|---------------|
| ≥ 50 (ratio ≥ 1) | Good cardiac coherence |
| 30 – 50 | Moderate |
| < 30 | Low — spontaneous-breathing level |

Thresholds are cardiolab's (no validated cut-off exists). Changed in 0.5.0: the score
used the resonance band only, and rest already scored ≈ 50–60 % — reprocess.

```python
from cardiolab.protocols import cardiac_coherence
result = cardiac_coherence(rr)
# result.coherence_score, result.resonance_freq, result.rmssd
```

See [`docs/protocols/cardiac_coherence.md`](cardiolab/docs/protocols/cardiac_coherence.md) for full protocol instructions.

### Heart Rate Recovery (HRR)

Measures the speed of vagal reactivation after maximal or submaximal exercise.
The series must start at peak effort; HR drop at 60 s (HRR1) and 120 s (HRR2)
are computed:

| HRR1 (bpm) | Category | Risk |
|------------|----------|------|
| ≥ 25 | Excellent | Very low |
| 20 – 24 | Good | Low |
| 12 – 19 | Normal | Average |
| < 12 | **Impaired** | Elevated — independent mortality predictor (Cole et al. 1999) |

```python
from cardiolab.protocols import heart_rate_recovery
result = heart_rate_recovery(rr_post_exercise)
# result.hrr_60, result.hrr_60_category, result.hrr_120
```

See [`docs/protocols/hrr.md`](cardiolab/docs/protocols/hrr.md) for full protocol instructions.

### Cardiac drift

Detects and quantifies the progressive HR increase during constant-load
exercise. Linear regression of windowed mean HR over time yields the
**drift rate** (bpm/min):

| Rate (bpm/min) | Category |
|----------------|---------|
| < 0.5 | No drift |
| 0.5 – 1.5 | Mild |
| 1.5 – 3.0 | Moderate |
| > 3.0 | Strong drift |

```python
from cardiolab.protocols import cardiac_drift
result = cardiac_drift(rr_exercise, window_sec=60.0)
# result.drift_rate, result.drift_magnitude, result.r_squared
```

See [`docs/protocols/cardiac_drift.md`](cardiolab/docs/protocols/cardiac_drift.md) for full protocol instructions.

### VO2max estimation from HRV

Estimates maximal oxygen uptake from a resting recording:

| Model | Formula | Precision |
|-------|---------|-----------|
| **Uth et al. (2004)** — reference | `15.3 × (HRmax / HRrest)` — HRmax provided, otherwise `208 − 0.7 × age` (Tanaka 2001) | ±10–15 % |
| **ln-RMSSD** — indicative, without HRmax nor age | `24.89 + 5.97 × ln(RMSSD)` | not established (no verified source) |

The "Esco & Flatt (2014)" RMSSD model was removed in 0.4.0: it gave ≈ 21 mL/kg/min
whatever the RMSSD and classed every user without HRmax as "poor" / "fair"
(`vo2max_esco_flatt` is now always `nan`).

Fitness categories **by age and sex** (v0.5.0): percentile among people of the same
sex and decade — FRIEND registry norms (Kaminsky et al. 2015, adopted by ACSM 2022):
< 10th poor · 10–25th fair · 25–75th good · 75–90th very good · ≥ 90th excellent. The
score is the percentile. Without age and sex, the fixed adult scale (< 28 poor … ≥ 58
excellent mL/kg/min).

```python
from cardiolab.protocols import vo2max_from_hrv
result = vo2max_from_hrv(rr_resting, age=36, sex="male")     # HRmax from Tanaka
# result.vo2max_uth, result.hr_max_source, result.percentile, result.fitness_category
```

See [`docs/protocols/vo2max.md`](cardiolab/docs/protocols/vo2max.md) for full protocol instructions.

---

## Bilingual labels

`cardiolab.labels` provides human-readable display strings for all metrics,
clinical zones, and protocol names. Pass a labels dict to any reporting table
or visualization function to translate headers and legend entries.

```python
from cardiolab.labels import LABELS_EN, LABELS_FR, lbl

# In reporting:
from cardiolab.reporting import table_resting_history, table_orthostatic_comparison
styler = table_resting_history(features_list, labels=LABELS_FR)
styler = table_orthostatic_comparison(results, labels=LABELS_FR)

# In visualization:
from cardiolab.visualization.resting_plots import plot_resting_evolution
fig = plot_resting_evolution(features_list, scores, labels=LABELS_FR)

# Custom override (partial dict — unknown keys fall back to the raw name):
my_labels = {**LABELS_FR, "rmssd": "RMSSD (ms) — repos"}
```

Two ready-made dicts: `LABELS_EN` (default in the package) and `LABELS_FR`
(intended for the `local/` scripts). Both cover:
- HRV metrics (time-domain, frequency, non-linear)
- Orthostatic response metrics (`hr_response`, `delta_rmssd`, `lf_hr_pct_change`, …)
- Clinical zone labels (readiness bands, HRR zones, drift zones, VO2max zones, TSB zones)
- Protocol names (`protocol_resting`, `protocol_orthostatic`, …)

The `session_labels` parameter (list of date strings) remains separate from `labels`
(translation dict) in all visualization functions.

---

## Visualization

The `cardiolab.visualization` module provides ready-made matplotlib figures
for exploring raw RR signals and tracking HRV trends over time.

### Raw RR signal — `rr_plots`

```python
from cardiolab.visualization.rr_plots import (
    plot_rr_tachogram,    # beat-by-beat time series + HR secondary axis
    plot_rr_distribution, # histogram + Gaussian KDE
    plot_rr_filtered,     # raw vs cleaned overlay, artefacts in red
    plot_rr_comparison,   # stacked multi-session tachograms
    plot_rr_summary,      # 2×2 compound figure with HRV stats table
)

fig = plot_rr_tachogram(rr, show_mean=True, show_band=True, show_hr_axis=True)
fig.savefig("tachogram.png", dpi=150)

fig = plot_rr_summary(rr, title="Session 2026-05-20")
fig.show()
```

All functions return a `Figure` and accept a `figsize` argument. Input
validation raises `TypeError` on wrong types and `ValueError` on out-of-range
parameters.

See [`docs/visualization/reading_charts.md`](cardiolab/docs/visualization/reading_charts.md)
for a guide on interpreting each chart type.

### HRV evolution over time — `resting_plots`

```python
from cardiolab.visualization.resting_plots import (
    plot_resting_evolution,         # RMSSD + readiness score over time
    plot_resting_evolution_rolling, # same with rolling-median RMSSD overlay
)

# features_list: list[HRVFeatures], scores: list[float]
fig = plot_resting_evolution(features_list, scores, session_labels=dates)
fig.savefig("evolution.png", dpi=150, bbox_inches="tight")

# rolling_rmssd: list[float | None]  (None = no prior baseline)
fig = plot_resting_evolution_rolling(features_list, scores, rolling_rmssd, session_labels=dates)
fig.savefig("evolution_rolling.png", dpi=150, bbox_inches="tight")
```

Both functions return a `Figure` with two stacked panels (RMSSD top, readiness
score bottom). `None` values in `rolling_rmssd` appear as gaps in the line.
See [`examples/10_resting_evolution_plots.py`](examples/10_resting_evolution_plots.py)
for a complete worked example including data loading and score computation.

### Cardiac coherence — `coherence_plots`

```python
from cardiolab.visualization.coherence_plots import (
    plot_coherence_psd,             # AR PSD + resonance band + peak annotation
    plot_coherence_score_evolution, # score over sessions with interpretation bands
    plot_coherence_tachogram,       # RR tachogram + sinusoidal respiratory reference
)

result = cardiac_coherence(rr)

# AR PSD with resonance band [0.04–0.26 Hz] colored
fig = plot_coherence_psd(rr, result)
fig.savefig("coherence_psd.png", dpi=150, bbox_inches="tight")

# Score evolution over multiple sessions (list[CoherenceResult])
fig = plot_coherence_score_evolution(results, session_labels=dates)
fig.savefig("coherence_score.png", dpi=150, bbox_inches="tight")

# RR tachogram + sine reference at resonance frequency
fig = plot_coherence_tachogram(rr, result)
fig.savefig("coherence_tacho.png", dpi=150, bbox_inches="tight")
```

### Non-linear visualisation — `nonlinear_plots`

```python
from cardiolab.visualization.nonlinear_plots import (
    plot_poincare,            # RR(n) vs RR(n+1) scatter with SD1/SD2 ellipse
    plot_poincare_comparison, # supine vs standing side-by-side
    plot_sd1_sd2_evolution,   # SD1/SD2/ratio evolution over sessions
    plot_dfa_fluctuation,     # log-log F(n) with α1 regression line
)

# Single session — Poincaré scatter
fig = plot_poincare(rr, title="Session 2026-05-20")
fig.savefig("poincare.png", dpi=150, bbox_inches="tight")

# Orthostatic comparison (rr from OrthstaticResult.phases)
fig = plot_poincare_comparison(result.phases.supine.rr, result.phases.standing.rr)
fig.savefig("poincare_ortho.png", dpi=150, bbox_inches="tight")

# Evolution over multiple sessions
fig = plot_sd1_sd2_evolution(features_list, session_labels=dates)  # session dates on x-axis
fig.savefig("sd1_sd2.png", dpi=150, bbox_inches="tight")

# DFA α1 log-log fluctuation plot
fig = plot_dfa_fluctuation(rr, n_min=4, n_max=16, title="DFA α1 — Session 2026-05-20")
fig.savefig("dfa_fluctuation.png", dpi=150, bbox_inches="tight")
```

All four functions return a `Figure`.  The comparison function uses a shared
axis range so the SD1 contraction on standing is directly visible.

### Cardiac drift — `drift_plots`

```python
from cardiolab.visualization.drift_plots import (
    plot_drift_curve,  # windowed HR + linear regression + zone background
    plot_drift_zones,  # multi-session drift-rate evolution with zone bands
)

result = cardiac_drift(rr_exercise, window_sec=60.0)

# Single session — scatter points + regression line, background tinted by category
fig = plot_drift_curve(rr_exercise, result, title="Session 2026-05-20")
fig.savefig("drift_curve.png", dpi=150, bbox_inches="tight")

# Multi-session evolution — coloured dots on zone-banded axes
fig = plot_drift_zones(results, session_labels=dates)
fig.savefig("drift_zones.png", dpi=150, bbox_inches="tight")
```

Both functions return a `Figure`.  `plot_drift_curve` applies the same
non-overlapping windowing as `cardiac_drift()` so the scatter exactly matches
the regression input.  The background tint immediately signals the clinical
category without reading the annotation box.

### Heart Rate Recovery — `hrr_plots`

```python
from cardiolab.visualization.hrr_plots import (
    plot_hrr_curve,       # HR(t) recovery curve with HRR1/HRR2 markers
    plot_hrr_comparison,  # multi-session HR-drop curves coloured by date
    plot_hrr_gauge,       # semi-circular HRR1 gauge (red → green)
)

result = heart_rate_recovery(rr_post_exercise)

# Recovery curve with drop arrows at 60 s and 120 s
fig = plot_hrr_curve(rr_post_exercise, result, title="Session 2026-05-20")
fig.savefig("hrr_curve.png", dpi=150, bbox_inches="tight")

# Superimposed HR-drop curves across sessions
fig = plot_hrr_comparison(rr_list, results, session_labels=dates)
fig.savefig("hrr_comparison.png", dpi=150, bbox_inches="tight")

# Instant HRR1 gauge (colour-coded by clinical zone)
fig = plot_hrr_gauge(result, title="HRR1 — Session 2026-05-20")
fig.savefig("hrr_gauge.png", dpi=150, bbox_inches="tight")
```

All three functions return a `Figure`.  The comparison chart uses **HR drop from
peak** (starts at 0 for all sessions) so curves with different peak HRs remain
directly comparable.  The gauge spans 0–40 bpm with four clinical zones
colour-coded from red (impaired) to green (excellent) following Cole et al. 1999.

### Orthostatic phases evolution — `orthostatic_plots`

```python
from cardiolab.visualization.orthostatic_plots import plot_orthostatic_phases_evolution
from cardiolab.labels import LABELS_FR

# results: list[OrthostaticResult] or list[OrthostaticRecord]
fig = plot_orthostatic_phases_evolution(results, session_labels=dates, labels=LABELS_FR)
fig.savefig("ortho_phases.png", dpi=150, bbox_inches="tight")
```

Four stacked panels sharing the same session x-axis:

1. **RMSSD** — supine (blue), transition (orange), standing (green): read as three
   parallel resting HRV lines to spot inter-phase differences at a glance.
2. **Heart Rate** — same colour convention: track the HR shift per phase.
3. **Autonomic response magnitude** — ΔHR (bars) and ΔRMSSD (line, right axis):
   quantify the amplitude of the postural shift session by session.
4. **Autonomic balance (%)** — `hf_hr_pct_change` and `lf_hr_pct_change`: assess vagal
   withdrawal quality and sympathetic activation over time.

Accepts both `OrthostaticResult` (file-based workflow) and `OrthostaticRecord`
(database read-back) — duck-typed.

### VO2max estimation — `vo2max_plots`

```python
from cardiolab.visualization.vo2max_plots import (
    plot_vo2max_comparison,  # grouped bars (Uth / ln-RMSSD) + ACSM zones
    plot_vo2max_evolution,   # best-estimate timeline with ±10 % uncertainty band
    plot_vo2max_gauge,       # semi-circular fitness gauge (poor → excellent)
)

result = vo2max_from_hrv(rr_resting, hr_max=185.0)

# Model comparison — 2 or 3 bars depending on whether hr_max was provided
fig = plot_vo2max_comparison(result, title="VO2max — Session 2026-05-20")
fig.savefig("vo2max_comparison.png", dpi=150, bbox_inches="tight")

# Multi-session evolution with uncertainty band
fig = plot_vo2max_evolution(results, session_labels=dates)
fig.savefig("vo2max_evolution.png", dpi=150, bbox_inches="tight")

# Instant fitness gauge with needle and central category text
fig = plot_vo2max_gauge(result, title="Fitness Gauge — Session 2026-05-20")
fig.savefig("vo2max_gauge.png", dpi=150, bbox_inches="tight")
```

All three functions return a `Figure`.  The best estimate used by the gauge and
evolution chart follows the priority Uth > ln-RMSSD: Uth is the most validated
model when `hr_max` is known, otherwise ln-RMSSD is preferred.  The ±10 %
uncertainty band on the evolution chart reflects the typical model error range
(Uth: ±10–15 %; ln-RMSSD: indicative, no verified source).  ACSM zones (< 28 poor,
28–37 fair, 38–47 good, 48–57 very good, ≥ 58 excellent) are shown as coloured
backgrounds in all three charts.

### Dashboards — `dashboard_plots`

```python
from cardiolab.visualization.dashboard_plots import (
    # C6 global dashboards
    plot_session_dashboard,    # 2×3 multi-protocol overview for one session
    plot_longitudinal_heatmap, # sessions × metrics colour heatmap
    plot_readiness_evolution,  # daily readiness score line with rolling band
    # Per-protocol mini-dashboards
    plot_resting_mini,         # 2×2: tachogram + Poincaré + PSD + score panel
    plot_hrr_mini,             # 1×2: recovery curve + HRR1 gauge
    plot_drift_mini,           # 1×2: drift curve + metrics summary
    plot_vo2max_mini,          # 1×2: model comparison bars + fitness gauge
    plot_coherence_mini,       # 1×2: AR PSD + RR tachogram
)

# Multi-protocol session overview
fig = plot_session_dashboard(
    rr_resting, features,
    rr_recovery=rr_post, hrr_result=hrr_res,
    rr_exercise=rr_ex, drift_result=drift_res,
    vo2max_result=vo2max_res,
    title="Session 2026-05-20",
)
fig.savefig("session_dashboard.png", dpi=150, bbox_inches="tight")

# Longitudinal heatmap (RMSSD + score + HRR1 + VO2max + drift)
fig = plot_longitudinal_heatmap(
    features_list,
    hrr_results=hrr_list,
    drift_results=drift_list,
    vo2max_results=vo2max_list,
    session_labels=dates,
)
fig.savefig("heatmap.png", dpi=150, bbox_inches="tight")

# Daily readiness score evolution
fig = plot_readiness_evolution(features_list, session_labels=dates)
fig.savefig("readiness.png", dpi=150, bbox_inches="tight")

# Per-protocol mini-dashboards
fig = plot_resting_mini(rr, features)
fig = plot_hrr_mini(rr_post, hrr_result)
fig = plot_drift_mini(rr_exercise, drift_result)
fig = plot_vo2max_mini(vo2max_result)
fig = plot_coherence_mini(rr, coherence_result)
```

`plot_session_dashboard` adapts gracefully: when a protocol result is provided
without its associated RR series, it falls back to a text summary panel; when
neither is provided, a "No data" placeholder is shown.
`plot_longitudinal_heatmap` normalises each metric column to [0, 1] so sessions
can be compared visually even when metrics have different scales.  Missing data
cells appear in grey.

---

## Reporting

The `cardiolab.reporting` module produces **ready-to-display pandas Styler tables**
for Jupyter Notebook, with colour gradients and clinical category highlighting.
Each function returns a `pd.Styler` that is directly exportable to HTML or Excel.

```python
from cardiolab.reporting import (
    # Resting HRV
    table_resting_history,        # multi-session history — one row per session
    table_resting_session,        # single-session detail — one row per metric
    # Orthostatic
    table_orthostatic_comparison, # supine vs standing side-by-side comparison
    table_orthostatic_history,    # condensed orthostatic history
    # HRR
    table_hrr_history,            # HRR1/HRR2 history with clinical categories
    # Cardiac drift
    table_drift_history,          # drift rate, magnitude, R² history
    # Cardiac coherence
    table_coherence_history,      # coherence score history with category
    # VO2max
    table_vo2max_history,         # all three model estimates history
    table_vo2max_session,         # single-session detail (model breakdown)
    # Training load
    table_training_load_history,  # daily ATL/CTL/TSB history with zone colours
    summary_training_load,        # dict: atl, ctl, tsb, tsb_zone, ctl_trend
)
```

### Resting HRV tables

```python
# Multi-session history with colour gradients
styler = table_resting_history(features_list)
display(styler)

# Optional: restrict columns
styler = table_resting_history(features_list, cols=["date", "rmssd", "score"])

# Single-session detail (one row per metric, grouped by domain)
styler = table_resting_session(features)
display(styler)
```

`table_resting_history` includes: date · RMSSD · SDNN · mean HR · SD1 · SD2 ·
SD1/SD2 · DFA α1 · ApEn · SampEn · score.  
Green gradient = better (RMSSD, SD1, SD2, score, DFA α1).  Red gradient = better low (mean HR).

### Orthostatic HRV tables

```python
results = [r1, r2, r3]           # list[OrthostaticResult]
dates   = ["2024-01-01", ...]    # optional — defaults to "Session N"

# Side-by-side supine vs standing with delta columns
styler = table_orthostatic_comparison(results, dates=dates)
display(styler)

# Condensed history — key autonomic response indicators
styler = table_orthostatic_history(results, dates=dates)
display(styler)
```

`table_orthostatic_comparison` includes: `supine_*` and `standing_*` columns for
RMSSD, mean HR, SD1, SD2, SD1/SD2, DFA α1, HF_nu, ApEn, SampEn — plus response
indicators (`hr_response`, `lf_hf_change`, `hf_response_pct`, `hf_hr_pct_change`)
and a colour-coded `interpretation` column.

### HRR, drift, coherence, VO2max tables

```python
# Heart Rate Recovery — HRR1/HRR2 with clinical categories
styler = table_hrr_history(hrr_results, dates=dates)
display(styler)

# Cardiac drift — rate (bpm/min), magnitude, R², category
styler = table_drift_history(drift_results, dates=dates)
display(styler)

# Cardiac coherence — score gradient 0–100, derived category
styler = table_coherence_history(coherence_results, dates=dates)
display(styler)

# VO2max — all three model estimates, ACSM fitness category
styler = table_vo2max_history(vo2max_results, dates=dates)
display(styler)

# VO2max single session — model breakdown + inputs
styler = table_vo2max_session(vo2max_result)
display(styler)
```

### Export

```python
# HTML with colours
styler.to_html("report.html")

# Excel with colours (requires openpyxl)
styler.to_excel("report.xlsx", engine="openpyxl")
```

See [`docs/reporting/tables.md`](cardiolab/docs/reporting/tables.md) for the full API reference.

---

## Analytics & Scoring

All scores are stored in the `score` field of each result dataclass and
in the corresponding PostgreSQL column. Values are in **[0–100]**.

### Resting HRV — relative baseline score

The resting score is **relative to the personal baseline** (progressive:
session N scored against sessions 1…N-1). Three complementary functions:

```python
from cardiolab.analytics import readiness_score_multi, readiness_score_nonlinear, readiness_score_composite
from cardiolab.analytics import Baseline

baseline = Baseline.from_features(previous_sessions)

score = readiness_score_multi(current_session, baseline)      # lnRMSSD 45% + HR 25% + 7-day trend 20% + DFA α1 10%
score = readiness_score_nonlinear(current_session, baseline)  # DFA α1 40% (vs history) + SD1 35% + SD1/SD2 25%
score = readiness_score_composite(current_session, baseline)  # weighted combination of both
```

| Score | Interpretation |
|-------|---------------|
| > 60 | Above personal baseline — good recovery |
| 40–60 | Near baseline — normal variability |
| < 40 | Below baseline — possible fatigue or stress |

Since 0.5.0 every component is scored against the athlete's own history:
today's **lnRMSSD** (45 %) and **DFA α1** (10 %, lower is better) against the
previous 28 days in units of the athlete's variability; **resting HR** (25 %);
the **trend** (20 %) — change of the 7-day lnRMSSD mean versus the previous week
in SWC units. Components without enough history stay at 50 (about two weeks).
Details: [`docs/analytics/monitoring.md`](cardiolab/docs/analytics/monitoring.md).

### Training adaptation monitoring — 7-day lnRMSSD (Plews)

The reference approach for monitoring training adaptation (Plews et al. 2012,
2013; Buchheit 2014): 7-day rolling mean of lnRMSSD, its coefficient of variation,
and the smallest worthwhile change band (28-day baseline ± 0.5 SD). Each day gets
a state — `coping`, `normal`, `maladaptation` or `overreaching_risk`.

```python
from cardiolab.analytics import Baseline, monitoring_series
from cardiolab.visualization import plot_ln_rmssd_monitoring
from cardiolab.reporting import table_weekly_monitoring

baseline = Baseline.from_features(history)
monitoring_series(baseline)[-1].state     # 'normal'
plot_ln_rmssd_monitoring(baseline)        # 7-day mean, SWC band, CV
table_weekly_monitoring(baseline)         # one row per week
```

Interpretation guide: [`docs/analytics/monitoring.md`](cardiolab/docs/analytics/monitoring.md).

### Protocol-specific scores — absolute clinical thresholds

For protocols with established scientific thresholds, the score is computed
from the primary metric without needing a personal baseline:

```python
from cardiolab.analytics import hrr_score, coherence_score_100, drift_score, vo2max_score
```

| Protocol | Function | Primary metric | Reference |
|----------|---------|---------------|-----------|
| **HRR** | `hrr_score(hrr_60)` | HRR1 (bpm drop at 60 s) | Cole et al., *NEJM* 1999 |
| **Coherence** | `coherence_score_100(coherence_score)` | % resonance-band peak power | Lehrer & Gevirtz, *Front. Psychol.* 2014 |
| **Drift** | `drift_score(drift_rate)` | Drift rate (bpm/min) | Coyle & González-Alonso, *ESSR* 2001 |
| **VO2max** | `vo2max_score(vo2max)` | VO2max estimate (mL/kg/min) | ACSM Guidelines, 11th ed. 2022 |

**HRR score calibration** (Cole et al. 1999):

| HRR1 (bpm) | Category | Score (~) |
|------------|---------|-----------|
| ≥ 25 | Excellent | ≥ 88 |
| 20–24 | Good | 64–87 |
| 12–19 | Normal | 14–63 |
| < 12 | Impaired | < 14 |

**Coherence score calibration** (Lehrer & Gevirtz 2014):

| Coherence (%) | Clinical level | Score (~) |
|---------------|--------------|-----------|
| ≥ 60 | Good | ≥ 75 |
| 40–59 | Moderate | 25–74 |
| < 40 | Poor | < 25 |

**Drift score calibration** (Coyle & González-Alonso 2001):

| Drift rate (bpm/min) | Category | Score (~) |
|----------------------|---------|-----------|
| < 0.5 | No drift | ≥ 82 |
| 0.5–1.5 | Mild | 55–81 |
| 1.5–3.0 | Moderate | 22–54 |
| > 3.0 | Strong | < 22 |

**VO2max score calibration** (ACSM 2022):

| VO2max (mL/kg/min) | Category | Score (~) |
|--------------------|---------|-----------|
| ≥ 58 | Excellent | ≥ 93 |
| 48–57 | Very good | 70–92 |
| 38–47 | Good | 30–69 |
| 28–37 | Fair | 8–29 |
| < 28 | Poor | < 8 |

### Other analytics

* **Baseline** — rolling 7-session RMSSD mean, median, mean HR
* **Anomaly detection** — three methods: `simple` (% deviation), `zscore`,
  `rolling` (sliding median)
* **Trend** (since 0.5.0) — `linear_trend()`: slope, r² and p-value over a window
  of calendar days; `increasing` / `decreasing` only when significant (p < 0.05)
  **and** the fitted change reaches 5 % of the mean (relative threshold).
  `detect_sustained_decline()` (≥ 5 consecutive values below mean − 0.5 SD),
  `trend_report()` (rolling 7 / 30-day slopes per session). See
  [`docs/analytics/trends.md`](cardiolab/docs/analytics/trends.md).

---

## Database

PostgreSQL persistence via `HRVRepository` (context manager, upsert-safe).
**Eight dedicated tables** — six protocol tables + one raw RR intervals table + one training sessions table:

```python
with HRVRepository.from_env() as repo:
    # Resting HRV
    repo.create_table()
    repo.save_features(features, user_id="<uuid>")
    history = repo.load_features(user_id="<uuid>")

    # Orthostatic
    repo.create_orthostatic_table()
    repo.save_orthostatic(result, user_id="<uuid>", date="2026-05-15")

    # Cardiac coherence
    repo.create_coherence_table()
    repo.save_coherence(coherence_result, user_id="<uuid>", date="2026-05-19")

    # Heart Rate Recovery
    repo.create_hrr_table()
    repo.save_hrr(hrr_result, user_id="<uuid>", date="2026-05-19")

    # Cardiac drift
    repo.create_drift_table()
    repo.save_drift(drift_result, user_id="<uuid>", date="2026-05-19")

    # VO2max estimation
    repo.create_vo2max_table()
    repo.save_vo2max(vo2max_result, user_id="<uuid>", date="2026-05-19")

    # Raw RR intervals (FLOAT[] — stored before protocol analysis for reprocessing)
    repo.create_raw_sessions_table()
    repo.save_raw_session(rr, user_id="<uuid>", date="2026-05-19", protocol="resting",
                          source_file="2026-05-19 07-52.txt")
    rr_back = repo.load_raw_session(user_id="<uuid>", date="2026-05-19", protocol="resting")
    sessions = repo.list_raw_sessions(user_id="<uuid>")           # all protocols
    sessions = repo.list_raw_sessions(user_id="<uuid>", protocol="hrr")  # one protocol

    # Training sessions (ATL/CTL/TSB — v0.2.0)
    # One row per activity — multiple activities per day allowed
    repo.create_training_sessions_table()
    aid = repo.save_training_session(user_id="<uuid>", date="2026-05-19",
                                     duration_min=45.0, sport_type="running", trimp=38.2)
    # aid is a UUID string (activity_id) — keep it to delete later if needed
    repo.save_training_session(user_id="<uuid>", date="2026-05-19",
                               duration_min=30.0, sport_type="strength", trimp=12.5)
    sessions = repo.load_training_sessions(user_id="<uuid>")  # sorted ASC by date, includes activity_id
    # Lookup activities for a date (for interactive deletion)
    matches = repo.find_training_sessions(user_id="<uuid>", date="2026-05-19")
    matches = repo.find_training_sessions(user_id="<uuid>", date="2026-05-19", sport_type="running")
    # Delete a specific activity by its UUID
    deleted = repo.delete_training_session(activity_id=aid)  # True if deleted
```

`sport_type` is validated on save against the sports reference list
(`cardiolab.sports`): labels and synonyms are stored as their code
(`"Course à pied"` → `"running"`), and an unknown sport raises `ValueError`
with the closest one suggested. Offer `list_sports()` in your interface rather
than a free text field — see [`docs/training_load/sports.md`](cardiolab/docs/training_load/sports.md).

Each protocol table includes a `score FLOAT` column (see [Analytics & Scoring](#analytics--scoring)).

See [`examples/README.md`](examples/README.md) for the full step-by-step setup.

---

## Status

| Module | State |
|--------|-------|
| `signals/` — ECGSignal, RRSeries | Implemented |
| `features/` — time, frequency & non-linear domain | Implemented |
| `protocols/resting` | Implemented |
| `protocols/orthostatic` | Implemented |
| `protocols/cardiac_coherence` | Implemented |
| `protocols/hrr` | Implemented |
| `protocols/cardiac_drift` | Implemented |
| `protocols/vo2max` | Implemented |
| `analytics/` — baseline, scoring (all 6 protocols), anomaly, trend | Implemented |
| `database/` — 8 tables (6 protocol + raw RR + training sessions, multi-activity) | Implemented |
| `io/` — CSV & JSON export for all protocols | Implemented |
| `sensors_tools/` — Polar, HRV4Training, Apple Health, Garmin (`.fit` / CSV, sport included) | Implemented |
| `sports.py` — sports reference list, validation on save | Implemented |
| `visualization/` | Implemented |
| `reporting/` — all 6 protocols (9 functions) + training load (2 functions) | Implemented |
| PPG signal support | Planned |
| Training load — Phases 1-6 (DB / TRIMP / ATL-CTL-TSB / Viz / Reporting / Scripts) | Implemented |

**Test coverage:** 1 763 tests (1 708 unit + 55 PostgreSQL integration), 0 failures — 97.0 % coverage (unit + integration, as measured in CI).

**CI/CD:** GitLab [centralised Python pipeline](https://gitlab.com/project-jmilon-devsecops/ci-cd/pipeline-python-centralisee) (CI/CD component `python-package@0.11.1`) — gitleaks, ruff (lint, format, security rules), pytest (with a throwaway PostgreSQL for integration tests), pip-audit, build + `twine check`. Tag `V-x.y.z` → PyPI; tag `V-x.y.z-rcN` → TestPyPI (Trusted Publishing). The tag must match `version` in `pyproject.toml` (`V-0.3.1-rc1` ↔ `0.3.1rc1`).

---

## Philosophy

* scientific approach grounded in published standards
* modularity — each layer is independently testable
* reproducibility — deterministic pipelines
* extensibility — easy to add new protocols or sensors

---

## References

### HRV — Standards and general reviews

* Task Force of the European Society of Cardiology and the North American Society of Pacing and Electrophysiology (1996). Standards of measurement, physiological interpretation and clinical use of Heart Rate Variability. *Circulation*, 93(5), 1043–1065.
* Shaffer, F., & Ginsberg, J. P. (2017). An overview of heart rate variability metrics and norms. *Frontiers in Public Health*, 5, 258. https://doi.org/10.3389/fpubh.2017.00258
* Camm, A. J., et al. (1996). Heart rate variability: standards of measurement, physiological interpretation, and clinical use. *European Heart Journal*, 17(3), 354–381.

### Non-linear features

* Pincus, S. M. (1991). Approximate entropy as a measure of system complexity. *Proceedings of the National Academy of Sciences*, 88(6), 2297–2301. https://doi.org/10.1073/pnas.88.6.2297
* Richman, J. S., & Moorman, J. R. (2000). Physiological time-series analysis using approximate entropy and sample entropy. *American Journal of Physiology — Heart and Circulatory Physiology*, 278(6), H2039–H2049. https://doi.org/10.1152/ajpheart.2000.278.6.H2039
* Peng, C. K., Havlin, S., Stanley, H. E., & Goldberger, A. L. (1995). Quantification of scaling exponents and crossover phenomena in nonstationary heartbeat time series. *Chaos*, 5(1), 82–87. https://doi.org/10.1063/1.166141
* Gronwald, T., & Hoos, O. (2020). Correlation properties of heart rate variability during endurance exercise: A systematic review. *Annals of Noninvasive Electrocardiology*, 25(1), e12697. https://doi.org/10.1111/anec.12697

### Cardiac coherence

* Lehrer, P. M., & Gevirtz, R. (2014). Heart rate variability biofeedback: how and why does it work? *Frontiers in Psychology*, 5, 756. https://doi.org/10.3389/fpsyg.2014.00756
* McCraty, R., & Shaffer, F. (2015). Heart rate variability: new perspectives on physiological mechanisms, assessment of self-regulatory capacity, and health risk. *Global Advances in Health and Medicine*, 4(1), 46–61. https://doi.org/10.7453/gahmj.2014.073
* Shaffer, F., McCraty, R., & Zerr, C. L. (2014). A healthy heart is not a metronome: an integrative review of the heart's anatomy and heart rate variability. *Frontiers in Psychology*, 5, 1040. https://doi.org/10.3389/fpsyg.2014.01040

### Heart Rate Recovery

* Cole, C. R., Blackstone, E. H., Pashkow, F. J., Snader, C. E., & Lauer, M. S. (1999). Heart-rate recovery immediately after exercise as a predictor of mortality. *New England Journal of Medicine*, 341(18), 1351–1357. https://doi.org/10.1056/NEJM199910283411804
* Imai, K., Sato, H., Hori, M., et al. (1994). Vagally mediated heart rate recovery after exercise is accelerated in athletes but blunted in patients with chronic heart failure. *Journal of the American College of Cardiology*, 24(6), 1529–1535. https://doi.org/10.1016/0735-1097(94)90150-3
* Jouven, X., Empana, J. P., Schwartz, P. J., Desnos, M., Courbon, D., & Ducimetière, P. (2005). Heart-rate profile during exercise as a predictor of sudden death. *New England Journal of Medicine*, 352(19), 1951–1958. https://doi.org/10.1056/NEJMoa043012
* Morshedi-Meibodi, A., Larson, M. G., Levy, D., O'Donnell, C. J., & Vasan, R. S. (2002). Heart rate recovery after treadmill exercise testing and risk of cardiovascular disease events (The Framingham Heart Study). *American Journal of Cardiology*, 90(8), 848–852. https://doi.org/10.1016/S0002-9149(02)02801-1

### Cardiac drift

* Coyle, E. F., & González-Alonso, J. (2001). Cardiovascular drift during prolonged exercise: new perspectives. *Exercise and Sport Sciences Reviews*, 29(2), 88–92. https://doi.org/10.1097/00003677-200104000-00009
* Wingo, J. E., & Cureton, K. J. (2006). Cardiovascular responses to exercise with and without hydration. *Medicine & Science in Sports & Exercise*, 38(4), 739–748. https://doi.org/10.1249/01.mss.0000191765.30569.03
* González-Alonso, J., Calbet, J. A., & Nielsen, B. (1999). Metabolic and thermodynamic responses to dehydration-induced reductions in muscle blood flow in exercising humans. *Journal of Physiology*, 520(2), 577–589. https://doi.org/10.1111/j.1469-7793.1999.00577.x

### VO2max estimation

* Uth, N., Sørensen, H., Overgaard, K., & Pedersen, P. K. (2004). Estimation of VO2max from the ratio between HRmax and HRrest — the Heart Rate Ratio Method. *European Journal of Applied Physiology*, 91(1), 111–115. https://doi.org/10.1007/s00421-003-0988-y
* Grant, C. C., Murray, C., Janse van Rensburg, D. C., & Fletcher, L. (2013). A comparison between heart rate and heart rate variability as indicators of cardiac health and fitness. *Frontiers in Physiology*, 4, 337. https://doi.org/10.3389/fphys.2013.00337
* Tanaka, H., Monahan, K. D., & Seals, D. R. (2001). Age-predicted maximal heart rate revisited. *Journal of the American College of Cardiology*, 37(1), 153–156. https://doi.org/10.1016/S0735-1097(00)01054-8
* American College of Sports Medicine. (2022). *ACSM's Guidelines for Exercise Testing and Prescription* (11th ed.). Lippincott Williams & Wilkins.

---

## Related project

**cardioanalysis** → web platform for cardiac analysis

---

## Roadmap

---

### v0.1.0 — Released (2026-05-28)

#### Core pipeline
* [x] Full HRV implementation (time & frequency domain)
* [x] Resting protocol
* [x] Orthostatic protocol with automatic phase detection
* [x] Analytics pipeline (baseline, scoring, anomaly, trend)
* [x] PostgreSQL persistence layer (7 tables — 6 protocol + raw RR intervals)
* [x] Score [0–100] for all protocols (resting: baseline-relative; HRR / coherence / drift / VO2max / orthostatic: clinical thresholds)
* [x] Physiological validation with `PhysiologicalWarning` on `RRSeries`
* [x] `auto_clean` option in the resting and orthostatic protocols
* [x] `to_dict()` export on all result dataclasses
* [x] SD1 / SD2 / SD1:SD2 / DFA α1 non-linear features
* [x] ApEn / SampEn entropy features
* [x] Feature documentation (`docs/features/`)
* [x] Cardiac coherence 5-5 protocol
* [x] Heart Rate Recovery (HRR) protocol
* [x] Cardiac drift protocol
* [x] VO2max estimation (Uth, indicative ln-RMSSD — Esco-Flatt removed in 0.4.0)
* [x] Protocol documentation (`docs/protocols/`)
* [x] CSV & JSON export for all protocols

#### Visualization
* [x] Raw RR signal tachogram with HR secondary axis (`plot_rr_tachogram`)
* [x] RR interval distribution — histogram + Gaussian KDE (`plot_rr_distribution`)
* [x] Raw vs filtered overlay with artefact highlighting (`plot_rr_filtered`)
* [x] Multi-session stacked comparison (`plot_rr_comparison`)
* [x] 2×2 compound summary figure with HRV stats table (`plot_rr_summary`)
* [x] RMSSD and readiness score evolution over time (`plot_resting_evolution`)
* [x] RMSSD evolution with rolling-median overlay (`plot_resting_evolution_rolling`)
* [x] Chart reading guide (`docs/visualization/reading_charts.md`)
* [x] Welch PSD with VLF/LF/HF coloured bands (`plot_psd_welch`)
* [x] AR vs Welch PSD overlay (`plot_psd_comparison`)
* [x] LF/HF balance grouped bars + ratio line (`plot_lf_hf_evolution`)
* [x] HRV radar chart — 5 normalised metrics (`plot_hrv_radar`)
* [x] Sessions × frequency bands heatmap (`plot_spectral_heatmap`)
* [x] Spectral chart reading guide (`docs/visualization/reading_spectral_charts.md`)
* [x] Poincaré scatter with SD1/SD2 ellipse and arrows (`plot_poincare`)
* [x] Supine vs standing Poincaré comparison (`plot_poincare_comparison`)
* [x] SD1/SD2/ratio evolution over sessions (`plot_sd1_sd2_evolution`)
* [x] Cardiac coherence AR PSD with resonance band (`plot_coherence_psd`)
* [x] Cardiac coherence score evolution (`plot_coherence_score_evolution`)
* [x] RR tachogram with respiratory reference (`plot_coherence_tachogram`)
* [x] HR recovery curve with HRR1/HRR2 markers (`plot_hrr_curve`)
* [x] Multi-session HR-drop comparison (`plot_hrr_comparison`)
* [x] Semi-circular HRR1 gauge, red → green (`plot_hrr_gauge`)
* [x] Windowed HR + regression curve with zone background (`plot_drift_curve`)
* [x] Multi-session drift-rate evolution with zone bands (`plot_drift_zones`)
* [x] DFA α1 log-log fluctuation plot with regression line (`plot_dfa_fluctuation`)
* [x] VO2max model comparison bars with ACSM zone bands (`plot_vo2max_comparison`)
* [x] VO2max evolution across sessions with ±10 % uncertainty band (`plot_vo2max_evolution`)
* [x] Semi-circular VO2max fitness gauge, poor → excellent (`plot_vo2max_gauge`)
* [x] Multi-protocol session dashboard — 2×3 grid of 6 mini-plots (`plot_session_dashboard`)
* [x] Longitudinal heatmap — sessions × metrics normalised colour map (`plot_longitudinal_heatmap`)
* [x] Readiness score evolution with rolling band (`plot_readiness_evolution`)
* [x] Per-protocol mini-dashboards — resting, HRR, drift, VO2max, coherence (`plot_*_mini`)

#### Reporting
* [x] Shared formatting infrastructure — colour palettes, gradient builders (`reporting/_core`)
* [x] Resting history table with colour gradients (`table_resting_history`)
* [x] Resting session detail table — one row per metric (`table_resting_session`)
* [x] Orthostatic supine vs standing comparison table (`table_orthostatic_comparison`)
* [x] Orthostatic history table — condensed autonomic response view (`table_orthostatic_history`)
* [x] HRR reporting table — HRR1/HRR2 with clinical categories (`table_hrr_history`)
* [x] Cardiac drift reporting table — rate, magnitude, R², category (`table_drift_history`)
* [x] Cardiac coherence reporting table — score gradient + derived category (`table_coherence_history`)
* [x] VO2max history table — all three model estimates (`table_vo2max_history`)
* [x] VO2max session detail table — model breakdown + inputs (`table_vo2max_session`)

---

### v0.2.3 — Packaging fix (2026-06-03)

No functional changes. Fixed the PyPI sdist size (was 113 MB, exceeding the 100 MB upload
limit) by adding an explicit `[tool.hatch.build.targets.sdist]` inclusion list in
`pyproject.toml`. Versions 0.2.1 and 0.2.2 were intermediate attempts at the same fix.

---

### v0.2.0 — Training load (ATL / CTL / TSB)

**DB change:** one new table `training_sessions` — zero modification to the existing 7 tables.

#### Protocol consistency rule

The readiness score used to compute the TRIMP is drawn from a **single primary protocol** chosen at setup — either `"resting"` or `"orthostatic"` — and never mixed across sessions.

* If `"orthostatic"` is selected, the **supine-phase HRV** (not the orthostatic ΔHR score) feeds the readiness baseline, giving equivalent or better signal quality compared to a standalone resting session.
* If the user switches protocol, the new series starts fresh; the two series are never crossed in baseline or TRIMP computation.

Three load methods (use one consistently per athlete — their scales differ):
```
HRV-based     TRIMP = duration_min × (1 − readiness / 100)       (cardiolab heuristic)
Banister      TRIMP = duration_min × HRR × e^(b × HRR)            (effort heart rate)
Session RPE   load  = duration_min × RPE (0–10, Foster 2001)      (all sports, since 0.5.0)
```
Comparison: [`docs/training_load/atl_ctl_tsb.md`](cardiolab/docs/training_load/atl_ctl_tsb.md#which-method).
With the orthostatic test as primary protocol, the score de forme of the supine phase is
stored with the session (`readiness_score`, since 0.5.0).

Zones are read on the **relative form** — TSB in % of CTL, i.e. 1 − ATL / CTL — so
that they mean the same thing for every load method (changed in 0.5.0; they used
absolute TSB, which only suited one scale):

| Form (% of CTL) | ATL / CTL | Zone |
|-----------------|-----------|------|
| > +20 % | < 0.8 | Fresh / detraining — load too low if it lasts |
| +5 to +20 % | 0.8 – 0.95 | Optimal — rested, ready for a competition or a test |
| −30 to +5 % | 0.95 – 1.3 | Neutral — load in line with the usual level |
| −50 to −30 % | 1.3 – 1.5 | Accumulated fatigue — load rising fast |
| < −50 % | ≥ 1.5 | Overload — load spike |

Bounds after the acute:chronic workload ratio (Gabbett 2016; debated — Impellizzeri
et al. 2020). No zone during the first 42 days. Compute on the whole history and crop
with `TrainingLoad.between()`.

#### Phase 1 — Database ✅
* [x] New table `training_sessions`: `activity_id TEXT PK | user_id | date | duration_min | sport_type | trimp | notes` — one row per activity, multiple activities per day allowed
* [x] `HRVRepository.create_training_sessions_table()`, `save_training_session() → str` (returns `activity_id`), `load_training_sessions()`, `find_training_sessions()`, `delete_training_session()`
* [x] Integration tests `TestTrainingSessionsIntegration` (11 tests)

#### Phase 2 — TRIMP calculation ✅
* [x] `analytics/training_load.py`
  * [x] `trimp_hrv_based(duration_min, readiness_score) → float`
  * [x] `trimp_banister(duration_min, hr_mean, hr_max, hr_rest, sex) → float`
  * [x] `load_readiness_for_date(user_id, date, repo, baseline, protocol) → float | None`
* [x] Unit tests `TestTrimpHrvBased` (12), `TestTrimpBanister` (10) + integration tests (6)

#### Phase 3 — ATL / CTL / TSB ✅
* [x] `compute_atl(trimp, tau=7) → np.ndarray` — 7-day EMA (acute fatigue)
* [x] `compute_ctl(trimp, tau=42) → np.ndarray` — 42-day EMA (chronic fitness)
* [x] `compute_tsb(ctl, atl) → np.ndarray` — TSB = CTL − ATL (form)
* [x] `class TrainingLoad` with `.from_sessions()` and `.to_dataframe()`; gaps filled with TRIMP=0
* [x] Unit tests `TestComputeAtl` (8), `TestComputeCtl` (5), `TestComputeTsb` (5), `TestTrainingLoad` (12)

#### Phase 4 — Visualization ✅
* [x] `visualization/training_load_plots.py`
  * [x] `plot_atl_ctl_tsb()` — dual-axis: CTL + ATL top, TSB with coloured zones bottom
  * [x] `plot_trimp_history()` — TRIMP bar chart coloured by sport type; stacked bars for multi-activity days
  * [x] `plot_tsb_zones()` — coloured zone bands (overload / optimal / fresh / detraining)
* [x] 34 visualization tests

#### Phase 5 — Reporting ✅
* [x] `reporting/training_load_report.py`
  * [x] `table_training_load_history(training_load, caption_text) → pd.Styler` — daily ATL/CTL/TSB history; TSB zone highlighted; CTL green gradient; ATL red gradient
  * [x] `summary_training_load(training_load) → dict` — atl, ctl, tsb, tsb_zone, ctl_trend
* [x] 45 tests in `tests/reporting/test_training_load_report.py`

#### Phase 6 — Local scripts ✅
* [x] `local/main_training_load.py` — log session → TRIMP → save → ATL/CTL/TSB plots
  * TRIMP methods: `hrv` (day's readiness), `banister` (HR sensor), `manual` (readiness typed in), `rpe` (perceived effort, since 0.5.0)
  * Options: `--protocol resting|orthostatic`, `--date`, `--sport`, `--dry-run`, `--save-plot`
  * Interactive `--delete` mode: lookup by (user, date, optional sport); numbered menu when multiple activities
* [x] `local/main_training_load_report.py` — HTML ATL/CTL/TSB report over a period
  * Period filter: `--from / --to` or `--last N` days; KPI summary + table + 3 base64-embedded plots; `--open`

**References:** Banister EW et al. (1991); Morton RH et al. (1990); Foster C et al. (2001)

#### Additional local scripts (added during v0.2.0 development) ✅
* [x] `local/main_report_files.py` — generate an HTML report from `.txt` files, **no database required**
  * `--protocol` is optional — without it, all protocols with available files are included in a single report
  * All tables rendered with `LABELS_FR`; output: `local/reports/<user>_<protocol>_files_<ts>.html`
    (single protocol) or `local/reports/<user>_rapport_complet_<ts>.html` (all protocols)
* [x] `local/main_visualize_files.py` — generate PNG plots from `.txt` files, **no database required**
  * `--protocol` optional (default: all available); `--show` opens the plot interactively
  * All plots rendered with `LABELS_FR`; raw `RRSeries` stored alongside results for HRR comparison

---

### v0.3.0 — Notebooks + Additional sensors — Released (2026-06-12)

**DB change:** none.

* [x] `notebooks/` — 10 thematic notebooks (`00_setup` → `09_sensors`) + README, replacing the monolithic `pipeline-notebook.ipynb`
* [x] `sensors_tools/hrv4training.py` — `parse_hrv4training_csv()`, `to_rrseries()`
* [x] `sensors_tools/apple_health.py` — `parse_apple_health_export()`, `extract_hrv_samples()` (SDNN only — Apple does not export raw RR)
* [x] `sensors_tools/garmin.py` — `parse_garmin_fit()`, `parse_garmin_csv()`, `extract_training_session_garmin()` — optional `[garmin]` extra (`fitparse`)
* [x] Sensor documentation in `cardiolab/docs/sensors/`

See [CHANGELOG.md](CHANGELOG.md#030---2026-06-12) for the full list.

---

### Upcoming versions

The forward-looking roadmap, ordered by priority (P0 → P3), lives in **[ROADMAP.md](ROADMAP.md)**:

| Version | Priority | Theme |
|---------|----------|-------|
| v0.3.1 | P0 | CI pipeline 0.9.0, TestPyPI pre-release — released 2026-10-12 |
| v0.3.2 | P1 | Readiness consistency fix, hygiene, entropy speed-up, sample datasets — released |
| v0.3.3 | P1 | Generic `HRVRepository` — shipped in v0.3.4 |
| v0.3.4 | P1 | Sports reference list, sport validated on save, sport from `.fit` files — released 2026-10-16 |
| v0.4.0 | P1 | Signal reliability — artefact correction, spectral fixes, signal quality, reprocessing — ready 2026-10-18 |
| v0.5.0 | P2 | Athlete longitudinal monitoring — 7-day lnRMSSD, CV, SWC, trends |
| v0.6.0 | P2 | Exercise protocols — DFA α1 thresholds, submaximal test |
| v0.7.0 | P3 | Statistical intelligence — Mahalanobis anomaly |
| v0.8.0 | P3 | Autonomic function tests (Ewing battery) |
| v0.9.0 | P3 | PPG / pulse rate variability |
