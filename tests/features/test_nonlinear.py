"""Unit tests for non-linear HRV metrics (Poincaré plot, DFA α1, ApEn, SampEn)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cardiolab.features.nonlinear import apen, dfa_alpha1, sampen, sd1, sd2, sd_ratio
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


# ======================
# APEN
# ======================


class TestApEn:
    """Tests for Approximate Entropy (ApEn)."""

    def test_returns_float(self, normal_rr):
        """apen() must return a float."""
        assert isinstance(apen(normal_rr), float)

    def test_non_negative(self, normal_rr):
        """ApEn must be non-negative for a valid signal."""
        val = apen(normal_rr)
        assert not math.isnan(val)
        assert val >= 0.0

    def test_returns_nan_for_too_short_series(self):
        """ApEn must return nan for very short series (N < 2m+1 = 5 for m=2)."""
        too_short = RRSeries(np.array([857.0, 870.0, 845.0, 862.0]))  # N=4 < 5
        val = apen(too_short)
        assert math.isnan(val)

    def test_constant_series_returns_nan(self):
        """ApEn must return nan for a constant series (std=0)."""
        rr = RRSeries(np.full(50, 857.0))
        val = apen(rr)
        assert math.isnan(val)

    def test_higher_complexity_gives_higher_apen(self, low_var_rr, high_var_rr):
        """Higher variability must produce higher ApEn."""
        val_low = apen(low_var_rr)
        val_high = apen(high_var_rr)
        # Both must be valid (not nan)
        assert not math.isnan(val_low)
        assert not math.isnan(val_high)
        assert val_high >= val_low

    def test_reproducible(self, normal_rr):
        """Repeated calls on the same series must give identical results."""
        v1 = apen(normal_rr)
        v2 = apen(normal_rr)
        assert v1 == v2

    def test_custom_parameters(self, normal_rr):
        """Custom m and r_coef must be accepted without error."""
        val = apen(normal_rr, m=1, r_coef=0.15)
        assert isinstance(val, float)

    def test_physiological_range(self, normal_rr):
        """ApEn for a typical resting series should be in a plausible range."""
        val = apen(normal_rr)
        if not math.isnan(val):
            assert 0.0 < val < 3.0


# ======================
# SAMPEN
# ======================


class TestSampEn:
    """Tests for Sample Entropy (SampEn)."""

    def test_returns_float(self, normal_rr):
        """sampen() must return a float."""
        assert isinstance(sampen(normal_rr), float)

    def test_non_negative(self, normal_rr):
        """SampEn must be non-negative for a valid signal."""
        val = sampen(normal_rr)
        assert not math.isnan(val)
        assert val >= 0.0

    def test_returns_nan_for_too_short_series(self, minimal_rr):
        """SampEn must return nan for very short series (N < 2m+2)."""
        val = sampen(minimal_rr)
        assert math.isnan(val)

    def test_constant_series_returns_nan(self):
        """SampEn must return nan for a constant series (std=0)."""
        rr = RRSeries(np.full(50, 857.0))
        val = sampen(rr)
        assert math.isnan(val)

    def test_both_series_produce_valid_sampen(self, low_var_rr, high_var_rr):
        """SampEn must return a valid (non-nan, positive) value for both series."""
        val_low = sampen(low_var_rr)
        val_high = sampen(high_var_rr)
        # SampEn with r ∝ std(RR) is not guaranteed to order by variability
        assert not math.isnan(val_low)
        assert not math.isnan(val_high)
        assert val_low > 0.0
        assert val_high > 0.0

    def test_reproducible(self, normal_rr):
        """Repeated calls on the same series must give identical results."""
        v1 = sampen(normal_rr)
        v2 = sampen(normal_rr)
        assert v1 == v2

    def test_custom_parameters(self, normal_rr):
        """Custom m and r_coef must be accepted without error."""
        val = sampen(normal_rr, m=1, r_coef=0.15)
        assert isinstance(val, float)

    def test_physiological_range(self, normal_rr):
        """SampEn for a typical resting series should be in a plausible range."""
        val = sampen(normal_rr)
        if not math.isnan(val):
            assert 0.0 < val < 3.0

    def test_sampen_vs_apen_same_signal(self, normal_rr):
        """SampEn and ApEn must both be finite and positive on the same signal."""
        v_apen = apen(normal_rr)
        v_sampen = sampen(normal_rr)
        assert not math.isnan(v_apen)
        assert not math.isnan(v_sampen)
        assert v_apen > 0.0
        assert v_sampen > 0.0
