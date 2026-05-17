# Frequency-Domain HRV Features

Frequency-domain metrics decompose the variability of the RR series into
distinct frequency bands using spectral analysis. Each band corresponds to a
different physiological regulation loop.

cardiolab uses **Welch's method** on a 4 Hz cubic-spline interpolation of the
RR series to estimate the power spectral density (PSD).

---

## How frequency-domain analysis works

1. **Interpolation**: the unevenly-spaced RR series is resampled to a uniform
   time grid at 4 Hz using cubic spline interpolation.
2. **PSD estimation**: Welch's method divides the signal into overlapping
   windows, applies a Hann taper, computes the FFT per window, and averages the
   squared magnitudes.
3. **Band integration**: the power in each frequency band is obtained by
   integrating (summing) the PSD over the band's frequency range.

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

| Metric | Minimum duration | Notes |
|--------|-----------------|-------|
| HF | 2 min | Reliable from short recordings |
| LF | 4 min | Needs at least 2–3 full LF cycles (~25 s each) |
| VLF | 5+ min | Very sensitive to recording length |
| LF/HF | 5 min | Computed from LF and HF |

For all metrics, **5 minutes is the recommended minimum**. Below 2 minutes,
frequency-domain estimates should not be used for clinical decisions.
