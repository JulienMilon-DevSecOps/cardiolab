# Anomaly detection — `detect_rmssd_anomaly()` and `is_multivariate_anomaly()`

Modules: `cardiolab.analytics.anomaly` (one metric) and `cardiolab.analytics.multivariate`
(several metrics, added in v0.7.0).

## One metric: lnRMSSD

`detect_rmssd_anomaly(current, baseline, method="zscore")` compares today's lnRMSSD with the
daily lnRMSSD of the previous 28 days: `low` below −2 SD, `high` above +2 SD.

## Several metrics: Mahalanobis distance

A morning can have a normal RMSSD and still be unusual. For example, the resting heart rate
is high *and* DFA α1 is low: each value is within its own range, but the two together are
unlike any of your usual mornings. The **Mahalanobis distance** measures how far a session lies from
the cloud of your previous sessions, taking into account how the metrics usually move
together:

| Session | Each metric alone | Combination | Distance |
|---|---|---|---|
| RMSSD −2 SD, heart rate +2 SD | unusual | **usual** (tired morning: both move together) | small |
| RMSSD +2 SD, heart rate +2 SD | unusual | **unusual** (they normally move in opposite directions) | large |

```python
from cardiolab.analytics import Baseline, anomaly_report, is_multivariate_anomaly

baseline = Baseline.from_features(history)       # poor-quality sessions excluded
res = is_multivariate_anomaly(today, baseline)
res.status        # 'anomaly'
res.distance      # 4.6   (illustrative values)
res.threshold     # 3.51  (90 reference sessions, 4 metrics)
res.main_driver   # 'mean_hr'
res.z_scores      # {'ln_rmssd': 1.9, 'mean_hr': 3.1, 'dfa_alpha1': -0.4, 'sd_ratio': 0.2}

report = anomaly_report(baseline)   # pandas DataFrame, one row per session
# date | zscore | mahalanobis | threshold | is_anomaly | status | main_driver | z_<metric>…
```

### Choices

| Element | Choice | Why |
|---|---|---|
| Metrics | `ln_rmssd`, `mean_hr`, `dfa_alpha1`, `sd_ratio` | The four components of the readiness score. Near-duplicates (SD1 = RMSSD/√2, pNN50) make the covariance unstable |
| Reference | Sessions of the **90 days before** the session; never the session itself or later ones | Same rule as the score: no look-ahead. `anomaly_report` reads like it would have day after day |
| Minimum | **40** sessions with every metric, otherwise `insufficient_data` | Below that, false alarms rise (about 6 % with 30 sessions instead of 2.5 %) |
| Cloud | Robust: outlying reference sessions are set aside | Otherwise a few sick mornings widen the cloud and hide the next ones (masking) |
| Threshold | 97.5 % quantile of the distance of a *new* session to a cloud of *n* sessions | Adapts to the number of sessions and metrics |
| Explanation | z-score of each metric, `main_driver` | An alert must say what is unusual |

### Robust cloud — `robust_covariance()`

1. **Core of the cloud** — Minimum Covariance Determinant (Rousseeuw 1984), FAST-MCD
   algorithm (Rousseeuw & Van Driessen 1999). From random subsets, it keeps the half of the
   sessions that form the tightest cloud. The random starts use a fixed seed, so the
   results are reproducible.
2. **Screening** — sessions beyond the 99.9 % χ² quantile of that core are set aside. The
   cloud is then the usual mean and covariance of the others, corrected for the truncation.
   This step is repeated until the retained set no longer changes. `n_used` gives the
   number of sessions kept.

The core alone would be too tight with a few dozen sessions: about 20 % false alarms with 40
sessions. The screened estimate keeps the robustness and is well calibrated.

### Threshold — `prediction_threshold()`

If the sessions follow a normal law, the squared distance of a **new** session to a cloud
estimated from *n* sessions follows Hotelling's T² prediction law:
`p (n − 1)(n + 1) / (n (n − p)) · F(p, n − p)`. The threshold is the square root of its
97.5 % quantile:

| Reference sessions (4 metrics) | 40 | 60 | 90 | ∞ (`chi2_threshold`) |
|---|---|---|---|---|
| Distance threshold | 3.75 | 3.60 | 3.51 | 3.34 |

`threshold=` overrides it, for example `3.0` for a more sensitive alert.

### Calibration

These figures come from simulated normal clouds of 4 correlated metrics, 40 runs each:

| Reference sessions | 40 | 60 | 90 |
|---|---|---|---|
| False alarms (nominal 2.5 %) | 4.3 % | 2.7 % | 2.6 % |
| Same, with 15 % sick mornings in the reference | 4.0 % | 2.5 % | 2.3 % |

With 10–20 % of sick mornings in the reference, a classical covariance (no screening) **no
longer detected anything**. The robust cloud kept detecting.

### Reading the result

| `status` | Meaning |
|---|---|
| `normal` | Distance ≤ threshold |
| `anomaly` | Distance > threshold. Look at `main_driver` and `z_scores` |
| `insufficient_data` | Fewer than 40 reference sessions with every metric |
| `missing_features` | A metric of the session is missing (`0.0` means "not computed", e.g. DFA α1 on a short recording) |
| `no_variability` | A metric does not vary in the reference |

An anomaly is **not a diagnosis**. It says that the session does not look like your
previous ones: possible causes include illness, a bad night, alcohol, stress, a measurement
taken in different conditions, or a faulty recording. Check the signal quality and how you
feel. Repeated anomalies matter more than a single one.

### Chart — `plot_anomaly_timeline()`

Added in v0.7.0. Module: `cardiolab.visualization.statistical_plots`.

```python
from cardiolab.analytics import anomaly_report
from cardiolab.labels import LABELS_FR
from cardiolab.visualization import plot_anomaly_timeline

fig = plot_anomaly_timeline(anomaly_report(baseline), labels=LABELS_FR)
fig.savefig("anomalies.png", dpi=150, bbox_inches="tight")
```

| Element | Meaning |
|---|---|
| Dark dots and line | Distance of each session to its reference cloud |
| Red dashed steps | Threshold of the day (it decreases as reference sessions accumulate) |
| Purple diamond and shading | Unusual session: distance above the threshold |
| Grey band | Fewer than 40 reference sessions (`insufficient_data`) |
| Hollow grey circle on the axis | Session not checked (`missing_features` or `no_variability`) |
| Bottom panel | One row per metric, one square per session, coloured by its deviation from the reference in SD (blue below, red above, capped at ±4) |

How to read it: about one session in 40 crosses the threshold by chance. Look at
**repeated** diamonds, and at the bottom panel to see which metric moves; a dark
square in the same column as a diamond is the `main_driver`.

### Limits

- The method assumes a roughly normal cloud. lnRMSSD is used for that reason (RMSSD itself
  is skewed).
- With one measurement a day, 40 sessions means about six weeks of history; the reference
  covers the last 90 days.
- A slow drift (fitness gain, ageing) moves the cloud with it: the method flags **unusual
  days**, not long-term changes. For those, see [`trends.md`](trends.md) and
  [`monitoring.md`](monitoring.md).

## References

- Mahalanobis, P. C. (1936). On the generalised distance in statistics. *Proceedings of the
  National Institute of Sciences of India*, 2, 49–55.
- Rousseeuw, P. J. (1984). Least median of squares regression. *Journal of the American
  Statistical Association*, 79(388), 871–880.
- Rousseeuw, P. J., & Van Driessen, K. (1999). A fast algorithm for the minimum covariance
  determinant estimator. *Technometrics*, 41(3), 212–223.
- Hardin, J., & Rocke, D. M. (2005). The distribution of robust distances. *Journal of
  Computational and Graphical Statistics*, 14(4), 928–946.
