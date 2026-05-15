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
Raw signal (ECG / PPG)
        ↓
Preprocessing
        ↓
RR intervals
        ↓
Features (HRV)
        ↓
Protocols
        ↓
Scoring
        ↓
Analytics
```

---

## Project structure

```
cardiolab/
│
├── signals/          → raw data (ECG, PPG, RR)
├── preprocessing/    → signal cleaning
├── transformations/  → conversion (ECG → RR)
├── features/         → HRV computation
├── protocols/        → physiological tests
├── scoring/          → scores (fatigue, readiness)
├── analytics/        → long-term analysis
├── models/           → business objects
└── validation/       → scientific validation
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

---

## Status

Work in progress.

Currently implemented modules:

* `ECGSignal` — raw ECG signal representation and R-peak detection
* `RRSeries` — RR interval series with cleaning, interpolation and segmentation
* `features/` — time-domain and frequency-domain HRV metrics
* `protocols/` — resting HRV protocol
* `analytics/` — baseline, scoring, anomaly detection, trend analysis
* `database/` — PostgreSQL persistence layer

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

* [ ] Full HRV implementation
* [ ] Additional physiological protocols
* [ ] PPG signal support

---

## Note

This package is in the design phase and is not yet distributed.
