# HRV Metric Interpretation Guide (Resting Protocol)

## Overview

All HRV values must be interpreted **relative to the individual's personal baseline**.
A single measurement in isolation has limited clinical or practical value.
Trends over multiple sessions are what matter.

---

## Time-domain metrics

### RMSSD

Root Mean Square of Successive Differences — the primary HRV metric.

* ↑ RMSSD → recovery, relaxation, strong vagal tone
* ↓ RMSSD → fatigue, stress, high training load

### ln(RMSSD)

Natural logarithm of RMSSD. More normally distributed, better suited for
statistical comparisons and baseline tracking.

### SDNN

Standard deviation of NN intervals — measures overall HRV.
Sensitive to recording duration; values are not comparable across different window lengths.

### pNN50

Percentage of consecutive interval pairs differing by more than 50 ms.
Reflects parasympathetic activity. Sensitive to noise; use alongside RMSSD.

---

## Frequency-domain metrics

### HF (0.15 – 0.4 Hz)

High-frequency band — driven by respiratory sinus arrhythmia.
Primary marker of parasympathetic (vagal) activity.

| HF power | Interpretation |
| -------- | -------------- |
| high     | recovery       |
| low      | fatigue        |

### LF (0.04 – 0.15 Hz)

Low-frequency band — reflects a mix of sympathetic and parasympathetic modulation.

### LF/HF ratio

Autonomic balance indicator. **Controversial**: its interpretation as a
sympatho-vagal balance marker is debated in the literature.

| LF/HF | Interpretation        |
| ----- | --------------------- |
| < 1   | recovery / relaxation |
| 1 – 2 | normal                |
| > 2   | potential stress      |

### HF %

HF power as a percentage of total spectral power.

| HF %   | Interpretation |
| ------ | -------------- |
| > 50 % | deep rest      |
| 30–50% | normal         |
| < 30 % | stress         |

### LF_nu / HF_nu

LF and HF power in normalised units: relative distribution of autonomic activity.

---

## Heart rate (HR)

| HR      | Interpretation  |
| ------- | --------------- |
| low     | rest, recovery  |
| elevated | stress, fatigue |

---

## Key rules

* Always compare against your own baseline — not population norms.
* Look at trends, not individual values.
* Never draw conclusions from a single session.

---

## Quick reference

| Condition   | RMSSD | HF  | HR  | Interpretation  |
| ----------- | ----- | --- | --- | --------------- |
| Recovery    | ↑     | ↑   | ↓   | optimal state   |
| Baseline    | ~     | ~   | ~   | stable          |
| Fatigue     | ↓     | ↓   | ↑   | stress / overload |

---

## Summary

* **RMSSD** is the primary indicator.
* **HF** reflects recovery quality.
* **HR** is a stress / load marker.
* **Baseline** is the reference — without it, metrics lack context.
