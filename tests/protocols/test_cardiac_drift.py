"""Unit tests for cardiac drift protocol."""

from __future__ import annotations

import numpy as np
import pytest

from cardiolab.protocols.cardiac_drift import (
    DriftResult,
    _interpret_drift,
    cardiac_drift,
)
from cardiolab.signals.rr import RRSeries

# ======================
# FIXTURES
# ======================


def _make_constant_hr_rr(n: int = 300, mean_ms: float = 600) -> RRSeries:
    """Stable HR — no drift expected."""
    rng = np.random.default_rng(1)
    return RRSeries(rng.normal(mean_ms, 5, n).clip(300, 1800))


def _make_drifting_rr(
    n: int = 600,
    drift_bpm_per_min: float = 1.0,
    initial_hr: float = 140.0,
) -> RRSeries:
    """Simulate a gradually drifting HR series."""
    rng = np.random.default_rng(42)
    # Each beat is ~60_000/initial_hr ms initially
    ms_per_beat = 60_000.0 / initial_hr
    t_min = np.arange(n) * ms_per_beat / 1000.0 / 60.0  # time in minutes
    hr_t = initial_hr + drift_bpm_per_min * t_min
    rr_ms = 60_000.0 / hr_t + rng.normal(0, 2, n)
    return RRSeries(rr_ms.clip(300, 1800))


# ======================
# DriftResult
# ======================


class TestDriftResult:
    """Tests for the DriftResult dataclass."""

    def test_default_values(self):
        """All fields initialise to their documented zero/None defaults."""
        r = DriftResult()
        assert r.date is None
        assert r.drift_rate == 0.0
        assert r.drift_magnitude == 0.0
        assert r.r_squared == 0.0
        assert r.drift_detected is False
        assert r.initial_hr == 0.0
        assert r.final_hr == 0.0
        assert r.n_windows == 0
        assert r.interpretation == "no_drift"
        assert r.duration == 0.0

    def test_to_dict_keys(self):
        """to_dict returns exactly the expected set of keys."""
        r = DriftResult()
        expected = {
            "date",
            "drift_rate",
            "drift_magnitude",
            "r_squared",
            "drift_detected",
            "initial_hr",
            "final_hr",
            "n_windows",
            "interpretation",
            "duration",
            "score",
        }
        assert set(r.to_dict().keys()) == expected

    def test_to_dict_values_match(self):
        """to_dict values match the fields set at construction."""
        r = DriftResult(drift_rate=1.2, interpretation="mild", n_windows=10)
        d = r.to_dict()
        assert d["drift_rate"] == 1.2
        assert d["interpretation"] == "mild"
        assert d["n_windows"] == 10


# ======================
# _interpret_drift()
# ======================


class TestInterpretDrift:
    """Tests for the _interpret_drift() helper."""

    def test_no_drift(self):
        """Rate below 0.5 bpm/min returns no_drift."""
        assert _interpret_drift(0.3) == "no_drift"
        assert _interpret_drift(0.0) == "no_drift"

    def test_mild(self):
        """Rate in [0.5, 1.5) bpm/min returns mild."""
        assert _interpret_drift(0.5) == "mild"
        assert _interpret_drift(1.4) == "mild"

    def test_moderate(self):
        """Rate in [1.5, 3.0) bpm/min returns moderate."""
        assert _interpret_drift(1.5) == "moderate"
        assert _interpret_drift(2.9) == "moderate"

    def test_strong(self):
        """Rate >= 3.0 bpm/min returns strong."""
        assert _interpret_drift(3.0) == "strong"
        assert _interpret_drift(5.0) == "strong"


# ======================
# cardiac_drift()
# ======================


class TestCardiacDrift:
    """Tests for the cardiac_drift() function."""

    def test_raises_if_too_short(self):
        """Recording too short to yield 3 windows raises ValueError."""
        rr = RRSeries(np.full(60, 600.0))  # only ~36 s at 100 bpm
        with pytest.raises(ValueError, match="Too few windows"):
            cardiac_drift(rr, window_sec=60.0)

    def test_returns_drift_result(self):
        """Function returns a DriftResult instance."""
        rr = _make_constant_hr_rr(300)
        result = cardiac_drift(rr, window_sec=30.0)
        assert isinstance(result, DriftResult)

    def test_stable_hr_no_drift(self):
        """Stable HR series produces a drift rate close to zero."""
        rr = _make_constant_hr_rr(600)
        result = cardiac_drift(rr, window_sec=30.0)
        assert abs(result.drift_rate) < 1.0

    def test_drifting_hr_detected(self):
        """A drifting HR series produces a non-zero drift rate or flags detection."""
        rr = _make_drifting_rr(n=600, drift_bpm_per_min=2.0, initial_hr=130.0)
        result = cardiac_drift(rr, window_sec=30.0)
        assert result.drift_detected or abs(result.drift_rate) > 0.0

    def test_n_windows_at_least_3(self):
        """Result contains at least 3 windows."""
        rr = _make_constant_hr_rr(600)
        result = cardiac_drift(rr, window_sec=30.0)
        assert result.n_windows >= 3

    def test_initial_final_hr_positive(self):
        """Initial and final HR are both positive."""
        rr = _make_constant_hr_rr(300)
        result = cardiac_drift(rr, window_sec=30.0)
        assert result.initial_hr > 0.0
        assert result.final_hr > 0.0

    def test_duration_positive(self):
        """Duration is positive for a valid recording."""
        rr = _make_constant_hr_rr(300)
        result = cardiac_drift(rr, window_sec=30.0)
        assert result.duration > 0.0

    def test_r_squared_in_range(self):
        """R² lies in [0, 1]."""
        rr = _make_constant_hr_rr(600)
        result = cardiac_drift(rr, window_sec=30.0)
        assert 0.0 <= result.r_squared <= 1.0

    def test_drift_magnitude_consistent(self):
        """Drift magnitude equals final_hr minus initial_hr."""
        rr = _make_constant_hr_rr(300)
        result = cardiac_drift(rr, window_sec=30.0)
        assert (
            abs(result.drift_magnitude - (result.final_hr - result.initial_hr)) < 0.01
        )

    def test_strong_drift_detection(self):
        """A strong drift signal is detected and categorised correctly."""
        rr = _make_drifting_rr(n=1200, drift_bpm_per_min=4.0, initial_hr=120.0)
        result = cardiac_drift(rr, window_sec=60.0)
        assert result.drift_rate > 0.0
        assert result.drift_detected is True
        assert result.interpretation in ("mild", "moderate", "strong")

    def test_custom_window_sec(self):
        """A custom window size is accepted without error."""
        rr = _make_constant_hr_rr(600)
        result = cardiac_drift(rr, window_sec=20.0)
        assert result.n_windows >= 3

    def test_interpretation_valid_category(self):
        """Interpretation is always one of the four valid labels."""
        rr = _make_constant_hr_rr(600)
        result = cardiac_drift(rr, window_sec=30.0)
        assert result.interpretation in ("no_drift", "mild", "moderate", "strong")

    def test_to_dict_round_trip(self):
        """to_dict preserves n_windows and drift_detected."""
        rr = _make_constant_hr_rr(300)
        result = cardiac_drift(rr, window_sec=30.0)
        d = result.to_dict()
        assert d["n_windows"] == result.n_windows
        assert d["drift_detected"] == result.drift_detected
