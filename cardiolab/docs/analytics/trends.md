# Trend analysis — `linear_trend()`

Rewritten in v0.5.0. Module: `cardiolab.analytics.trends`.

Day-to-day HRV is noisy: a line fitted through a few noisy sessions almost always
has a non-zero slope. A trend is therefore only reported when it is both
**statistically significant** and **large enough to matter**.

```python
from cardiolab.analytics import linear_trend

series = [(f.date, f.rmssd) for f in history]
result = linear_trend(series, window_days=30)
result.label        # 'decreasing'
result.slope        # -0.42  (ms per day)
result.change_pct   # -18.3  (fitted change over the window, % of the mean)
result.p_value      # 0.003
result.r2           # 0.29
```

---

## How the label is decided

| Condition | Label |
|-----------|-------|
| Fewer than 5 values in the window | `insufficient_data` |
| p ≥ 0.05 (slope not different from zero) | `stable` |
| p < 0.05 but fitted change < 5 % of the mean | `stable` |
| p < 0.05 and change ≥ +5 % | `increasing` |
| p < 0.05 and change ≤ −5 % | `decreasing` |

- **Slope** — least-squares line (`scipy.stats.linregress`), in units of the
  series **per calendar day** (missing days are respected), or per session for a
  series without dates.
- **p-value** — two-sided test of a zero slope. On pure noise, about 5 % of
  series reach p < 0.05 by chance (tested); the magnitude threshold filters most
  of those.
- **Relative threshold** — `change_pct = slope × window span / mean × 100`. A
  fixed ms threshold means a lot for an RMSSD of 25 ms and little for 120 ms; a
  percentage compares athletes fairly.

Parameters: `window_days` (`None` = whole series), `end` (last day of the window),
`min_points` (5), `alpha` (0.05), `min_change_pct` (5 %).

---

## Sustained decline — `detect_sustained_decline()`

```python
from cardiolab.analytics import detect_sustained_decline

result = detect_sustained_decline([f.score for f in history])
result.detected, result.run_length, result.limit
```

A decline is **sustained** when the last 5 values (`min_sessions`) are all below
`mean + threshold × SD` of the reference — the values preceding them (at most 30).
With `threshold = −0.5`, that is half a standard deviation below the usual range,
the smallest worthwhile change used in HRV monitoring
([monitoring.md](monitoring.md)). One value back in range resets the run.

---

## Rolling report — `trend_report()`

```python
from cardiolab.analytics import Baseline, trend_report

trend_report(Baseline.from_features(history), metric="score")
```

| Column | Content |
|--------|---------|
| `date` | Session date |
| `score` (or the chosen metric) | Value |
| `slope_7d`, `slope_30d` | Slope per day over the last 7 / 30 days (`nan` with fewer than 5 values) |
| `change_30d_pct`, `p_30d` | Fitted change (%) and p-value over 30 days |
| `trend_label` | 30-day label |

`poor`-quality sessions are left out when a `Baseline` is given. Requires pandas
(`pip install cardiolab[analysis]`).

---

## `trend_rmssd()` — kept for compatibility

Same keys as before (`slope` in ms per session, `trend`), plus `p_value`, `r2` and
`change_pct`. Changed in v0.5.0: `trend` is `increasing` / `decreasing` only for
a significant slope with a change of at least 5 % — it used a fixed ±1 ms/session
threshold without significance, so noise alone often produced a "trend".

---

## Trend or monitoring?

| Question | Tool |
|----------|------|
| Is the athlete adapting to training this week? | [`monitoring_series()`](monitoring.md) — 7-day lnRMSSD vs SWC band |
| Has the metric changed significantly over the last month? | `linear_trend(series, 30)` |
| Has the score stayed low for several sessions in a row? | `detect_sustained_decline()` |

No predictive model (ARIMA, hidden Markov…) is provided: the biological
variability of HRV makes short-term forecasts unreliable.
