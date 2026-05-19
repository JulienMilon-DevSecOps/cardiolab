"""Unit tests for cardiac drift protocol."""

from __future__ import annotations

import numpy as np
import pytest

from cardiolab.protocols.cardiac_drift import DriftResult, _interpret_drift, cardiac_drift
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
    def test_default_values(self):
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
        r = DriftResult()
        expected = {
            "date", "drift_rate", "drift_magnitude", "r_squared",
            "drift_detected", "initial_hr", "final_hr",
            "n_windows", "interpretation", "duration",
        }
        assert set(r.to_dict().keys()) == expected

    def test_to_dict_values_match(self):
        r = DriftResult(drift_rate=1.2, interpretation="mild", n_windows=10)
        d = r.to_dict()
        assert d["drift_rate"] == 1.2
        assert d["interpretation"] == "mild"
        assert d["n_windows"] == 10


# ======================
# _interpret_drift()
# ======================


class TestInterpretDrift:
    def test_no_drift(self):
        assert _interpret_drift(0.3) == "no_drift"
        assert _interpret_drift(0.0) == "no_drift"

    def test_mild(self):
        assert _interpret_drift(0.5) == "mild"
        assert _interpret_drift(1.4) == "mild"

    def test_moderate(self):
        assert _interpret_drift(1.5) == "moderate"
        assert _interpret_drift(2.9) == "moderate"

    def test_strong(self):
        assert _interpret_drift(3.0) == "strong"
        assert _interpret_drift(5.0) == "strong"


# ======================
# cardiac_drift()
# ======================


class TestCardiacDrift:
    def test_raises_if_too_short(self):
        rr = RRSeries(np.full(60, 600.0))  # only ~36 s at 100 bpm
        with pytest.raises(ValueError, match="Too few windows"):
            cardiac_drift(rr, window_sec=60.0)

    def test_returns_drift_result(self):
        rr = _make_constant_hr_rr(300)
        result = cardiac_drift(rr, window_sec=30.0)
        assert isinstance(result, DriftResult)

    def test_stable_hr_no_drift(self):
        rr = _make_constant_hr_rr(600)
        result = cardiac_drift(rr, window_sec=30.0)
        assert abs(result.drift_rate) < 1.0

    def test_drifting_hr_detected(self):
        rr = _make_drifting_rr(n=600, drift_bpm_per_min=2.0, initial_hr=130.0)
        result = cardiac_drift(rr, window_sec=30.0)
        assert result.drift_detected or abs(result.drift_rate) > 0.0

    def test_n_windows_at_least_3(self):
        rr = _make_constant_hr_rr(600)
        result = cardiac_drift(rr, window_sec=30.0)
        assert result.n_windows >= 3

    def test_initial_final_hr_positive(self):
        rr = _make_constant_hr_rr(300)
        result = cardiac_drift(rr, window_sec=30.0)
        assert result.initial_hr > 0.0
        assert result.final_hr > 0.0

    def test_duration_positive(self):
        rr = _make_constant_hr_rr(300)
        result = cardiac_drift(rr, window_sec=30.0)
        assert result.duration > 0.0

    def test_r_squared_in_range(self):
        rr = _make_constant_hr_rr(600)
        result = cardiac_drift(rr, window_sec=30.0)
        assert 0.0 <= result.r_squared <= 1.0

    def test_drift_magnitude_consistent(self):
        rr = _make_constant_hr_rr(300)
        result = cardiac_drift(rr, window_sec=30.0)
        assert abs(result.drift_magnitude - (result.final_hr - result.initial_hr)) < 0.01

    def test_strong_drift_detection(self):
        rr = _make_drifting_rr(n=1200, drift_bpm_per_min=4.0, initial_hr=120.0)
        result = cardiac_drift(rr, window_sec=60.0)
        assert result.drift_rate > 0.0
        assert result.drift_detected is True
        assert result.interpretation in ("mild", "moderate", "strong")

    def test_custom_window_sec(self):
        rr = _make_constant_hr_rr(600)
        result = cardiac_drift(rr, window_sec=20.0)
        assert result.n_windows >= 3

    def test_interpretation_valid_category(self):
        rr = _make_constant_hr_rr(600)
        result = cardiac_drift(rr, window_sec=30.0)
        assert result.interpretation in ("no_drift", "mild", "moderate", "strong")

    def test_to_dict_round_trip(self):
        rr = _make_constant_hr_rr(300)
        result = cardiac_drift(rr, window_sec=30.0)
        d = result.to_dict()
        assert d["n_windows"] == result.n_windows
        assert d["drift_detected"] == result.drift_detected
