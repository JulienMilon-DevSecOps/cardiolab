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
- **p-value** — two-sided test of a zero slope, **corrected for
  autocorrelation**. Successive HRV values are not independent (a low day is
  often followed by another): the ordinary p-value would be too small. cardiolab
  uses the effective sample size `n_eff = n × (1 − r1) / (1 + r1)`, `r1` = lag-1
  autocorrelation of the residuals (Santer et al. 2000), in the t-test of the
  slope (`result.n_eff`). On strongly autocorrelated noise (r = 0.7, 30 values),
  false trends drop from ≈ 39 % to ≈ 13 % (tested); on independent noise, about
  5 % of series reach p < 0.05 by chance. The magnitude threshold filters most
  of the rest. Added in v0.5.0.
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

## Trend line and confidence band — `trend_line()`

Added in v0.7.0. Same window and fit as `linear_trend()`, plus the confidence band of
the **line** (where the mean of the series lies, not where single values fall):

```python
from cardiolab.analytics import trend_line

tl = trend_line(series, window_days=30)       # level=0.95 by default
tl.days, tl.fitted, tl.lower, tl.upper      # one value per session of the window
tl.result                                   # the TrendResult of linear_trend()
```

- Half-width `t × s × √(1/n + (x − x̄)² / Σ(x − x̄)²)`: narrowest at the centre of the
  window, wider at its edges.
- Same autocorrelation correction as the p-value: with `n_eff < n`, the standard
  error is multiplied by `√((n − 2) / (n_eff − 2))` and `t` has `n_eff − 2` degrees
  of freedom. The band is as cautious as the label.
- `insufficient_data`: everything `nan`. `n_eff ≤ 2`: line drawn, band `nan`.
- Coverage checked by simulation (white noise): the true line lies inside the 95 %
  band 90–99 % of the time in the tests.

---

## Chart — `plot_trend_overlay()`

Added in v0.7.0. Module: `cardiolab.visualization.statistical_plots`.

```python
from cardiolab.labels import LABELS_FR
from cardiolab.visualization import plot_trend_overlay

fig = plot_trend_overlay(baseline, windows=(None, 28), metric="score", labels=LABELS_FR)
```

| Element | Meaning |
|---|---|
| Grey dots | The values (`series` as `[(date, value), …]`, a `Baseline` or dated `HRVFeatures`, read through `metric`) |
| One line per window | Fitted trend; green `increasing`, red `decreasing`, blue `stable`; solid, dashed, then dotted for the next windows (`None` = whole series) |
| Band of the same colour | Confidence band of the line (`level`, 95 % by default) |
| Legend | Slope per week, p-value and label of each window |
| Red rings and dotted line | `show_decline=True`: last values below the usual range (`detect_sustained_decline`) and the limit |

A line that slopes but stays blue is **not a trend yet**: day-to-day variation can
explain it.

---

## Trend or monitoring?

| Question | Tool |
|----------|------|
| Is the athlete adapting to training this week? | [`monitoring_series()`](monitoring.md) — 7-day lnRMSSD vs SWC band |
| Has the metric changed significantly over the last month? | `linear_trend(series, 30)` |
| Has the score stayed low for several sessions in a row? | `detect_sustained_decline()` |

No predictive model (ARIMA, hidden Markov…) is provided: the biological
variability of HRV makes short-term forecasts unreliable.

---

## Reference

Santer, B. D., Wigley, T. M. L., Boyle, J. S., Gaffen, D. J., Hnilo, J. J.,
Nychka, D., Parker, D. E., & Taylor, K. E. (2000). Statistical significance of
trends and trend differences in layer-average atmospheric temperature time
series. *Journal of Geophysical Research*, 105(D6), 7337–7356.
