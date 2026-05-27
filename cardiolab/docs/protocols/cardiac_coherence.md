# Cardiac Coherence 5-5 Protocol

## Physiological principle

Cardiac coherence is a physiological state in which heart rate oscillates sinusoidally
and regularly, resonating with the autonomic nervous system. It is induced by guided
breathing at **6 cycles/min** (5 s inhale / 5 s exhale), which generates a maximal
oscillation of RR intervals at **0.1 Hz** — the baroreflex resonance frequency.

At 0.1 Hz, the vagal baroreflex amplifies respiratory oscillations of blood pressure
and HR, producing the largest possible spectral power in the HF band. This mechanism,
called **cardiovascular resonance**, is associated with maximal activation of the vagus
nerve (parasympathetic activity).

## How to perform the protocol

### Measurement conditions

- **Seated** or **supine** position in a quiet environment.
- Minimum recommended duration: **5 minutes** (ideally 10 min).
- Avoid any physical activity in the hour before measurement.
- Use a chest strap for continuous RR interval recording.

### Procedure

1. Settle comfortably and note the start time.
2. Use a breathing guide (visual or audio) at **6 cycles/min**:
   - Inhale for **5 seconds**.
   - Exhale for **5 seconds**.
3. Maintain this rhythm throughout the session.
4. Export the RR intervals at the end of the session.

### Recording

```python
from cardiolab.signals.rr import RRSeries
from cardiolab.protocols.cardiac_coherence import cardiac_coherence

rr = RRSeries.from_csv("coherence_session.csv")
result = cardiac_coherence(rr)
print(f"Coherence score: {result.coherence_score:.1f} %")
print(f"Resonance frequency: {result.resonance_freq:.3f} Hz")
```

## Computed metrics

| Metric | Description | Unit |
|---|---|---|
| `coherence_score` | % of power concentrated at the resonance peak | % (0–100) |
| `resonance_freq` | Dominant peak frequency in the 0.04–0.26 Hz band | Hz |
| `peak_power` | Spectral density at the resonance peak | ms²/Hz |
| `total_power_resonance` | Total power in the resonance band | ms² |
| `rmssd` | RMSSD during the session | ms |
| `sdnn` | SDNN during the session | ms |
| `mean_hr` | Mean heart rate | bpm |
| `duration` | Effective recording duration | s |

### Coherence score

The score is computed as:

```
coherence_score = (peak_window_power / total_resonance_power) × 100
```

where the peak window is centred on the dominant frequency with a half-width of
±0.015 Hz.

## Interpreting results

### Coherence score

| Score (%) | Interpretation | Recommendation |
|---|---|---|
| ≥ 60 | **Good coherence** — strong vagal resonance | Maintain the practice |
| 40 – 60 | **Moderate coherence** — partial resonance | Improve breathing regularity |
| < 40 | **Low coherence** — little vagal resonance | Check the guide and breathing rate |

### Resonance frequency

For a 5-5 protocol (6 cycles/min), the expected frequency is:

```
f_resonance = 6 / 60 = 0.100 Hz
```

A peak between **0.09 and 0.11 Hz** confirms that the subject is correctly following
the breathing guide. A shifted peak suggests a breathing rate different from 6 cycles/min.

### RMSSD and SDNN

A high coherence score is generally accompanied by high RMSSD values (vagal
activation). RMSSD > 50 ms combined with a score ≥ 60 % indicates excellent
parasympathetic modulation.

## Spectral method

The analysis uses the **AR (Yule-Walker)** method at order 16, which is preferred
over Welch for short sessions (2–5 min) because it provides better spectral resolution.
The RR signal is resampled at **4 Hz** before spectral estimation.

Analysis band: **0.04 – 0.26 Hz** (covers the HF band and extends slightly below to
capture slow breathing rates).

## Limitations and precautions

- The coherence score is sensitive to **inter-breath variability**: irregular breathing
  widens the spectral peak and reduces the score.
- A session < 2 minutes (< 120 beats) yields unreliable results.
- Some subjects have a personal resonance frequency slightly different from 0.1 Hz;
  adapt the breathing guide if necessary.
- Cardiac coherence is not a standalone global health indicator — combine it with
  resting HRV measurements.

## References

Lehrer, P. M., & Gevirtz, R. (2014). Heart rate variability biofeedback: how and why
does it work? *Frontiers in Psychology*, 5, 756.
https://doi.org/10.3389/fpsyg.2014.00756

McCraty, R., & Shaffer, F. (2015). Heart rate variability: new perspectives on
physiological mechanisms, assessment of self-regulatory capacity, and health risk.
*Global Advances in Health and Medicine*, 4(1), 46–61.
https://doi.org/10.7453/gahmj.2014.073

Shaffer, F., McCraty, R., & Zerr, C. L. (2014). A healthy heart is not a metronome:
an integrative review of the heart's anatomy and heart rate variability.
*Frontiers in Psychology*, 5, 1040.
https://doi.org/10.3389/fpsyg.2014.01040
