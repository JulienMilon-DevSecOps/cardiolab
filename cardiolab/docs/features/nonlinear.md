# Non-Linear HRV Features

Non-linear HRV metrics go beyond mean and variability to capture the
**structure and complexity** of the heartbeat sequence. They reveal fractal
properties and correlation patterns that linear methods miss, and are
particularly valuable for detecting early signs of overtraining, fatigue, and
cardiovascular disease.

cardiolab computes two families of non-linear metrics:
- **Poincaré plot analysis** (SD1, SD2, SD1/SD2) — geometric, intuitive.
- **Detrended Fluctuation Analysis** (DFA α1) — fractal correlation structure.

---

## Poincaré Plot Analysis

A **Poincaré plot** is a scatter plot where each point represents a pair of
consecutive RR intervals: the x-axis shows RR_n and the y-axis shows RR_{n+1}.
In a healthy heart at rest, the cloud of points forms a characteristic
**elongated ellipse** aligned along the identity line (x = y).

```
RR_{n+1}
    │     .   .
    │   . . . . .
    │  . . . . . .
    │   . . . . .
    │     .   .
    └──────────────── RR_n
```

The width of this ellipse (perpendicular to the identity line) is **SD1**.
The length of the ellipse (along the identity line) is **SD2**.

---

### SD1 — Short-term Poincaré variability

**Field**: `sd1` | **Unit**: ms

#### Definition

$$\text{SD1} = \frac{\text{RMSSD}}{\sqrt{2}}$$

This equivalence is exact: SD1 is simply RMSSD rescaled to the Poincaré
geometry. It represents the **standard deviation of the perpendicular distance**
from each point to the identity line.

#### Physiological background

SD1 captures **beat-to-beat variability** driven by the parasympathetic nervous
system. It is mathematically equivalent to RMSSD and reflects the same
physiology — the Poincaré representation makes it visually intuitive.

A wide Poincaré ellipse (large SD1) means consecutive beats vary substantially
→ strong vagal modulation. A narrow ellipse (small SD1) means beats are nearly
identical → sympathetic dominance or low vagal tone.

#### Reference values (5-minute resting supine)

| SD1 (ms) | Interpretation |
|----------|----------------|
| < 15 | Very low — possible fatigue or sympathetic dominance |
| 15 – 30 | Low |
| 30 – 50 | Normal |
| > 50 | High — strong vagal tone |

#### Notes

- Directly equivalent to RMSSD / √2. Both fields are always coherent.
- Reliable from 2-minute recordings.

---

### SD2 — Long-term Poincaré variability

**Field**: `sd2` | **Unit**: ms

#### Definition

$$\text{SD2} = \sqrt{2 \cdot \text{SDNN}^2 - \text{SD1}^2}$$

SD2 represents the **standard deviation of the distance along the identity
line** — the length of the Poincaré ellipse.

#### Physiological background

SD2 reflects **long-term variability** including both slow (LF-band) sympathetic
oscillations and fast (HF-band) parasympathetic oscillations. It is closely
related to SDNN and captures overall autonomic regulation over the recording
window.

- Large SD2: strong overall HRV, good autonomic regulation.
- Small SD2: reduced autonomic flexibility — may indicate deconditioning,
  illness, or chronic fatigue.

In a healthy resting person, SD2 > SD1 (the ellipse is longer than it is wide).

#### Reference values (5-minute resting supine)

| SD2 (ms) | Interpretation |
|----------|----------------|
| < 30 | Very low |
| 30 – 70 | Low |
| 70 – 120 | Normal |
| > 120 | High |

---

### SD1/SD2 — Poincaré ellipse shape

**Field**: `sd_ratio` | **Unit**: dimensionless

#### Definition

$$\text{SD1/SD2} = \frac{\text{SD1}}{\text{SD2}}$$

#### Physiological background

SD1/SD2 describes the **shape** of the Poincaré cloud:

- **SD1/SD2 = 1**: circular cloud — equal short- and long-term variability.
- **SD1/SD2 < 1**: elongated ellipse — long-term variability dominates
  (typical at rest).
- **SD1/SD2 → 0**: nearly flat ellipse — minimal beat-to-beat variation
  relative to slower oscillations.

A **decreasing SD1/SD2** (narrowing ellipse) over a training block may indicate
accumulating fatigue, as SD1 drops faster than SD2. An **increasing SD1/SD2**
(more circular cloud) after a recovery week signals parasympathetic rebound.

#### Reference values (resting supine)

| SD1/SD2 | Interpretation |
|---------|----------------|
| < 0.25 | Low — sympathetic dominance or high-intensity training load |
| 0.25 – 0.55 | Normal resting range |
| > 0.55 | High — possible parasympathetic dominance |

#### Notes

- Returns `nan` if SD2 = 0 (degenerate case with a perfectly regular series).
- Complement to LF/HF ratio: both measure autonomic balance from different
  perspectives.

---

## Detrended Fluctuation Analysis (DFA α1)

**Field**: `dfa_alpha1` | **Unit**: dimensionless

### Definition

DFA quantifies **long-range fractal correlations** in the RR series. The
short-term exponent **α1** is estimated from window sizes in the range 4–16
beats.

**Algorithm**:

1. Compute the integrated signal (cumulative deviation from mean):
   $$y(k) = \sum_{i=1}^{k} (RR_i - \overline{RR})$$

2. For each window size *n*:
   a. Divide *y* into non-overlapping windows of size *n*.
   b. Fit a linear trend to each window (detrending).
   c. Compute the root-mean-square of residuals: *F(n)*.

3. Fit a log-log regression: $\log F(n) \approx \alpha \cdot \log n + C$.

The slope of this regression is **α1** (short-term, using n = 4–16 beats).

### Physiological background

A healthy resting heartbeat sequence is **not random** — successive beats have
long-range correlations. The degree of this correlation is captured by α1:

- **α1 ≈ 0.5**: uncorrelated (white noise) — seen in severe cardiac disease or
  completely arrhythmic patients.
- **α1 ≈ 1.0**: 1/f noise — fractal, self-similar, long-range correlations.
  This is the target zone for healthy resting HR.
- **α1 ≈ 1.5**: Brownian motion (random walk) — seen during vigorous exercise
  when heart rate follows a strongly correlated trajectory.
- **α1 < 0.75**: possible pathological or overtraining state — loss of fractal
  organisation in the HR control.

### Reference values

| α1 | Interpretation |
|----|----------------|
| < 0.5 | Pathological — arrhythmia, severe autonomic dysfunction |
| 0.5 – 0.75 | Low — possible overtraining, illness, or poor recovery |
| 0.75 – 1.25 | Normal resting range — healthy fractal organisation |
| 1.25 – 1.5 | Elevated — transitional state, moderate exercise |
| > 1.5 | Very high — vigorous exercise or non-stationary recording |

### DFA α1 in sports monitoring

DFA α1 at rest < 0.75 is an early indicator of overreaching and has been
validated as a marker of accumulated training stress:

- **Fresh / well-recovered**: α1 ≈ 1.0–1.2.
- **Moderately fatigued**: α1 ≈ 0.75–1.0.
- **Overreaching**: α1 < 0.75.

A **trending decrease in α1 over a training block** (e.g. 1.1 → 0.8 over 3
weeks) signals that recovery is not keeping pace with load.

### DFA α1 during exercise

At exercise intensities above the first ventilatory threshold (VT1), α1
transitions from ≈ 1.0 toward 1.5 and above. The threshold where α1 = 0.75 has
been proposed as a non-invasive intensity marker for the **aerobic threshold**
(Gronwald & Hoos, 2020 review). This application requires sub-maximal exercise
protocols and is not the primary use case in cardiolab's resting protocol.

### Minimum requirements

DFA α1 requires:
- At least **2 × n_max** intervals (32 beats for the default n_max = 16).
- Returns `float('nan')` for series that are too short.
- Reliable estimates typically require **100+ intervals** (≈ 1–2 minutes at
  rest).

---

## Comparing linear and non-linear metrics

| Situation | RMSSD / SD1 | LF/HF | SD1/SD2 | DFA α1 |
|-----------|-------------|-------|---------|---------|
| Good recovery | High | Low | Normal | ≈ 1.0–1.2 |
| Acute stress | Low | High | Low | ↓ or ↑ |
| Overtraining | Low | Variable | Low | < 0.75 |
| Endurance athlete (trained) | High | Low | Normal | ≈ 1.0–1.1 |
| Vigorous exercise | ↓ | ↑ | Low | > 1.5 |
| Illness | Low | Variable | Low | Variable |

Non-linear metrics add an **independent dimension** to HRV analysis: two
athletes with the same RMSSD can have very different DFA α1 values, revealing
different underlying regulatory dynamics.
