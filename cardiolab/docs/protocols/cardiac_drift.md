# Cardiac Drift Protocol

## Physiological principle

Cardiac drift is the progressive and continuous increase in heart rate during prolonged
exercise at constant work rate. This phenomenon occurs without any increase in metabolic
demand and reflects a growing mismatch between cardiac output and haemodynamic needs.

The three main mechanisms are:

1. **Dehydration**: the reduction in plasma volume (−10 to −15 % after 60 min of
   exercise in the heat) decreases venous return and stroke volume. To maintain cardiac
   output (Q = HR × SV), the heart compensates by increasing HR.

2. **Thermoregulation**: the redistribution of blood flow to the skin (cooling via
   sweating) reduces the central volume available to the cardiac muscle, amplifying the
   fall in stroke volume.

3. **Autonomic fatigue**: the progressive decrease in parasympathetic tone during
   prolonged exercise contributes to the rise in baseline HR.

Drift is quantified by the **slope of the linear regression** of window-averaged HR
over exercise duration.

## How to perform the protocol

### Measurement conditions

- **Constant work rate** exercise: cycling at a fixed wattage, running at a steady
  pace, treadmill at constant speed and grade.
- Minimum duration: **20 minutes** (for 3 windows of 60 s + margin).
- Optimal duration: **30–60 minutes**.
- Environmental conditions to record: temperature, humidity, hydration status.

### Procedure

1. Start RR recording at the beginning of constant-load exercise (no warm-up in the
   series).
2. Maintain a stable breathing cadence and posture.
3. Do not drink or stop during the measurement (or log any interruptions).
4. Export the RR intervals at the end of the session.

### Recording

```python
from cardiolab.signals.rr import RRSeries
from cardiolab.protocols.cardiac_drift import cardiac_drift

rr = RRSeries.from_csv("constant_effort.csv")
result = cardiac_drift(rr, window_sec=60.0)

print(f"Drift rate: {result.drift_rate:.2f} bpm/min")
print(f"Initial HR: {result.initial_hr:.0f} bpm → Final HR: {result.final_hr:.0f} bpm")
print(f"Total magnitude: {result.drift_magnitude:.1f} bpm")
print(f"R²: {result.r_squared:.3f}")
print(f"Interpretation: {result.interpretation}")
```

## Computed metrics

| Metric | Description | Unit |
|---|---|---|
| `drift_rate` | HR ∼ time linear regression slope | bpm/min |
| `drift_magnitude` | Final HR − Initial HR | bpm |
| `r_squared` | R² coefficient of determination of the regression | dimensionless (0–1) |
| `drift_detected` | True if drift ≥ 0.5 bpm/min | boolean |
| `initial_hr` | Mean HR of the first window | bpm |
| `final_hr` | Mean HR of the last window | bpm |
| `n_windows` | Number of time windows | integer |
| `interpretation` | Clinical category | text |
| `duration` | Total recording duration | s |

## Interpreting results

### Drift rate

| Rate (bpm/min) | Category | Meaning |
|---|---|---|
| < 0.5 | **No drift** | Efficient thermoregulation, good hydration |
| 0.5 – 1.5 | **Mild drift** | Monitor hydration |
| 1.5 – 3.0 | **Moderate drift** | Hydrate, consider reducing intensity |
| > 3.0 | **Strong drift** | Stop or significantly reduce intensity |

### R² coefficient

The R² of the linear regression indicates whether the drift is **progressive and
regular**:

- R² > 0.8: clear linear drift → constant physiological mechanism.
- R² 0.5–0.8: moderately linear drift → possible effort variability.
- R² < 0.5: no clear trend → no true cardiac drift, or high power variability.

### Total magnitude

The magnitude (final HR − initial HR) is a useful complement:

- A drift of +10 bpm over 30 min (0.33 bpm/min) is mild.
- A drift of +20 bpm over 30 min (0.67 bpm/min) warrants attention.
- A drift of +30 bpm over 30 min (1.0 bpm/min) is clinically significant.

### Time windows

The algorithm divides the RR series into windows of `window_sec` seconds (default
60 s). Each window produces a mean HR data point. A **minimum of 3 windows** is
required to compute a meaningful regression.

## Practical applications

### Hydration assessment

A simple protocol consists of two sessions at the same work rate:
- Session 1: without hydration.
- Session 2: with ad libitum hydration.

The difference in drift between the two sessions quantifies the effect of hydration.

### Longitudinal tracking

Repeating the test under identical conditions (same work rate, same duration, same
time of day) allows tracking of the evolution of thermal tolerance and cardiovascular
efficiency.

### Exercise prescription

If drift is strong (> 3 bpm/min) at a given work rate, reduce the target intensity by
10–15 % to limit drift in subsequent sessions.

## Limitations and precautions

- The work rate must be **strictly constant**; any variation in cadence or pace
  introduces a bias in the regression.
- Drift is physiologically greater in **hot and humid conditions** (> 25 °C, > 70 %
  relative humidity); interpret in light of ambient conditions.
- Minimum duration is **3 × window_sec**: for window_sec = 60 s, at least 3 min of
  effort is required.
- Do not measure during intermittent exercise (HIIT, intervals) — reserved for
  steady-state effort.

## References

Coyle, E. F., & González-Alonso, J. (2001). Cardiovascular drift during prolonged
exercise: new perspectives. *Exercise and Sport Sciences Reviews*, 29(2), 88–92.
https://doi.org/10.1097/00003677-200104000-00009

Wingo, J. E., & Cureton, K. J. (2006). Cardiovascular responses to exercise with and
without hydration. *Medicine & Science in Sports & Exercise*, 38(4), 739–748.
https://doi.org/10.1249/01.mss.0000191765.30569.03

González-Alonso, J., Calbet, J. A., & Nielsen, B. (1999). Metabolic and thermodynamic
responses to dehydration-induced reductions in muscle blood flow in exercising humans.
*Journal of Physiology*, 520(2), 577–589.
https://doi.org/10.1111/j.1469-7793.1999.00577.x

Cheung, S. S., & McLellan, T. M. (1998). Heat acclimation, aerobic fitness, and
hydration effects on tolerance during uncompensable heat stress.
*Journal of Applied Physiology*, 84(5), 1731–1739.
https://doi.org/10.1152/jappl.1998.84.5.1731
