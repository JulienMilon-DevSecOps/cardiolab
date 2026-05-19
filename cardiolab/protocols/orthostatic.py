"""Orthostatic HRV protocol: 5-min supine + 5-min standing test."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cardiolab.protocols.resting import HRVFeatures, resting_hrv
from cardiolab.signals.rr import RRSeries


@dataclass
class PhaseSegment:
    """A single posture phase extracted from a continuous RR recording.

    Attributes:
        rr: RR intervals for this phase.
        start_sec: Phase start time in seconds (relative to recording start).
        end_sec: Phase end time in seconds.
        duration_sec: Phase duration in seconds.
        features: HRV features computed for this phase.

    """

    rr: RRSeries
    start_sec: float
    end_sec: float
    duration_sec: float
    features: HRVFeatures

    def to_dict(self) -> dict:
        """Return a plain-Python dict for this phase segment.

        The ``rr`` field is excluded (raw signal, too large for serialisation).

        Returns:
            Dictionary with timing fields and nested ``features`` dict.

        """
        return {
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "duration_sec": self.duration_sec,
            "features": self.features.to_dict(),
        }


@dataclass
class TransitionSegment:
    """The postural change window between supine and standing phases.

    Attributes:
        rr: RR intervals captured during the transition.
        start_sec: Transition start time in seconds.
        end_sec: Transition end time in seconds.
        duration_sec: Transition duration in seconds.
        delta_hr: HR increase from supine baseline to transition peak (bpm).
        peak_hr: Maximum instantaneous HR reached during the transition (bpm).
        features: HRV features computed on the transition window.

    """

    rr: RRSeries
    start_sec: float
    end_sec: float
    duration_sec: float
    delta_hr: float
    peak_hr: float
    features: HRVFeatures

    def to_dict(self) -> dict:
        """Return a plain-Python dict for this transition segment.

        The ``rr`` field is excluded (raw signal, too large for serialisation).

        Returns:
            Dictionary with timing, HR dynamics, and nested ``features`` dict.

        """
        return {
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "duration_sec": self.duration_sec,
            "delta_hr": self.delta_hr,
            "peak_hr": self.peak_hr,
            "features": self.features.to_dict(),
        }


@dataclass
class OrthostaticPhases:
    """Container for the three temporal segments of an orthostatic test.

    Attributes:
        supine: Resting lying-down phase.
        transition: Postural change window.
        standing: Stabilised standing phase.

    """

    supine: PhaseSegment
    transition: TransitionSegment
    standing: PhaseSegment


@dataclass
class OrthostaticResult:
    """Results of the 5-min supine + 5-min standing HRV protocol.

    Attributes:
        phases: Segmented phases with their RR series and HRV features.
        hr_response: HR increase from supine to standing (bpm).
            Normal physiological range: 10–25 bpm.
        lf_hf_ratio_change: Ratio of standing LF/HF to supine LF/HF.
            Values above 1 reflect sympathetic activation on standing.
        hf_response_pct: Relative HF power change from supine to standing (%).
            Normal: −30 % to −50 % (vagal withdrawal on standing).
        hf_hr_pct_change: Relative change in the HF/FC ratio from supine to
            standing, expressed as a percentage.
            Formula: (HF/FC_supine − HF/FC_standing) / HF/FC_supine × 100.
            Negative values indicate vagal withdrawal on standing.
            A decline > 80 % reflects strong sympathetic activation.
        interpretation: Clinical classification of the orthostatic response.

    """

    phases: OrthostaticPhases
    hr_response: float
    lf_hf_ratio_change: float
    hf_response_pct: float
    hf_hr_pct_change: float
    interpretation: str

    def to_dict(self) -> dict:
        """Return a plain-Python dict of the full orthostatic result.

        The dictionary is nested: top-level keys are ``phases`` (which
        contains sub-dicts for ``supine``, ``transition``, and ``standing``
        with their timing fields and nested ``features`` dict) and the four
        derived clinical metrics plus ``interpretation``.

        Returns:
            Nested dictionary with ``phases`` (supine / transition / standing)
            and all derived clinical metrics.

        """
        return {
            "phases": {
                "supine": self.phases.supine.to_dict(),
                "transition": self.phases.transition.to_dict(),
                "standing": self.phases.standing.to_dict(),
            },
            "hr_response": self.hr_response,
            "lf_hf_ratio_change": self.lf_hf_ratio_change,
            "hf_response_pct": self.hf_response_pct,
            "hf_hr_pct_change": self.hf_hr_pct_change,
            "interpretation": self.interpretation,
        }

    def to_flat_dict(self) -> dict:
        """Return a wide-format flat dict of the full orthostatic result.

        All phase HRV features are prefixed (``supine_``, ``transition_``,
        ``standing_``). Phase timing fields and the derived clinical metrics
        are appended at the same level. Intended for CSV/DataFrame export.

        Returns:
            Flat dictionary with one key per scalar value.

        """
        row: dict = {}

        for prefix, phase in [
            ("supine", self.phases.supine),
            ("standing", self.phases.standing),
        ]:
            for key, val in phase.features.to_dict().items():
                row[f"{prefix}_{key}"] = val
            row[f"{prefix}_start_sec"] = phase.start_sec
            row[f"{prefix}_end_sec"] = phase.end_sec
            row[f"{prefix}_duration_sec"] = phase.duration_sec

        trans = self.phases.transition
        for key, val in trans.features.to_dict().items():
            row[f"transition_{key}"] = val
        row["transition_start_sec"] = trans.start_sec
        row["transition_end_sec"] = trans.end_sec
        row["transition_duration_sec"] = trans.duration_sec
        row["transition_delta_hr"] = trans.delta_hr
        row["transition_peak_hr"] = trans.peak_hr

        row["hr_response"] = self.hr_response
        row["lf_hf_ratio_change"] = self.lf_hf_ratio_change
        row["hf_response_pct"] = self.hf_response_pct
        row["hf_hr_pct_change"] = self.hf_hr_pct_change
        row["interpretation"] = self.interpretation

        return row

    def to_dataframe(self):
        """Return a one-row wide-format pandas DataFrame of the full result.

        Each phase's HRV features are flattened with a prefix (``supine_``,
        ``transition_``, ``standing_``). Phase timing and the derived clinical
        metrics are added at top level. The result is a single row suitable
        for building a time-series of orthostatic test records.

        Returns:
            A ``pandas.DataFrame`` with one row and one column per scalar
            field.

        Raises:
            ImportError: If ``pandas`` is not installed. Install with
                ``pip install cardiolab[analysis]``.

        """
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install it with: pip install cardiolab[analysis]"
            ) from exc

        return pd.DataFrame([self.to_flat_dict()])


# ======================
# MAIN PROTOCOL
# ======================


def orthostatic_hrv(
    rr: RRSeries,
    min_phase_duration: float = 240.0,
    hr_threshold: float = 10.0,
    window_sec: float = 30.0,
    auto_clean: bool = False,
    method: str = "welch",
) -> OrthostaticResult:
    """Run the orthostatic HRV protocol on a continuous RR recording.

    The recording must span a supine phase immediately followed by a standing
    phase. The postural transition is detected automatically: its onset is the
    first sustained HR rise of at least ``hr_threshold`` bpm above the supine
    baseline; its end is where HR re-stabilises at the new standing level.

    Recommended recording conditions:
        * Total duration ≥ 12 minutes (5 min supine + transition + 5 min standing).
        * Subject remains still during each phase.
        * The signal is outlier-cleaned before calling this function.

    Args:
        rr: Continuous RR recording covering both postures.
        min_phase_duration: Minimum acceptable duration for each phase in
            seconds. Defaults to 240 s (4 minutes).
        hr_threshold: Minimum HR increase (bpm) above the supine baseline that
            triggers transition detection. Defaults to 10 bpm.
        window_sec: Duration of the rolling HR window used for smoothing.
            Defaults to 30 s.
        auto_clean: If ``True``, removes physiological outliers (< 300 ms or
            > 2000 ms) from ``rr`` before phase detection and feature
            computation. Defaults to ``False``.
        method: Spectral estimation method passed to ``resting_hrv()`` for
            each phase. ``"welch"`` (default) suits long phases (≥ 5 min);
            ``"ar"`` offers better resolution on the short transition window
            (< 2 min) — consider ``"ar"`` when the transition is brief.

    Returns:
        An ``OrthostaticResult`` with segmented phases, HRV features for each
        phase, and derived clinical metrics.

    Raises:
        ValueError: If no orthostatic transition is detected.
        ValueError: If the supine or standing phase is shorter than
            ``min_phase_duration``.

    """
    if auto_clean:
        rr = rr.remove_outliers()

    phases = detect_phases(rr, hr_threshold=hr_threshold, window_sec=window_sec, method=method)

    if phases.supine.duration_sec < min_phase_duration:
        raise ValueError(
            f"Supine phase duration {phases.supine.duration_sec:.0f} s "
            f"is shorter than the required {min_phase_duration:.0f} s."
        )
    if phases.standing.duration_sec < min_phase_duration:
        raise ValueError(
            f"Standing phase duration {phases.standing.duration_sec:.0f} s "
            f"is shorter than the required {min_phase_duration:.0f} s."
        )

    supine_f = phases.supine.features
    standing_f = phases.standing.features

    hr_response = standing_f.mean_hr - supine_f.mean_hr

    lf_hf_ratio_change = (
        standing_f.lf_hf / supine_f.lf_hf if supine_f.lf_hf > 0 else float("nan")
    )

    hf_response_pct = (
        (supine_f.hf - standing_f.hf) / supine_f.hf * 100.0
        if supine_f.hf > 0
        else float("nan")
    )

    hf_hr_pct_change = (
        (supine_f.hf_hr - standing_f.hf_hr) / supine_f.hf_hr * 100.0
        if supine_f.hf_hr > 0
        else float("nan")
    )

    interpretation = _interpret_response(hr_response, hf_response_pct)

    return OrthostaticResult(
        phases=phases,
        hr_response=hr_response,
        lf_hf_ratio_change=lf_hf_ratio_change,
        hf_response_pct=hf_response_pct,
        hf_hr_pct_change=hf_hr_pct_change,
        interpretation=interpretation,
    )


# ======================
# PHASE DETECTION
# ======================


def detect_phases(
    rr: RRSeries,
    hr_threshold: float = 10.0,
    window_sec: float = 30.0,
    stabilization_window_sec: float = 20.0,
    stabilization_std_threshold: float = 5.0,
    method: str = "welch",
) -> OrthostaticPhases:
    """Detect supine, transition, and standing phases in a continuous RR series.

    Uses a trailing rolling mean HR window to smooth beat-to-beat noise, then
    locates the first sustained HR rise of at least ``hr_threshold`` bpm above
    the supine baseline. The transition ends when HR re-stabilises at the new
    standing level.

    Args:
        rr: Continuous RR recording spanning both postures.
        hr_threshold: Minimum HR increase (bpm) above the supine baseline to
            declare the onset of the orthostatic transition. Defaults to 10 bpm.
        window_sec: Duration of the trailing rolling HR window for smoothing.
            Defaults to 30 s.
        stabilization_window_sec: Look-ahead window duration used to decide
            when the standing HR has stabilised. Defaults to 20 s.
        stabilization_std_threshold: Maximum beat-to-beat HR standard
            deviation (bpm) within the stabilisation window for the transition
            to be declared complete. Defaults to 5 bpm.
        method: Spectral estimation method forwarded to ``resting_hrv()`` for
            each phase. Defaults to ``"welch"``.

    Returns:
        An ``OrthostaticPhases`` with the three segments and their HRV features.

    Raises:
        ValueError: If no orthostatic transition is detected.

    """
    intervals = rr.intervals
    cumtime = np.cumsum(intervals) / 1000.0
    hr = 60000.0 / intervals

    rolling_hr = _compute_rolling_mean_hr(hr, cumtime, window_sec)

    # Supine baseline: mean HR over the first rolling window
    baseline_mask = cumtime <= window_sec
    baseline_indices = np.where(baseline_mask)[0]
    if len(baseline_indices) == 0:
        baseline_indices = np.arange(min(10, len(hr)))
    supine_baseline_hr = float(np.mean(hr[baseline_indices]))

    transition_threshold = supine_baseline_hr + hr_threshold
    transition_start_idx = _find_sustained_onset(
        rolling_hr, transition_threshold, min_beats=5
    )

    if transition_start_idx is None:
        raise ValueError(
            f"No orthostatic transition detected. "
            f"Supine baseline HR: {supine_baseline_hr:.1f} bpm, "
            f"required rise: ≥ {hr_threshold:.1f} bpm. "
            f"Verify that the recording spans a postural change."
        )

    transition_end_idx = _find_stabilization(
        hr,
        cumtime,
        transition_start_idx,
        stabilization_window_sec,
        stabilization_std_threshold,
    )

    supine_rr, supine_start, supine_end = _extract_segment(
        rr, cumtime, 0, transition_start_idx
    )
    transition_rr, trans_start, trans_end = _extract_segment(
        rr, cumtime, transition_start_idx, transition_end_idx
    )
    standing_rr, standing_start, standing_end = _extract_segment(
        rr, cumtime, transition_end_idx, len(intervals)
    )

    trans_hr_vals = hr[transition_start_idx:transition_end_idx]
    delta_hr = (
        float(np.max(trans_hr_vals) - supine_baseline_hr)
        if len(trans_hr_vals) > 0
        else 0.0
    )
    peak_hr = (
        float(np.max(trans_hr_vals)) if len(trans_hr_vals) > 0 else supine_baseline_hr
    )

    return OrthostaticPhases(
        supine=PhaseSegment(
            rr=supine_rr,
            start_sec=supine_start,
            end_sec=supine_end,
            duration_sec=supine_end - supine_start,
            features=resting_hrv(supine_rr, method=method),
        ),
        transition=TransitionSegment(
            rr=transition_rr,
            start_sec=trans_start,
            end_sec=trans_end,
            duration_sec=trans_end - trans_start,
            delta_hr=delta_hr,
            peak_hr=peak_hr,
            features=resting_hrv(transition_rr, method=method),
        ),
        standing=PhaseSegment(
            rr=standing_rr,
            start_sec=standing_start,
            end_sec=standing_end,
            duration_sec=standing_end - standing_start,
            features=resting_hrv(standing_rr, method=method),
        ),
    )


# ======================
# HELPER FUNCTIONS
# ======================


def _compute_rolling_mean_hr(
    hr: np.ndarray,
    cumtime: np.ndarray,
    window_sec: float,
) -> np.ndarray:
    """Compute a trailing rolling mean HR using a time-based sliding window.

    For each beat ``i``, averages all HR values in the interval
    ``[cumtime[i] − window_sec, cumtime[i]]``. This causal formulation avoids
    future-data leakage and is suitable for onset detection.

    Args:
        hr: Instantaneous HR values (bpm), one per RR interval.
        cumtime: Cumulative beat timestamps (seconds).
        window_sec: Trailing window length in seconds.

    Returns:
        Smoothed HR array with the same shape as ``hr``.

    """
    n = len(hr)
    rolling_hr = np.zeros(n)
    left = 0
    window_sum = 0.0
    window_count = 0

    for i in range(n):
        window_sum += hr[i]
        window_count += 1

        while cumtime[i] - cumtime[left] > window_sec:
            window_sum -= hr[left]
            window_count -= 1
            left += 1

        rolling_hr[i] = window_sum / window_count

    return rolling_hr


def _find_sustained_onset(
    rolling_hr: np.ndarray,
    threshold: float,
    min_beats: int = 5,
) -> int | None:
    """Return the index of the first sustained rise above ``threshold``.

    Requires ``min_beats`` consecutive values above the threshold to avoid
    triggering on isolated ectopic beats or motion artefacts.

    Args:
        rolling_hr: Smoothed HR time series (bpm).
        threshold: HR level above which the transition is considered started.
        min_beats: Minimum consecutive beats required. Defaults to 5.

    Returns:
        Index of the first beat in the first qualifying run, or ``None``.

    """
    run_start = None
    run_length = 0

    for i, h in enumerate(rolling_hr):
        if h > threshold:
            if run_start is None:
                run_start = i
            run_length += 1
            if run_length >= min_beats:
                return run_start
        else:
            run_start = None
            run_length = 0

    return None


def _find_stabilization(
    hr: np.ndarray,
    cumtime: np.ndarray,
    start_idx: int,
    window_sec: float = 20.0,
    std_threshold: float = 5.0,
    min_duration_sec: float = 10.0,
) -> int:
    """Return the index where HR stabilises after the transition onset.

    Starting from ``start_idx + min_duration_sec``, scans forward until the
    standard deviation of HR values within the next ``window_sec`` seconds
    falls below ``std_threshold``. The mandatory offset avoids declaring
    stabilisation before the posture change has had time to take effect.
    If stabilisation is never confirmed, returns the midpoint between
    ``start_idx`` and the end of the recording.

    Args:
        hr: Instantaneous HR array (bpm).
        cumtime: Cumulative timestamps (seconds).
        start_idx: First index to consider (transition onset).
        window_sec: Look-ahead window duration in seconds.
        std_threshold: Maximum HR std (bpm) to declare stability.
        min_duration_sec: Minimum time (s) to wait after ``start_idx`` before
            checking for stabilisation. Defaults to 10 s.

    Returns:
        Index of the first beat where stability is confirmed.

    """
    n = len(hr)
    min_time = cumtime[start_idx] + min_duration_sec

    for i in range(start_idx, n):
        if cumtime[i] < min_time:
            continue

        end_time = cumtime[i] + window_sec
        ahead_mask = (cumtime >= cumtime[i]) & (cumtime <= end_time)
        ahead_hr = hr[ahead_mask]

        if len(ahead_hr) >= 5 and float(np.std(ahead_hr)) < std_threshold:  # noqa: PLR2004
            return i

    return start_idx + (n - start_idx) // 2


def _extract_segment(
    rr: RRSeries,
    cumtime: np.ndarray,
    start_idx: int,
    end_idx: int,
) -> tuple[RRSeries, float, float]:
    """Extract a contiguous sub-series between two beat indices.

    Args:
        rr: Source RR series.
        cumtime: Cumulative timestamps (seconds), same length as ``rr``.
        start_idx: Index of the first beat to include (inclusive).
        end_idx: Index of the first beat to exclude (exclusive).

    Returns:
        A tuple ``(segment_rr, start_sec, end_sec)`` where ``start_sec`` and
        ``end_sec`` are the absolute timestamps of the first and last included
        beats.

    Raises:
        ValueError: If the extracted segment contains fewer than 2 intervals.

    """
    seg_intervals = rr.intervals[start_idx:end_idx]
    seg_timestamps = cumtime[start_idx:end_idx]

    if len(seg_intervals) < 2:  # noqa: PLR2004
        raise ValueError(
            f"Segment [{start_idx}:{end_idx}] contains {len(seg_intervals)} "
            "interval(s); at least 2 are required for HRV computation."
        )

    start_sec = float(cumtime[start_idx - 1]) if start_idx > 0 else 0.0
    end_sec = float(cumtime[end_idx - 1])

    return RRSeries(seg_intervals, seg_timestamps), start_sec, end_sec


# ======================
# INTERPRETATION
# ======================


def _interpret_response(hr_response: float, hf_response_pct: float) -> str:
    """Classify the orthostatic HR response.

    Reference ranges:
        * Normal: 10–25 bpm HR rise, HF drop −30 % to −50 %.
        * Elevated response (possible POTS): HR rise > 30 bpm.
        * Impaired response (possible autonomic dysfunction): HR rise < 5 bpm.
        * Excessive vagal withdrawal: HF drop > 60 %.

    Args:
        hr_response: HR increase from supine to standing (bpm).
        hf_response_pct: Relative HF power change from supine to standing (%).

    Returns:
        One of ``"normal"``, ``"elevated_response"``, ``"impaired_response"``,
        or ``"excessive_vagal_withdrawal"``.

    """
    if hr_response > 30:  # noqa: PLR2004
        return "elevated_response"
    if hr_response < 5:  # noqa: PLR2004
        return "impaired_response"
    if not np.isnan(hf_response_pct) and hf_response_pct < -60:  # noqa: PLR2004
        return "excessive_vagal_withdrawal"
    return "normal"
