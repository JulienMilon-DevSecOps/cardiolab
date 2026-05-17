"""Unit tests for non-linear HRV metrics (Poincaré plot, DFA α1)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cardiolab.features.nonlinear import dfa_alpha1, sd1, sd2, sd_ratio
from cardiolab.signals.rr import RRSeries

# ======================
# FIXTURES
# ======================

RNG = np.random.default_rng(42)


@pytest.fixture
def normal_rr():
    """Return a normal resting RR series (~70 bpm, 400 beats)."""
    return RRSeries(RNG.normal(857, 20, 400).clip(300, 1800))


@pytest.fixture
def low_var_rr():
    """Return a very low-variability RR series (std ≈ 2 ms)."""
    return RRSeries(RNG.normal(857, 2, 400).clip(300, 1800))


@pytest.fixture
def high_var_rr():
    """Return a high-variability RR series (std ≈ 60 ms)."""
    return RRSeries(RNG.normal(857, 60, 400).clip(300, 1800))


@pytest.fixture
def minimal_rr():
    """Return a minimal series with only 5 intervals (too short for DFA)."""
    return RRSeries(np.array([857.0, 870.0, 845.0, 862.0, 855.0]))


# ======================
# SD1
# ======================


class TestSD1:
    """Tests for the Poincaré SD1 metric."""

    def test_returns_float(self, normal_rr):
        """sd1() must return a float."""
        assert isinstance(sd1(normal_rr), float)

    def test_positive(self, normal_rr):
        """SD1 must be strictly positive for a series with non-zero variability."""
        assert sd1(normal_rr) > 0.0

    def test_equals_rmssd_over_sqrt2(self, normal_rr):
        """SD1 must equal RMSSD / √2 within floating-point precision."""
        from cardiolab.features.time_domain import rmssd

        expected = rmssd(normal_rr) / np.sqrt(2)
        assert sd1(normal_rr) == pytest.approx(expected, rel=1e-9)

    def test_higher_for_high_variability(self, low_var_rr, high_var_rr):
        """SD1 must be larger for a higher-variability series."""
        assert sd1(high_var_rr) > sd1(low_var_rr)

    def test_units_in_milliseconds(self, normal_rr):
        """SD1 should be in a physiologically plausible range (ms)."""
        val = sd1(normal_rr)
        assert 1.0 < val < 500.0  # ms, for a resting series


# ======================
# SD2
# ======================


class TestSD2:
    """Tests for the Poincaré SD2 metric."""

    def test_returns_float(self, normal_rr):
        """sd2() must return a float."""
        assert isinstance(sd2(normal_rr), float)

    def test_positive(self, normal_rr):
        """SD2 must be strictly positive for a series with non-zero variability."""
        assert sd2(normal_rr) > 0.0

    def test_greater_than_sd1(self, normal_rr):
        """For a typical resting series, SD2 should exceed SD1."""
        assert sd2(normal_rr) > sd1(normal_rr)

    def test_formula_consistency(self, normal_rr):
        """SD2² must equal 2·SDNN² - SD1²."""
        from cardiolab.features.time_domain import sdnn

        sd1_val = sd1(normal_rr)
        sd2_val = sd2(normal_rr)
        sdnn_val = sdnn(normal_rr)

        expected_sq = 2.0 * sdnn_val**2 - sd1_val**2
        assert sd2_val**2 == pytest.approx(expected_sq, rel=1e-6)

    def test_non_negative_for_low_variability(self, low_var_rr):
        """SD2 must not be negative even for near-constant series."""
        assert sd2(low_var_rr) >= 0.0

    def test_units_in_milliseconds(self, normal_rr):
        """SD2 should be in a physiologically plausible range (ms)."""
        val = sd2(normal_rr)
        assert 1.0 < val < 500.0


# ======================
# SD_RATIO
# ======================


class TestSDRatio:
    """Tests for the SD1/SD2 ratio."""

    def test_returns_float(self, normal_rr):
        """sd_ratio() must return a float."""
        assert isinstance(sd_ratio(normal_rr), float)

    def test_positive(self, normal_rr):
        """SD ratio must be strictly positive."""
        assert sd_ratio(normal_rr) > 0.0

    def test_less_than_one(self, normal_rr):
        """For a typical resting series, SD1/SD2 must be less than 1."""
        assert sd_ratio(normal_rr) < 1.0

    def test_equals_sd1_over_sd2(self, normal_rr):
        """sd_ratio() must equal sd1() / sd2() exactly."""
        expected = sd1(normal_rr) / sd2(normal_rr)
        assert sd_ratio(normal_rr) == pytest.approx(expected, rel=1e-9)

    def test_in_normal_range(self, normal_rr):
        """SD1/SD2 at rest should fall within [0.1, 1.0]."""
        val = sd_ratio(normal_rr)
        assert 0.1 < val < 1.0


# ======================
# DFA ALPHA1
# ======================


class TestDFAAlpha1:
    """Tests for the DFA short-term scaling exponent α1."""

    def test_returns_float(self, normal_rr):
        """dfa_alpha1() must return a float."""
        assert isinstance(dfa_alpha1(normal_rr), float)

    def test_normal_resting_range(self, normal_rr):
        """DFA α1 for a normal resting series should be > 0."""
        val = dfa_alpha1(normal_rr)
        assert not math.isnan(val)
        assert val > 0.0

    def test_returns_nan_for_too_short_series(self, minimal_rr):
        """DFA α1 must return nan when fewer than 2 valid scales are computed."""
        val = dfa_alpha1(minimal_rr)
        assert math.isnan(val)

    def test_custom_n_range(self, normal_rr):
        """Custom n_min/n_max must be accepted without error."""
        val = dfa_alpha1(normal_rr, n_min=4, n_max=8)
        assert isinstance(val, float)
        assert not math.isnan(val)

    def test_dimensionless(self, normal_rr):
        """DFA α1 must be in a physiologically plausible range."""
        val = dfa_alpha1(normal_rr)
        # Typical range for resting adults: 0.5 – 2.0
        assert 0.3 < val < 2.5

    def test_white_noise_near_half(self):
        """For white-noise RR series, α1 should be near 0.5."""
        rng = np.random.default_rng(0)
        # Pure white noise: uncorrelated increments → α ≈ 0.5
        rr = RRSeries(rng.normal(857, 30, 500).clip(300, 1800))
        val = dfa_alpha1(rr)
        # Allow generous tolerance since white noise is approximate
        assert 0.3 < val < 1.2

    def test_reproducible_with_same_seed(self):
        """Same seed must produce same DFA α1 value."""
        rng = np.random.default_rng(99)
        rr = RRSeries(rng.normal(857, 20, 400).clip(300, 1800))
        v1 = dfa_alpha1(rr)
        v2 = dfa_alpha1(rr)
        assert v1 == v2
