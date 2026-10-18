# Training adaptation monitoring — 7-day lnRMSSD (Plews)

Added in v0.5.0. Module: `cardiolab.analytics.monitoring`.

A single morning RMSSD is noisy: it moves from one day to the next with sleep,
hydration, stress or the measurement itself. Plews, Buchheit and colleagues
showed that training adaptation is better read from the **7-day rolling mean of
lnRMSSD**, its **day-to-day variability** (coefficient of variation, CV) and the
athlete's **smallest worthwhile change** (SWC).

```python
from cardiolab.analytics import Baseline, monitoring_series, swc_band

baseline = Baseline.from_features(history)       # poor-quality sessions left out
points = monitoring_series(baseline)
points[-1].mean_7d, points[-1].cv_7d, points[-1].state
# (4.18, 2.4, 'normal')
```

---

## Definitions

| Quantity | Definition |
|----------|------------|
| Daily value | lnRMSSD of each measurement day (mean if several sessions that day). `poor` sessions excluded |
| 7-day mean | Mean of the daily values over the calendar days `(d − 7, d]` — at least **3** measurements, otherwise `nan` |
| 7-day CV | SD / mean × 100 of the same daily values (%) |
| Baseline | Daily values of the last **28 days** — at least 6 measurements |
| SWC | **0.5 × SD** of the baseline (Buchheit 2014) |
| SWC band | Baseline mean ± SWC — the athlete's normal range |
| Elevated CV | 7-day CV above the mean + 1 SD of the 7-day CVs of the same 28 days (cardiolab's operational threshold) |

Windows are counted in **calendar days**, not in sessions: a missing day does not
stretch the window. Three measurements a week are enough for a valid 7-day mean
(Plews et al. 2014: the agreement with a full week plateaus after 3–4 randomly
chosen measurements; they recommend at least 3 valid measurements a week).

---

## Interpreting the state

| 7-day mean | 7-day CV | State | Reading |
|------------|----------|-------|---------|
| Above the SWC band | — | `coping` | Parasympathetic activity rises: the athlete absorbs the training load well |
| Inside the band | — | `normal` | Usual fluctuation — nothing to read into day-to-day changes |
| Below the band | Normal | `maladaptation` | HRV drops steadily: accumulated fatigue, illness, life stress — lighten the load and watch the next days |
| Below the band | Elevated | `overreaching_risk` | HRV drops **and** becomes unstable: the pattern Plews et al. (2012) observed before non-functional overreaching — reduce the load |

This is a simplified version of the decision grid of Buchheit (2014). Read it
with context:

- **A rise is not always good news.** In very high-volume phases, some
  athletes show *parasympathetic saturation*: lnRMSSD rises while performance
  drops (Plews et al. 2013). If `coping` comes with fatigue and poor
  performance, trust the athlete.
- **Look at the trend over one to three weeks**, not at a single day's state.
- **Measure in the same conditions** every morning (position, time, duration);
  the orthostatic test supine phase and a resting measure are not interchangeable.

---

## In the readiness score — trend component

The 20 % *trend* component of `readiness_score_multi()` uses the same quantities
(`ln_rmssd_trend_score()`):

```
x = (7-day mean today − 7-day mean one week earlier) / SWC
trend = 50                                  if |x| ≤ 1  (normal fluctuation)
        50 ± 50 × tanh(|x| − 1)             otherwise   (+ for a rise, − for a decline)
```

| Change of the 7-day mean | Trend component |
|--------------------------|-----------------|
| within ±1 SWC | 50 |
| +2 SWC | ≈ 88 |
| −2 SWC | ≈ 12 |
| ±3 SWC | ≈ 98 / 2 |

It stays **neutral (50)** with less than 14 days since the first measurement, or
when either week has fewer than 3 measurements.

Changed in v0.5.0: the component compared today's RMSSD with the median of the
last 7 sessions — the same reference as the main RMSSD component (35 %), so RMSSD
actually weighed ≈ 55 % and no trend was measured. **Readiness values change**:
reprocess the history (`reprocess_sessions()`, see
[reprocessing](../database/reprocessing.md)).

---

## Chart and table

```python
from cardiolab.visualization import plot_ln_rmssd_monitoring
from cardiolab.reporting import table_weekly_monitoring
from cardiolab.labels import LABELS_FR

plot_ln_rmssd_monitoring(baseline, labels=LABELS_FR)
table_weekly_monitoring(baseline, labels=LABELS_FR)
```

- **Chart** — grey dots: daily lnRMSSD; blue line: 7-day mean, its markers
  coloured by state (green coping, blue normal, orange maladaptation, red
  overreaching risk); green band: SWC band; orange dashed line (right axis):
  7-day CV.
- **Weekly table** — one row per ISO week with the values of its last
  measurement day: measurements, 7-day mean, CV, SWC band, state (coloured).

---

## API

| Function | Returns |
|----------|---------|
| `daily_ln_rmssd(baseline)` | `[(day, ln_rmssd), …]` |
| `rolling_ln_rmssd(baseline, window=7)` | `[(iso_date, mean), …]` per measurement day |
| `rolling_cv(baseline, window=7)` | `[(iso_date, cv_percent), …]` |
| `swc_band(baseline, factor=0.5, baseline_days=28, at=None)` | `SWCBand(mean, swc, low, high, n)` or `None` |
| `interpret_trend_state(mean_7d, band, cv_7d, cv_threshold)` | `"coping"`, `"normal"`, `"maladaptation"`, `"overreaching_risk"` or `None` |
| `monitoring_series(baseline)` | `[MonitoringPoint, …]` — everything above, per day |
| `ln_rmssd_trend_score(current, baseline)` | Trend component [0–100] |

`baseline` is a `Baseline` (its `sessions`: `poor` quality excluded) or a list of
`HRVFeatures`. Computed on the fly — no database change.

---

## References

Plews, D. J., Laursen, P. B., Kilding, A. E., & Buchheit, M. (2012). Heart rate
variability in elite triathletes, is variation in variability the key to effective
training? A case comparison. *European Journal of Applied Physiology*, 112(11),
3729–3741.

Plews, D. J., Laursen, P. B., Stanley, J., Kilding, A. E., & Buchheit, M. (2013).
Training adaptation and heart rate variability in elite endurance athletes:
opening the door to effective monitoring. *Sports Medicine*, 43(9), 773–781.

Plews, D. J., Laursen, P. B., Le Meur, Y., Hausswirth, C., Kilding, A. E., &
Buchheit, M. (2014). Monitoring training with heart-rate variability: how much
compliance is needed for valid assessment? *International Journal of Sports
Physiology and Performance*, 9(5), 783–790.

Buchheit, M. (2014). Monitoring training status with HR measures: do all roads
lead to Rome? *Frontiers in Physiology*, 5, 73.
