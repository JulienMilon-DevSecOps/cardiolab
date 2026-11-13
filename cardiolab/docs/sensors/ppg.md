# PPG — optical sensors and pulse rate variability

Added in v0.9.0. Modules: `cardiolab.signals.ppg` (`PPGSignal`) and
`cardiolab.sensors_tools.ppg` (`parse_ppg_csv`).

## What it is

Optical sensors measure the **pulse wave**: the green light under a watch, a finger on a
phone camera with its flash, a clip on the ear lobe. Each heartbeat sends a wave of blood
into the small vessels, about 0.2 s after the electrical R peak a chest strap detects.

```
Chest strap (ECG) : ──┐╷┌────┐╷┌────┐╷┌──   sharp electrical peak at each beat
PPG (optical)     :  ╱‾╲__╱‾╲__╱‾╲__╱‾╲_   rounded pulse wave, ~0.2 s later
```

cardiolab finds each pulse peak, turns them into pulse-to-pulse intervals and passes them to
every feature and protocol as RR intervals. Nothing new is computed: the same RMSSD,
readiness score… are measured **with another kind of sensor**.

## PRV is not exactly HRV

The variability of pulse intervals is called **pulse rate variability** (PRV). The time the
pulse takes to travel from the heart to the finger varies a little from beat to beat, so:

| Situation | PRV compared with HRV (chest strap) |
|---|---|
| At rest, lying or sitting, still | Close. Short-term indices (RMSSD, pNN50, HF) tend to be slightly higher |
| Standing, breathing slowly | Larger differences |
| Moving, exercising | Wrong: motion distorts the wave |

(Schäfer & Vagedes 2013, review of studies comparing PPG with an ECG.) Hence:

- **Use PPG at rest only**: morning measurement (resting), supine phase of the orthostatic
  test, cardiac coherence. Not for heart rate recovery, cardiac drift, DFA α1 thresholds, the
  autonomic tests or the HRmax test — those need a chest strap.
- **Do not mix** PPG and chest-strap sessions in the same baseline: keep the same sensor
  every morning. The intervals carry `metadata["signal_type"] = "ppg"`
  (`cardiolab.signals.is_ppg(rr)`) so an application can tell them apart.

## Which devices give a raw PPG

Few consumer devices export the raw wave: most watches only export a heart rate, or
intervals they computed themselves (then use the Garmin or Apple readers, not this one).
Raw PPG comes from:

- **phone camera apps** (finger on the lens, flash on) — one brightness value per frame,
  25–30 Hz;
- **sensors with a developer kit or logger** (e.g. arm or ear optical sensors);
- **research devices**.

`parse_ppg_csv` reads any of them as long as the file has a value column and either a time
column or a known sampling rate.

## How to record

- Still, lying or sitting, 5 minutes as for the [resting protocol](../protocols/resting.md).
- **Finger on a camera**: cover the lens and the flash with the fingertip, without pressing
  (pressing empties the vessels), in a lit room, hand resting on a table.
- **Wrist**: watch tight just above the wrist bone, arm resting.
- At least **25 Hz**, ideally 50 Hz or more.

## Use

```python
from cardiolab.sensors_tools import parse_ppg_csv
from cardiolab.protocols import resting_hrv
from cardiolab.signals import signal_quality

ppg = parse_ppg_csv(
    "2026-11-14_finger.csv", "ppg",
    time_column="time_ms", time_unit="ms",   # or sampling_rate=30.0 without time column
    source="camera", invert=True,            # camera brightness falls on each pulse
)
rr = ppg.to_rr()                  # artefacts corrected (Lipponen & Tarvainen 2019)
signal_quality(rr).grade          # 'good'
rr.metadata["ppg_regularity"]     # 0.76 — a regular pulse
features = resting_hrv(rr)
```

From an array: `PPGSignal(values, sampling_rate=100.0, source="finger")`, or with
`timestamps=` (uneven timestamps are resampled to their mean rate).

## How it is computed

1. **Band-pass** 0.5–8 Hz (2nd-order Butterworth, zero phase): removes the baseline wander
   (breathing, finger pressure) and fast noise.
2. **Motion**: 2-s windows whose amplitude is more than twice the median are set aside; no
   peak is taken there. Over 20 % of motion → warning: measure again.
3. **Systolic peaks** — two moving averages (Elgendi et al. 2013): a 111-ms average above a
   667-ms average marks each pulse; its highest sample is the peak; at most one peak per
   0.3 s (200 bpm).
4. **Sub-sample timing**: a parabola through the peak and its two neighbours. At 30 Hz the
   samples are 33 ms apart — too coarse for RMSSD without it. Below 50 Hz a warning recalls
   it; below 20 Hz the signal is refused.
5. **Pulse present?** Regularity = autocorrelation of the signal at one beat (lag
   0.33–2 s), median over 10-s windows. A pulse gives 0.7–0.8, noise about 0.15. Below
   **0.4** the intervals are graded `poor` whatever the peaks look like — a sensor off the
   skin produces "peaks" from noise.
6. **Intervals** peak to peak, artefacts corrected; then the usual
   [signal quality](../features/signal_quality.md) grade.

Frequency domain: Lomb-Scargle, the default since v0.4.0, suits uneven pulse intervals.

### Checked on synthetic pulse waves

Pulse wave with a systolic and a dicrotic wave, baseline wander and noise, beats modulated
by breathing; 5 minutes:

| Sampling | Largest interval error | RMSSD (true 48.7 ms) |
|---|---|---|
| 100 Hz | 3.4 ms | 48.8 ms |
| 30 Hz (camera) | 6.8 ms | 48.9 ms |
| 100 Hz, 8 s of motion | — | 48.7 ms (motion set aside, beats corrected) |

Not yet compared with a chest strap on a real recording: record both at the same time to
check it on your own sensor.

## Limitations

- Rest only; one sensor type per baseline.
- The detection assumes a clear wave: cold fingers, nail polish, a loose watch or ambient
  light lower the regularity — check `signal_quality(rr).grade`.
- No real-time processing; recording with the camera is up to the application.

## References

- Elgendi, M., Norton, I., Brearley, M., Abbott, D., & Schuurmans, D. (2013). Systolic peak
  detection in acceleration photoplethysmograms measured from emergency responders in
  tropical conditions. *PLoS ONE*, 8(10), e76585.
- Schäfer, A., & Vagedes, J. (2013). How accurate is pulse rate variability as an estimate
  of heart rate variability? *International Journal of Cardiology*, 166(1), 15–29.
