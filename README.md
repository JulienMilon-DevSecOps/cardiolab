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
├── database/         → PostgreSQL persistence layer (6 tables)
├── io/               → CSV and JSON export for all protocols
├── scripts/          → CLI import tools
├── datasets/         → sample recordings (resting/, orthostatic/)
├── docs/             → protocol & feature documentation
│   ├── protocols/    → resting.md, orthostatic.md, cardiac_coherence.md,
│   │                   hrr.md, cardiac_drift.md, vo2max.md
│   ├── features/     → index.md, time_domain.md, frequency_domain.md, nonlinear.md
│   └── visualization/→ reading_charts.md — how to read each chart type
└── visualization/    → signal and HRV plots
    ├── resting_plots.py  → RMSSD & readiness score evolution over time
    └── rr_plots.py       → raw RR: tachogram, distribution, filtered,
                            multi-session comparison, 2×2 summary

example/              → step-by-step usage scripts (01 – 10)
tests/                → full unit test suite (621 tests)
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
| Meta | Score | Recovery score (0–1) |

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
```

All three functions return a `Figure`.  The comparison function uses a shared
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

---

## Analytics

* **Baseline** — rolling 7-session RMSSD mean, median, mean HR
* **Scoring** — Oura-inspired (RMSSD 70 % + HR 30 %) and multi-factor
  (RMSSD + HR + HF_nu + trend)
* **Anomaly detection** — three methods: `simple` (% deviation), `zscore`,
  `rolling` (sliding median)
* **Trend** — linear regression on RMSSD history (`increasing`, `stable`,
  `decreasing`)

---

## Database

PostgreSQL persistence via `HRVRepository` (context manager, upsert-safe).
Six dedicated tables, one per protocol:

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
```

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
| `analytics/` — baseline, scoring, anomaly, trend | Implemented |
| `database/` — 6 protocol tables | Implemented |
| `io/` — CSV & JSON export for all protocols | Implemented |
| `sensors_tools/` — Polar | Implemented |
| `visualization/` | Implemented |
| PPG signal support | Planned |
| Training load model (ATL / CTL / TSB) | Planned |

**Test coverage:** 584+ unit tests, 0 failures.

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

### Core pipeline
* [x] Full HRV implementation (time & frequency domain)
* [x] Resting protocol
* [x] Orthostatic protocol with automatic phase detection
* [x] Analytics pipeline (baseline, scoring, anomaly, trend)
* [x] PostgreSQL persistence layer (6 protocol tables)
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
* [ ] Training load model (ATL / CTL / TSB)
* [ ] PPG signal support

### Visualization
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
* [ ] DFA α1 fluctuation plot — log-log scale with α1 regression line
* [ ] VO2max evolution across sessions
* [ ] Multi-protocol recovery dashboard — side-by-side session comparison
