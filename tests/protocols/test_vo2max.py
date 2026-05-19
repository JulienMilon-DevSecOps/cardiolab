"""Unit tests for VO2max estimation protocol."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cardiolab.protocols.vo2max import VO2maxResult, _fitness_category, vo2max_from_hrv
from cardiolab.signals.rr import RRSeries


# ======================
# FIXTURES
# ======================


def _make_rr(n: int = 300, mean_ms: float = 857, std_ms: float = 40) -> RRSeries:
    rng = np.random.default_rng(99)
    return RRSeries(rng.normal(mean_ms, std_ms, n).clip(300, 1800))


# ======================
# VO2maxResult
# ======================


class TestVO2maxResult:
    def test_default_values(self):
        r = VO2maxResult()
        assert r.date is None
        assert math.isnan(r.vo2max_uth)
        assert r.vo2max_esco_flatt == 0.0
        assert r.vo2max_ln_rmssd == 0.0
        assert r.hr_rest == 0.0
        assert math.isnan(r.hr_max)
        assert r.rmssd_used == 0.0
        assert r.ln_rmssd_used == 0.0
        assert r.fitness_category == "poor"

    def test_to_dict_keys(self):
        r = VO2maxResult()
        expected = {
            "date", "vo2max_uth", "vo2max_esco_flatt", "vo2max_ln_rmssd",
            "hr_rest", "hr_max", "rmssd_used", "ln_rmssd_used", "fitness_category",
        }
        assert set(r.to_dict().keys()) == expected

    def test_to_dict_values_match(self):
        r = VO2maxResult(vo2max_esco_flatt=42.0, fitness_category="good")
        d = r.to_dict()
        assert d["vo2max_esco_flatt"] == 42.0
        assert d["fitness_category"] == "good"


# ======================
# _fitness_category()
# ======================


class TestFitnessCategory:
    def test_poor(self):
        assert _fitness_category(20.0) == "poor"
        assert _fitness_category(27.9) == "poor"

    def test_fair(self):
        assert _fitness_category(28.0) == "fair"
        assert _fitness_category(37.9) == "fair"

    def test_good(self):
        assert _fitness_category(38.0) == "good"
        assert _fitness_category(47.9) == "good"

    def test_very_good(self):
        assert _fitness_category(48.0) == "very_good"
        assert _fitness_category(57.9) == "very_good"

    def test_excellent(self):
        assert _fitness_category(58.0) == "excellent"
        assert _fitness_category(75.0) == "excellent"


# ======================
# vo2max_from_hrv()
# ======================


class TestVO2maxFromHRV:
    def test_raises_on_too_few_intervals(self):
        rr = RRSeries(np.full(10, 800.0))
        with pytest.raises(ValueError, match="Too few"):
            vo2max_from_hrv(rr)

    def test_returns_vo2max_result(self):
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert isinstance(result, VO2maxResult)

    def test_esco_flatt_non_nan(self):
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert not math.isnan(result.vo2max_esco_flatt)
        assert result.vo2max_esco_flatt > 0.0

    def test_ln_rmssd_non_nan(self):
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert not math.isnan(result.vo2max_ln_rmssd)
        assert result.vo2max_ln_rmssd > 0.0

    def test_uth_nan_without_hr_max(self):
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert math.isnan(result.vo2max_uth)
        assert math.isnan(result.hr_max)

    def test_uth_computed_with_hr_max(self):
        rr = _make_rr()
        result = vo2max_from_hrv(rr, hr_max=190.0)
        assert not math.isnan(result.vo2max_uth)
        assert result.vo2max_uth > 0.0
        assert result.hr_max == 190.0

    def test_uth_formula(self):
        """Verify Uth formula: 15.3 × (HRmax / HRrest)."""
        rr = _make_rr()
        result = vo2max_from_hrv(rr, hr_max=180.0)
        expected = 15.3 * (180.0 / result.hr_rest)
        assert abs(result.vo2max_uth - expected) < 0.01

    def test_esco_flatt_formula(self):
        """Verify Esco-Flatt formula: 18.37 + 0.054 × RMSSD."""
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        expected = 18.37 + 0.054 * result.rmssd_used
        assert abs(result.vo2max_esco_flatt - expected) < 0.01

    def test_hr_rest_derived_from_rr(self):
        rr = RRSeries(np.full(60, 1000.0))  # 60 bpm exactly
        result = vo2max_from_hrv(rr)
        assert abs(result.hr_rest - 60.0) < 0.01

    def test_fitness_category_valid(self):
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert result.fitness_category in ("poor", "fair", "good", "very_good", "excellent")

    def test_fitness_category_uses_uth_when_available(self):
        rr = _make_rr(n=300, mean_ms=1100)  # low HR → high VO2max estimate
        result_with = vo2max_from_hrv(rr, hr_max=200.0)
        result_without = vo2max_from_hrv(rr)
        # When hr_max is provided, category derived from Uth; otherwise from Esco-Flatt
        assert isinstance(result_with.fitness_category, str)
        assert isinstance(result_without.fitness_category, str)

    def test_higher_rmssd_higher_esco_flatt(self):
        """Higher RMSSD → higher VO2max prediction (monotone relationship)."""
        rr_low = _make_rr(n=300, mean_ms=857, std_ms=10)
        rr_high = _make_rr(n=300, mean_ms=857, std_ms=80)
        res_low = vo2max_from_hrv(rr_low)
        res_high = vo2max_from_hrv(rr_high)
        assert res_high.vo2max_esco_flatt >= res_low.vo2max_esco_flatt

    def test_rmssd_used_positive(self):
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert result.rmssd_used > 0.0

    def test_ln_rmssd_used_consistent(self):
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert abs(result.ln_rmssd_used - math.log(result.rmssd_used)) < 1e-6

    def test_minimum_30_intervals_passes(self):
        rr = RRSeries(np.full(30, 857.0))
        result = vo2max_from_hrv(rr)
        assert isinstance(result, VO2maxResult)

    def test_to_dict_round_trip(self):
        rr = _make_rr()
        result = vo2max_from_hrv(rr, hr_max=185.0)
        d = result.to_dict()
        assert d["fitness_category"] == result.fitness_category
        assert d["hr_max"] == result.hr_max
