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

---

## 6. RMSSD and Readiness Score Evolution — `plot_resting_evolution`

### What it shows

A two-panel stacked figure covering an entire session history.

**Top panel — RMSSD (ms)**

| Element | Meaning |
|---|---|
| Blue line + dots | RMSSD value for each session |
| Grey dashed line | Overall mean RMSSD across all sessions |

**Bottom panel — Readiness score (0–100)**

| Element | Meaning |
|---|---|
| Green line + dots | Readiness score computed from RMSSD and HR |
| Coloured bands | Interpretation zones (see table below) |

### Score interpretation bands

| Band | Colour | Meaning |
|---|---|---|
| 80 – 100 | Light green | Very good recovery — full training load acceptable |
| 60 – 80 | Light yellow | Normal recovery |
| 40 – 60 | Light orange | Moderate fatigue — consider reduced intensity |
| 0 – 40 | Light red | Fatigued — prioritise rest or active recovery |

### How to read it

**Horizontal axis** — sessions in chronological order (one point per day when
data is recorded daily). Labels default to the `date` attribute of each
`HRVFeatures` object.

**RMSSD top panel** — scan for trends rather than individual values.
A consistently rising RMSSD indicates improving recovery over the period.
The grey mean line is a simple reference; prefer the rolling median (see
`plot_resting_evolution_rolling`) for a noise-robust baseline.

**Score bottom panel** — use the coloured bands to quickly categorise each
session. A score that dips into the orange or red zone repeatedly over 3–4
days suggests accumulated fatigue.

### API

```python
from cardiolab.visualization.resting_plots import plot_resting_evolution

fig = plot_resting_evolution(
    features_list,          # list[HRVFeatures] — chronological order
    scores,                 # list[float] — one score per session (0–100)
    labels=dates,           # optional list[str] — x-axis labels
    title="My Evolution",   # optional
    figsize=(12, 7),        # optional
)
fig.savefig("evolution.png", dpi=150, bbox_inches="tight")
```

---

## 7. RMSSD with Rolling Median — `plot_resting_evolution_rolling`

### What it shows

Identical layout to the previous chart but adds a rolling RMSSD median
to the top panel.

**Top panel — RMSSD + rolling median**

| Element | Meaning |
|---|---|
| Blue line + dots | Raw RMSSD per session |
| Orange dashed line + squares | Rolling RMSSD median (7-session window by default) |
| Gap in orange line | `None` entry — no prior baseline available yet |

**Bottom panel** — same readiness score bands as `plot_resting_evolution`.

### Why the rolling median matters

Day-to-day RMSSD fluctuates significantly (stress, sleep quality, digestion,
measurement time). The rolling median smooths this noise and reveals:

| Pattern | Interpretation |
|---|---|
| Blue line consistently above orange | RMSSD trending up — good adaptation |
| Blue line crosses below orange | Single-day drop — could be one poor night |
| Blue line stays below orange for ≥ 3 days | Sustained underperformance — likely accumulated fatigue |
| Rolling median itself rising over weeks | Long-term improvement in autonomic recovery |

### First-session gap

The rolling median requires a prior history window. The first session (and
sometimes the first several sessions) will have `None` as their rolling value,
which appears as a gap in the orange line. This is expected behaviour.

### API

```python
from cardiolab.visualization.resting_plots import plot_resting_evolution_rolling

fig = plot_resting_evolution_rolling(
    features_list,          # list[HRVFeatures]
    scores,                 # list[float]
    rolling_rmssd,          # list[float | None] — None draws a gap
    labels=dates,           # optional list[str]
    title="My Evolution",   # optional
    figsize=(12, 7),        # optional
)
fig.savefig("evolution_rolling.png", dpi=150, bbox_inches="tight")
```

### Computing rolling_rmssd from a Baseline

```python
from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.scoring import readiness_score_oura

all_features, rolling_rmssd, scores = [], [], []
for session_features in chronological_features:
    baseline = Baseline.from_features(all_features) if all_features else Baseline()
    rolling = baseline.rolling_rmssd_median()
    rolling_rmssd.append(float(rolling[-1]) if rolling else None)
    scores.append(readiness_score_oura(session_features, baseline))
    all_features.append(session_features)
```

---

---

## 8. Poincaré Plot — `plot_poincare`

### What it shows

| Element | Meaning |
|---|---|
| Grey dots | Each consecutive pair (RR_n, RR_{n+1}) |
| Dashed grey line | Identity line y = x |
| Dark ellipse | SD1/SD2 fitted ellipse centred on mean RR |
| Blue arrow (SD1) | Short axis — perpendicular to y=x |
| Orange arrow (SD2) | Long axis — along y=x |
| Text box (top-left) | SD1, SD2 and SD1/SD2 ratio |

### How to read it

The Poincaré plot maps each RR interval against the following one.  The shape of
the resulting cloud encodes autonomic tone:

| Shape | SD1 vs SD2 | Interpretation |
|---|---|---|
| Elongated comet | SD1 ≪ SD2 | Sympathetic dominance, low vagal tone |
| Compact oval | SD1 ≈ SD2 | Balanced autonomic regulation |
| Wide round cloud | Both large | High variability, strong parasympathetic tone |
| Tight cluster | Both small | Very low HRV — fatigue, exercise, or pathology |

**SD1** (perpendicular to y=x, blue arrow): short-term beat-to-beat variability.
Mathematically equal to RMSSD / √2.

**SD2** (along y=x, orange arrow): long-term and overall variability.
Mathematically derived from SDNN and SD1.

**SD1/SD2 ratio**: shape index of the ellipse.

| Ratio | Interpretation |
|---|---|
| < 0.25 | Very low — sympathetic dominance |
| 0.25 – 0.55 | Normal resting range |
| > 0.55 | High — parasympathetic dominance |

### API

```python
from cardiolab.visualization.nonlinear_plots import plot_poincare

fig = plot_poincare(rr, title="Session 2026-05-20", figsize=(6, 6))
fig.savefig("poincare.png", dpi=150, bbox_inches="tight")
```

---

## 9. Orthostatic Poincaré Comparison — `plot_poincare_comparison`

### What it shows

Two side-by-side Poincaré plots sharing the same axis range:

| Panel | Colour | Content |
|---|---|---|
| Left — Supine | Blue | Resting lying-down phase |
| Right — Standing | Red | Stabilised standing phase |

Each panel shows the scatter cloud, the SD1/SD2 ellipse, and a stats annotation
box.  Because both panels share the same scale, the geometry change is
immediately visible.

### What to look for

The key signature of the orthostatic reflex is **SD1 contraction on standing**:
the vagal withdrawal triggered by posture change shrinks the short axis of the
ellipse (SD1) while SD2 remains more stable.

| Observation | Interpretation |
|---|---|
| SD1 visibly smaller on right panel | Normal vagal withdrawal on standing |
| SD1 unchanged between panels | Blunted orthostatic response — possible autonomic impairment |
| Both SD1 and SD2 decrease | Global reduction in HRV — general fatigue or deconditioning |
| Right cloud shifted left (lower mean RR) | HR increase on standing — expected (+10–30 bpm) |

### API

```python
from cardiolab.visualization.nonlinear_plots import plot_poincare_comparison

# rr_supine and rr_standing are RRSeries from an OrthstaticResult:
#   result.phases.supine.rr  /  result.phases.standing.rr
fig = plot_poincare_comparison(
    result.phases.supine.rr,
    result.phases.standing.rr,
    label_supine="Supine (5 min)",
    label_standing="Standing (5 min)",
)
fig.savefig("poincare_ortho.png", dpi=150, bbox_inches="tight")
```

---

## 10. SD1 / SD2 Evolution — `plot_sd1_sd2_evolution`

### What it shows

A single figure with two y-axes:

| Element | Axis | Meaning |
|---|---|---|
| Blue line + circles | Left (ms) | SD1 per session — short-term vagal activity |
| Orange line + squares | Left (ms) | SD2 per session — overall autonomic regulation |
| Green dashed + triangles | Right (ratio) | SD1/SD2 ratio — ellipse shape index |

### How to read it

**SD1 trend** — a rising SD1 over days indicates improving vagal tone and
recovery from training load.

**SD2 trend** — SD2 is more stable than SD1 and reflects longer-term autonomic
adaptation.

**Ratio trend** — divergence between SD1 and SD2 is captured by the ratio:

| Ratio trend | Interpretation |
|---|---|
| Falling ratio | SD1 decreasing faster than SD2 — growing sympathetic load |
| Rising ratio | SD1 recovering — parasympathetic reactivation |
| Ratio stable at < 0.3 | Chronic sympathetic dominance — watch for overtraining |

A `float('nan')` SD1/SD2 ratio (SD2 = 0) appears as a gap in the green line.

### API

```python
from cardiolab.visualization.nonlinear_plots import plot_sd1_sd2_evolution

fig = plot_sd1_sd2_evolution(
    features_list,      # list[HRVFeatures] — chronological order
    labels=dates,       # optional list[str]
    title="SD1/SD2 — May 2026",
)
fig.savefig("sd1_sd2_evolution.png", dpi=150, bbox_inches="tight")
```

---

## See also

- [`docs/features/time_domain.md`](../features/time_domain.md) — RMSSD, SDNN, pNN50 definitions
- [`docs/features/frequency_domain.md`](../features/frequency_domain.md) — LF, HF, LF/HF
- [`docs/hrv_interpretations.md`](../hrv_interpretations.md) — full HRV interpretation guide
- [`example/09_rr_signal_plots.py`](../../../../example/09_rr_signal_plots.py) — demonstration of all 5 RR signal functions
- [`example/10_resting_evolution_plots.py`](../../../../example/10_resting_evolution_plots.py) — complete worked example for sections 6 and 7
