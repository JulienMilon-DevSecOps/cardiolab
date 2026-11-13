"""Tests of the PPG signal and its pulse-to-pulse intervals — synthetic pulse waves."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from cardiolab.features.frequency_domain import frequency_domain
from cardiolab.protocols.resting import resting_hrv
from cardiolab.sensors_tools.ppg import parse_ppg_csv
from cardiolab.signals.ppg import PPGSignal, is_ppg
from cardiolab.signals.quality import signal_quality
from cardiolab.signals.rr import RRSeries


def _synthetic(
    fs: float,
    duration: float = 300.0,
    seed: int = 0,
    noise: float = 0.02,
    motion: tuple[float, float] | None = None,
):
    """Pulse wave with known beats: systolic + dicrotic wave, baseline wander.

    Beats ≈ 900 ms, modulated by breathing (0.25 Hz) and a slow 0.1 Hz wave.
    Returns ``(signal, time, true intervals in ms)``.
    """
    rng = np.random.default_rng(seed)
    beats = [0.5]
    while beats[-1] < duration:
        t = beats[-1]
        beats.append(
            t
            + 0.9
            + 0.05 * np.sin(2 * np.pi * 0.25 * t)
            + 0.03 * np.sin(2 * np.pi * 0.1 * t)
            + rng.normal(0, 0.01)
        )
    beats = np.array(beats)
    t = np.arange(0, duration, 1 / fs)
    x = np.zeros_like(t)
    for b in beats:
        x += np.exp(-(((t - b - 0.12) / 0.09) ** 2))
        x += 0.35 * np.exp(-(((t - b - 0.42) / 0.08) ** 2))
    x += 0.3 * np.sin(2 * np.pi * 0.2 * t) + rng.normal(0, noise, len(t))
    if motion:
        m = (t >= motion[0]) & (t < motion[1])
        x[m] += rng.normal(0, 2.0, m.sum())
    return x, t, np.diff(beats) * 1000.0


def _rmssd(v) -> float:
    return float(np.sqrt(np.mean(np.diff(v) ** 2)))


# ======================
# Construction
# ======================


class TestConstruction:
    """Time axis, source, validation."""

    def test_sampling_rate(self):
        """Timestamps generated from the rate."""
        s = PPGSignal(np.zeros(500), 100.0, source="finger")
        assert s.timestamps[1] == pytest.approx(0.01)
        assert s.duration == pytest.approx(4.99)
        assert "finger" in repr(s)

    def test_uneven_timestamps_resampled(self):
        """A camera's uneven frames are put on an even grid at their mean rate."""
        rng = np.random.default_rng(0)
        ts = np.cumsum(1 / 30 + rng.normal(0, 0.004, 900))
        s = PPGSignal(np.sin(ts), timestamps=ts, source="camera")
        assert s.sampling_rate == pytest.approx(30.0, rel=0.02)
        assert np.allclose(np.diff(s.timestamps), 1 / s.sampling_rate)
        assert s.metadata["resampled"]

    def test_invert(self):
        """invert=True flips the signal (camera brightness)."""
        s = PPGSignal(np.array([1.0, 2.0, 3.0]), 25.0, invert=True)
        np.testing.assert_array_equal(s.data, [-1.0, -2.0, -3.0])

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"data": np.zeros(10)}, "sampling_rate or timestamps"),
            ({"data": np.zeros(10), "sampling_rate": 10.0}, "too low"),
            ({"data": np.zeros(10), "sampling_rate": 50.0, "source": "toe"}, "source"),
            ({"data": np.array([1.0, np.nan]), "sampling_rate": 50.0}, "missing"),
            ({"data": np.zeros(3), "timestamps": np.array([0, 1, 1.0])}, "increasing"),
            ({"data": np.zeros(3), "timestamps": np.zeros(2)}, "same length"),
        ],
    )
    def test_invalid(self, kwargs, match):
        """Missing time axis, rate under 20 Hz, unknown source, bad data."""
        with pytest.raises(ValueError, match=match):
            PPGSignal(**kwargs)


# ======================
# Peaks and intervals — acceptance criterion: ±10 ms
# ======================


class TestIntervals:
    """Known pulse intervals recovered."""

    @pytest.mark.parametrize("fs", [100.0, 50.0, 30.0])
    def test_intervals_within_10_ms(self, fs):
        """Every interval within 10 ms of the truth, at 100, 50 and 30 Hz (camera)."""
        x, _, true = _synthetic(fs)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rr = PPGSignal(x, fs, source="finger").to_rr()
        n = min(len(rr.intervals), len(true))
        assert abs(len(rr.intervals) - len(true)) <= 1
        assert np.abs(rr.intervals[:n] - true[:n]).max() < 10.0
        assert _rmssd(rr.intervals) == pytest.approx(_rmssd(true), rel=0.03)

    def test_metadata(self):
        """The intervals say they come from a PPG."""
        x, _, _ = _synthetic(100.0, duration=60.0)
        rr = PPGSignal(x, 100.0, source="wrist").to_rr()
        assert is_ppg(rr)
        assert not is_ppg(RRSeries(np.full(10, 900.0)))
        assert rr.metadata["ppg_source"] == "wrist"
        assert rr.metadata["ppg_sampling_rate"] == 100.0
        assert rr.metadata["ppg_motion_pct"] == 0.0
        assert "artifact_correction" in rr.metadata

    def test_low_rate_warns(self):
        """Under 50 Hz: a warning on the timing."""
        x, _, _ = _synthetic(30.0, duration=60.0)
        with pytest.warns(UserWarning, match="interpolation"):
            PPGSignal(x, 30.0).to_rr()

    def test_motion_set_aside(self):
        """8 s of motion: marked, no peak taken there, RMSSD unchanged."""
        x, t, true = _synthetic(100.0, motion=(100.0, 108.0))
        s = PPGSignal(x, 100.0)
        mask = s.motion_mask()
        assert mask[(t >= 101) & (t < 107)].mean() > 0.5
        assert not mask[t < 90].any()
        peaks = s.detect_peaks()
        idx = np.round(peaks * 100.0).astype(int)
        assert not mask[np.clip(idx, 0, len(mask) - 1)].any()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rr = s.to_rr()
        assert rr.metadata["ppg_motion_pct"] > 0
        assert _rmssd(rr.intervals) == pytest.approx(_rmssd(true), rel=0.05)

    def test_mostly_motion_warns(self):
        """More than 20 % of motion: measure again."""
        x, _, _ = _synthetic(100.0, duration=60.0, motion=(10.0, 30.0))
        with pytest.warns(UserWarning, match="motion"):
            PPGSignal(x, 100.0).to_rr(clean=False)

    def test_too_few_peaks(self):
        """A flat signal (sensor not on the skin): no pulse."""
        with pytest.raises(ValueError, match="peaks"):
            PPGSignal(np.full(3000, 0.5), 100.0).to_rr()


# ======================
# Downstream: quality, features, protocols
# ======================


class TestDownstream:
    """The intervals feed the usual pipeline."""

    def test_quality_and_resting(self):
        """Clean PPG → good quality; resting_hrv gives the true RMSSD."""
        x, _, true = _synthetic(100.0)
        rr = PPGSignal(x, 100.0, source="finger").to_rr()
        assert signal_quality(rr).grade == "good"
        features = resting_hrv(rr)
        assert features.rmssd == pytest.approx(_rmssd(true), rel=0.05)

    def test_lomb_scargle_default(self):
        """Breathing at 0.25 Hz lands in HF with the default (Lomb-Scargle)."""
        x, _, _ = _synthetic(100.0)
        rr = PPGSignal(x, 100.0).to_rr()
        freq = frequency_domain(rr)
        assert freq["HF"] > freq["LF"]


# ======================
# CSV reader
# ======================


class TestParsePPGCsv:
    """Generic CSV: value column + time column or sampling rate."""

    def _write(self, tmp_path, header, rows, sep=","):
        path = tmp_path / "ppg.csv"
        lines = [sep.join(header)] + [sep.join(str(v) for v in r) for r in rows]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def test_time_column_in_ms(self, tmp_path):
        """Semicolon, decimal commas, time in ms → 100 Hz signal."""
        x, t, true = _synthetic(100.0, duration=60.0)
        rows = [
            (f"{ti * 1000:.1f}", f"{xi:.5f}".replace(".", ","))
            for ti, xi in zip(t, x, strict=True)
        ]
        path = self._write(tmp_path, ["time_ms", "ppg"], rows, sep=";")
        s = parse_ppg_csv(
            path, "ppg", time_column="time_ms", time_unit="ms", source="finger"
        )
        assert s.sampling_rate == pytest.approx(100.0, rel=0.01)
        assert s.metadata["file"] == "ppg.csv"
        rr = s.to_rr()
        assert _rmssd(rr.intervals) == pytest.approx(_rmssd(true), rel=0.05)

    def test_sampling_rate_and_bad_rows(self, tmp_path):
        """No time column; an empty and a text value are skipped."""
        path = self._write(
            tmp_path, ["green", "ambient"], [(1, 0), ("", 0), ("x", 0), (2, 0), (3, 0)]
        )
        s = parse_ppg_csv(path, "green", sampling_rate=25.0)
        np.testing.assert_array_equal(s.data, [1.0, 2.0, 3.0])

    def test_errors(self, tmp_path):
        """Missing file, unknown column, no time axis, bad unit."""
        path = self._write(tmp_path, ["ppg"], [(1,), (2,)])
        with pytest.raises(FileNotFoundError):
            parse_ppg_csv(tmp_path / "none.csv", "ppg", sampling_rate=25.0)
        with pytest.raises(ValueError, match="not found"):
            parse_ppg_csv(path, "red", sampling_rate=25.0)
        with pytest.raises(ValueError, match="time_column or sampling_rate"):
            parse_ppg_csv(path, "ppg")
        with pytest.raises(ValueError, match="time_unit"):
            parse_ppg_csv(path, "ppg", time_column="ppg", time_unit="min")


class TestPulseRegularity:
    """A regular pulse is told apart from noise."""

    def test_pulse_vs_noise(self):
        """Pulse ≈ 0.7–0.8; noise (sensor off the skin) ≈ 0.15 → poor quality."""
        x, _, _ = _synthetic(30.0)
        assert PPGSignal(x, 30.0).pulse_regularity() > 0.6
        noise = PPGSignal(np.random.default_rng(0).normal(0, 1, 30000), 100.0)
        assert noise.pulse_regularity() < 0.3
        with pytest.warns(UserWarning, match="No regular pulse"):
            rr = noise.to_rr()
        assert rr.metadata["ppg_regularity"] < 0.3
        assert signal_quality(rr).grade == "poor"

    def test_short_recording(self):
        """Shorter than one 10-s window: 0."""
        assert PPGSignal(np.sin(np.arange(500) / 10), 100.0).pulse_regularity() == 0.0
