# cardiolab

**cardiolab** is a physiological analysis engine dedicated to heart rate and heart rate variability (HRV) analysis.

This project is the scientific core of the **cardioanalysis** product.

---

## Goal

Transform raw physiological signals (ECG, PPG, HR) into:

* reliable metrics (HR, HRV)
* physiological insights (fatigue, recovery)
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
Features (HRV — time & frequency domain)
        ↓
Protocols (resting · orthostatic)
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
├── features/         → HRV computation (time-domain & frequency-domain)
├── protocols/        → physiological tests (resting, orthostatic)
├── analytics/        → baseline, scoring, anomaly detection, trend analysis
├── sensors_tools/    → Polar sensor integration
├── database/         → PostgreSQL persistence layer
├── scripts/          → CLI import tools
├── datasets/         → sample recordings (resting/, orthostatic/)
└── visualization/    → signal and HRV plots

example/              → step-by-step database usage scripts
tests/                → full unit test suite (337 tests)
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

### HRV indicators

15 indicators computed for every protocol phase (all band powers in ms²):

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
| Composite | HF/FC | HF divided by mean HR (ms²/bpm) — HR-normalised vagal activity |
| Meta | Duration | Phase duration (s) |
| Meta | Score | Recovery score (0–100) |

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
and pandas-compatible:

```python
result = resting_hrv(rr)
result.date = "2026-05-17"

# JSON
import json
print(json.dumps(result.to_dict(), indent=2))

# DataFrame
import pandas as pd
df = pd.DataFrame([s.to_dict() for s in sessions])
```

`OrthostaticResult.to_dict()` is nested (`phases.supine / transition / standing`),
each phase containing its `features` dict.

---

## Protocols

### Resting HRV

Standard 5-minute supine recording. Computes all 14 HRV indicators and a
recovery score (Oura-inspired: RMSSD 70 % + HR 30 %).

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

PostgreSQL persistence via `HRVRepository` (context manager, upsert-safe):

```python
with HRVRepository.from_env() as repo:
    repo.create_table()
    repo.save_features(features, user_id="<uuid>")
    history = repo.load_features(user_id="<uuid>")

    repo.create_orthostatic_table()
    repo.save_orthostatic(result, user_id="<uuid>", date="2026-05-15")
    records = repo.load_orthostatic(user_id="<uuid>")
```

See [`example/README.md`](example/README.md) for the full step-by-step setup.

---

## Status

| Module | State |
|--------|-------|
| `signals/` — ECGSignal, RRSeries | Implemented |
| `features/` — time & frequency domain | Implemented |
| `protocols/resting` | Implemented |
| `protocols/orthostatic` | Implemented |
| `analytics/` — baseline, scoring, anomaly, trend | Implemented |
| `database/` — resting + orthostatic | Implemented |
| `sensors_tools/` — Polar | Implemented |
| `visualization/` | Implemented |
| PPG signal support | Planned |

**Test coverage:** 360+ unit tests, 0 failures.

---

## Philosophy

* scientific approach grounded in published standards
* modularity — each layer is independently testable
* reproducibility — deterministic pipelines
* extensibility — easy to add new protocols or sensors

---

## References

* Task Force of the European Society of Cardiology (1996). *Standards of measurement, physiological interpretation and clinical use of Heart Rate Variability.*
* Shaffer, F. & Ginsberg, J.P. (2017). *An Overview of Heart Rate Variability Metrics and Norms.*

---

## Related project

**cardioanalysis** → web platform for cardiac analysis

---

## Roadmap

* [x] Full HRV implementation (time & frequency domain)
* [x] Resting protocol
* [x] Orthostatic protocol with automatic phase detection
* [x] Analytics pipeline (baseline, scoring, anomaly, trend)
* [x] PostgreSQL persistence layer (resting + orthostatic)
* [x] Physiological validation with `PhysiologicalWarning` on `RRSeries`
* [x] `auto_clean` option in all protocols
* [x] `to_dict()` export on all result dataclasses
* [ ] SD1 / SD2 / DFA α1 non-linear features
* [ ] Heart Rate Recovery (HRR) and cardiac drift protocols
* [ ] Training load model (ATL / CTL / TSB)
* [ ] PPG signal support
