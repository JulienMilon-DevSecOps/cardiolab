# Reading Spectral HRV Charts

This guide explains how to interpret the five frequency-domain visualisations
produced by `cardiolab.visualization.spectral_plots`.

---

## Frequency band definitions

All spectral charts use the same physiological band boundaries:

| Band | Range | Physiology |
|---|---|---|
| VLF | 0.003 – 0.04 Hz | Very low frequency — hormonal, thermoregulatory, vasomotor control |
| LF  | 0.04 – 0.15 Hz | Low frequency — baroreflex, mix of sympathetic and parasympathetic |
| HF  | 0.15 – 0.40 Hz | High frequency — respiratory sinus arrhythmia, parasympathetic tone |

**Colour code** used consistently across all charts:
VLF = violet `#8e44ad`, LF = blue `#2980b9`, HF = green `#27ae60`.

---

## 1. PSD with Band Fills — `plot_psd_welch`

### What it shows

| Element | Meaning |
|---|---|
| Dark line | PSD curve (ms²/Hz) — overall spectral shape |
| Violet fill | VLF band power |
| Blue fill | LF band power |
| Green fill | HF band power |
| Dotted verticals | Band boundaries at 0.04, 0.15, 0.40 Hz |
| Power annotation box | Integrated power in each band (ms²) |

### How to read it

**Peaks**: each physiological system produces a characteristic peak in the PSD.
The LF peak (~ 0.1 Hz) reflects baroreflex oscillations; the HF peak (~ 0.25 Hz,
breathing rate) reflects respiratory sinus arrhythmia.

**Band power**: the area under the curve within each coloured region corresponds
to the integrated power annotated in the legend box.

**Method choice** (`method="welch"` vs `"ar"`):

| Method | Characteristics |
|---|---|
| Welch | Smoothed estimate, optimal for recordings ≥ 5 min. Default choice. |
| AR (Yule-Walker) | Sharper peaks, better for short recordings (1–3 min). Order 16 is a good default. |

### Healthy resting PSD

A well-recovered resting recording shows:
- Dominant HF peak (parasympathetic predominance).
- Visible LF peak at ~ 0.1 Hz.
- VLF power present but not dominant.

High stress or fatigue shifts power from HF to LF, raising the LF/HF ratio.

---

## 2. AR vs Welch Overlay — `plot_psd_comparison`

### What it shows

Both curves are drawn on the same axis:
- **Solid blue line** — Welch PSD (smoothed)
- **Dashed red line** — AR PSD (sharper peaks)
- Band fills from the Welch estimate (at 25 % alpha)

### How to read it

**Agreement between curves**: if both methods produce peaks at the same
frequencies, the result is reliable regardless of method choice.

**Divergence**: large differences indicate a recording at the edge of one
method's validity range:
- Welch needs ≥ 256 interpolated samples (≈ 64 s at 4 Hz) for full resolution.
- AR over-fits on very long recordings if the model order is too low.

### When to use this chart

Use `plot_psd_comparison` for quality control — especially for recordings
shorter than 5 minutes or when PSD peaks seem unusual.

---

## 3. LF/HF Balance Evolution — `plot_lf_hf_evolution`

### What it shows

| Element | Meaning |
|---|---|
| Blue bars | LF_nu per session |
| Green bars | HF_nu per session |
| Red diamond line | LF/HF ratio (right axis) |
| Grey dotted line at 0.5 | Balance reference (LF_nu = HF_nu) |
| Red dotted line at 1.0 | LF/HF = 1 reference |

**LF_nu + HF_nu = 1** by construction, so the two adjacent bars are
complementary — a taller LF bar means a shorter HF bar by the same amount.

### How to read it

**LF/HF ratio**:
| LF/HF | Interpretation |
|---|---|
| < 1.0 | Parasympathetic dominance — good recovery |
| ≈ 1.0 | Autonomic balance |
| > 2.0 | Sympathetic dominance — stress, fatigue, or intense training load |
| > 4.0 | Marked sympathetic excess — warrants attention |

**Longitudinal trend**: a progressive increase in LF/HF over consecutive days
suggests accumulating fatigue; a return to low LF/HF after a rest day confirms
recovery.

**LF_nu alone is not a pure sympathetic marker** — LF reflects both sympathetic
and parasympathetic influences. Interpret it alongside HF_nu and RMSSD.

---

## 4. HRV Radar Chart — `plot_hrv_radar`

### What it shows

Five normalised HRV dimensions displayed as a filled polygon on polar axes:

| Axis | Metric | Reference range | High value = |
|---|---|---|---|
| RMSSD (ms) | Short-term beat-to-beat variability | 0 – 100 ms | High vagal tone, good recovery |
| LF_nu | LF in normalised units | 0 – 1 | Sympathetic dominance |
| HF_nu | HF in normalised units | 0 – 1 | Parasympathetic dominance |
| SD1 (ms) | Poincaré short-term scatter | 0 – 70 ms | High beat-to-beat variability |
| DFA α1 | Short-range fractal scaling | 0 – 1.5 | Long-range correlations |

Each value is normalised against the reference range so that a value of 1.0
corresponds to the upper bound. Grey dashed rings at 25 %, 50 %, 75 % and 100 %.

### How to read it

**Shape** — a large polygon area generally indicates a good HRV profile.
A collapsed shape (all axes near zero) suggests fatigue or a short recording
that could not compute reliable metrics.

**Asymmetry** — a polygon elongated toward LF_nu with a small HF_nu indicates
sympathetic dominance. The reverse (large HF_nu, small LF_nu) indicates
parasympathetic dominance — typical of good overnight recovery.

**DFA α1**: values close to 1.0 indicate healthy long-range correlations
typical of a well-functioning autonomic system. Values near 0 or above 1.5 are
atypical. If DFA α1 shows a `⚠ NaN` annotation, the recording was too short
(< 60 beats) for reliable fractal estimation.

### Comparing sessions

Call `plot_hrv_radar` on two different sessions and overlay the figures
(or save as PNGs side by side) to visually compare how the profile shifts
between a recovered and a fatigued state.

---

## 5. Spectral Heatmap — `plot_spectral_heatmap`

### What it shows

A matrix where:
- **Rows** = sessions (chronological, from top to bottom)
- **Columns** = six spectral metrics:

| Column | Metric | Unit |
|---|---|---|
| VLF | VLF band power | ms² |
| LF | LF band power | ms² |
| HF | HF band power | ms² |
| LF/HF | LF-to-HF ratio | dimensionless |
| LF_nu | LF normalised units | 0 – 1 |
| HF_nu | HF normalised units | 0 – 1 |

### Colour scale

`normalize=True` (default): each column is rescaled to [0, 1] using
per-column min-max, so the **colour reflects relative position within
your own data range**, not an absolute reference.
Raw absolute values are always annotated inside each cell.

`normalize=False`: the colour is proportional to the raw value — useful
for spotting absolute outliers but makes columns with very different scales
(e.g., LF in ms² vs LF/HF) hard to compare visually.

### How to read it

**Column-by-column scan**:
- VLF / LF / HF — look for sessions where all three are unusually low
  (possible signal quality issue or very short recording).
- LF/HF + LF_nu / HF_nu — track the balance over time: a row with high
  LF/HF and high LF_nu is a stress/fatigue signature.

**Row-by-row scan**:
- A uniformly green row indicates a session with above-average values in most
  bands (good HRV session).
- A uniformly red row indicates below-average values (poor recovery or artefact).

**Discontinuities** — a sudden change from one row to the next (abrupt colour
shift) can indicate an irregular training event, illness, or sensor issue.

---

## See also

- [`docs/visualization/reading_charts.md`](reading_charts.md) — guide for time-domain RR charts
- [`docs/features/frequency_domain.md`](../features/frequency_domain.md) — LF, HF, LF/HF definitions
- [`docs/hrv_interpretations.md`](../hrv_interpretations.md) — full HRV interpretation guide
- [`example/11_spectral_plots.py`](../../../../example/11_spectral_plots.py) — demonstration of all 5 spectral functions
