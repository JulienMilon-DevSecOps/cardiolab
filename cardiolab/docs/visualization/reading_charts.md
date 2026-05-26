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

---

## 11. Cardiac Coherence AR PSD — `plot_coherence_psd`

### What it shows

| Element | Meaning |
|---|---|
| Dark curve | Full AR power spectral density (0–0.5 Hz) |
| Light green fill | Cardiac resonance band (default 0.04–0.26 Hz) |
| Red dashed line | Dominant peak within the resonance band |
| Grey dotted line | Target breathing frequency (0.1 Hz = 6 breaths/min) |
| Annotation box | Coherence score and interpretation |

### How to read it

The cardiac resonance band (0.04–0.26 Hz) covers the frequency range activated by
paced breathing at 4–15 breaths/min.  For the 5-5 pattern (6 breaths/min), the
dominant peak should appear near **0.1 Hz**.

| Peak position | Interpretation |
|---|---|
| Near 0.10 Hz (target line) | Breathing cadence well calibrated |
| Shifted left (< 0.08 Hz) | Breathing too slow — below target cadence |
| Shifted right (> 0.12 Hz) | Breathing too fast — above target cadence |
| Flat or multiple peaks | Irregular breathing — coherence not achieved |

**Coherence score** (annotation box):

| Score | Interpretation |
|---|---|
| ≥ 60 % | Good — dominant peak is narrow and concentrated |
| 40–60 % | Moderate — peak is present but diffuse |
| < 40 % | Low — energy spread across the band, no clear peak |

### API

```python
from cardiolab.visualization.coherence_plots import plot_coherence_psd
from cardiolab.protocols.cardiac_coherence import cardiac_coherence

result = cardiac_coherence(rr)
fig = plot_coherence_psd(rr, result, title="Session 2026-05-20")
fig.savefig("coherence_psd.png", dpi=150, bbox_inches="tight")
```

---

## 12. Coherence Score Evolution — `plot_coherence_score_evolution`

### What it shows

| Element | Meaning |
|---|---|
| Green line + dots | Coherence score per session (0–100 %) |
| Score labels | Numeric value annotated above each point |
| Light green band (≥ 60 %) | Good coherence zone |
| Light yellow band (40–60 %) | Moderate coherence zone |
| Light red band (< 40 %) | Low coherence zone |

### How to read it

Track the progression of coherence score over weeks of practice:

| Trend | Interpretation |
|---|---|
| Stable in green zone | Consistent parasympathetic activation — good practice |
| Gradual rise from red to yellow | Improvement in breathing control |
| Dip below threshold | Stress, fatigue, or irregular session |
| Persistent red zone | Technique needs adjustment |

The **threshold at 60 %** is the commonly used clinical target for cardiac
coherence biofeedback practice (Lehrer & Gevirtz 2014).

### API

```python
from cardiolab.visualization.coherence_plots import plot_coherence_score_evolution

# results: list[CoherenceResult] — one per session
fig = plot_coherence_score_evolution(results, labels=dates)
fig.savefig("coherence_score.png", dpi=150, bbox_inches="tight")
```

---

## 13. Coherence Tachogram — `plot_coherence_tachogram`

### What it shows

| Element | Meaning |
|---|---|
| Blue line + dots | Raw RR tachogram (ms over time) |
| Grey dashed line | Mean RR for the session |
| Red dashed sine | Reference sinusoid at the resonance frequency |
| Light blue band | ±RMSSD band around the mean |
| Annotation box | Coherence score and RMSSD |

### How to read it

The reference sine wave represents the ideal RR oscillation for the measured
resonance frequency.  When the blue RR curve **tracks the sine closely**, the
session shows good cardiac coherence — the vagal system is being driven
rhythmically by the breathing pattern.

| Observation | Interpretation |
|---|---|
| RR follows sine closely, same period | Good synchronisation — high coherence |
| RR oscillates but phase drifts | Breathing cadence inconsistent |
| RR amplitude much smaller than sine | Weak vagal response |
| No visible oscillation | Poor coherence — breathing not entrained |

The **±RMSSD band** shows the range of normal beat-to-beat variation.  During
a good coherence session, the RR amplitude should exceed the RMSSD band,
producing the characteristic large sinusoidal swing.

### API

```python
from cardiolab.visualization.coherence_plots import plot_coherence_tachogram

fig = plot_coherence_tachogram(rr, result, title="Session 2026-05-20")
fig.savefig("coherence_tacho.png", dpi=150, bbox_inches="tight")
```

---

---

## 14. HR Recovery Curve — `plot_hrr_curve`

### What it shows

| Element | Meaning |
|---|---|
| Blue line | Interpolated heart rate (bpm) from peak effort to end of recording |
| Grey dashed line | Peak HR reference |
| Red dotted line + dot | HRR1 marker at t = 60 s |
| Purple dotted line + dot | HRR2 marker at t = 120 s (when available) |
| Double-headed arrows | HR drop (bpm) between peak and the marker time point |
| Text annotation | Drop in bpm and clinical category for each marker |

### How to read it

**Horizontal axis** — time in seconds since peak effort (t = 0).

**Vertical axis** — instantaneous heart rate (bpm), linearly interpolated from
the RR intervals at 4 Hz.

The curve should fall continuously and quickly after the effort stops.
A fast initial drop (steep slope in the first 30–60 s) indicates strong vagal
reactivation.

| Curve shape | Interpretation |
|---|---|
| Steep drop in the first 60 s | Rapid vagal reactivation — good recovery |
| Gradual, slow descent | Delayed vagal reactivation — possible fatigue or deconditioning |
| Plateau or secondary rise | Possible continued sympathetic activation, incomplete recovery |
| HRR1 arrow large (≥ 25 bpm) | Excellent vagal withdrawal reversal — low cardiovascular risk |
| HRR1 arrow small (< 12 bpm) | Impaired recovery — independent predictor of mortality (Cole et al. 1999) |

### HRR1 clinical thresholds (Cole et al. 1999)

| HRR1 drop (bpm) | Category | Risk |
|---|---|---|
| ≥ 25 | Excellent | Very low |
| 20 – 24 | Good | Low |
| 12 – 19 | Normal | Average |
| < 12 | **Impaired** | Elevated — independent mortality predictor |

### API

```python
from cardiolab.visualization.hrr_plots import plot_hrr_curve

fig = plot_hrr_curve(
    rr_post_exercise,           # RRSeries from peak effort onward
    result,                     # HRRResult from heart_rate_recovery()
    fs=4.0,                     # resampling frequency (optional)
    title="Session 2026-05-20",
)
fig.savefig("hrr_curve.png", dpi=150, bbox_inches="tight")
```

---

## 15. HR Recovery Comparison — `plot_hrr_comparison`

### What it shows

Multiple recovery curves superimposed on the same axes, one per session, each
expressed as **HR drop from peak** (bpm): ``HR_peak − HR(t)``.

| Element | Meaning |
|---|---|
| Coloured line per session | HR drop from peak — starts at 0, rises with recovery |
| Coloured dot at 60 s | HRR1 for that session |
| Vertical dashed line at 60 s | Reference for reading HRR1 |
| Background horizontal bands | Clinical zones (impaired / normal / good / excellent) |
| Zone labels (right margin) | Zone name and threshold range |

### Why HR drop and not absolute HR

Expressing recovery as ``HR_peak − HR(t)`` normalises for differences in peak
HR between sessions.  All curves start at 0 and rise as the heart slows, so the
**slope** of each curve directly encodes recovery speed regardless of absolute
fitness level.

### How to read it

| Observation | Interpretation |
|---|---|
| Curve rises faster (steeper) | Better recovery speed that session |
| Dot at 60 s in green zone (≥ 25 bpm) | Excellent HRR1 — strong vagal reactivation |
| Dot at 60 s in red zone (< 12 bpm) | Impaired recovery — rest or investigate |
| Curves trending upward over weeks | Long-term improvement in autonomic recovery capacity |
| Flatter curve vs previous sessions | Possible fatigue or overtraining |

### API

```python
from cardiolab.visualization.hrr_plots import plot_hrr_comparison

fig = plot_hrr_comparison(
    rr_list,            # list[RRSeries] — one per session
    results,            # list[HRRResult]
    labels=dates,       # optional list[str]
    title="Multi-session HRR Comparison",
)
fig.savefig("hrr_comparison.png", dpi=150, bbox_inches="tight")
```

---

## 16. HRR1 Gauge — `plot_hrr_gauge`

### What it shows

A semi-circular (180°) speedometer-style gauge covering 0–40 bpm.

| Element | Meaning |
|---|---|
| Red sector (0–12 bpm) | Impaired zone |
| Orange sector (12–20 bpm) | Normal zone |
| Blue sector (20–25 bpm) | Good zone |
| Green sector (25–40 bpm) | Excellent zone |
| Tick marks with labels | Zone boundary values (0, 12, 20, 25, 40 bpm) |
| Needle | Points to the HRR1 value |
| Central text (large number) | HRR1 value in bpm — colour-matched to category |
| Category label below | Clinical category (Excellent / Good / Normal / Impaired) |

### How to read it

The needle position immediately conveys clinical status without needing to read
a number.  At a glance:

| Needle position | Meaning |
|---|---|
| Far right (green zone) | Excellent recovery — strong vagal reactivation |
| Centre-right (blue zone) | Good recovery |
| Centre-left (orange zone) | Normal — room for improvement |
| Far left (red zone) | Impaired — investigate and prioritise recovery |

**Colour coding** is consistent with the comparison chart background bands, so
the two plots can be read side by side.

### Best used as

A quick-read summary at the end of a session report.  Pair it with
`plot_hrr_curve` for the detailed trajectory and `plot_hrr_comparison` for
the longitudinal trend.

### API

```python
from cardiolab.visualization.hrr_plots import plot_hrr_gauge

fig = plot_hrr_gauge(
    result,                     # HRRResult from heart_rate_recovery()
    title="HRR1 — Session 2026-05-20",
    figsize=(6, 4),
)
fig.savefig("hrr_gauge.png", dpi=150, bbox_inches="tight")
```

---

## 17. Cardiac Drift Curve — `plot_drift_curve`

### What it shows

| Element | Meaning |
|---|---|
| Coloured dots | Mean HR for each non-overlapping window (bpm) |
| Dark dashed line | Linear regression of windowed HR over time |
| Grey dotted horizontal | Initial HR (first window mean) |
| Coloured dotted horizontal | Final HR (last window mean) |
| Tinted background | Category colour — green (no drift) → yellow → orange → red (strong) |
| Annotation box | Drift rate, magnitude, R², category |

### How to read it

**Horizontal axis** — time in minutes since the start of the recording.

**Vertical axis** — mean heart rate (bpm) per window.

**Regression slope** = drift rate in bpm/min.  A positive slope means HR is
rising; a negative slope means HR is falling (may reflect warm-up adaptation or
a recording starting after peak effort).

| Slope | Category | Interpretation |
|---|---|---|
| < 0.5 bpm/min | No drift | Normal thermoregulation at constant load |
| 0.5 – 1.5 | Mild | Monitor hydration; reduce intensity if hot |
| 1.5 – 3.0 | Moderate | Drink soon; consider pace reduction |
| > 3.0 | Strong | Stop or sharply reduce intensity |

**R²** (annotation box) measures how linearly the drift progresses.  High R²
(> 0.7) means a clean, consistent upward trend; low R² suggests irregular HR
behaviour (arrhythmia, pace variations, sensor noise).

**Background tint** provides an at-a-glance category signal: a greenish
background means no significant drift; a reddish background warrants
immediate attention.

### API

```python
from cardiolab.visualization.drift_plots import plot_drift_curve

result = cardiac_drift(rr_exercise, window_sec=60.0)
fig = plot_drift_curve(
    rr_exercise,
    result,
    window_sec=60.0,          # must match cardiac_drift() call
    title="Session 2026-05-20",
)
fig.savefig("drift_curve.png", dpi=150, bbox_inches="tight")
```

---

## 18. Cardiac Drift Zones — `plot_drift_zones`

### What it shows

| Element | Meaning |
|---|---|
| Coloured dots (per session) | |Drift rate| in bpm/min — colour = category |
| Grey connecting line | Session-to-session trend |
| Annotated value above each dot | Numeric drift rate (bpm/min) |
| Horizontal coloured bands | Clinical zones (green / yellow / orange / red) |
| Threshold lines at 0.5, 1.5, 3.0 | Zone boundaries |
| Legend | Zone name and threshold range |

### How to read it

The y-axis uses the **absolute** drift rate so that both upward and downward
progressive HR changes are evaluated against the same clinical thresholds.

| Observation | Interpretation |
|---|---|
| Points consistently in green zone | Good thermoregulation — pace, hydration, conditions stable |
| Gradual upward trend across sessions | Accumulating training load or declining heat tolerance |
| Single spike into orange/red | Isolated event — check hydration, ambient temperature, effort level |
| Points falling back to green | Successful adaptation after rest or protocol adjustment |

**Comparing across sessions over weeks** helps identify whether drift is a
chronic issue (poor fitness or persistent dehydration) versus an acute one
(single hot session, insufficient hydration that day).

### API

```python
from cardiolab.visualization.drift_plots import plot_drift_zones

# results: list[DriftResult] — one per session, chronological order
fig = plot_drift_zones(results, labels=dates, title="Drift Evolution — May 2026")
fig.savefig("drift_zones.png", dpi=150, bbox_inches="tight")
```

---

## See also

- [`docs/features/time_domain.md`](../features/time_domain.md) — RMSSD, SDNN, pNN50 definitions
- [`docs/features/frequency_domain.md`](../features/frequency_domain.md) — LF, HF, LF/HF
- [`docs/hrv_interpretations.md`](../hrv_interpretations.md) — full HRV interpretation guide
- [`docs/protocols/hrr.md`](../protocols/hrr.md) — HRR protocol instructions and clinical references
---

## 19. DFA α1 Fluctuation Plot — `plot_dfa_fluctuation`

### What it shows

| Element | Meaning |
|---|---|
| Blue dots | Each `(n, F(n))` pair on a log-log scale — one per window size |
| Dark dashed line | Linear regression: slope = α1 |
| Green shaded band | Normal α1 zone (0.75 – 1.25) |
| Grey dotted line | α = 0.5 reference (white noise — uncorrelated) |
| Grey dashed line | α = 1.5 reference (Brownian noise — strongly correlated) |
| Annotation box | α1 value, clinical interpretation, number of scales used |

### How to read it

**Horizontal axis** — window size `n` in beats (4 to 16 by default), shown on a log scale with actual beat values as tick labels.

**Vertical axis** — `log F(n)`, the log of the root-mean-square fluctuation at each scale.

**The regression line** fits all points.  Its slope is α1.  A steeper slope (closer to 1.0) means the RR signal has stronger long-range fractal correlations — a hallmark of healthy autonomic regulation.

| α1 range | Interpretation |
|---|---|
| ≈ 0.5 | White noise — no correlation structure, pathological at rest |
| < 0.75 | Below normal — possible overtraining, autonomic impairment |
| 0.75 – 1.25 | **Normal** fractal long-range correlations (green zone) |
| > 1.25 | Strongly correlated — typical during exercise or with artefacts |
| ≈ 1.5 | Brownian noise — maximal correlation |

**The normal zone band** (green fill) visually anchors where the regression line should sit for a healthy resting recording.  If the line runs clearly above or below the band, the signal departs from the expected fractal structure.

### What to look for

| Observation | Interpretation |
|---|---|
| Points well-aligned with the regression line (high R²) | Clean fractal structure — reliable α1 estimate |
| Scattered points, poor alignment | Irregular HR behaviour or short signal |
| Regression line inside the green band | Normal autonomic regulation |
| Line below the green band (α1 < 0.75) | Possible fatigue, overtraining, or pathology |
| Line above the green band (α1 > 1.25) | Possible exercise residue, strong trend, or artefacts |

### Signal length note

DFA requires at least **32 intervals** (2 × n_max with default n_max = 16) to compute two or more valid scales.  Very short recordings will raise `ValueError`.  For resting HRV, a standard 5-minute recording (~350–450 intervals) provides all 13 scales and a reliable α1.

### API

```python
from cardiolab.visualization.nonlinear_plots import plot_dfa_fluctuation

fig = plot_dfa_fluctuation(
    rr,                         # RRSeries — at least 32 intervals
    n_min=4,                    # smallest window size in beats (optional)
    n_max=16,                   # largest window size in beats (optional)
    title="DFA α1 — Session 2026-05-20",
)
fig.savefig("dfa_fluctuation.png", dpi=150, bbox_inches="tight")
```

---

- [`docs/protocols/cardiac_drift.md`](../protocols/cardiac_drift.md) — cardiac drift protocol and thresholds
- [`example/09_rr_signal_plots.py`](../../../../example/09_rr_signal_plots.py) — demonstration of all 5 RR signal functions
- [`example/10_resting_evolution_plots.py`](../../../../example/10_resting_evolution_plots.py) — complete worked example for sections 6 and 7
