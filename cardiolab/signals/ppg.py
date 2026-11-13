"""PPG signal — optical pulse wave, and its pulse-to-pulse intervals (PRV).

A PPG (photoplethysmogram) is what optical sensors record: the green light
under a watch, a finger on a phone camera with its flash. It does not see the
electrical activity of the heart (ECG) but the **pulse wave** in the small
vessels — one rounded wave per beat, about 0.2 s after the R peak.

:class:`PPGSignal` turns it into an :class:`~cardiolab.signals.rr.RRSeries`
of pulse-to-pulse intervals, which every protocol and feature then uses as RR
intervals. The variability is called **pulse rate variability** (PRV):

* at rest and still, PRV is close to HRV — not identical: the pulse transit
  time from the heart to the finger varies a little from beat to beat, which
  tends to raise short-term indices such as RMSSD (Schäfer & Vagedes 2013);
* in motion or during exercise, the wave is distorted: the intervals become
  wrong. Use PPG **at rest only**;
* do not mix PPG and chest-strap sessions in the same baseline.

Processing (cardiolab):

1. **Band-pass** 0.5–8 Hz (2nd-order Butterworth, zero phase): removes the
   baseline wander (breathing, pressure of the finger) and high-frequency
   noise.
2. **Motion**: 2-s windows whose amplitude (SD) is more than 2 × the median
   are marked as motion; no peak is taken there.
3. **Systolic peaks** — two event-related moving averages (Elgendi et al.
   2013): squared positive signal, a 111-ms average (peak) above a 667-ms
   average (beat) + an offset marks blocks of interest; the highest sample of
   each block wide enough is a peak; at most one peak per 0.3 s (200 bpm).
4. **Sub-sample timing**: each peak is refined by a parabola through its
   three samples — at 30 Hz (phone camera) the samples are 33 ms apart, too
   coarse for RMSSD without it.
5. **Pulse present?** — regularity = median over 10-s windows of the
   highest autocorrelation of the filtered signal at a lag of 0.33–2 s (one
   beat, 30–180 bpm). A pulse gives about 0.7–0.8, noise (sensor off the
   skin, too much light) about 0.15; below 0.4 the intervals are graded
   ``poor`` by :func:`~cardiolab.signals.quality.signal_quality`, whatever
   the peaks look like.
6. **Intervals**: peak to peak, in ms; with ``clean=True`` (default) the
   artefacts — missed peaks around motion, extra peaks — are corrected by
   :meth:`~cardiolab.signals.rr.RRSeries.correct_artifacts` (Lipponen &
   Tarvainen 2019), so :func:`~cardiolab.signals.quality.signal_quality`
   grades the series like any other.

Spectral analysis of the result: Lomb-Scargle, the default of
:func:`~cardiolab.features.frequency_domain.frequency_domain` since
0.4.0, suits uneven pulse intervals.

References:
    Elgendi, M., Norton, I., Brearley, M., Abbott, D., & Schuurmans, D.
    (2013). Systolic peak detection in acceleration photoplethysmograms
    measured from emergency responders in tropical conditions. PLoS ONE,
    8(10), e76585.

    Schäfer, A., & Vagedes, J. (2013). How accurate is pulse rate variability
    as an estimate of heart rate variability? A review on studies comparing
    photoplethysmographic technology with an electrocardiogram.
    International Journal of Cardiology, 166(1), 15–29.

"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
from scipy.signal import butter, filtfilt

from cardiolab.signals.rr import RRSeries

MIN_SAMPLING_RATE = 20.0
"""Below this rate (Hz) the pulse wave is not resolved: refused."""

LOW_SAMPLING_RATE = 50.0
"""Below this rate (Hz) the timing relies on the sub-sample refinement: warning."""

BAND_HZ = (0.5, 8.0)
"""Pass band of the pre-filter (Hz)."""

MIN_REGULARITY = 0.4
"""Below this pulse regularity, no regular pulse: the intervals are graded ``poor``."""

REGULARITY_WINDOW_SEC = 10.0

MOTION_WINDOW_SEC = 2.0
MOTION_FACTOR = 2.0
MIN_PEAK_DISTANCE_SEC = 0.3

_W_PEAK_SEC = 0.111
_W_BEAT_SEC = 0.667
_BETA = 0.02

SOURCES: tuple[str, ...] = ("finger", "wrist", "ear", "camera", "unknown")
"""Where the PPG was taken — recorded in the metadata of the intervals."""


@dataclass
class PPGSignal:
    """A raw PPG signal with its time axis.

    Either ``sampling_rate`` or ``timestamps`` is required. Uneven timestamps
    (a phone camera rarely keeps a perfect frame rate) are resampled to an
    even grid at their mean rate.

    Attributes:
        data: Raw PPG samples (any unit; the polarity must make the systolic
            peak a **maximum** — use ``invert=True`` otherwise).
        sampling_rate: Sampling frequency in Hz, inferred from ``timestamps``
            when not given.
        timestamps: Time of each sample in seconds.
        source: Where it was measured — ``finger``, ``wrist``, ``ear``,
            ``camera`` or ``unknown``.
        invert: ``True`` to flip the signal (camera brightness falls when the
            blood volume rises).
        metadata: Free information carried to the intervals.

    Raises:
        ValueError: Missing time axis, length mismatch, unknown source, or a
            sampling rate under 20 Hz.

    """

    data: np.ndarray
    sampling_rate: float | None = None
    timestamps: np.ndarray | None = None
    source: str = "unknown"
    invert: bool = False
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate inputs, resolve the time axis, resample uneven timestamps."""
        self.data = np.asarray(self.data, dtype=float)
        if self.data.ndim != 1 or len(self.data) < 2:
            raise ValueError("data must be a 1-D array of at least 2 samples")
        if not np.all(np.isfinite(self.data)):
            raise ValueError("data contains missing or infinite values")
        if self.source not in SOURCES:
            raise ValueError(
                f"Unknown source {self.source!r}; expected one of {SOURCES}."
            )
        if self.invert:
            self.data = -self.data
            self.invert = False
        if self.timestamps is None and self.sampling_rate is None:
            raise ValueError("Provide either sampling_rate or timestamps")
        if self.timestamps is not None:
            ts = np.asarray(self.timestamps, dtype=float)
            if len(ts) != len(self.data):
                raise ValueError("timestamps and data must have the same length")
            if np.any(np.diff(ts) <= 0):
                raise ValueError("timestamps must be strictly increasing")
            fs = (len(ts) - 1) / (ts[-1] - ts[0])
            if self.sampling_rate is None:
                self.sampling_rate = float(fs)
            grid = ts[0] + np.arange(len(ts)) / self.sampling_rate
            if not np.allclose(ts, grid, atol=0.25 / self.sampling_rate):
                grid = np.arange(ts[0], ts[-1], 1.0 / self.sampling_rate)
                self.data = np.interp(grid, ts, self.data)
                self.metadata.setdefault("resampled", True)
            self.timestamps = grid
        else:
            if self.sampling_rate <= 0:
                raise ValueError("sampling_rate must be > 0")
            self.timestamps = np.arange(len(self.data)) / self.sampling_rate
        if self.sampling_rate < MIN_SAMPLING_RATE:
            raise ValueError(
                f"Sampling rate {self.sampling_rate:.1f} Hz is too low for a pulse "
                f"wave (at least {MIN_SAMPLING_RATE:g} Hz)."
            )

    @property
    def duration(self) -> float:
        """Recording duration in seconds."""
        return float(self.timestamps[-1] - self.timestamps[0])

    # ======================
    # PREPROCESSING
    # ======================

    def bandpass_filter(
        self, low: float = BAND_HZ[0], high: float = BAND_HZ[1]
    ) -> np.ndarray:
        """Return the signal band-passed (2nd-order Butterworth, zero phase).

        Args:
            low: Lower cut-off (Hz).
            high: Upper cut-off (Hz), capped below the Nyquist frequency.

        Returns:
            The filtered signal, same length as ``data``.

        """
        high = min(high, 0.45 * self.sampling_rate)
        b, a = butter(2, [low, high], btype="bandpass", fs=self.sampling_rate)
        return filtfilt(b, a, self.data - np.mean(self.data))

    def motion_mask(self, filtered: np.ndarray | None = None) -> np.ndarray:
        """Return ``True`` for samples in a window marked as motion.

        A 2-s window is motion when its SD exceeds 2 × the median SD of all
        windows.

        Args:
            filtered: Band-passed signal (computed when not given).

        Returns:
            Boolean array, same length as ``data``.

        """
        x = self.bandpass_filter() if filtered is None else filtered
        n = max(1, int(round(MOTION_WINDOW_SEC * self.sampling_rate)))
        starts = range(0, len(x), n)
        sds = np.array([np.std(x[s : s + n]) for s in starts])
        limit = MOTION_FACTOR * float(np.median(sds))
        mask = np.zeros(len(x), dtype=bool)
        for s, sd in zip(starts, sds, strict=True):
            if sd > limit:
                mask[s : s + n] = True
        return mask

    def pulse_regularity(self, filtered: np.ndarray | None = None) -> float:
        """Return how regular the pulse is, from 0 (noise) to 1.

        Median over 10-s windows of the highest autocorrelation of the
        band-passed signal at a lag of 0.33–2 s (one beat at 30–180 bpm).
        A pulse gives about 0.7–0.8, noise about 0.15.

        Args:
            filtered: Band-passed signal (computed when not given).

        Returns:
            The regularity; ``0.0`` for a recording shorter than one window.

        """
        x = self.bandpass_filter() if filtered is None else filtered
        fs = self.sampling_rate
        n = int(REGULARITY_WINDOW_SEC * fs)
        lo, hi = int(0.33 * fs), int(2.0 * fs)
        values = []
        for start in range(0, len(x) - n + 1, n):
            w = x[start : start + n] - np.mean(x[start : start + n])
            energy = float(np.dot(w, w))
            if energy == 0.0:
                values.append(0.0)
                continue
            values.append(
                max(float(np.dot(w[:-k], w[k:])) / energy for k in range(lo, hi))
            )
        return float(np.median(values)) if values else 0.0

    # ======================
    # PEAK DETECTION
    # ======================

    def detect_peaks(self) -> np.ndarray:
        """Detect the systolic peaks (Elgendi et al. 2013), outside motion.

        Returns:
            Peak times in seconds, refined between samples (parabola through
            the peak and its two neighbours).

        """
        fs = self.sampling_rate
        x = self.bandpass_filter()
        motion = self.motion_mask(x)
        y = np.clip(x, 0.0, None) ** 2
        w1 = max(1, int(round(_W_PEAK_SEC * fs)))
        w2 = max(w1 + 1, int(round(_W_BEAT_SEC * fs)))
        ma_peak = np.convolve(y, np.ones(w1) / w1, mode="same")
        ma_beat = np.convolve(y, np.ones(w2) / w2, mode="same")
        blocks = ma_peak > ma_beat + _BETA * float(np.mean(y))

        peaks: list[int] = []
        edges = np.flatnonzero(np.diff(np.r_[0, blocks.astype(int), 0]))
        for start, stop in zip(edges[::2], edges[1::2], strict=True):
            if stop - start < w1 or motion[start:stop].any():
                continue
            i = start + int(np.argmax(x[start:stop]))
            if peaks and (i - peaks[-1]) < MIN_PEAK_DISTANCE_SEC * fs:
                if x[i] > x[peaks[-1]]:
                    peaks[-1] = i
                continue
            peaks.append(i)

        times = []
        for i in peaks:
            shift = 0.0
            if 0 < i < len(x) - 1:
                a, b, c = x[i - 1], x[i], x[i + 1]
                denom = a - 2 * b + c
                if denom < 0:
                    shift = float(np.clip(0.5 * (a - c) / denom, -0.5, 0.5))
            times.append(self.timestamps[i] + shift / fs)
        return np.asarray(times)

    # ======================
    # PPG → INTERVALS
    # ======================

    def to_rr(self, clean: bool = True) -> RRSeries:
        """Convert the pulse wave to pulse-to-pulse intervals.

        Args:
            clean: Correct the artefacts (missed or extra peaks, Lipponen &
                Tarvainen 2019). ``False`` keeps the raw intervals —
                :func:`~cardiolab.signals.quality.signal_quality` then grades
                any artefact as ``poor``.

        Returns:
            An :class:`~cardiolab.signals.rr.RRSeries` (timestamps = time of
            the second peak of each interval) whose metadata carries
            ``signal_type = "ppg"``, the source, the sampling rate, the number
            of peaks, the share of the recording marked as motion and the
            pulse regularity.

        Raises:
            ValueError: If fewer than 3 peaks are found.

        """
        if self.sampling_rate < LOW_SAMPLING_RATE:
            warnings.warn(
                f"PPG at {self.sampling_rate:.0f} Hz: the beat timing relies on "
                "interpolation between samples; 50 Hz or more is better.",
                stacklevel=2,
            )
        peaks = self.detect_peaks()
        if len(peaks) < 3:
            raise ValueError("Not enough pulse peaks detected (fewer than 3).")
        filtered = self.bandpass_filter()
        motion_pct = 100.0 * float(np.mean(self.motion_mask(filtered)))
        regularity = self.pulse_regularity(filtered)
        rr = RRSeries(
            np.diff(peaks) * 1000.0,
            timestamps=peaks[1:],
            metadata={
                **self.metadata,
                "signal_type": "ppg",
                "ppg_source": self.source,
                "ppg_sampling_rate": round(float(self.sampling_rate), 2),
                "ppg_n_peaks": int(len(peaks)),
                "ppg_motion_pct": round(motion_pct, 1),
                "ppg_regularity": round(regularity, 3),
            },
        )
        if regularity < MIN_REGULARITY:
            warnings.warn(
                f"No regular pulse (regularity {regularity:.2f} < {MIN_REGULARITY}): "
                "check that the sensor touches the skin; these intervals are "
                "graded poor.",
                stacklevel=2,
            )
        if motion_pct > 20.0:
            warnings.warn(
                f"{motion_pct:.0f} % of the recording is motion: measure again, "
                "still, the sensor held steady.",
                stacklevel=2,
            )
        return rr.correct_artifacts()[0] if clean else rr

    def __repr__(self):
        """Return a concise string representation."""
        return (
            f"PPGSignal(len={len(self.data)}, fs={self.sampling_rate:.2f}Hz, "
            f"duration={self.duration:.2f}s, source={self.source!r})"
        )


def is_ppg(rr: RRSeries) -> bool:
    """Return ``True`` when the intervals come from a PPG (pulse, not ECG)."""
    return bool(rr.metadata) and rr.metadata.get("signal_type") == "ppg"
