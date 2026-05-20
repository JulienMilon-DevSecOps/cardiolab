# Reading cardiolab Charts

This guide explains how to interpret each visualisation produced by
`cardiolab.visualization`. All plots take an `RRSeries` as input and return
a matplotlib `Figure` object that you can save or display.

---

## 1. RR Tachogram — `plot_rr_tachogram`

### What it shows

| Element | Meaning |
|---|---|
| Blue line | Each RR interval over time (ms) — beat by beat |
| Blue dots | Individual beats |
| Dark dashed line | Mean RR → corresponding mean heart rate |
| Translucent blue band | ±1 standard-deviation band around the mean |
| Right axis (bpm) | Non-linear RR → HR conversion (60 000 / RR) |

### How to read it

**Horizontal axis** — recording time in seconds.

**Left axis (ms)** — the longer the interval, the lower the heart rate.
1 000 ms = 60 bpm; 750 ms = 80 bpm.

**Right axis (bpm)** — direct heart rate reading, but the scale is non-linear:
the same vertical distance does not represent the same number of bpm across
different HR zones.

### What to look for

| Observation | Interpretation |
|---|---|
| Wide band (high σ) | Good variability — recovery, dominant parasympathetic tone |
| Narrow band (low σ) | Low variability — fatigue, stress, overtraining |
| Regular oscillations | Normal respiratory sinus arrhythmia |
| Isolated abrupt jumps | Artefacts or ectopic beats — verify with `plot_rr_filtered` |
| Progressive upward drift | HR increasing over time — see `cardiac_drift` protocol |

### Healthy signal (resting)

The blue line oscillates regularly within stable bounds, with a clearly visible
±1 σ band. The oscillations reflect respiratory sinus arrhythmia (inspiration →
shorter RR, expiration → longer RR).

---

## 2. RR Distribution — `plot_rr_distribution`

### What it shows

| Element | Meaning |
|---|---|
| Blue histogram | Frequency of each interval range |
| Dark vertical line | Mean RR |
| Grey dotted lines | ±1 standard deviation |
| KDE curve (right axis) | Smoothed probability density |
| Stats box | n, duration, mean RR, mean HR, σ, min, max |

### How to read it

The RR interval distribution should approximately follow a slightly right-skewed
normal distribution (long tail toward larger intervals).

**Width** (σ or SDNN) — measures overall variability.

**Peak position** — corresponds to the mean RR. Far left → high HR (effort, stress);
far right → low HR (deep rest, athletes).

**Asymmetry** — a tail to the right is normal (slightly longer pauses during
expiration); a marked tail to the left often signals artefacts.

### Comparing states

| State | Distribution shape |
|---|---|
| Recovered at rest | Wide, centred ~800–900 ms, flat KDE |
| Fatigue / stress | Narrow, centred ~600–750 ms, sharp KDE peak |
| Maximal exercise | Very narrow, centred < 600 ms |
| Artefacts present | Isolated tail or secondary peak outside the main distribution |

---

## 3. Raw vs Filtered Signal — `plot_rr_filtered`

### What it shows

The chart is split into two vertical panels:

**Top panel — raw signal**

| Element | Meaning |
|---|---|
| Grey line | Raw tachogram |
| Blue dots | Valid intervals (within [low, high] bounds) |
| Red crosses | Removed artefacts |
| Red dotted horizontal lines | Physiological bounds (default: 300 and 2 000 ms) |

**Bottom panel — filtered signal**

Tachogram after artefact removal + mean line.

### How to read it

The goal is to confirm that **artefacts are few and isolated**.

| Observation | Recommended action |
|---|---|
| 0 red crosses | Clean signal — proceed with analysis normally |
| 1 – 3 isolated artefacts | Acceptable — `remove_outliers()` removes them without biasing metrics |
| > 5 % artefacts | Degraded signal — check sensor placement or signal quality |
| Clustered artefacts | Likely sensor disconnection — consider trimming that segment |

### Physiological bounds

| Bound | Default value | Corresponding HR |
|---|---|---|
| Lower (`low`) | 300 ms | HR > 200 bpm — virtually impossible at rest |
| Upper (`high`) | 2 000 ms | HR < 30 bpm — artefact or pathological sinus pause |

---

## 4. Multi-session Comparison — `plot_rr_comparison`

### What it shows

One panel per session, stacked vertically, each with a secondary HR axis.
All panels share the same vertical range (1st–99th percentile across all sessions)
so amplitude is directly comparable.

### How to read it

**Compare levels (vertical axis)** — a panel higher up (longer intervals)
means a lower heart rate, indicating better recovery.

**Compare oscillation amplitude** — a session with wider vertical excursions
shows greater variability.

**`normalize_time=True` mode** — rescales each recording to 0–100 % of its
duration. Useful for comparing sessions of different lengths without the time
axis being misleading.

### Typical use cases

| Use case | What to look for |
|---|---|
| Week-over-week tracking | Slight upward shift in mean RR level = improvement |
| Before / after intense training | Lower level + narrower band |
| Morning vs evening comparison | Lower morning HR often = good overnight recovery |

---

## 5. 2×2 Summary Figure — `plot_rr_summary`

### Layout

```
┌─────────────────────┬─────────────────────┐
│  A — Tachogram      │  B — Distribution   │
│  (raw signal)       │  Histogram + KDE    │
├─────────────────────┼─────────────────────┤
│  C — Raw vs filtered│  D — HRV Statistics │
│  (red artefacts)    │  Text table         │
└─────────────────────┴─────────────────────┘
```

### Panel D — HRV statistics table

| Metric | Value shown | Resting reference |
|---|---|---|
| n intervals | Number of recorded beats | — |
| Duration | Total duration in seconds | ≥ 300 s recommended |
| Mean RR | Average interval in ms | — |
| Mean HR | Mean heart rate in bpm | 50 – 70 bpm |
| Min HR | HR corresponding to the longest RR | — |
| Max HR | HR corresponding to the shortest RR | — |
| RMSSD | Short-term beat-to-beat variability in ms | > 20 ms |
| SDNN | Overall variability in ms | > 50 ms |
| pNN50 | % of consecutive pairs differing by > 50 ms | > 3 % |
| Artefacts | Intervals outside [300, 2 000] ms | 0 ideal |

**Quick RMSSD reference** (ms, general population, resting):

| RMSSD | Interpretation |
|---|---|
| > 80 | Excellent recovery — high vagal tone |
| 50 – 80 | Good recovery |
| 30 – 50 | Moderate recovery |
| 20 – 30 | Mild fatigue or stress |
| < 20 | Marked fatigue — rest recommended |

> These are population-level benchmarks. Always compare against your own
> personal baseline (`Baseline.from_features()`).

---

## Combined reading — using the 2×2 summary

The summary figure enables a full evaluation in a single pass:

1. **Look at A (tachogram)** — is the ±1 σ band wide or narrow?
   A wide band indicates good variability.

2. **Look at B (distribution)** — is the peak centred on your usual RR?
   Are there abnormal tails suggesting artefacts?

3. **Look at C (filtered)** — are there red crosses? Are they isolated or clustered?

4. **Read D (statistics)** — are RMSSD and SDNN within reference bounds?
   Duration ≥ 300 s? Artefact count acceptable?

### Quick-read grid

| RMSSD | Artefacts | Duration | Conclusion |
|---|---|---|---|
| ↑, wide band | 0 | ≥ 300 s | Clean signal, good recovery state |
| ↓, narrow band | 0 | ≥ 300 s | Clean signal, likely fatigue |
| Any | > 5 % | Any | Re-assess signal quality before drawing conclusions |
| Any | 0 | < 120 s | Insufficient duration — metrics are unreliable |

---

## See also

- [`docs/features/time_domain.md`](../features/time_domain.md) — RMSSD, SDNN, pNN50 definitions
- [`docs/features/frequency_domain.md`](../features/frequency_domain.md) — LF, HF, LF/HF
- [`docs/hrv_interpretations.md`](../hrv_interpretations.md) — full HRV interpretation guide
- [`example/09_rr_signal_plots.py`](../../../../example/09_rr_signal_plots.py) — demonstration of all 5 functions
