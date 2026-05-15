"""ECG signal representation and processing."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import find_peaks

from cardiolab.signals.rr import RRSeries


@dataclass
class ECGSignal:
    """A raw ECG signal with its associated temporal axis.

    Stores a single-lead ECG recording and exposes methods for preprocessing,
    R-peak detection, and conversion to RR intervals. Either ``sampling_rate``
    or ``timestamps`` must be provided; if both are given, their consistency
    is validated at construction time.

    Attributes:
        data: Raw ECG voltage samples as a 1-D array.
        sampling_rate: Acquisition frequency in Hz. Inferred from
            ``timestamps`` when not supplied.
        timestamps: Time of each sample in seconds. Generated from
            ``sampling_rate`` when not supplied.

    Raises:
        ValueError: If neither ``sampling_rate`` nor ``timestamps`` is given.
        ValueError: If ``timestamps`` is provided but its length differs from
            ``data``.
        ValueError: If both ``sampling_rate`` and ``timestamps`` are provided
            but are inconsistent (relative tolerance 1 %).

    """

    data: np.ndarray
    sampling_rate: float | None = None
    timestamps: np.ndarray | None = None

    def __post_init__(self):
        """Validate inputs and resolve the timestamps/sampling_rate pair."""
        self.data = np.asarray(self.data, dtype=float)

        if self.timestamps is not None:
            self.timestamps = np.asarray(self.timestamps, dtype=float)
            if len(self.timestamps) != len(self.data):
                raise ValueError("timestamps and data must have the same length")

        if self.sampling_rate is None and self.timestamps is None:
            raise ValueError("Provide either sampling_rate or timestamps")

        # Case 1: timestamps provided → infer sampling_rate
        if self.sampling_rate is None:
            self.sampling_rate = self._infer_sampling_rate()

        # Case 2: sampling_rate provided → generate timestamps
        elif self.timestamps is None:
            self.timestamps = self._generate_timestamps()

        # Case 3: both provided → validate consistency
        else:
            self._validate_consistency()

    # ======================
    # INFERENCE
    # ======================

    def _infer_sampling_rate(self) -> float:
        """Estimate the sampling frequency from the timestamps.

        Uses the mean inter-sample interval to handle minor jitter in the
        time axis.

        Returns:
            Estimated sampling frequency in Hz.

        Raises:
            ValueError: If the mean inter-sample interval is zero or negative.

        """
        dt = np.diff(self.timestamps)
        mean_dt = np.mean(dt)

        if mean_dt <= 0:
            raise ValueError("Invalid timestamps: non-positive mean interval")

        return float(1.0 / mean_dt)

    def _generate_timestamps(self) -> np.ndarray:
        """Build a uniform timestamp array from the sampling rate.

        Returns:
            Array of sample timestamps starting at 0.0 seconds, with step
            ``1 / sampling_rate``.

        Raises:
            ValueError: If ``sampling_rate`` is zero or negative.

        """
        if self.sampling_rate <= 0:
            raise ValueError("sampling_rate must be > 0")

        n = len(self.data)
        return np.arange(n) / self.sampling_rate

    # ======================
    # VALIDATION
    # ======================

    def _validate_consistency(self):
        """Verify that the provided sampling_rate matches the timestamps.

        Compares the mean inter-sample interval derived from ``timestamps``
        against the expected interval from ``sampling_rate``, using a 1 %
        relative tolerance.

        Raises:
            ValueError: If the relative discrepancy exceeds 1 %.

        """
        dt = np.diff(self.timestamps)
        mean_dt = np.mean(dt)
        expected_dt = 1.0 / self.sampling_rate

        if not np.isclose(mean_dt, expected_dt, rtol=1e-2):
            raise ValueError(
                f"Inconsistency between timestamps and sampling_rate "
                f"(dt={mean_dt:.6f} vs expected={expected_dt:.6f})"
            )

    # ======================
    # PROPERTIES
    # ======================

    @property
    def duration(self) -> float:
        """Total recording duration in seconds.

        Returns:
            Difference between the last and first timestamps.

        """
        return self.timestamps[-1] - self.timestamps[0]

    # ======================
    # PREPROCESSING
    # ======================

    def bandpass_filter(self, low: float = 5.0, high: float = 15.0) -> np.ndarray:
        """Apply a second-order Butterworth bandpass filter to the ECG signal.

        The default pass-band (5–15 Hz) attenuates baseline wander and
        high-frequency noise while preserving the QRS complex energy.

        Args:
            low: Lower cutoff frequency in Hz. Defaults to 5.0 Hz.
            high: Upper cutoff frequency in Hz. Defaults to 15.0 Hz.

        Returns:
            Filtered ECG signal as a 1-D array, same shape as ``data``.

        """
        from scipy.signal import butter, filtfilt

        nyquist = 0.5 * self.sampling_rate
        low /= nyquist
        high /= nyquist

        b, a = butter(2, [low, high], btype="band")
        return filtfilt(b, a, self.data)

    # ======================
    # R-PEAK DETECTION
    # ======================

    def detect_r_peaks(self) -> np.ndarray:
        """Detect R-peak positions using a Pan-Tompkins-inspired approach.

        The pipeline applies bandpass filtering, signal squaring, and moving
        window integration before peak detection. A minimum inter-peak
        distance of 300 ms is enforced to avoid double-detection.

        Returns:
            Array of sample indices corresponding to detected R-peaks.

        """
        filtered = self.bandpass_filter()
        squared = filtered**2

        window_size = int(0.150 * self.sampling_rate)
        integrated = np.convolve(
            squared, np.ones(window_size) / window_size, mode="same"
        )

        distance = int(0.3 * self.sampling_rate)
        peaks, _ = find_peaks(integrated, distance=distance)

        return peaks

    # ======================
    # ECG → RR
    # ======================

    def to_rr(self, clean: bool = True) -> RRSeries:
        """Convert the ECG signal to an RR interval series.

        Detects R-peaks, computes inter-peak intervals in milliseconds, and
        optionally removes physiologically implausible intervals.

        Args:
            clean: If ``True``, calls ``RRSeries.remove_outliers()`` on the
                resulting series to eliminate artefacts. Defaults to ``True``.

        Returns:
            RRSeries derived from consecutive R-peak intervals, with
            timestamps set to the midpoint between each pair of peaks.

        Raises:
            ValueError: If fewer than 2 R-peaks are detected.

        """
        r_peaks = self.detect_r_peaks()

        if len(r_peaks) < 2:
            raise ValueError("Not enough R-peaks detected")

        rr_intervals = np.diff(self.timestamps[r_peaks]) * 1000.0

        rr_timestamps = (
            self.timestamps[r_peaks[:-1]] + self.timestamps[r_peaks[1:]]
        ) / 2

        rr = RRSeries(rr_intervals, rr_timestamps)

        if clean:
            rr = rr.remove_outliers()

        return rr

    def __repr__(self):
        """Return a concise string representation."""
        return (
            f"ECGSignal(len={len(self.data)}, "
            f"fs={self.sampling_rate:.2f}Hz, "
            f"duration={self.duration:.2f}s)"
        )
