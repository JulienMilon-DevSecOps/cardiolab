"""RR interval series representation and processing."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np

_RR_LOW: float = 300.0
_RR_HIGH: float = 2000.0


class PhysiologicalWarning(UserWarning):
    """Raised when RR intervals fall outside physiological bounds.

    Intervals below 300 ms correspond to HR > 200 bpm; intervals above 2000 ms
    to HR < 30 bpm. Both ranges are likely artefacts unless the subject has a
    documented extreme cardiac condition. Consider calling
    ``RRSeries.remove_outliers()`` before further analysis.
    """


@dataclass
class RRSeries:
    """A time series of RR intervals measured in milliseconds.

    An RR interval is the time between two consecutive R-peaks in an ECG signal,
    or equivalently the inter-beat interval from a heart rate monitor. This class
    is the core data structure for all HRV computations in cardiolab.

    Attributes:
        intervals: RR intervals in milliseconds. Must contain at least 2 values,
            all strictly positive.
        timestamps: Absolute timestamps (in seconds) associated with each interval.
            If not provided, cumulative timestamps are derived on demand.
        metadata: Free-form dictionary for contextual information such as the
            recording device, subject ID, or session type.

    Raises:
        ValueError: If ``intervals`` contains fewer than 2 values or any
            non-positive value.
        ValueError: If ``timestamps`` is provided but does not match the length
            of ``intervals``.

    """

    intervals: np.ndarray
    timestamps: np.ndarray | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate and normalise inputs after dataclass initialisation."""
        self.intervals = np.asarray(self.intervals, dtype=float)

        if self.timestamps is not None:
            self.timestamps = np.asarray(self.timestamps, dtype=float)
            if len(self.timestamps) != len(self.intervals):
                raise ValueError("timestamps and intervals must have the same length")

        self._validate()

    # ======================
    # VALIDATION
    # ======================

    def _validate(self) -> None:
        if len(self.intervals) < 2:
            raise ValueError("RRSeries must contain at least 2 intervals")

        if np.any(self.intervals <= 0):
            raise ValueError("RR intervals must be positive")

        n_low = int(np.sum(self.intervals < _RR_LOW))
        n_high = int(np.sum(self.intervals > _RR_HIGH))

        if n_low > 0:
            warnings.warn(
                f"{n_low} interval(s) below {_RR_LOW:.0f} ms "
                f"(HR > {60000.0 / _RR_LOW:.0f} bpm) detected — possible artefacts. "
                "Call remove_outliers() before analysis.",
                PhysiologicalWarning,
                stacklevel=3,
            )
        if n_high > 0:
            warnings.warn(
                f"{n_high} interval(s) above {_RR_HIGH:.0f} ms "
                f"(HR < {60000.0 / _RR_HIGH:.0f} bpm) detected — possible artefacts. "
                "Call remove_outliers() before analysis.",
                PhysiologicalWarning,
                stacklevel=3,
            )

    # ======================
    # BASIC PROPERTIES
    # ======================

    @property
    def duration(self) -> float:
        """Total recording duration in seconds.

        Computed as the sum of all RR intervals converted from milliseconds.

        Returns:
            Total duration in seconds.

        """
        return np.sum(self.intervals) / 1000.0

    @property
    def mean_rr(self) -> float:
        """Mean RR interval in milliseconds.

        Returns:
            Arithmetic mean of all RR intervals (ms).

        """
        return float(np.mean(self.intervals))

    @property
    def mean_hr(self) -> float:
        """Mean heart rate in beats per minute.

        Derived from the mean RR interval: HR = 60000 / mean_rr.

        Returns:
            Mean heart rate (bpm).

        """
        return float(60000.0 / self.mean_rr)

    @property
    def min_hr(self) -> float:
        """Minimum heart rate in beats per minute.

        Corresponds to the longest RR interval in the series.

        Returns:
            Minimum heart rate (bpm).

        """
        return float(60000.0 / np.max(self.intervals))

    @property
    def max_hr(self) -> float:
        """Maximum heart rate in beats per minute.

        Corresponds to the shortest RR interval in the series.

        Returns:
            Maximum heart rate (bpm).

        """
        return float(60000.0 / np.min(self.intervals))

    # ======================
    # CONVERSIONS
    # ======================

    def to_hr(self) -> np.ndarray:
        """Convert the RR interval series to instantaneous heart rate values.

        Each interval is converted using HR = 60000 / RR.

        Returns:
            Array of instantaneous heart rate values (bpm), same length as
            ``intervals``.

        """
        return 60000.0 / self.intervals

    @classmethod
    def from_hr(cls, hr_values: np.ndarray) -> RRSeries:
        """Create an RRSeries from a heart rate series.

        Converts each HR value to an RR interval using RR = 60000 / HR.
        This conversion is an approximation: it loses beat-to-beat timing
        information and should be used only when raw RR data is unavailable.

        Args:
            hr_values: Array of heart rate values in beats per minute.
                All values must be strictly positive.

        Returns:
            A new RRSeries derived from the provided HR values.

        Raises:
            ValueError: If any value in ``hr_values`` is zero or negative.

        """
        hr_values = np.asarray(hr_values, dtype=float)

        if np.any(hr_values <= 0):
            raise ValueError("HR must be > 0")

        rr = 60000.0 / hr_values
        return cls(rr)

    # ======================
    # CLEANING
    # ======================

    def remove_outliers(
        self,
        low: float = 300,
        high: float = 2000,
        method: str = "threshold",
    ) -> RRSeries:
        """Return a new RRSeries with outlier intervals removed.

        Two methods are supported:

        * ``"threshold"``: removes any interval outside [``low``, ``high``].
        * ``"zscore"``: removes any interval whose z-score exceeds 3.

        Args:
            low: Lower physiological bound in milliseconds. Intervals below
                this value are considered artefacts. Defaults to 300 ms.
            high: Upper physiological bound in milliseconds. Intervals above
                this value are considered artefacts. Defaults to 2000 ms.
            method: Outlier detection strategy, either ``"threshold"`` or
                ``"zscore"``.

        Returns:
            A new RRSeries containing only the retained intervals. Timestamps
            and metadata are preserved and filtered accordingly.

        Raises:
            ValueError: If ``method`` is not ``"threshold"`` or ``"zscore"``.

        """
        rr = self.intervals.copy()

        if method == "threshold":
            mask = (rr >= low) & (rr <= high)

        elif method == "zscore":
            std = np.std(rr)
            if std == 0.0:
                return RRSeries(rr, self.timestamps, self.metadata)
            z = (rr - np.mean(rr)) / std
            mask = np.abs(z) < 3

        else:
            raise ValueError("Method unknown")

        cleaned_rr = rr[mask]
        timestamps = self.timestamps[mask] if self.timestamps is not None else None

        return RRSeries(cleaned_rr, timestamps, self.metadata)

    # ======================
    # INTERPOLATION
    # ======================

    def interpolate(self, fs: float = 4.0) -> tuple[np.ndarray, np.ndarray]:
        """Resample the RR series onto a uniform time grid.

        RR intervals are unevenly spaced in time. Frequency-domain analysis
        (Welch PSD) requires a uniformly sampled signal. This method performs
        linear interpolation to produce an evenly-spaced version.

        Args:
            fs: Target sampling frequency in Hz. The HRV standard recommends
                at least 4 Hz to capture the HF band (0.15–0.4 Hz).
                Defaults to 4.0 Hz.

        Returns:
            A tuple ``(t_interp, rr_interp)`` where:

            * ``t_interp`` is the uniform time axis (seconds).
            * ``rr_interp`` is the interpolated RR signal (ms).

        """
        if self.timestamps is None:
            t = np.cumsum(self.intervals) / 1000.0
        else:
            t = self.timestamps

        t_interp = np.arange(t[0], t[-1], 1.0 / fs)
        rr_interp = np.interp(t_interp, t, self.intervals)

        return t_interp, rr_interp

    # ======================
    # SEGMENTATION
    # ======================

    def segment(self, window_sec: float) -> list[RRSeries]:
        """Split the series into non-overlapping fixed-duration segments.

        Segments are built by accumulating consecutive intervals until their
        cumulative duration reaches ``window_sec``. The last incomplete segment
        (if any) is discarded.

        Args:
            window_sec: Desired segment duration in seconds.

        Returns:
            List of RRSeries objects, each covering approximately
            ``window_sec`` seconds. May be empty if the total duration is
            shorter than one window.

        """
        segments = []
        current: list[float] = []
        current_ts: list[float] = []
        total_time = 0.0

        for i, rr in enumerate(self.intervals):
            current.append(rr)
            if self.timestamps is not None:
                current_ts.append(self.timestamps[i])
            total_time += rr / 1000.0

            if total_time >= window_sec:
                ts = np.array(current_ts) if self.timestamps is not None else None
                segments.append(RRSeries(np.array(current), ts, self.metadata))
                current = []
                current_ts = []
                total_time = 0.0

        return segments

    # ======================
    # DEBUG
    # ======================

    def summary(self) -> dict:
        """Return a brief summary of the series.

        Returns:
            Dictionary with the following keys:

            * ``"n"``: number of intervals.
            * ``"duration_s"``: total duration in seconds.
            * ``"mean_rr"``: mean RR interval in milliseconds.
            * ``"mean_hr"``: mean heart rate in bpm.

        """
        return {
            "n": len(self.intervals),
            "duration_s": self.duration,
            "mean_rr": self.mean_rr,
            "mean_hr": self.mean_hr,
        }

    # ======================
    # MAGIC METHODS
    # ======================

    def __len__(self):
        """Return the number of RR intervals in the series."""
        return len(self.intervals)

    def __repr__(self):
        """Return a concise string representation."""
        return f"RRSeries(n={len(self)}, mean_hr={self.mean_hr:.1f}, "
