# HRV Features — Reference Guide

This section documents all heart-rate variability (HRV) indicators computed by
cardiolab. Each indicator is described with its formula, typical reference
values, and clinical interpretation.

---

## Feature groups

| Group | Indicators | Source |
|-------|-----------|--------|
| [Time-domain](time_domain.md) | RMSSD, ln_RMSSD, SDNN, pNN50, mean HR | RR intervals |
| [Frequency-domain](frequency_domain.md) | VLF, LF, HF, LF/HF, LF_nu, HF_nu, HF%, HF/FC | Welch PSD on interpolated RR |
| [Non-linear](nonlinear.md) | SD1, SD2, SD1/SD2, DFA α1 | Poincaré plot, DFA |

---

## Complete indicator table

| Field | Unit | Domain | Short description |
|-------|------|--------|-------------------|
| `rmssd` | ms | Time | Beat-to-beat variability, primary vagal marker |
| `ln_rmssd` | — | Time | Log-transformed RMSSD for statistical normality |
| `sdnn` | ms | Time | Overall HRV, both branches of the ANS |
| `pnn50` | % | Time | % of successive pairs differing > 50 ms |
| `mean_hr` | bpm | Time | Mean heart rate over the recording window |
| `vlf` | ms² | Frequency | Very-low-frequency band power (0.003–0.04 Hz) |
| `lf` | ms² | Frequency | Low-frequency band power (0.04–0.15 Hz) |
| `hf` | ms² | Frequency | High-frequency band power (0.15–0.40 Hz) |
| `lf_hf` | — | Frequency | LF/HF ratio — sympatho-vagal balance |
| `lf_nu` | — | Frequency | LF in normalised units = LF / (LF + HF) |
| `hf_nu` | — | Frequency | HF in normalised units = HF / (LF + HF) |
| `hf_pct` | — | Frequency | HF as fraction of total power |
| `hf_hr` | ms²/bpm | Frequency | HF power normalised by mean HR |
| `sd1` | ms | Non-linear | Poincaré short-term variability (= RMSSD / √2) |
| `sd2` | ms | Non-linear | Poincaré long-term variability |
| `sd_ratio` | — | Non-linear | SD1/SD2 — shape of the Poincaré ellipse |
| `dfa_alpha1` | — | Non-linear | DFA short-term scaling exponent (scales 4–16 beats) |
| `duration` | s | Meta | Effective recording duration |
| `score` | 0–1 | Meta | Optional readiness score |

---

## How to read this guide

Each feature page follows the same structure:

1. **Definition** — formula and mathematical derivation.
2. **Physiological background** — what it measures in the autonomic nervous
   system.
3. **Reference values** — typical ranges for healthy adults at rest.
4. **Clinical interpretation** — what deviations from the normal range suggest.
5. **Notes** — practical considerations (recording length, artefacts, etc.).

---

## General interpretation principles

- HRV is highly individual. A single absolute value is less informative than a
  **personal trend** over time.
- **Short-term recordings** (< 5 min) are suitable for RMSSD, SD1, and DFA α1,
  but frequency-domain estimates are less reliable.
- **Long-term recordings** (≥ 24 h) are required for reliable VLF and SDNN in
  the clinical sense; cardiolab targets 5-minute resting segments.
- Artefacts (ectopic beats, motion) inflate RMSSD and SDNN — always clean with
  `remove_outliers()` or `auto_clean=True` before analysis.
- RMSSD and HF reflect **parasympathetic** activity. LF, SDNN, and SD2 reflect
  **mixed** autonomic activity. DFA α1 reflects **fractal organisation**.
