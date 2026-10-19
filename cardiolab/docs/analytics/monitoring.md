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
| Baseline | Daily values of the **28 days preceding the 7-day window** — `(d − 35, d − 7]`, at least 6 measurements. With less history, every day before the window is used |
| SWC | **0.5 × SD** of the baseline (Buchheit 2014) |
| SWC band | Baseline mean ± SWC — the athlete's normal range |
| Elevated CV | 7-day CV above the mean + 1 SD of the 7-day CVs of the same baseline days (cardiolab's operational threshold) |

**The evaluated week is not part of its own reference**: a decline in progress
does not drag the band down with it. States appear after about 13 days of daily
measurements (6 baseline days + a 7-day window).

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

## In the readiness score

`readiness_score_multi()` (changed in v0.5.0) scores each component against the
athlete's own history:

| Component | Weight | Score |
|-----------|--------|-------|
| **lnRMSSD of the day** | 45 % | Today's lnRMSSD against the daily values of the previous 28 days (`ln_rmssd_day_score()`), higher is better |
| **Resting HR** | 25 % | `50 − 50 × tanh((HR − mean HR of the last 7 sessions) / 10)` |
| **Trend of the week** | 20 % | 7-day mean versus the previous week, in SWC units (`ln_rmssd_trend_score()`) |
| **DFA α1** | 10 % | Today's α1 against the previous 28 days (`dfa_alpha1_score()`), **lower is better** |

### Day components — individual reference band

Comparing the day's value with the athlete's usual range is the basis of
HRV-guided training — with HF power in Kiviniemi et al. (2007), with lnRMSSD in
later work (Plews et al. 2013):

```
score = 50 ± 50 × tanh(Δ / (2 × SD))      Δ = today − mean of the previous 28 days
```

| Deviation from the usual level | Score (higher is better) |
|--------------------------------|--------------------------|
| 0 | 50 |
| ±½ SD (±1 SWC) | 62 / 38 |
| ±1 SD | 73 / 27 |
| ±2 SD | 88 / 12 |

The deviation is measured in units of **the athlete's own variability**: the same
change in ms means more for a very stable athlete than for a naturally variable
one. The SD has a floor of 0.05 (≈ 5 % of RMSSD) so that a few nearly identical
previous values cannot turn a small change into an extreme score. Neutral (50)
with fewer than 6 previous measurements; undated sessions use the last 28 sessions.

**DFA α1 — lower is better.** Vagal activity lowers the short-term exponent and
sympathetic activity raises it (Castiglioni et al. 2011): an α1 above the usual
level points to a less vagal state. Evidence for resting α1 as a recovery marker
is limited, hence its 10 % weight.

### Trend of the week

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

Neutral (50) with less than 14 days since the first measurement, or when either
week has fewer than 3 measurements.

### Early days

Components without enough history stay at 50 and their weight is **not
redistributed**: during the first two weeks the score moves within a narrower
range (it starts from the heart rate component alone), then uses the full scale.

### What changed in v0.5.0

| | Before | From v0.5.0 |
|---|---|---|
| RMSSD | 35 %, ratio to the median of the last 7 sessions | 45 %, lnRMSSD against the previous 28 days, in SD units |
| Resting HR | 20 % | 25 % |
| Trend | 20 %, today's RMSSD vs the same median (no trend measured) | 20 %, 7-day mean vs previous week in SWC units |
| DFA α1 | 25 %, fixed 0.75 threshold, higher is better | 10 %, against the previous 28 days, lower is better |

**Readiness values change**: reprocess the history (`reprocess_sessions()`, see
[reprocessing](../database/reprocessing.md)). The weights remain cardiolab's
heuristic — no study validates a precise weighting of these markers.

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

Castiglioni, P., Parati, G., Di Rienzo, M., Carabalona, R., Cividjian, A., &
Quintin, L. (2011). Scale exponents of blood pressure and heart rate during
autonomic blockade as assessed by detrended fluctuation analysis. *The Journal of
Physiology*, 589(2), 355–369.

Kiviniemi, A. M., Hautala, A. J., Kinnunen, H., & Tulppo, M. P. (2007).
Endurance training guided individually by daily heart rate variability
measurements. *European Journal of Applied Physiology*, 101(6), 743–751.
