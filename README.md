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
├── preprocessing/    → signal cleaning
├── features/         → HRV computation (time, frequency & non-linear)
├── protocols/        → physiological tests
│   ├── resting.py            → standard 5-min resting HRV
│   ├── orthostatic.py        → supine → standing with automatic phase detection
│   ├── cardiac_coherence.py  → paced-breathing resonance score
│   ├── hrr.py                → Heart Rate Recovery post-exercise
│   ├── cardiac_drift.py      → progressive HR increase at constant load
│   └── vo2max.py             → VO2max estimation from HRV (Uth, Esco-Flatt)
├── analytics/        → baseline, scoring, anomaly detection, trend analysis
├── sensors_tools/    → Polar sensor integration
├── database/         → PostgreSQL persistence layer (8 tables)
├── io/               → CSV and JSON export for all protocols
├── reporting/        → tabular reporting (pandas Styler, HTML/Excel export)
│   ├── _core.py          → shared formatters, colour palettes, gradient builders
│   ├── resting.py        → table_resting_history, table_resting_session
│   └── orthostatic.py    → table_orthostatic_comparison, table_orthostatic_history
├── scripts/          → CLI import tools
├── datasets/         → sample recordings (resting/, orthostatic/)
├── docs/             → protocol & feature documentation
│   ├── protocols/    → resting.md, orthostatic.md, cardiac_coherence.md,
│   │                   hrr.md, cardiac_drift.md, vo2max.md
│   ├── features/     → index.md, time_domain.md, frequency_domain.md, nonlinear.md
│   ├── visualization/→ reading_charts.md — how to read each chart type
│   ├── reporting/    → tables.md — reporting API reference
│   └── training_load/→ index.md, training_sessions.md, atl_ctl_tsb.md
└── visualization/    → signal and HRV plots
    ├── resting_plots.py  → RMSSD & readiness score evolution over time
    └── rr_plots.py       → raw RR: tachogram, distribution, filtered,
                            multi-session comparison, 2×2 summary

example/              → step-by-step usage scripts (01 – 10)
tests/                → full unit test suite (1190 tests)
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
| Frequency | Méthode | Spectral estimation method (`welch` / `ar`) |
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
always indicates artefacts. Use `remove_outliers()` to clean the signal, or
pass `auto_clean=True` to any protocol function.

```python
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries
import warnings

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    rr = RRSeries(raw_intervals)  # PhysiologicalWarning if outliers present

rr_clean = rr.remove_outliers()  # or: resting_hrv(rr, auto_clean=True)
```

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
result = resting_hrv(rr, compute_score=True, method="welch")
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
At 0.1 Hz the baroreflex resonates, producing maximal HRV power in the cardiac
resonance band. The **coherence score** quantifies how well power concentrates
at the dominant spectral peak (AR PSD method):

```
coherence_score = peak_window_power / total_resonance_power × 100
```

| Score (%) | Interpretation |
|-----------|---------------|
| ≥ 60 | Good cardiac coherence |
| 40 – 60 | Moderate |
| < 40 | Low — improve breathing cadence |

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

Estimates maximal oxygen uptake from a resting HRV recording using two
complementary models:

| Model | Formula | Precision |
|-------|---------|-----------|
| **Uth et al. (2004)** | `15.3 × (HRmax / HRrest)` | ±10–15 % |
| **Esco & Flatt (2014)** | `18.37 + 0.054 × RMSSD` | ±7–12 % |
| **ln-RMSSD** | `24.89 + 5.97 × ln(RMSSD)` | ±7–12 % |

Fitness categories (ACSM 2022):

| VO2max (mL/kg/min) | Category |
|--------------------|---------|
| ≥ 58 | Excellent |
| 48 – 57 | Very good |
| 38 – 47 | Good |
| 28 – 37 | Fair |
| < 28 | Poor |

```python
from cardiolab.protocols import vo2max_from_hrv
result = vo2max_from_hrv(rr_resting, hr_max=185.0)
# result.vo2max_uth, result.vo2max_esco_flatt, result.fitness_category
```

See [`docs/protocols/vo2max.md`](cardiolab/docs/protocols/vo2max.md) for full protocol instructions.

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
fig = plot_resting_evolution(features_list, scores, labels=dates)
fig.savefig("evolution.png", dpi=150, bbox_inches="tight")

# rolling_rmssd: list[float | None]  (None = no prior baseline)
fig = plot_resting_evolution_rolling(features_list, scores, rolling_rmssd, labels=dates)
fig.savefig("evolution_rolling.png", dpi=150, bbox_inches="tight")
```

Both functions return a `Figure` with two stacked panels (RMSSD top, readiness
score bottom). `None` values in `rolling_rmssd` appear as gaps in the line.
See [`example/10_resting_evolution_plots.py`](example/10_resting_evolution_plots.py)
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
fig = plot_coherence_score_evolution(results, labels=dates)
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
fig = plot_sd1_sd2_evolution(features_list, labels=dates)
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
fig = plot_drift_zones(results, labels=dates)
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
fig = plot_hrr_comparison(rr_list, results, labels=dates)
fig.savefig("hrr_comparison.png", dpi=150, bbox_inches="tight")

# Instant HRR1 gauge (colour-coded by clinical zone)
fig = plot_hrr_gauge(result, title="HRR1 — Session 2026-05-20")
fig.savefig("hrr_gauge.png", dpi=150, bbox_inches="tight")
```

All three functions return a `Figure`.  The comparison chart uses **HR drop from
peak** (starts at 0 for all sessions) so curves with different peak HRs remain
directly comparable.  The gauge spans 0–40 bpm with four clinical zones
colour-coded from red (impaired) to green (excellent) following Cole et al. 1999.

### VO2max estimation — `vo2max_plots`

```python
from cardiolab.visualization.vo2max_plots import (
    plot_vo2max_comparison,  # grouped bars (Uth / Esco-Flatt / ln-RMSSD) + ACSM zones
    plot_vo2max_evolution,   # best-estimate timeline with ±10 % uncertainty band
    plot_vo2max_gauge,       # semi-circular fitness gauge (poor → excellent)
)

result = vo2max_from_hrv(rr_resting, hr_max=185.0)

# Model comparison — 2 or 3 bars depending on whether hr_max was provided
fig = plot_vo2max_comparison(result, title="VO2max — Session 2026-05-20")
fig.savefig("vo2max_comparison.png", dpi=150, bbox_inches="tight")

# Multi-session evolution with uncertainty band
fig = plot_vo2max_evolution(results, labels=dates)
fig.savefig("vo2max_evolution.png", dpi=150, bbox_inches="tight")

# Instant fitness gauge with needle and central category text
fig = plot_vo2max_gauge(result, title="Fitness Gauge — Session 2026-05-20")
fig.savefig("vo2max_gauge.png", dpi=150, bbox_inches="tight")
```

All three functions return a `Figure`.  The best estimate used by the gauge and
evolution chart follows the priority Uth > ln-RMSSD: Uth is the most validated
model when `hr_max` is known, otherwise ln-RMSSD is preferred.  The ±10 %
uncertainty band on the evolution chart reflects the typical model error range
(Uth: ±10–15 %, ln-RMSSD / Esco-Flatt: ±7–12 %).  ACSM zones (< 28 poor,
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
    labels=dates,
)
fig.savefig("heatmap.png", dpi=150, bbox_inches="tight")

# Daily readiness score evolution
fig = plot_readiness_evolution(features_list, labels=dates)
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

score = readiness_score_multi(current_session, baseline)      # RMSSD 35% + HR 20% + DFA α1 25% + trend 20%
score = readiness_score_nonlinear(current_session, baseline)  # DFA α1 40% + SD1 35% + SD1/SD2 25%
score = readiness_score_composite(current_session, baseline)  # weighted combination of both
```

| Score | Interpretation |
|-------|---------------|
| > 60 | Above personal baseline — good recovery |
| 40–60 | Near baseline — normal variability |
| < 40 | Below baseline — possible fatigue or stress |

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
* **Trend** — linear regression on RMSSD history (`increasing`, `stable`,
  `decreasing`)

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
    repo.create_training_sessions_table()
    repo.save_training_session(user_id="<uuid>", date="2026-05-19",
                               duration_min=45.0, sport_type="running", trimp=38.2)
    sessions = repo.load_training_sessions(user_id="<uuid>")  # sorted ASC by date
```

Each protocol table includes a `score FLOAT` column (see [Analytics & Scoring](#analytics--scoring)).

See [`example/README.md`](example/README.md) for the full step-by-step setup.

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
| `database/` — 8 tables (6 protocol + raw RR + training sessions) | Implemented |
| `io/` — CSV & JSON export for all protocols | Implemented |
| `sensors_tools/` — Polar | Implemented |
| `visualization/` | Implemented |
| `reporting/` — all 6 protocols (9 functions) | Implemented |
| PPG signal support | Planned |
| Training load — Phase 1 (DB layer) + Phase 2 (TRIMP) | In progress |

**Test coverage:** 1190 unit tests, 0 failures.

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
* Esco, M. R., & Flatt, A. A. (2014). Ultra-short-term heart rate variability indices for gender identification and automatic prediction of cardiorespiratory fitness. *Sensors*, 14(3), 3934–3952. https://doi.org/10.3390/s140303934
* Nunan, D., Donovan, G., Jakovljevic, D. G., Hodges, L. D., Sandercock, G. R., & Brodie, D. A. (2010). Validity and reliability of short-term heart-rate variability from the Polar S810. *Medicine & Science in Sports & Exercise*, 42(2), 243–250. https://doi.org/10.1249/MSS.0b013e3181b6dd7a
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
* [x] `auto_clean` option in all protocols
* [x] `to_dict()` export on all result dataclasses
* [x] SD1 / SD2 / SD1:SD2 / DFA α1 non-linear features
* [x] ApEn / SampEn entropy features
* [x] Feature documentation (`docs/features/`)
* [x] Cardiac coherence 5-5 protocol
* [x] Heart Rate Recovery (HRR) protocol
* [x] Cardiac drift protocol
* [x] VO2max estimation from HRV (Uth, Esco-Flatt, ln-RMSSD)
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

### v0.2.0 — Training load (ATL / CTL / TSB)

**DB change:** one new table `training_sessions` — zero modification to the existing 7 tables.

#### Protocol consistency rule

The readiness score used to compute the TRIMP is drawn from a **single primary protocol** chosen at setup — either `"resting"` or `"orthostatic"` — and never mixed across sessions.

* If `"orthostatic"` is selected, the **supine-phase HRV** (not the orthostatic ΔHR score) feeds the readiness baseline, giving equivalent or better signal quality compared to a standalone resting session.
* If the user switches protocol, the new series starts fresh; the two series are never crossed in baseline or TRIMP computation.

The TRIMP formula:
```
TRIMP = duration_min × (1 − readiness / 100)
```

| TSB zone | Interpretation |
|----------|---------------|
| > +20 | Detraining — load too low |
| +5 to +20 | Fresh — ready for an intense session |
| −10 to +5 | Optimal — good form |
| < −10 | Fatigued — risk of overtraining |

#### Phase 1 — Database
* [ ] New table `training_sessions`: `user_id | date | duration_min | sport_type | trimp | notes` — UNIQUE `(user_id, date)`
* [ ] `HRVRepository.create_training_sessions_table(table_name)`
* [ ] `HRVRepository.save_training_session(user_id, date, duration_min, sport_type, trimp, notes)` — upsert on `(user_id, date)`
* [ ] `HRVRepository.load_training_sessions(user_id) → list[dict]` — ascending date order
* [ ] Integration tests `TestTrainingSessionsIntegration`

#### Phase 2 — TRIMP calculation
* [ ] `analytics/training_load.py`
  * [ ] `trimp_hrv_based(duration_min, readiness_score) → float`
  * [ ] `trimp_banister(duration_min, hr_mean, hr_max, hr_rest) → float` — Banister 1991, for sensors providing effort HR
* [ ] `load_readiness_for_date(user_id, date, repo, baseline, protocol: Literal["resting", "orthostatic"]) → float | None`
  * Strict: reads only from the declared protocol table, never mixes
  * `"orthostatic"` → `readiness_score_composite(record.supine, baseline)`
  * `"resting"` → `readiness_score_composite(features, baseline)`
  * Returns `None` if no measurement exists for that date (TRIMP not computed)
* [ ] Unit tests — edge cases: `readiness=0`, `readiness=100`, `duration=0`

#### Phase 3 — ATL / CTL / TSB
* [ ] `compute_atl(sessions_df, tau=7) → pd.Series` — 7-day EMA (acute fatigue)
* [ ] `compute_ctl(sessions_df, tau=42) → pd.Series` — 42-day EMA (chronic fitness)
* [ ] `compute_tsb(ctl, atl) → pd.Series` — TSB = CTL − ATL (form)
* [ ] `class TrainingLoad` with `.from_sessions(sessions_list)` and `.to_dataframe()` — columns: `date | trimp | atl | ctl | tsb`
* [ ] Rest days (no session logged) contribute TRIMP = 0 — ATL decays naturally faster than CTL
* [ ] Unit tests — 60-day series with known values, EMA verified at day 7 and day 42, 0-session and 1-session edge cases

#### Phase 4 — Visualization
* [ ] `visualization/training_load_plots.py`
  * [ ] `plot_atl_ctl_tsb(load, title, figsize)` — dual-axis: CTL + ATL top, TSB with coloured zones bottom
  * [ ] `plot_trimp_history(sessions, title, figsize)` — TRIMP bar chart coloured by sport type
  * [ ] `plot_tsb_zones(load, title, figsize)` — coloured zone bands (overload / optimal / fresh / detraining)
* [ ] Visualization tests

#### Phase 5 — Reporting
* [ ] `reporting/training_load_report.py`
  * [ ] `table_training_load_history(sessions) → pd.DataFrame`
  * [ ] `summary_training_load(load) → dict` — current ATL, CTL, TSB, CTL weekly trend
* [ ] Reporting tests

#### Phase 6 — Local scripts
* [ ] `local/main_training_load.py` — log session → compute TRIMP → save → refresh ATL/CTL/TSB chart
* [ ] `local/main_training_load_report.py` — training load report over a chosen period

**References:** Banister EW et al. (1991); Morton RH et al. (1990); Manzi V et al. (2009)

---

### v0.3.0 — Additional sensors

**DB change:** none — new sensor data maps to the existing `training_sessions` and `hrv_raw_sessions` tables.

#### Phase 1 — Garmin
* [ ] `sensors_tools/garmin.py`
  * [ ] `parse_garmin_fit(filepath) → RRSeries` — via `fitparse`
  * [ ] `parse_garmin_csv(filepath) → RRSeries` — Garmin Connect CSV export
  * [ ] `extract_training_session_garmin(filepath) → dict` — duration + HR mean/max for Banister TRIMP
* [ ] Tests with synthetic `.fit` and CSV fixtures

#### Phase 2 — Apple Health
* [ ] `sensors_tools/apple_health.py`
  * [ ] `parse_apple_health_export(xml_path) → list[RRSeries]`
  * [ ] `extract_hrv_samples(xml_path) → list[dict]` — timestamped SDNN / RMSSD
* [ ] Tests with minimal XML fixture

#### Phase 3 — HRV4Training
* [ ] `sensors_tools/hrv4training.py`
  * [ ] `parse_hrv4training_csv(filepath) → list[dict]`
  * [ ] `to_rrseries(row) → RRSeries`
* [ ] Tests

#### Phase 4 — Sensor documentation
* [ ] `docs/sensors/polar.md` — HRV Elite export procedure
* [ ] `docs/sensors/garmin.md` — Garmin Connect `.fit` + CSV export
* [ ] `docs/sensors/apple_health.md` — Apple Health XML export
* [ ] `docs/sensors/hrv4training.md` — HRV4Training CSV export

**Optional dependency:** `fitparse` (Garmin `.fit`) — `[garmin]` extra in `pyproject.toml`

---

### v0.4.0 — Statistical intelligence

**DB change:** optional `ALTER TABLE … ADD COLUMN anomaly_score FLOAT` on protocol tables to cache results — not required for core functionality.

> Note: this version is most useful once the database contains sufficient longitudinal data (~100+ sessions). GMM / HMM and ARIMA models are excluded from this version — the biological variance of HRV makes short-term prediction unreliable, and clustering requires data volumes unlikely to be reached before this point.

#### Phase 1 — Multivariate anomaly detection (Mahalanobis)
* [ ] `analytics/anomaly.py` additions
  * [ ] `mahalanobis_distance(features_matrix, new_point) → float`
  * [ ] `is_multivariate_anomaly(features_matrix, new_point, threshold=3.0) → bool`
  * [ ] `anomaly_report(user_features_history) → pd.DataFrame` — `date | zscore | mahalanobis | is_anomaly`
* [ ] Tests — point equal to mean → distance = 0; clear outlier → distance > threshold

#### Phase 2 — Trend analysis
* [ ] `analytics/trends.py`
  * [ ] `linear_trend(series, window_days) → dict` — slope, r², p-value on sliding window
  * [ ] `detect_sustained_decline(scores, min_sessions=5, threshold=-0.5) → bool`
  * [ ] `trend_report(user_scores_history) → pd.DataFrame` — `date | score | slope_7d | slope_30d | trend_label`
* [ ] Tests — known linear trend → expected slope

#### Phase 3 — Statistical visualisation
* [ ] `visualization/statistical_plots.py`
  * [ ] `plot_anomaly_timeline(report, title, figsize)` — score line with anomaly points highlighted
  * [ ] `plot_trend_overlay(scores, trends, title, figsize)` — raw score + trend line + 95 % CI
* [ ] Tests

---

### Out of scope — parallel repositories

These projects live in separate GitLab repositories and do not affect cardiolab versioning.

| Project | Repository | Depends on | Can start |
|---------|-----------|-----------|-----------|
| `cardioanalysis-api` (FastAPI) | New GitLab repo | cardiolab ≥ v0.2.0 via PyPI | After v0.2.0 published |
| Web interface | New GitLab repo | `cardioanalysis-api` stable | After API v1 stable |
