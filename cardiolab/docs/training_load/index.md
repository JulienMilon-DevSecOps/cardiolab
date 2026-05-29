# Training Load — Index

This section covers the training load model built into cardiolab.
Training load quantifies the physiological stress imposed by exercise sessions
and tracks the balance between fatigue and fitness over time.

---

## Documents

| File | Content |
|------|---------|
| [training_sessions.md](training_sessions.md) | What a training session is, how to log one, database schema, repository API |
| [atl_ctl_tsb.md](atl_ctl_tsb.md) | ATL / CTL / TSB model — principle, formulas, TRIMP, protocol consistency rule, TSB zones, references |

---

## Overview

The model is built in three layers:

```
Training session (duration + sport type)
        ↓
TRIMP  (Training Impulse — depends on daily readiness from HRV protocol)
        ↓
ATL / CTL / TSB  (computed on-the-fly from the TRIMP time series)
```

**ATL** (Acute Training Load) — short-term fatigue accumulator (7-day EMA).  
**CTL** (Chronic Training Load) — long-term fitness accumulator (42-day EMA).  
**TSB** (Training Stress Balance) — form = CTL − ATL.

See [atl_ctl_tsb.md](atl_ctl_tsb.md) for the full mathematical model and
[training_sessions.md](training_sessions.md) for the data layer.
