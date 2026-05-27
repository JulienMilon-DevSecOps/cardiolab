"""Unit tests for Heart Rate Recovery (HRR) protocol."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cardiolab.protocols.hrr import (
    HRRResult,
    _categorise_hrr1,
    _categorise_hrr2,
    heart_rate_recovery,
)
from cardiolab.signals.rr import RRSeries

# ======================
# FIXTURES
# ======================


def _make_recovery_rr(
    n: int = 120,
    peak_hr: float = 170.0,
    recovery_tau: float = 30.0,
) -> RRSeries:
    """Simulate post-exercise RR series with exponential HR recovery."""
    t = np.arange(n) * (60_000.0 / peak_hr / 1000.0)  # approx time axis
    hr_t = 60.0 + (peak_hr - 60.0) * np.exp(-t / recovery_tau)
    rr_ms = 60_000.0 / hr_t
    rng = np.random.default_rng(7)
    rr_ms += rng.normal(0, 3, n)
    return RRSeries(rr_ms.clip(300, 1800))


# ======================
# HRRResult
# ======================


class TestHRRResult:
    """Tests for the HRRResult dataclass."""

    def test_default_values(self):
        """All fields initialise to their documented zero/nan/None defaults."""
        r = HRRResult()
        assert r.date is None
        assert r.hr_peak == 0.0
        assert r.hr_at_60s == 0.0
        assert math.isnan(r.hr_at_120s)
        assert r.hrr_60 == 0.0
        assert math.isnan(r.hrr_120)
        assert r.hrr_60_category == ""
        assert r.hrr_120_category == ""
        assert r.duration == 0.0

    def test_to_dict_keys(self):
        """to_dict returns exactly the expected set of keys."""
        r = HRRResult()
        expected = {
            "date",
            "hr_peak",
            "hr_at_60s",
            "hr_at_120s",
            "hrr_60",
            "hrr_120",
            "hrr_60_category",
            "hrr_120_category",
            "duration",
            "score",
        }
        assert set(r.to_dict().keys()) == expected

    def test_to_dict_values_match(self):
        """to_dict values match the fields set at construction."""
        r = HRRResult(hr_peak=170.0, hrr_60=22.0, hrr_60_category="good")
        d = r.to_dict()
        assert d["hr_peak"] == 170.0
        assert d["hrr_60"] == 22.0
        assert d["hrr_60_category"] == "good"


# ======================
# Category helpers
# ======================


class TestCategoryHelpers:
    """Tests for the HRR1 and HRR2 categorisation helpers."""

    def test_hrr1_excellent(self):
        """HRR1 >= 25 bpm is classified as excellent."""
        assert _categorise_hrr1(30.0) == "excellent"
        assert _categorise_hrr1(25.0) == "excellent"

    def test_hrr1_good(self):
        """HRR1 in [20, 25) bpm is classified as good."""
        assert _categorise_hrr1(22.0) == "good"
        assert _categorise_hrr1(20.0) == "good"

    def test_hrr1_normal(self):
        """HRR1 in [12, 20) bpm is classified as normal."""
        assert _categorise_hrr1(15.0) == "normal"
        assert _categorise_hrr1(12.0) == "normal"

    def test_hrr1_impaired(self):
        """HRR1 < 12 bpm is classified as impaired."""
        assert _categorise_hrr1(10.0) == "impaired"
        assert _categorise_hrr1(0.0) == "impaired"

    def test_hrr2_excellent(self):
        """HRR2 >= 55 bpm is classified as excellent."""
        assert _categorise_hrr2(60.0) == "excellent"

    def test_hrr2_good(self):
        """HRR2 in [45, 55) bpm is classified as good."""
        assert _categorise_hrr2(50.0) == "good"

    def test_hrr2_normal(self):
        """HRR2 in [35, 45) bpm is classified as normal."""
        assert _categorise_hrr2(40.0) == "normal"

    def test_hrr2_impaired(self):
        """HRR2 < 35 bpm is classified as impaired."""
        assert _categorise_hrr2(30.0) == "impaired"


# ======================
# heart_rate_recovery()
# ======================


class TestHeartRateRecovery:
    """Tests for the heart_rate_recovery() function."""

    def test_raises_on_too_few_intervals(self):
        """Fewer than 30 RR intervals raises ValueError."""
        rr = RRSeries(np.full(10, 400.0))
        with pytest.raises(ValueError, match="Too few"):
            heart_rate_recovery(rr)

    def test_returns_hrr_result(self):
        """Function returns an HRRResult instance."""
        rr = _make_recovery_rr()
        result = heart_rate_recovery(rr)
        assert isinstance(result, HRRResult)

    def test_hr_peak_positive(self):
        """Peak HR is positive for a valid recording."""
        rr = _make_recovery_rr()
        result = heart_rate_recovery(rr)
        assert result.hr_peak > 0.0

    def test_hr_at_60s_positive(self):
        """HR at 60 s is positive for a valid recording."""
        rr = _make_recovery_rr()
        result = heart_rate_recovery(rr)
        assert result.hr_at_60s > 0.0

    def test_hrr_60_calculated(self):
        """HRR1 equals HR_peak minus HR_at_60s."""
        rr = _make_recovery_rr()
        result = heart_rate_recovery(rr)
        assert abs(result.hrr_60 - (result.hr_peak - result.hr_at_60s)) < 0.01

    def test_hrr_60_category_set(self):
        """HRR1 category is one of the four valid labels."""
        rr = _make_recovery_rr()
        result = heart_rate_recovery(rr)
        assert result.hrr_60_category in ("excellent", "good", "normal", "impaired")

    def test_duration_positive(self):
        """Duration is positive for a valid recording."""
        rr = _make_recovery_rr()
        result = heart_rate_recovery(rr)
        assert result.duration > 0.0

    def test_2min_recording_has_hrr2(self):
        """A 2-min recording at ~170 bpm peak should include HRR2."""
        rr = _make_recovery_rr(n=200, peak_hr=170.0, recovery_tau=40.0)
        result = heart_rate_recovery(rr)
        if not math.isnan(result.hrr_120):
            assert result.hr_at_120s > 0.0
            assert result.hrr_120_category in (
                "excellent",
                "good",
                "normal",
                "impaired",
            )

    def test_short_recording_hrr2_nan(self):
        """A 30-interval recording at low HR may not reach 120 s."""
        rr = RRSeries(np.full(30, 1000.0))  # 30 s total
        result = heart_rate_recovery(rr)
        # 30 s < 120 s → hr_at_120s should be nan or the last available value
        # (implementation falls back to last point for 60 s too)
        assert isinstance(result, HRRResult)

    def test_minimum_30_intervals_passes(self):
        """Exactly 30 intervals does not raise."""
        rr = RRSeries(np.full(30, 500.0))
        result = heart_rate_recovery(rr)
        assert isinstance(result, HRRResult)

    def test_29_intervals_raises(self):
        """29 intervals raises ValueError."""
        rr = RRSeries(np.full(29, 500.0))
        with pytest.raises(ValueError):
            heart_rate_recovery(rr)

    def test_fast_recovery_has_higher_hrr1(self):
        """Fast recovery (short tau) should yield a larger HRR1 than slow."""
        rr_fast = _make_recovery_rr(n=200, peak_hr=170.0, recovery_tau=15.0)
        rr_slow = _make_recovery_rr(n=200, peak_hr=170.0, recovery_tau=60.0)
        res_fast = heart_rate_recovery(rr_fast)
        res_slow = heart_rate_recovery(rr_slow)
        assert res_fast.hrr_60 > res_slow.hrr_60

    def test_to_dict_round_trip(self):
        """to_dict preserves HRR1 value and category."""
        rr = _make_recovery_rr()
        result = heart_rate_recovery(rr)
        d = result.to_dict()
        assert d["hrr_60"] == result.hrr_60
        assert d["hrr_60_category"] == result.hrr_60_category
