"""Non-linear HRV metrics: Poincaré plot (SD1/SD2) and DFA α1."""

from __future__ import annotations

import numpy as np


def sd1(rr) -> float:
    """Compute SD1 from the Poincaré plot.

    SD1 is the standard deviation of the projection of the RR series onto the
    identity line's perpendicular (the short axis of the Poincaré ellipse). It
    measures **short-term**, beat-to-beat variability and is mathematically
    equivalent to RMSSD / √2.

    Formula: ``SD1 = RMSSD / √2``

    Clinical interpretation:

    | SD1 (ms)  | Interpretation       |
    | --------- | -------------------- |
    | < 15      | very low             |
    | 15 – 30   | low                  |
    | 30 – 50   | normal               |
    | > 50      | high                 |

    SD1 reflects parasympathetic (vagal) activity — the same information as
    RMSSD but expressed in the Poincaré domain. High SD1 indicates strong
    vagal modulation and good short-term recovery.

    Args:
        rr: An ``RRSeries`` instance containing the intervals to analyse.

    Returns:
        SD1 value in milliseconds.

    """
    diff = np.diff(rr.intervals)
    rmssd_val = float(np.sqrt(np.mean(diff**2)))
    return rmssd_val / np.sqrt(2)


def sd2(rr) -> float:
    """Compute SD2 from the Poincaré plot.

    SD2 is the standard deviation of the projection of the RR series onto the
    identity line (the long axis of the Poincaré ellipse). It measures
    **long-term** variability, reflecting both sympathetic and parasympathetic
    contributions, and is related to SDNN.

    Formula: ``SD2 = √(2·SDNN² − SD1²)``

    Clinical interpretation:

    | SD2 (ms)  | Interpretation       |
    | --------- | -------------------- |
    | < 30      | very low             |
    | 30 – 70   | low                  |
    | 70 – 120  | normal               |
    | > 120     | high                 |

    SD2 reflects overall autonomic regulation. A large SD2 with a small SD1
    indicates sympathetic dominance; balanced SD1 and SD2 reflect good
    autonomic flexibility.

    Args:
        rr: An ``RRSeries`` instance containing the intervals to analyse.

    Returns:
        SD2 value in milliseconds. Returns ``0.0`` if the squared value is
        negative (numerical edge case with very low variability series).

    """
    diff = np.diff(rr.intervals)
    rmssd_val = float(np.sqrt(np.mean(diff**2)))
    sdnn_val = float(np.std(rr.intervals, ddof=1))

    sd1_sq = 0.5 * rmssd_val**2
    sd2_sq = 2.0 * sdnn_val**2 - sd1_sq

    if sd2_sq < 0.0:
        return 0.0

    return float(np.sqrt(sd2_sq))


def sd_ratio(rr) -> float:
    """Compute the SD1/SD2 ratio from the Poincaré plot.

    SD1/SD2 quantifies the **shape** of the Poincaré ellipse. A ratio near 1
    indicates a circular cloud (equal short- and long-term variability);
    a low ratio indicates a stretched ellipse driven primarily by long-term
    variability (sympathetic dominance).

    Formula: ``SD1 / SD2``

    Clinical interpretation:

    | SD1/SD2     | Interpretation                          |
    | ----------- | --------------------------------------- |
    | < 0.25      | very low — sympathetic dominance        |
    | 0.25 – 0.55 | normal resting range                    |
    | > 0.55      | high — parasympathetic dominance        |

    Args:
        rr: An ``RRSeries`` instance containing the intervals to analyse.

    Returns:
        SD1/SD2 ratio (dimensionless). Returns ``float('nan')`` if SD2 is
        zero to avoid division by zero.

    """
    sd2_val = sd2(rr)
    if sd2_val == 0.0:
        return float("nan")
    return float(sd1(rr) / sd2_val)


def dfa_alpha1(rr, n_min: int = 4, n_max: int = 16) -> float:
    """Compute the DFA α1 short-term scaling exponent.

    Detrended Fluctuation Analysis (DFA) quantifies the **fractal correlation
    structure** of the RR series. The short-term exponent α1 is estimated from
    window sizes in the range [``n_min``, ``n_max``] beats (default 4–16).

    Algorithm:
        1. Compute the integrated signal: ``y(k) = Σ (RR_i − mean_RR)``.
        2. For each scale ``n``:
           a. Divide ``y`` into non-overlapping windows of size ``n``.
           b. Fit a linear trend in each window and compute the RMS of
              residuals: ``F(n)``.
        3. Estimate α1 as the slope of ``log F(n)`` vs ``log n``.

    Clinical interpretation:

    | α1          | Interpretation                                    |
    | ----------- | ------------------------------------------------- |
    | ≈ 0.5       | uncorrelated (white noise) — pathological         |
    | 0.75 – 1.25 | normal fractal long-range correlations            |
    | ≈ 1.5       | Brownian noise — strongly correlated (exercise)   |
    | < 0.75      | possible overtraining or cardiac pathology        |

    Minimum requirement: the series must have at least ``2 × n_max`` intervals
    for DFA to be meaningful. Below this threshold, the function returns
    ``float('nan')``.

    Args:
        rr: An ``RRSeries`` instance containing the intervals to analyse.
        n_min: Smallest window size in beats. Defaults to 4.
        n_max: Largest window size in beats. Defaults to 16.

    Returns:
        DFA α1 exponent (dimensionless). Returns ``float('nan')`` if fewer
        than two valid scales could be computed.

    """
    intervals = rr.intervals
    n_total = len(intervals)

    y = np.cumsum(intervals - np.mean(intervals))

    scales: list[int] = []
    fluctuations: list[float] = []

    for n in range(n_min, n_max + 1):
        n_windows = n_total // n
        if n_windows < 2:
            continue

        y_trimmed = y[: n_windows * n].reshape(n_windows, n)
        t = np.arange(n, dtype=float)
        t_mean = t.mean()
        t_c = t - t_mean
        t_sq_sum = float(np.sum(t_c**2))

        if t_sq_sum == 0.0:
            continue

        row_means = y_trimmed.mean(axis=1, keepdims=True)
        slopes = np.sum((y_trimmed - row_means) * t_c, axis=1) / t_sq_sum
        intercepts = row_means.squeeze() - slopes * t_mean
        trends = slopes[:, np.newaxis] * t + intercepts[:, np.newaxis]
        residuals = y_trimmed - trends

        f_n = float(np.sqrt(np.mean(residuals**2)))
        if f_n > 0.0:
            scales.append(n)
            fluctuations.append(f_n)

    if len(fluctuations) < 2:
        return float("nan")

    log_scales = np.log(np.array(scales, dtype=float))
    log_fluct = np.log(np.array(fluctuations))
    alpha = float(np.polyfit(log_scales, log_fluct, 1)[0])
    return alpha
