# Frequency-Domain HRV Features

Frequency-domain metrics decompose the variability of the RR series into
distinct frequency bands using spectral analysis. Each band corresponds to a
different physiological regulation loop.

cardiolab supports three PSD estimation methods:

- **Lomb-Scargle periodogram** (default): works on the beat times directly,
  without interpolation — the most accurate and stable estimate on 3–5 minute
  recordings (see [Default method](#default-method)); also suited to irregular
  series (gaps, PPG).
- **Welch's method**: 256 s windows, 50 % overlap — the Kubios standard,
  best on recordings ≥ 10 min.
- **Autoregressive (AR) model** (Yule-Walker): smooth, high-resolution spectrum,
  usable on short segments (< 2 min), e.g. the orthostatic transition.

Changed in v0.4.0: see [Changes in v0.4.0](#changes-in-v040).

---

## How frequency-domain analysis works

1. **Beat times**: each RR value is placed at its beat time — the recorded
   timestamps when they are strictly increasing, otherwise the cumulated RR
   intervals (`RRSeries.beat_times()`).
2. **Interpolation** (Welch, AR): the unevenly spaced series is resampled to a
   uniform 4 Hz grid with a **cubic spline** (`RRSeries.interpolate()`, the only
   interpolation of the package — protocols and charts use it too).
3. **Detrending**: a linear trend is removed (per window for Welch, over the
   whole signal for AR and Lomb-Scargle).
4. **PSD estimation**: the chosen method estimates the one-sided power spectral
   density in ms²/Hz.
5. **Band integration**: the power in each band is the integral of the PSD over
   the band (trapezoidal rule).

---

## PSD Estimation Methods

### Welch's Method (`method="welch"`)

Welch's periodogram splits the interpolated signal into windows of
`window_sec` seconds (default **256 s**, capped to the recording length) with
**50 % overlap**, removes a linear trend from each window, applies a Hann taper,
computes the FFT per window, and averages the squared magnitudes.

| `window_sec` | Samples at 4 Hz | Resolution | Bins in LF (0.04–0.15 Hz) |
|-------------:|----------------:|-----------:|--------------------------:|
| 64 s (before v0.4.0) | 256 | 0.016 Hz | 7 |
| **256 s** (default) | 1 024 | 0.004 Hz | 28 |

**When to use**:
- Resting recordings of ≥ 5 min (standard clinical analysis, Task Force 1996).
- When spectral leakage suppression is important.

**Limitation**: a 5-minute recording holds a single 256 s window — the estimate
is not averaged and varies more from one session to the next than on 10-minute
recordings. A shorter window (`window_sec=128`) averages more windows at the
cost of resolution.

### Autoregressive Method (`method="ar"`)

The AR method fits a parametric model of order *p* (default *p* = 16) to the
interpolated, detrended signal, then evaluates the theoretical PSD of the
fitted model on a fine frequency grid (4 096-point FFT grid: ≈ 0.001 Hz at 4 Hz).

The model parameters are estimated by solving the **Yule-Walker equations**:

$$\mathbf{R} \, \mathbf{a} = \mathbf{r}_{1:p}$$

where **R** is the *p × p* Toeplitz autocorrelation matrix and **a** are the AR
coefficients. The one-sided PSD is:

$$P(f) = \frac{2\,\sigma^2}{f_s \, |A(f)|^2}, \quad
A(f) = 1 - \sum_{k=1}^{p} a_k \, e^{-j2\pi f k / f_s}$$

with σ² the residual noise variance.

**When to use**:
- **Short segments** (< 2 min) — the orthostatic *transition* window is
  typically 20–60 s, where Welch's resolution degrades significantly.
- When a smoother, higher-resolution spectrum is needed.
- Set `method="ar"` on `orthostatic_hrv()` or `resting_hrv()`.

**Limitation**: spectral quality depends on the AR order *p*. Too low an order
under-smooths the spectrum; too high an order may fit noise. The default *p* = 16
is the Task Force 1996 recommendation for HRV.

> Fixed in v0.4.0: the AR PSD was evaluated on a 256-point grid (0.016 Hz). AR
> peaks are narrow, and the band integration missed most of their power — on a
> synthetic 0.1 Hz oscillation of 800 ms², LF came out at 277 ms².

### Lomb-Scargle Periodogram (default: `method="lomb"`)

The Lomb-Scargle periodogram (Lomb, 1976) fits sinusoids directly to the RR
values at their beat times: **no interpolation**, so no smoothing of the HF
band and no invented values in gaps. The series is linearly detrended, the
periodogram is evaluated from 1/(4T) to 0.5 Hz with a step of 1/(4T) (T = recording
duration), and scaled to a one-sided PSD in ms²/Hz (integrated power = variance).

**When to use**:
- Irregular series: recordings with removed beats or gaps, pulse rate from PPG
  (planned for v0.9.0).
- As an interpolation-free cross-check of Welch and AR.

**Limitation**: no taper — strong VLF power leaks slightly into the LF band.

### Choosing a method

| Situation | Method |
|-----------|--------|
| Resting recording 3–10 min, orthostatic phases | `lomb` (default) |
| Recording ≥ 10 min | `welch` or `lomb` |
| Segment < 2 min (orthostatic transition) | `ar` |
| Gaps, removed beats, PPG | `lomb` |

### Default method

60 synthetic RR series per duration, with a known spectrum (VLF 1 500 ms²,
LF 1 200 ms² around 0.10 Hz, HF 600 ms² around 0.25 Hz, many random-phase
components, beat-time sampling). Median of estimated / true value (1.00 = exact)
and dispersion across series (CV):

| Duration | Method | LF | HF | LF/HF |
|----------|--------|----|----|-------|
| 5 min | Welch 256 s | 0.98 ± 27 % | 1.05 ± 19 % | 0.95 ± 33 % |
| 5 min | AR 16 | 1.30 ± 15 % | 1.14 ± 6 % | 1.15 ± 15 % |
| 5 min | **Lomb-Scargle** | 1.06 ± 13 % | 1.03 ± 7 % | **1.00 ± 15 %** |
| 3 min | Welch 256 s | 1.00 ± 35 % | 0.98 ± 29 % | 1.02 ± 58 % |
| 3 min | AR 16 | 1.30 ± 22 % | 1.18 ± 12 % | 1.09 ± 24 % |
| 3 min | **Lomb-Scargle** | 0.99 ± 23 % | 1.04 ± 14 % | **0.98 ± 27 %** |
| 10 min | Welch 256 s | 0.97 ± 9 % | 1.01 ± 7 % | 0.98 ± 11 % |
| 10 min | AR 16 | 1.31 ± 7 % | 1.16 ± 4 % | 1.13 ± 7 % |
| 10 min | Lomb-Scargle | 1.03 ± 6 % | 1.03 ± 6 % | 0.99 ± 8 % |

- **Welch** is unbiased, but a 5-minute recording holds a single 256 s window:
  ± 33 % on LF/HF from one session to the next is larger than most real
  day-to-day changes.
- **AR** is stable but biased upwards: with order 16 at 4 Hz, VLF leaks into LF.
  With a strong VLF (6 000 ms², common at rest) LF is overestimated by ≈ 85 %,
  and the bias then depends on each day's VLF.
- **Lomb-Scargle** is both nearly unbiased and the most stable. Its weak point,
  a slight VLF leakage into LF (+ 23 % with a VLF of 6 000 ms²), is the
  smallest of the two stable methods.

Tests: `TestDefaultMethod` in `tests/features/test_spectral_accuracy.py`.
Changed in v0.4.0: the default was `welch`.
| Comparing sessions | always the **same** method — values from different methods are not interchangeable |

#### API example

```python
from cardiolab.features.frequency_domain import frequency_domain

# Lomb-Scargle (default)
result = frequency_domain(rr)

# Welch
result_w = frequency_domain(rr, method="welch")

# AR, order 16 (Task Force default)
result_ar = frequency_domain(rr, method="ar", order=16)

# AR for a short segment
result_ar = frequency_domain(short_rr, method="ar")

# Welch with a shorter window (more averaging, coarser resolution)
result_w = frequency_domain(rr, method="welch", window_sec=128)

result["VLF_reliable"]  # False if the recording is shorter than 5 min
```

```python
from cardiolab.protocols.resting import resting_hrv
from cardiolab.protocols.orthostatic import orthostatic_hrv

# Use AR for the whole resting session (short recording < 2 min)
features = resting_hrv(rr, method="ar")

# Use AR for all phases of the orthostatic protocol
result = orthostatic_hrv(rr, method="ar")
```

### References

> Task Force of ESC/NASPE (1996). Heart rate variability: Standards of
> measurement, physiological interpretation and clinical use.
> *Circulation*, **93**(5), 1043–1065.
> https://doi.org/10.1161/01.CIR.93.5.1043

> Marple, S. L. (1987). *Digital Spectral Analysis with Applications*.
> Prentice-Hall.

> Lomb, N. R. (1976). Least-squares frequency analysis of unequally spaced
> data. *Astrophysics and Space Science*, **39**(2), 447–462.

> Tarvainen, M. P., Niskanen, J.-P., Lipponen, J. A., Ranta-aho, P. O., &
> Karjalainen, P. A. (2014). Kubios HRV — heart rate variability analysis
> software. *Computer Methods and Programs in Biomedicine*, **113**(1), 210–220.

> Burg, J. P. (1975). *Maximum entropy spectral analysis* (Doctoral
> dissertation). Stanford University.

---

## Band definitions

| Band | Frequency range | Physiological origin |
|------|----------------|----------------------|
| VLF | 0.003 – 0.04 Hz | Thermoregulation, hormones, renin-angiotensin |
| LF | 0.04 – 0.15 Hz | Baroreflex, mixed sympathetic + parasympathetic |
| HF | 0.15 – 0.40 Hz | Respiratory sinus arrhythmia (parasympathetic) |

---

## Absolute band powers

### VLF — Very-Low-Frequency power

**Field**: `vlf` | **Unit**: ms²

VLF reflects very slow oscillations of heart rate driven by thermoregulation,
humoral mechanisms, and the renin-angiotensin system. It requires long
recordings (≥ 5 minutes) for a stable estimate and is **not reliable from
short segments**: `frequency_domain()` returns `VLF_reliable = False` when the
recording is shorter than 5 minutes (`VLF_MIN_DURATION_SEC = 300`).

> In 5-minute recordings, VLF should be interpreted with caution — its estimate
> depends heavily on recording length and is often dominated by low-frequency
> trends rather than true physiological oscillations.

---

### LF — Low-Frequency power

**Field**: `lf` | **Unit**: ms²

LF captures oscillations at 0.04–0.15 Hz, primarily driven by the **baroreflex
arc** (blood pressure feedback to heart rate). The contribution of sympathetic
vs. parasympathetic activity to LF is debated:

- Older literature: LF = sympathetic marker.
- Current consensus: LF reflects **both** branches, with baroreceptor-mediated
  parasympathetic contributions.

Elevated LF in standing or orthostatic tests is a marker of sympathetic
activation. Reduced LF in supine rest may indicate impaired baroreflex.

---

### HF — High-Frequency power

**Field**: `hf` | **Unit**: ms²

HF captures oscillations driven by **respiratory sinus arrhythmia** (RSA): the
heart rate rises during inhalation and falls during exhalation. This modulation
is mediated entirely by the **parasympathetic (vagal) nervous system**. HF is
therefore the most direct frequency-domain marker of vagal tone.

| HF (ms²) | Interpretation |
|----------|----------------|
| < 200 | Very low — sympathetic dominance or low vagal tone |
| 200 – 1 000 | Low-normal |
| 1 000 – 3 000 | Normal resting range |
| > 3 000 | High — strong vagal tone, good recovery |

> **HF is sensitive to respiratory rate**: breathing slower than 0.15 Hz (< 9
> breaths/min) shifts RSA energy below the HF band, causing HF to appear
> falsely low. Natural breathing at rest (12–20 breaths/min) keeps RSA within
> the band.

---

## Derived ratios

### LF/HF — Autonomic balance ratio

**Field**: `lf_hf` | **Unit**: dimensionless

$$\text{LF/HF} = \frac{\text{LF}}{\text{HF}}$$

The LF/HF ratio is widely used as a marker of **sympatho-vagal balance**. A
higher ratio indicates sympathetic dominance; a lower ratio indicates vagal
dominance.

| LF/HF | Interpretation |
|-------|----------------|
| < 0.5 | Vagal dominance — deep rest, parasympathetic state |
| 0.5 – 2.0 | Normal resting balance |
| > 2.0 | Sympathetic activation — stress, mental load, standing |

> **Caution**: LF/HF is not a pure sympathetic marker. Its value is influenced
> by respiratory rate, recording condition, and total power. It should not be
> over-interpreted in isolation.

---

### LF_nu / HF_nu — Normalised units

**Fields**: `lf_nu`, `hf_nu` | **Unit**: dimensionless (0 – 1)

$$\text{LF\_nu} = \frac{\text{LF}}{\text{LF} + \text{HF}}
\qquad
\text{HF\_nu} = \frac{\text{HF}}{\text{LF} + \text{HF}}$$

Normalised units express LF and HF as fractions of the total power *excluding
VLF*. This makes them less sensitive to recording-length-driven VLF variability,
and improves cross-session and cross-subject comparability.

Note: `lf_nu + hf_nu = 1` by construction.

| HF_nu | Interpretation |
|-------|----------------|
| < 0.30 | Low vagal tone — sympathetic dominance |
| 0.30 – 0.60 | Normal |
| > 0.60 | High vagal tone |

---

### HF_pct — HF as fraction of total power

**Field**: `hf_pct` | **Unit**: dimensionless (0 – 1)

$$\text{HF\_pct} = \frac{\text{HF}}{\text{VLF} + \text{LF} + \text{HF}}$$

Similar to HF_nu but includes VLF in the denominator. More sensitive to VLF
fluctuations than HF_nu; useful as a secondary confirmation of HF dominance.

---

### HF/FC — HF power normalised by heart rate

**Field**: `hf_hr` | **Unit**: ms²/bpm

$$\text{HF/FC} = \frac{\text{HF}}{\text{mean\_HR}}$$

HF power scales with heart rate: the same vagal modulation produces more HF
power at low HR than at high HR. Dividing by mean HR **removes this dependency**
and makes HF comparable across sessions with different resting HR.

HF/FC is particularly useful:
- For tracking vagal withdrawal in the **orthostatic protocol** (where HR rises
  sharply on standing).
- For comparing sessions with different resting HR levels.

| HF/FC (ms²/bpm) | Interpretation |
|-----------------|----------------|
| < 10 | Very low vagal activity |
| 10 – 40 | Normal resting range |
| > 40 | High vagal tone |

---

## Recording requirements for frequency-domain metrics

| Metric | Minimum duration | Recommended method |
|--------|-----------------|-------------------|
| HF | 2 min | Welch or AR |
| LF | 4 min | Welch or AR |
| VLF | 5+ min (`VLF_reliable`) | Welch (very sensitive to N) |
| LF/HF | 5 min | Welch or AR |
| Transition HF/LF | 20–60 s | **AR** (Welch resolution insufficient) |

For all metrics, **5 minutes is the recommended minimum** for Welch. The AR
method is specifically recommended for segments shorter than 2 minutes.

---

## Changes in v0.4.0

| Change | Before | From v0.4.0 |
|--------|--------|-------------|
| Interpolation | two linear interpolations (`RRSeries.interpolate`, `_interpolate`) | one **cubic spline** at 4 Hz, on the recorded beat times |
| Welch window | 256 samples = 64 s, 0.016 Hz | **256 s**, 50 % overlap, linear detrend, 0.004 Hz |
| AR grid | 256 points (0.016 Hz) — power of narrow peaks missed | 4 096 points (≈ 0.001 Hz), linear detrend |
| Lomb-Scargle | — | `method="lomb"`, **default** (was `welch`) |
| VLF reliability | — | `VLF_reliable` key (≥ 5 min) |

### Validation

Synthetic RR series (5 min, beat-time sampling) with a 0.10 Hz oscillation of
40 ms and a 0.25 Hz oscillation of 25 ms — expected LF = 800 ms², HF = 312.5 ms²:

| Method | LF (ms²) | HF (ms²) | Peaks |
|--------|---------:|---------:|-------|
| Welch | 792 | 311 | 0.100 / 0.250 Hz |
| AR | 792 | 310 | 0.100 / 0.250 Hz |
| Lomb-Scargle | 792 | 315 | 0.100 / 0.250 Hz |
| AR before v0.4.0 | 277 | 407 | — |

Integrated PSD = signal variance within 1 % (Parseval) for Welch and
Lomb-Scargle. Tests: `tests/features/test_spectral_accuracy.py`.

### Effect on real recordings

Author's Polar H10 recordings (`cardiolab.datasets`), artefacts corrected:

| Recording | Welch LF/HF | AR LF/HF | Lomb LF/HF | Welch HF (ms²) | AR HF (ms²) |
|-----------|------------:|---------:|-----------:|---------------:|------------:|
| resting 2026-04-24 | 3.10 → 3.60 | 3.66 → 3.14 | 2.94 | 385 → 541 | 407 → 575 |
| resting 2026-04-25 (11 min) | 2.95 → 1.86 | 2.92 → 2.34 | 2.88 | 497 → 904 | 510 → 830 |
| resting 2026-04-26 | 3.10 → 2.08 | 3.80 → 3.09 | 3.50 | 686 → 771 | 550 → 859 |
| resting 2026-04-27 | 1.49 → 0.91 | 1.75 → 1.54 | 1.65 | 658 → 713 | 614 → 949 |
| resting 2026-04-28 | 1.66 → 0.84 | 2.12 → 1.85 | 1.88 | 913 → 1 315 | 812 → 1 244 |
| resting 2026-04-30 | 2.59 → 2.35 | 2.31 → 1.89 | 2.10 | 943 → 1 217 | 1 173 → 1 843 |
| orthostatic 2026-05-17 | 0.89 → 0.58 | 0.86 → 0.78 | 1.18 | 1 219 → 2 076 | 1 225 → 1 934 |

- **HF rises by 10–80 %**: linear interpolation smoothed the beat-to-beat
  variations and attenuated the HF band; the cubic spline keeps them.
- **AR is closer to Lomb-Scargle** (the interpolation-free reference): LF/HF
  within ~20 % on the resting recordings.
- **Welch gives a lower LF/HF** on 5-minute recordings: a single tapered 256 s
  window, detrended on its own, keeps less of the slow LF oscillations than AR or
  Lomb-Scargle. Compare sessions with one method only.
- Time-domain and non-linear metrics, the readiness score and the resting score
  do not use spectral values and are unchanged.
