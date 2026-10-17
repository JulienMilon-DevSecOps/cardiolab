"""RR artefact detection and correction (Lipponen & Tarvainen, 2019).

Deleting an abnormal RR interval (as :meth:`RRSeries.remove_outliers` does)
joins its two neighbours into a fake successive difference, which biases
RMSSD, pNN50, SD1 and above all DFA α1. This module **classifies** each
abnormal beat and **corrects** it instead:

========================  ==============================  =======================================
Artefact                  Typical cause                   Correction
========================  ==============================  =======================================
Extra beat                spurious peak (noise, T wave)   merged with the next interval
Missed beat               undetected peak                 interval split in two equal halves
Ectopic beat              premature beat + compensation   value interpolated (cubic spline)
Long / short beat         other abnormal interval         value interpolated (cubic spline)
========================  ==============================  =======================================

Detection follows Lipponen & Tarvainen (2019): successive differences
``dRR`` and deviations from an 11-beat median ``mRR`` are normalised by
time-varying thresholds — ``5.2 ×`` the quartile deviation over 91 beats —
then classified with the decision rules of the paper (``c1 = 0.13``,
``c2 = 0.17``). Detection and correction are repeated until no artefact is
left (``max_passes``, one by default). A beat classified ectopic or long/short
is only corrected if it deviates by at least 20 % from the local median
(:data:`DEFAULT_MIN_DEVIATION`), so that the strong respiratory arrhythmia of
trained athletes is not mistaken for artefacts.

Reference:
    Lipponen, J. A., & Tarvainen, M. P. (2019). A robust algorithm for heart
    rate variability time series artefact correction using novel beat
    classification. *Journal of Medical Engineering & Technology*, 43(3),
    173–181.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.ndimage import median_filter

# Parameters of Lipponen & Tarvainen (2019)
_ALPHA = 5.2  # threshold = ALPHA × quartile deviation
_WINDOW = 91  # beats used for the time-varying thresholds
_MEDIAN_ORDER = 11  # beats of the local median RR
_C1 = 0.13  # ectopic decision boundary — slope
_C2 = 0.17  # ectopic decision boundary — offset

MIN_BEATS = 15
"""Below this number of intervals, no detection is attempted."""

DEFAULT_MIN_DEVIATION = 0.20
"""Minimum deviation from the local median for ectopic / long-short corrections.

Lipponen & Tarvainen's rules alone also flag the sharp but physiological
swings of a strong respiratory sinus arrhythmia (trained athletes at rest,
RR ≈ 1 100–1 300 ms): correcting them would erase real variability. A beat
classified ectopic or long/short is therefore only corrected if it deviates
from the 11-beat median by at least 20 % — the classic amplitude criterion of
HRV editing. Missed and extra beats keep their own structural tests.
``0`` (or ``None``) restores the published rules unchanged.
"""

WARNING_THRESHOLD_PCT = 5.0
"""Share of corrected beats above which the recording is considered unreliable."""


@dataclass
class ArtifactReport:
    """Summary of an artefact correction.

    Attributes:
        n_input: Number of RR intervals before correction.
        n_output: Number of RR intervals after correction (missed beats add
            one interval, extra beats remove one).
        ectopic: Ectopic beats corrected (all passes).
        missed: Missed beats corrected.
        extra: Extra beats corrected.
        long_short: Long or short beats corrected.
        passes: Detection passes run (``0`` if the series was too short).
        method: Correction method.
        indices: Detected indices per type, concatenated over passes (each
            pass indexes the series as it was at that pass).

    """

    n_input: int
    n_output: int
    ectopic: int = 0
    missed: int = 0
    extra: int = 0
    long_short: int = 0
    passes: int = 0
    method: str = "lipponen2019"
    indices: dict[str, list[int]] = field(default_factory=dict)

    @property
    def n_corrected(self) -> int:
        """Total number of corrected beats."""
        return self.ectopic + self.missed + self.extra + self.long_short

    @property
    def corrected_pct(self) -> float:
        """Share of corrected beats, in % of the input intervals."""
        return 100.0 * self.n_corrected / self.n_input if self.n_input else 0.0

    @property
    def is_reliable(self) -> bool:
        """``True`` when at most :data:`WARNING_THRESHOLD_PCT` % of beats were corrected."""
        return self.corrected_pct <= WARNING_THRESHOLD_PCT

    def to_dict(self) -> dict:
        """Return a JSON-serialisable summary (without the per-pass indices)."""
        return {
            "method": self.method,
            "n_input": self.n_input,
            "n_output": self.n_output,
            "ectopic": self.ectopic,
            "missed": self.missed,
            "extra": self.extra,
            "long_short": self.long_short,
            "n_corrected": self.n_corrected,
            "corrected_pct": round(self.corrected_pct, 2),
            "passes": self.passes,
        }


# ======================
# DETECTION
# ======================


def _rolling_quartile_deviation(values: np.ndarray, window: int) -> np.ndarray:
    """Quartile deviation ``(Q3 − Q1) / 2`` of ``|values|`` over a centred window."""
    abs_values = np.abs(values)
    half = window // 2
    n = len(abs_values)
    qd = np.empty(n)
    for i in range(n):
        chunk = abs_values[max(0, i - half) : i + half + 1]
        q1, q3 = np.percentile(chunk, [25, 75])
        qd[i] = (q3 - q1) / 2.0
    return qd


def _threshold(values: np.ndarray) -> np.ndarray:
    """Time-varying threshold ``ALPHA × QD``; zero thresholds become ``inf``."""
    th = _ALPHA * _rolling_quartile_deviation(values, _WINDOW)
    th[th <= 0] = np.inf
    return th


def detect_artifacts(
    intervals: np.ndarray,
    min_deviation: float | None = DEFAULT_MIN_DEVIATION,
) -> dict[str, list[int]]:
    """Classify the abnormal beats of an RR series (Lipponen & Tarvainen 2019).

    Args:
        intervals: RR intervals (any time unit, typically ms).
        min_deviation: Minimum relative deviation from the local median for a
            beat to be kept as ectopic or long/short (see
            :data:`DEFAULT_MIN_DEVIATION`). ``0`` or ``None`` disables it.

    Returns:
        ``{"ectopic": [...], "missed": [...], "extra": [...], "long_short": [...]}``
        — indices into ``intervals``. Empty lists when the series has fewer
        than :data:`MIN_BEATS` intervals.

    """
    result: dict[str, list[int]] = {
        "ectopic": [],
        "missed": [],
        "extra": [],
        "long_short": [],
    }
    rr = np.asarray(intervals, dtype=float)
    n = len(rr)
    if n < MIN_BEATS:
        return result

    # Successive differences, normalised by their time-varying threshold
    drrs = np.diff(rr, prepend=rr[0])
    drrs[0] = np.mean(drrs[1:])
    drr = drrs / _threshold(drrs)

    # Deviation from the local median; negative deviations count double
    med_rr = median_filter(rr, size=_MEDIAN_ORDER, mode="nearest")
    mrrs = rr - med_rr
    mrrs[mrrs < 0] *= 2.0
    th2 = _threshold(mrrs)
    mrr = mrrs / th2

    # Subspaces S12 / S22 (neighbour differences), reflect-padded by 2
    pad = np.pad(drr, 2, mode="reflect")
    s12 = np.zeros(n)
    s22 = np.zeros(n)
    for k in range(n):
        d = k + 2
        if pad[d] > 0:
            s12[k] = max(pad[d - 1], pad[d + 1])
        elif pad[d] < 0:
            s12[k] = min(pad[d - 1], pad[d + 1])
        if pad[d] >= 0:
            s22[k] = min(pad[d + 1], pad[d + 2])
        else:
            s22[k] = max(pad[d + 1], pad[d + 2])

    i = 0
    while i < n - 2:
        # Ectopic beat: large difference followed by an opposite one
        ectopic_up = drr[i] > 1 and s12[i] < -_C1 * drr[i] - _C2
        ectopic_down = drr[i] < -1 and s12[i] > -_C1 * drr[i] + _C2
        if ectopic_up or ectopic_down:
            result["ectopic"].append(i)
            i += 1
            continue

        if not (abs(drr[i]) > 1 or abs(mrr[i]) > 3):
            i += 1
            continue

        # Long / short candidates: this beat, and the next one if more abnormal
        candidates = [i]
        if abs(drr[i + 1]) < abs(drr[i + 2]):
            candidates.append(i + 1)

        for j in candidates:
            long_beat = drr[j] > 1 and s22[j] < -1
            short_beat = drr[j] < -1 and s22[j] > 1
            if not (long_beat or short_beat or abs(mrr[j]) > 3):
                continue
            missed = abs(rr[j] / 2.0 - med_rr[j]) < th2[j]
            extra = j + 1 < n and abs(rr[j] + rr[j + 1] - med_rr[j]) < th2[j]
            if short_beat and extra:
                result["extra"].append(j)
            elif long_beat and missed:
                result["missed"].append(j)
            else:
                result["long_short"].append(j)
        i += 1

    # Amplitude gate: ignore physiological swings (strong respiratory arrhythmia)
    if min_deviation:
        rel_dev = np.abs(rr - med_rr) / med_rr
        for key in ("ectopic", "long_short"):
            result[key] = [j for j in result[key] if rel_dev[j] >= min_deviation]

    # A beat is classified once (first label wins), sorted for correction
    seen: set[int] = set()
    for key in ("extra", "missed", "ectopic", "long_short"):
        result[key] = sorted(j for j in dict.fromkeys(result[key]) if j not in seen)
        seen.update(result[key])
    return result


# ======================
# CORRECTION
# ======================


def _apply_corrections(
    rr: np.ndarray,
    ts: np.ndarray | None,
    found: dict[str, list[int]],
) -> tuple[np.ndarray, np.ndarray | None]:
    """Apply one pass of corrections to ``rr`` (and its end timestamps ``ts``)."""
    rr_list = rr.tolist()
    ts_list = ts.tolist() if ts is not None else None
    interpolate = set(found["ectopic"]) | set(found["long_short"])
    merge = set(found["extra"])
    split = set(found["missed"])

    new_rr: list[float] = []
    new_ts: list[float] = []
    to_interp: list[int] = []
    j = 0
    while j < len(rr_list):
        if j in merge and j + 1 < len(rr_list):
            # Extra beat: the spurious peak is removed, two intervals become one
            new_rr.append(rr_list[j] + rr_list[j + 1])
            if ts_list is not None:
                new_ts.append(ts_list[j + 1])
            j += 2
            continue
        if j in split:
            # Missed beat: a peak is added in the middle of the long interval
            half = rr_list[j] / 2.0
            new_rr.extend([half, half])
            if ts_list is not None:
                new_ts.extend([ts_list[j] - half / 1000.0, ts_list[j]])
            j += 1
            continue
        if j in interpolate:
            to_interp.append(len(new_rr))
        new_rr.append(rr_list[j])
        if ts_list is not None:
            new_ts.append(ts_list[j])
        j += 1

    out = np.asarray(new_rr, dtype=float)
    if to_interp:
        idx = np.asarray(to_interp)
        good = np.ones(len(out), dtype=bool)
        good[idx] = False
        if good.sum() >= 2:
            t = np.cumsum(out)
            values = np.interp(t[idx], t[good], out[good])  # edges: nearest value
            if good.sum() >= 4:
                spline = CubicSpline(t[good], out[good], extrapolate=False)
                cubic = spline(t[idx])
                values = np.where(np.isnan(cubic), values, cubic)
            out[idx] = values
    return out, (np.asarray(new_ts, dtype=float) if ts_list is not None else None)


def correct_artifacts(
    intervals: np.ndarray,
    timestamps: np.ndarray | None = None,
    max_passes: int = 1,
    min_deviation: float | None = DEFAULT_MIN_DEVIATION,
) -> tuple[np.ndarray, np.ndarray | None, ArtifactReport]:
    """Detect and correct RR artefacts (Lipponen & Tarvainen 2019).

    Args:
        intervals: RR intervals in milliseconds.
        timestamps: Optional end time of each interval (seconds); kept in sync
            when beats are added or removed.
        max_passes: Maximum number of detection / correction passes; stops
            earlier as soon as a pass finds nothing. Defaults to 1, as in the
            published method: further passes tend to re-flag values that the
            previous pass interpolated.
        min_deviation: Amplitude gate for ectopic / long-short beats (see
            :data:`DEFAULT_MIN_DEVIATION`); ``0`` or ``None`` disables it.

    Returns:
        ``(intervals, timestamps, report)`` — corrected intervals, matching
        timestamps (or ``None``) and the :class:`ArtifactReport`.

    """
    rr = np.asarray(intervals, dtype=float)
    ts = None if timestamps is None else np.asarray(timestamps, dtype=float)
    report = ArtifactReport(n_input=len(rr), n_output=len(rr))
    if len(rr) < MIN_BEATS:
        return rr.copy(), (None if ts is None else ts.copy()), report

    for _ in range(max_passes):
        found = detect_artifacts(rr, min_deviation=min_deviation)
        report.passes += 1
        if not any(found.values()):
            break
        for key, idx in found.items():
            report.indices.setdefault(key, []).extend(idx)
        report.ectopic += len(found["ectopic"])
        report.missed += len(found["missed"])
        report.extra += len(found["extra"])
        report.long_short += len(found["long_short"])
        rr, ts = _apply_corrections(rr, ts, found)

    report.n_output = len(rr)
    return rr, ts, report
