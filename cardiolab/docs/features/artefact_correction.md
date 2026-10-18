# Artefact correction — `RRSeries.correct_artifacts()`

Added in v0.4.0. Module: `cardiolab.signals.artifacts`.

```python
corrected, report = rr.correct_artifacts()
report.to_dict()
# {'method': 'lipponen2019', 'n_input': 320, 'n_output': 321, 'ectopic': 0,
#  'missed': 1, 'extra': 0, 'long_short': 0, 'n_corrected': 1,
#  'corrected_pct': 0.31, 'passes': 1}
```

---

## Why correct instead of delete

Every time-domain and non-linear metric works on **successive** intervals.
Deleting an abnormal interval (`remove_outliers()`) joins its two neighbours
into a difference that never existed, and a fixed threshold (300–2000 ms) does
not even see most artefacts: an ectopic beat (≈ 585 ms after 900 ms beats) or
an extra beat split into 360 + 540 ms stays inside the bounds.

Example (`examples/07_auto_clean.py`): one ectopic, one extra and one missed
beat in 400 beats with a true RMSSD of 38.0 ms.

| Cleaning | RMSSD | Beats |
|----------|------:|------:|
| None | 88.7 ms | 400 |
| `remove_outliers()` (threshold) | 88.7 ms | 400 |
| `remove_outliers(method="zscore")` | 37.9 ms | 395 — 5 beats deleted, time axis shifted |
| `correct_artifacts()` | 37.6 ms | 400 |

---

## What is corrected, and how

| Artefact | Typical cause | Correction |
|----------|---------------|------------|
| **Extra beat** | spurious peak (noise, T wave) | merged with the next interval |
| **Missed beat** | undetected peak (≈ 2 × the normal interval) | split in two equal halves |
| **Ectopic beat** | premature beat + compensatory pause | value replaced by cubic-spline interpolation |
| **Long / short beat** | other abnormal interval | value replaced by cubic-spline interpolation |

Total duration is kept for extra and missed beats. Timestamps, if the series
has some, follow added / removed beats.

---

## Detection (Lipponen & Tarvainen, 2019)

1. **Successive differences** `dRR(j) = RR(j) − RR(j−1)`, divided by a
   time-varying threshold `Th1 = 5.2 × QD`, where QD is the quartile deviation
   `(Q3 − Q1) / 2` of `|dRR|` over 91 beats.
2. **Deviation from the local median** `mRR(j) = RR(j) − median₁₁(RR)` (negative
   deviations counted twice), divided by `Th2 = 5.2 × QD(|mRR|)` over 91 beats.
3. **Classification** with the decision rules of the paper: ectopic when a large
   difference is followed by an opposite one (boundary `c1 = 0.13`, `c2 = 0.17`);
   otherwise, a beat with `|dRR| > 1` or `|mRR| > 3` is a **missed** beat if half
   of it matches the local median, an **extra** beat if it plus the next one
   matches the local median, else **long / short**.

One detection / correction pass is applied (`max_passes=1`), as published:
further passes tend to re-flag values that the previous pass interpolated.

### Amplitude gate — protecting trained athletes

The published rules also flag the sharp but **physiological** swings of a strong
respiratory sinus arrhythmia: a slow heart (RR ≈ 1 100–1 300 ms) whose interval
rises over 3 beats then drops by 120 ms. Correcting them would erase real
variability and lower RMSSD — precisely for the athletes cardiolab is built for.

A beat classified **ectopic** or **long / short** is therefore only corrected if it
deviates by at least **20 %** from the 11-beat median (`min_deviation=0.20`, the
classic amplitude criterion of HRV editing). Missed and extra beats keep their own
structural tests. `min_deviation=0` restores the published rules unchanged.

On the author's Polar H10 recordings (`cardiolab.datasets`), the beats flagged by
the published rules alone deviate by 0–19 % (respiratory swings) or 25–58 %
(genuine artefacts): the 20 % gate falls in the gap.

---

## Validation

| Check | Result |
|-------|--------|
| 40 synthetic series × 12 injected artefacts (ectopic, missed, extra, long) | **100 %** detected, no flag outside artefacts |
| Corrected RMSSD vs true RMSSD | median error **1.1 %**, max **3.0 %** (uncorrected: ~ 315 %) |
| 100 clean synthetic series (40 000 beats) | **0** beat corrected |
| Athlete-like signal (strong respiratory arrhythmia) | 0 beat corrected (with the gate) |
| Independent implementation — NeuroKit2 0.2.13, `signal_fixpeaks(method="kubios", iterative=False)`, without the gate | **identical** classifications, beat for beat, on the synthetic series; on the 7 real recordings, identical except one beat (orthostatic, 7 vs 6 — edge handling of the median filter) |
| Author's recordings (`cardiolab.datasets`) | 0–1.06 % corrected; the 1 718 ms missed beat of 2026-04-24 is split (RMSSD 78.5 → 41.1 ms); movement artefacts when standing up (orthostatic test) are corrected |

Tests: `tests/signals/test_artifacts.py`.

---

## Parameters

| Parameter | Default | Effect |
|-----------|---------|--------|
| `method` | `"lipponen2019"` | Only method available |
| `max_passes` | `1` | Number of detection / correction passes |
| `min_deviation` | `0.20` | Amplitude gate for ectopic / long-short beats; `0` disables it |

`ArtifactReport` — `n_input`, `n_output`, `ectopic`, `missed`, `extra`,
`long_short`, `n_corrected`, `corrected_pct`, `is_reliable` (≤ 5 % corrected),
`passes`, `indices`, `to_dict()`. The corrected series stores the report in
`metadata["artifact_correction"]`.

**More than 5 % of beats corrected** → `PhysiologicalWarning`: the recording is
unreliable and should be measured again.

---

## In the protocols — `auto_clean=True`

`resting_hrv()` and `orthostatic_hrv()` run `correct_artifacts()` then remove any
remaining value outside 300–2000 ms (the last two beats of a series are never
classified). Changed in v0.4.0: earlier versions only applied
`remove_outliers()`.

---

## Limits

- Series shorter than 15 intervals are not corrected.
- The last two intervals are never classified (safety net: `auto_clean` removes
  impossible values).
- Long runs of artefacts (several consecutive bad beats, e.g. a loose strap) are
  partly corrected at best: above 5 % corrected, measure again.

---

## Reference

Lipponen, J. A., & Tarvainen, M. P. (2019). A robust algorithm for heart rate
variability time series artefact correction using novel beat classification.
*Journal of Medical Engineering & Technology*, 43(3), 173–181.
