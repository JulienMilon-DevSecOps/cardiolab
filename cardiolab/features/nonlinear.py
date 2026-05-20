"""Non-linear HRV metrics: Poincaré plot (SD1/SD2), DFA α1, ApEn and SampEn."""

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


def apen(rr, m: int = 2, r_coef: float = 0.2) -> float:
    """Compute Approximate Entropy (ApEn) of the RR series.

    ApEn quantifies the **regularity** of the signal: a lower value indicates
    a more regular, predictable sequence; a higher value indicates more
    complexity and irregularity.

    Algorithm (Pincus 1991):
        1. Form all templates of length ``m`` from the series.
        2. For each template ``i``, count how many other templates ``j``
           (including ``j = i``) are within Chebyshev distance ``r``.
        3. Compute ``φ(m) = (1 / (N-m+1)) · Σ log(C_i^m / (N-m+1))``.
        4. Repeat for length ``m+1``.
        5. ``ApEn(m, r) = φ(m) − φ(m+1)``.

    Standard clinical parameters: ``m = 2``, ``r = 0.2 · std(RR)``.

    **Complexity**: O(N²) — may be slow for N > 1 000 beats.

    Clinical interpretation:

    | ApEn   | Interpretation                    |
    | ------ | --------------------------------- |
    | < 0.5  | Very regular — low complexity     |
    | 0.5–1.2| Low complexity                    |
    | 1.2–1.8| Normal resting range              |
    | > 1.8  | High — very irregular signal      |

    Reference:
        Pincus, S. M. (1991). Approximate entropy as a measure of system
        complexity. *Proceedings of the National Academy of Sciences*, 88(6),
        2297–2301.

    Args:
        rr: An ``RRSeries`` instance containing the intervals to analyse.
        m: Template length. Defaults to 2.
        r_coef: Tolerance as a fraction of ``std(RR)``. Defaults to 0.2.

    Returns:
        ApEn value (dimensionless, ≥ 0). Returns ``float('nan')`` if the
        series is too short (N < 2m + 1) or has zero standard deviation.

    """
    x = np.asarray(rr.intervals, dtype=float)
    n = len(x)
    r = r_coef * float(np.std(x, ddof=1))

    if n < 2 * m + 1 or r == 0.0:
        return float("nan")

    return float(_apen_phi(x, m, r) - _apen_phi(x, m + 1, r))


def sampen(rr, m: int = 2, r_coef: float = 0.2) -> float:
    """Compute Sample Entropy (SampEn) of the RR series.

    SampEn is an improved version of ApEn that eliminates self-comparison bias
    and is **less sensitive to recording length** than ApEn. A lower SampEn
    indicates a more regular signal; a higher value reflects greater complexity.

    Algorithm (Richman & Moorman 2000):
        1. Count all m-length template pairs (i ≠ j) within Chebyshev distance
           ``r``: total count = **B**.
        2. Count all (m+1)-length template pairs (i ≠ j) within the same ``r``:
           total count = **A**.
        3. ``SampEn = −log(A / B)``.

    Standard clinical parameters: ``m = 2``, ``r = 0.2 · std(RR)``.

    **Complexity**: O(N²) — may be slow for N > 1 000 beats.

    Clinical interpretation:

    | SampEn  | Interpretation                        |
    | ------- | ------------------------------------- |
    | < 0.5   | Very regular — severely reduced HRV   |
    | 0.5–1.2 | Reduced complexity                    |
    | 1.2–2.0 | Normal resting range                  |
    | > 2.0   | High complexity                       |

    Reference:
        Richman, J. S., & Moorman, J. R. (2000). Physiological time-series
        analysis using approximate entropy and sample entropy.
        *American Journal of Physiology — Heart and Circulatory Physiology*,
        278(6), H2039–H2049.

    Args:
        rr: An ``RRSeries`` instance containing the intervals to analyse.
        m: Template length. Defaults to 2.
        r_coef: Tolerance as a fraction of ``std(RR)``. Defaults to 0.2.

    Returns:
        SampEn value (dimensionless, ≥ 0). Returns ``float('nan')`` if the
        series is too short (N < 2m + 2), has zero standard deviation, or
        if no m-length template pairs match (B = 0).

    """
    from numpy.lib.stride_tricks import sliding_window_view

    x = np.asarray(rr.intervals, dtype=float)
    n = len(x)
    r = r_coef * float(np.std(x, ddof=1))

    if n < 2 * m + 2 or r == 0.0:
        return float("nan")

    templates_m = sliding_window_view(x, m)  # shape: (N-m+1, m)
    templates_m1 = sliding_window_view(x, m + 1)  # shape: (N-m,   m+1)
    n_m1 = len(templates_m1)  # N-m (valid m+1 template starts)

    b_count = 0  # m-length matches (self excluded)
    a_count = 0  # (m+1)-length matches (self excluded)

    for i in range(n_m1):
        # b_count: compare m-length template i against all j > i (up to N-m)
        diffs_m = np.max(np.abs(templates_m[i + 1 :] - templates_m[i]), axis=1)
        b_count += int(np.sum(diffs_m <= r))

        # a_count: compare (m+1)-length template i against all j in (i, N-m-1]
        if i < n_m1 - 1:
            diffs_m1 = np.max(np.abs(templates_m1[i + 1 :] - templates_m1[i]), axis=1)
            a_count += int(np.sum(diffs_m1 <= r))

    if b_count == 0 or a_count == 0:
        return float("nan")

    return float(-np.log(a_count / b_count))


# ======================
# INTERNAL HELPERS
# ======================


def _apen_phi(x: np.ndarray, m: int, r: float) -> float:
    """Compute φ(m) for ApEn (Pincus 1991).

    φ(m) = (1 / (N-m+1)) · Σ_{i} log(#{j : d(x_m(i), x_m(j)) ≤ r} / (N-m+1))

    Self-comparison (j = i) is included, ensuring matches ≥ 1 when r > 0.

    Args:
        x: 1-D array of RR intervals.
        m: Template length.
        r: Absolute Chebyshev tolerance (ms).

    Returns:
        φ(m) value (dimensionless).

    """
    from numpy.lib.stride_tricks import sliding_window_view

    templates = sliding_window_view(x, m)  # shape: (N-m+1, m)
    n = len(templates)
    phi = 0.0
    for i in range(n):
        dists = np.max(np.abs(templates - templates[i]), axis=1)
        matches = int(np.sum(dists <= r))
        phi += np.log(matches / n)
    return phi / n
