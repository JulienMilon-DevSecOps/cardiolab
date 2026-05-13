"""Time-domain HRV metrics computed directly on RR intervals."""

from __future__ import annotations

import numpy as np


def rmssd(rr) -> float:
    """Compute the Root Mean Square of Successive Differences (RMSSD).

    RMSSD is the primary time-domain metric for short-term HRV. It measures
    beat-to-beat variability and reflects parasympathetic (vagal) nervous
    system activity.

    Formula: ``sqrt(mean((RR[i+1] - RR[i])²))``

    Clinical interpretation:
        * High RMSSD → good recovery, relaxed state, strong vagal tone.
        * Low RMSSD  → stress, fatigue, or high training load.

    Typical resting values (adults):

    | RMSSD (ms) | Interpretation |
    | ---------- | -------------- |
    | < 20       | very low       |
    | 20 – 40    | low            |
    | 40 – 70    | normal         |
    | 70 – 100   | high           |
    | > 100      | very high      |

    Values are highly individual and depend on age and fitness level.

    Args:
        rr: An ``RRSeries`` instance containing the intervals to analyse.

    Returns:
        RMSSD value in milliseconds.

    """
    diff = np.diff(rr.intervals)
    return float(np.sqrt(np.mean(diff ** 2)))


def ln_rmssd(rr) -> float:
    """Compute the natural logarithm of RMSSD.

    Raw RMSSD values are right-skewed, making statistical comparisons
    unreliable. The log transformation produces a more normally distributed
    metric that is better suited for tracking day-to-day changes and building
    baselines.

    Args:
        rr: An ``RRSeries`` instance containing the intervals to analyse.

    Returns:
        Natural logarithm of RMSSD. Returns ``0.0`` if RMSSD is zero or
        negative (degenerate case).

    """
    value = rmssd(rr)

    if value <= 0:
        return 0.0

    return float(np.log(value))


def sdnn(rr) -> float:
    """Compute the Standard Deviation of NN intervals (SDNN).

    SDNN captures overall heart rate variability over the recording window.
    Unlike RMSSD, it reflects both sympathetic and parasympathetic contributions
    and is therefore sensitive to the recording duration: values are not
    directly comparable across different window lengths.

    Typical resting values for short-term recordings (~5 min):

    | SDNN (ms) | Interpretation |
    | --------- | -------------- |
    | < 20      | very low       |
    | 20 – 50   | low            |
    | 50 – 80   | normal         |
    | > 80      | high           |

    Args:
        rr: An ``RRSeries`` instance containing the intervals to analyse.

    Returns:
        SDNN value in milliseconds (computed with ddof=1).

    """
    return float(np.std(rr.intervals, ddof=1))


def pnn50(rr) -> float:
    """Compute the percentage of successive RR pairs differing by more than 50 ms.

    pNN50 complements RMSSD as a measure of parasympathetic activity. It
    counts the proportion of consecutive interval differences that exceed 50 ms,
    expressed as a percentage of the total number of pairs.

    Formula: ``(count of |RR[i+1] - RR[i]| > 50 ms) / (n - 1) × 100``

    Typical resting values:

    | pNN50 (%) | Interpretation |
    | --------- | -------------- |
    | < 5 %     | very low       |
    | 5 – 15 %  | low            |
    | 15 – 30 % | normal         |
    | > 30 %    | high           |

    Note: pNN50 is sensitive to noise and short recordings. RMSSD is generally
    preferred for clinical or sports applications.

    Args:
        rr: An ``RRSeries`` instance containing the intervals to analyse.

    Returns:
        pNN50 as a percentage (float between 0 and 100).

    """
    diff = np.abs(np.diff(rr.intervals))
    return float(np.sum(diff > 50) / len(diff) * 100)
