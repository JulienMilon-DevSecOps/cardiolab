# Frequency-Domain HRV Features

Frequency-domain metrics decompose the variability of the RR series into
distinct frequency bands using spectral analysis. Each band corresponds to a
different physiological regulation loop.

cardiolab supports two PSD estimation methods:

- **Welch's method** (default): optimal for long recordings (≥ 5 min).
- **Autoregressive (AR) model** (Yule-Walker): better spectral resolution on
  short segments (< 2 min), recommended for the orthostatic transition phase.

---

## How frequency-domain analysis works

1. **Interpolation**: the unevenly-spaced RR series is resampled to a uniform
   time grid at 4 Hz using linear interpolation.
2. **PSD estimation**: one of two methods (see below) estimates the one-sided
   power spectral density in ms²/Hz.
3. **Band integration**: the power in each frequency band is obtained by
   integrating the PSD over the band's frequency range (trapezoidal rule).

---

## PSD Estimation Methods

### Welch's Method (default: `method="welch"`)

Welch's periodogram divides the interpolated signal into overlapping windows
(default 256 samples), applies a Hann taper, computes the FFT per window, and
averages the squared magnitudes.

**When to use**:
- Long resting recordings (≥ 5 min, ≥ 256 samples after interpolation).
- When spectral leakage suppression is important.
- Standard clinical HRV analysis (Task Force 1996 recommendation).

**Limitation**: spectral resolution is limited by segment length. Short segments
produce a coarse, noisy spectrum.

### Autoregressive Method (`method="ar"`)

The AR method fits a parametric model of order *p* (default *p* = 16) to the
interpolated signal, then evaluates the theoretical PSD of the fitted model on
a 256-point frequency grid.

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

#### API example

```python
from cardiolab.features.frequency_domain import frequency_domain

# Welch (default)
result = frequency_domain(rr)

# AR, order 16 (Task Force default)
result_ar = frequency_domain(rr, method="ar", order=16)

# AR for a short segment
result_ar = frequency_domain(short_rr, method="ar")
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
short segments**.

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
| VLF | 5+ min | Welch only (very sensitive to N) |
| LF/HF | 5 min | Welch or AR |
| Transition HF/LF | 20–60 s | **AR** (Welch resolution insufficient) |

For all metrics, **5 minutes is the recommended minimum** for Welch. The AR
method is specifically recommended for segments shorter than 2 minutes.
