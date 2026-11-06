"""DFA α1 thresholds: aerobic and anaerobic thresholds from an incremental test.

During exercise, the short-term fractal exponent DFA α1 of the RR series falls
as intensity rises: about 1.0 at low intensity (correlated beat pattern), 0.75
around the first ventilatory threshold, 0.5 (random pattern) around the second,
and below 0.5 at high intensity. On an incremental test (ramp or short stages
up to exhaustion), the heart rate at which α1 crosses these values estimates
the thresholds without gas exchange or lactate:

| α1   | Threshold | Reference                                                   |
| ---- | --------- | ----------------------------------------------------------- |
| 0.75 | HRVT1 ≈ VT1 (aerobic threshold)   | Rogers et al. 2021, *Front. Physiol.* |
| 0.5  | HRVT2 ≈ VT2 (anaerobic threshold) | Rogers et al. 2021, *J. Funct. Morphol. Kinesiol.* |

Method (Rogers et al. 2021):

1. α1 is computed over a **2-minute window** centred on each time point
   (1 min before, 1 min after), **every 5 s**, with box sizes 4–16 beats.
2. Over the decline of α1, a linear regression of α1 against heart rate gives
   the heart rate at the threshold value. For HRVT1 the regression uses the
   windows where α1 lies between about 1.0 and 0.5 (as published); for HRVT2,
   between 0.75 and 0.25 (same ±0.25 band around the threshold — cardiolab
   choice, the HRVT2 paper reuses the HRVT1 method).
3. A regression of α1 against time gives the moment of each threshold, from
   which the intensity (power, speed) is read when it is provided.

Only the part of the test up to the peak heart rate is used: α1 rises again
during recovery. A threshold is never extrapolated — if α1 never falls below
its value, it is reported as ``not_reached``.

Reliability. Agreement with ventilatory thresholds is good on average (HRVT1:
bias −1.9 bpm, limits of agreement −12 to +8 bpm, n = 15 — Rogers et al. 2021)
but individual errors of ±10 bpm occur, and the agreement is weaker with
stages of several minutes than with ramps. A chest strap is required: optical
sensors do not give beat-accurate intervals during exercise. Missed beats
bias α1 (Rogers et al. 2021, *Sensors*): artefacts are corrected first and a
:class:`PhysiologicalWarning` is raised above 5 % of corrected beats.

References:
    Rogers, B., Giles, D., Draper, N., Hoos, O., & Gronwald, T. (2021). A new
    detection method defining the aerobic threshold for endurance exercise and
    training prescription based on fractal correlation properties of heart
    rate variability. Frontiers in Physiology, 11, 596567.

    Rogers, B., Giles, D., Draper, N., Mourot, L., & Gronwald, T. (2021).
    Detection of the anaerobic threshold in endurance sports: validation of a
    new method using correlation properties of heart rate variability. Journal
    of Functional Morphology and Kinesiology, 6(2), 38.

    Rogers, B., Giles, D., Draper, N., Mourot, L., & Gronwald, T. (2021).
    Influence of artefact correction and recording device type on the
    practical application of a non-linear heart rate variability biomarker for
    aerobic threshold determination. Sensors, 21(3), 821.

"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np

from cardiolab.analytics.zones import HeartRateZone, five_zones, three_zones
from cardiolab.features.nonlinear import dfa_alpha1
from cardiolab.signals.quality import SignalQuality, signal_quality
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries

WINDOW_SEC = 120.0
"""Length of the window over which α1 is computed (s) — Rogers et al. 2021."""

STEP_SEC = 5.0
"""Interval between two α1 values (s) — Rogers et al. 2021."""

ALPHA_VT1 = 0.75
"""α1 value of the first (aerobic) threshold."""

ALPHA_VT2 = 0.5
"""α1 value of the second (anaerobic) threshold."""

FIT_BAND = 0.25
"""Half-width of the α1 band used by each regression (0.75 ± 0.25 = 1.0 – 0.5)."""

MIN_FIT_SEC = 60.0
"""Minimum time span of the windows used by a regression (s)."""

MAX_CORRECTED_PCT = 5.0
"""Share of corrected beats above which the thresholds are flagged (%)."""

HR_MAX_HOLD_SEC = 5.0
"""Duration a heart rate must be held to count as the maximal heart rate (s)."""


@dataclass
class ThresholdEstimate:
    """One threshold (HRVT1 or HRVT2) estimated from the α1 decline.

    Attributes:
        alpha: α1 value of the threshold (0.75 or 0.5).
        status: ``"detected"``, ``"not_reached"`` (α1 never fell below
            ``alpha`` before the peak heart rate) or ``"unreliable"`` (too few
            windows in the band, or α1 not decreasing with heart rate).
        hr: Heart rate at the threshold (bpm), ``nan`` unless detected.
        time_sec: Moment of the threshold from the start of the recording (s).
        intensity: Intensity (power, speed…) at that moment, when provided.
        r_squared: R² of the α1 – heart rate regression.
        n_windows: Number of α1 windows used by the regression.

    """

    alpha: float
    status: str
    hr: float = float("nan")
    time_sec: float = float("nan")
    intensity: float = float("nan")
    r_squared: float = float("nan")
    n_windows: int = 0

    @property
    def detected(self) -> bool:
        """``True`` when the threshold was found."""
        return self.status == "detected"


@dataclass
class DFAThresholdsResult:
    """Results of a DFA α1 threshold test.

    Attributes:
        vt1: First threshold (α1 = 0.75, aerobic).
        vt2: Second threshold (α1 = 0.5, anaerobic).
        times: Centre of each α1 window (s from the start).
        alpha1: α1 of each window (``nan`` when the window has too few beats).
        hr: Mean heart rate of each window (bpm).
        intensity: Mean intensity of each window, or ``None`` without
            intensity data.
        intensity_unit: Unit of the intensity (``"W"``, ``"km/h"``…).
        hr_peak: Highest window heart rate (bpm) — the end of the analysed
            part of the test.
        hr_max_observed: Highest heart rate held for 5 s (median of the
            beats of the last 5 s) — the maximal heart rate when the test
            went to exhaustion.
        quality: Signal quality of the recording.

    """

    vt1: ThresholdEstimate
    vt2: ThresholdEstimate
    times: np.ndarray
    alpha1: np.ndarray
    hr: np.ndarray
    intensity: np.ndarray | None = None
    intensity_unit: str | None = None
    hr_peak: float = float("nan")
    hr_max_observed: float = float("nan")
    quality: SignalQuality | None = field(default=None, repr=False)

    def zones(self, hr_max: float | None = None, model: int = 5) -> list[HeartRateZone]:
        """Return the heart rate training zones anchored on both thresholds.

        Args:
            hr_max: Maximal heart rate (bpm). Defaults to
                ``hr_max_observed`` — the test went to exhaustion.
            model: ``5`` (five zones, :func:`~cardiolab.analytics.zones.five_zones`)
                or ``3`` (three zones, :func:`~cardiolab.analytics.zones.three_zones`).

        Returns:
            The zones, from the easiest.

        Raises:
            ValueError: If a threshold was not detected, if ``model`` is not
                3 or 5, or if the heart rates are not ordered.

        """
        if not (self.vt1.detected and self.vt2.detected):
            raise ValueError(
                "Both thresholds are needed for the zones "
                f"(HRVT1: {self.vt1.status}, HRVT2: {self.vt2.status})."
            )
        if model not in (3, 5):
            raise ValueError(f"model must be 3 or 5, got {model}")
        top = self.hr_max_observed if hr_max is None else hr_max
        build = five_zones if model == 5 else three_zones
        return build(self.vt1.hr, self.vt2.hr, top)

    def to_dict(self) -> dict:
        """Return the scalar results as a JSON-ready dict (no window series)."""
        out: dict = {}
        for name, est in (("vt1", self.vt1), ("vt2", self.vt2)):
            out[f"{name}_status"] = est.status
            out[f"{name}_hr"] = est.hr
            out[f"{name}_time_sec"] = est.time_sec
            out[f"{name}_intensity"] = est.intensity
            out[f"{name}_r_squared"] = est.r_squared
        out["intensity_unit"] = self.intensity_unit
        out["hr_peak"] = self.hr_peak
        out["hr_max_observed"] = self.hr_max_observed
        out["n_windows"] = int(np.sum(np.isfinite(self.alpha1)))
        if self.quality is not None:
            out["quality"] = self.quality.to_dict()
        return out


THRESHOLD_SOURCES = ("dfa", "manual")
"""Origin of stored thresholds: a DFA α1 test, or values entered by hand (lab test)."""


@dataclass
class ThresholdRecord:
    """Thresholds as stored — from a DFA α1 test or entered by hand.

    The flat form of :class:`DFAThresholdsResult` (no α1 series), also used
    for thresholds measured elsewhere (laboratory test) so that the training
    zones can be built either way.

    Attributes:
        date: Date of the test (ISO).
        sport: Sport code of the reference list (zones are sport-specific).
        source: ``"dfa"`` or ``"manual"``.
        vt1_hr: Heart rate at the first threshold (bpm), ``nan`` if unknown.
        vt2_hr: Heart rate at the second threshold (bpm), ``nan`` if unknown.
        vt1_status: ``detected`` / ``not_reached`` / ``unreliable``
            (``detected`` for manual values).
        vt2_status: Same for the second threshold.
        vt1_intensity: Power or speed at the first threshold, ``nan`` if unknown.
        vt2_intensity: Same for the second threshold.
        intensity_unit: Unit of the intensities.
        vt1_r_squared: R² of the HRVT1 regression (``nan`` for manual values).
        vt2_r_squared: R² of the HRVT2 regression.
        hr_max_observed: Highest heart rate held for 5 s during the test.
        quality: Signal quality of the test (``None`` for manual values).

    """

    date: str
    sport: str = "other"
    source: str = "dfa"
    vt1_hr: float = float("nan")
    vt2_hr: float = float("nan")
    vt1_status: str = "not_reached"
    vt2_status: str = "not_reached"
    vt1_intensity: float = float("nan")
    vt2_intensity: float = float("nan")
    intensity_unit: str | None = None
    vt1_r_squared: float = float("nan")
    vt2_r_squared: float = float("nan")
    hr_max_observed: float = float("nan")
    quality: SignalQuality | None = None

    def __post_init__(self) -> None:
        """Validate the source."""
        if self.source not in THRESHOLD_SOURCES:
            raise ValueError(
                f"source must be one of {THRESHOLD_SOURCES}, got {self.source!r}"
            )

    @classmethod
    def from_result(
        cls, result: DFAThresholdsResult, date: str, sport: str = "other"
    ) -> ThresholdRecord:
        """Flatten a DFA α1 test for storage."""
        return cls(
            date=date,
            sport=sport,
            source="dfa",
            vt1_hr=result.vt1.hr,
            vt2_hr=result.vt2.hr,
            vt1_status=result.vt1.status,
            vt2_status=result.vt2.status,
            vt1_intensity=result.vt1.intensity,
            vt2_intensity=result.vt2.intensity,
            intensity_unit=result.intensity_unit,
            vt1_r_squared=result.vt1.r_squared,
            vt2_r_squared=result.vt2.r_squared,
            hr_max_observed=result.hr_max_observed,
            quality=result.quality,
        )

    @classmethod
    def manual(
        cls,
        date: str,
        vt1_hr: float,
        vt2_hr: float,
        sport: str = "other",
        vt1_intensity: float = float("nan"),
        vt2_intensity: float = float("nan"),
        intensity_unit: str | None = None,
    ) -> ThresholdRecord:
        """Thresholds entered by hand (laboratory test, known values).

        Raises:
            ValueError: Unless ``0 < vt1_hr < vt2_hr``.

        """
        if not 0 < vt1_hr < vt2_hr:
            raise ValueError(
                f"Expected 0 < HRVT1 < HRVT2, got {vt1_hr:.0f} / {vt2_hr:.0f} bpm"
            )
        return cls(
            date=date,
            sport=sport,
            source="manual",
            vt1_hr=float(vt1_hr),
            vt2_hr=float(vt2_hr),
            vt1_status="detected",
            vt2_status="detected",
            vt1_intensity=vt1_intensity,
            vt2_intensity=vt2_intensity,
            intensity_unit=intensity_unit,
        )

    def to_dict(self) -> dict:
        """Return a flat, JSON-ready dict (quality as a nested dict)."""
        out = {k: v for k, v in self.__dict__.items() if k != "quality"}
        out["quality"] = self.quality.to_dict() if self.quality is not None else None
        return out

    def zones(self, hr_max: float | None = None, model: int = 5) -> list[HeartRateZone]:
        """Return the training zones (see :meth:`DFAThresholdsResult.zones`).

        Args:
            hr_max: Maximal heart rate (bpm); defaults to ``hr_max_observed``.
            model: ``5`` or ``3``.

        Raises:
            ValueError: If a threshold is missing, HRmax is unknown, or the
                model is not 3 or 5.

        """
        if self.vt1_status != "detected" or self.vt2_status != "detected":
            raise ValueError("Both thresholds are needed for the zones.")
        if model not in (3, 5):
            raise ValueError(f"model must be 3 or 5, got {model}")
        top = self.hr_max_observed if hr_max is None else hr_max
        if not np.isfinite(top):
            raise ValueError("HRmax unknown: pass hr_max (profile or HRmax test).")
        build = five_zones if model == 5 else three_zones
        return build(self.vt1_hr, self.vt2_hr, top)


def dfa_alpha1_series(
    rr: RRSeries,
    window_sec: float = WINDOW_SEC,
    step_sec: float = STEP_SEC,
    n_min: int = 4,
    n_max: int = 16,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute α1 over a sliding window — the time-varying DFA α1.

    Each value uses the beats within ``window_sec / 2`` before and after its
    centre; centres are ``step_sec`` apart, the first and last half window
    excluded.

    Args:
        rr: RR series of the whole test.
        window_sec: Window length (s). Defaults to 120 s.
        step_sec: Interval between two centres (s). Defaults to 5 s.
        n_min: Smallest DFA box size (beats).
        n_max: Largest DFA box size (beats). A window with fewer than
            ``2 × n_max`` beats gives ``nan``.

    Returns:
        ``(times, alpha1, hr)``: window centres (s from the start), α1 and
        mean heart rate (bpm) of each window.

    Raises:
        ValueError: If the recording is shorter than one window.

    """
    rr_ms = np.asarray(rr.intervals, dtype=float)
    beat_t = np.cumsum(rr_ms) / 1000.0
    duration = float(beat_t[-1])
    half = window_sec / 2.0
    if duration < window_sec:
        raise ValueError(
            f"Recording too short ({duration:.0f} s) for one {window_sec:.0f}-s "
            "α1 window."
        )

    centres = np.arange(half, duration - half + 1e-9, step_sec)
    alpha = np.full(len(centres), np.nan)
    hr = np.full(len(centres), np.nan)
    starts = np.searchsorted(beat_t, centres - half, side="left")
    ends = np.searchsorted(beat_t, centres + half, side="left")
    for i, (a, b) in enumerate(zip(starts, ends, strict=True)):
        window = rr_ms[a:b]
        if len(window) == 0:
            continue
        hr[i] = 60_000.0 / float(np.mean(window))
        if len(window) >= 2 * n_max:
            alpha[i] = dfa_alpha1(RRSeries(window), n_min=n_min, n_max=n_max)
    return centres, alpha, hr


def dfa_thresholds(
    rr: RRSeries,
    intensity: tuple[np.ndarray, np.ndarray] | None = None,
    intensity_unit: str | None = None,
    *,
    auto_clean: bool = True,
    window_sec: float = WINDOW_SEC,
    step_sec: float = STEP_SEC,
    alpha_vt1: float = ALPHA_VT1,
    alpha_vt2: float = ALPHA_VT2,
) -> DFAThresholdsResult:
    """Estimate the aerobic and anaerobic thresholds from an incremental test.

    The test is a ramp or short stages from an easy pace up to exhaustion,
    recorded with a chest strap. See the module docstring for the method.

    Args:
        rr: RR series of the whole test (warm-up included is fine).
        intensity: Optional ``(time_sec, values)`` — power (W), speed (km/h)…
            sampled over the test, time counted from the first beat.
        intensity_unit: Unit of ``intensity``, stored with the result.
        auto_clean: Correct artefacts before the analysis (recommended:
            missed beats bias α1). Defaults to ``True``.
        window_sec: α1 window length (s). Defaults to 120 s.
        step_sec: Interval between two α1 values (s). Defaults to 5 s.
        alpha_vt1: α1 value of the first threshold. Defaults to 0.75.
        alpha_vt2: α1 value of the second threshold. Defaults to 0.5.

    Returns:
        ``DFAThresholdsResult`` with both thresholds, the α1 series and the
        signal quality.

    Raises:
        ValueError: If the recording is shorter than one α1 window, or if
            ``intensity`` arrays differ in length.

    Warns:
        PhysiologicalWarning: Above 5 % of corrected beats — α1 is biased.

    """
    if auto_clean:
        rr, _ = rr.correct_artifacts()
    quality = signal_quality(rr)
    if quality.artifact_pct > MAX_CORRECTED_PCT:
        warnings.warn(
            f"{quality.artifact_pct:.1f} % of beats corrected (above "
            f"{MAX_CORRECTED_PCT:.0f} %): DFA α1 is biased, the thresholds are "
            "unreliable. Check the chest strap contact and record again.",
            PhysiologicalWarning,
            stacklevel=2,
        )

    times, alpha, hr = dfa_alpha1_series(rr, window_sec=window_sec, step_sec=step_sec)

    window_intensity = None
    if intensity is not None:
        t_int = np.asarray(intensity[0], dtype=float)
        v_int = np.asarray(intensity[1], dtype=float)
        if t_int.shape != v_int.shape:
            raise ValueError("intensity time and values must have the same length")
        window_intensity = _window_means(t_int, v_int, times, window_sec)

    # Analyse up to the peak heart rate: α1 rises again during recovery
    valid = np.isfinite(alpha) & np.isfinite(hr)
    hr_peak = float(np.nanmax(hr)) if np.any(np.isfinite(hr)) else float("nan")
    end = int(np.nanargmax(np.where(np.isfinite(hr), hr, -np.inf))) + 1
    valid[end:] = False

    vt1 = _estimate(alpha_vt1, times, alpha, hr, valid, window_intensity, step_sec)
    vt2 = _estimate(alpha_vt2, times, alpha, hr, valid, window_intensity, step_sec)

    return DFAThresholdsResult(
        vt1=vt1,
        vt2=vt2,
        times=times,
        alpha1=alpha,
        hr=hr,
        intensity=window_intensity,
        intensity_unit=intensity_unit,
        hr_peak=hr_peak,
        hr_max_observed=_max_sustained_hr(rr, HR_MAX_HOLD_SEC),
        quality=quality,
    )


# ======================
# INTERNAL HELPERS
# ======================


def _max_sustained_hr(rr: RRSeries, hold_sec: float) -> float:
    """Highest median heart rate over the beats of any ``hold_sec``-second span."""
    rr_ms = np.asarray(rr.intervals, dtype=float)
    beat_t = np.cumsum(rr_ms) / 1000.0
    hr = 60_000.0 / rr_ms
    starts = np.searchsorted(beat_t, beat_t - hold_sec, side="right")
    best = float("nan")
    for i, s in enumerate(starts):
        if beat_t[i] - beat_t[0] < hold_sec:
            continue
        med = float(np.median(hr[s : i + 1]))
        if not med <= best:  # also replaces the initial nan
            best = med
    return best


def _window_means(
    t: np.ndarray, v: np.ndarray, centres: np.ndarray, window_sec: float
) -> np.ndarray:
    """Mean of ``v`` over each window; interpolated where a window has no sample."""
    half = window_sec / 2.0
    out = np.full(len(centres), np.nan)
    for i, c in enumerate(centres):
        mask = (t >= c - half) & (t < c + half) & np.isfinite(v)
        if np.any(mask):
            out[i] = float(np.mean(v[mask]))
        elif len(t):
            out[i] = float(np.interp(c, t, v))
    return out


def _estimate(
    target: float,
    times: np.ndarray,
    alpha: np.ndarray,
    hr: np.ndarray,
    valid: np.ndarray,
    intensity: np.ndarray | None,
    step_sec: float,
) -> ThresholdEstimate:
    """Estimate the threshold where α1 crosses ``target`` (see module docstring)."""
    if not np.any(valid & (alpha <= target)):
        return ThresholdEstimate(alpha=target, status="not_reached")

    # Windows of the decline whose α1 lies in target ± FIT_BAND, from the last
    # time α1 was above the band before it first fell below the target
    first_below = int(np.argmax(valid & (alpha <= target)))
    above = np.where(valid[:first_below] & (alpha[:first_below] >= target + FIT_BAND))[
        0
    ]
    start = int(above[-1]) if len(above) else 0
    band = (
        valid
        & (np.arange(len(alpha)) >= start)
        & (alpha <= target + FIT_BAND)
        & (alpha >= target - FIT_BAND)
    )
    n = int(np.sum(band))
    if n * step_sec < MIN_FIT_SEC:
        return ThresholdEstimate(alpha=target, status="unreliable", n_windows=n)

    slope, intercept = np.polyfit(hr[band], alpha[band], 1)
    if slope >= 0:
        return ThresholdEstimate(alpha=target, status="unreliable", n_windows=n)
    hr_thr = float((target - intercept) / slope)
    # Never extrapolate: the threshold must lie within the heart rates observed
    if not hr[band].min() <= hr_thr <= hr[band].max():
        return ThresholdEstimate(alpha=target, status="unreliable", n_windows=n)
    pred = slope * hr[band] + intercept
    ss_res = float(np.sum((alpha[band] - pred) ** 2))
    ss_tot = float(np.sum((alpha[band] - alpha[band].mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    t_slope, t_intercept = np.polyfit(times[band], alpha[band], 1)
    t_thr = float((target - t_intercept) / t_slope) if t_slope < 0 else float("nan")
    i_thr = float("nan")
    if intensity is not None and np.isfinite(t_thr):
        ok = np.isfinite(intensity)
        i_thr = float(np.interp(t_thr, times[ok], intensity[ok]))

    return ThresholdEstimate(
        alpha=target,
        status="detected",
        hr=hr_thr,
        time_sec=t_thr,
        intensity=i_thr,
        r_squared=r2,
        n_windows=n,
    )
