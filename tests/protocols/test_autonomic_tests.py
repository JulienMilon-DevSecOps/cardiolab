"""Tests of the autonomic reflex tests (Ewing battery) — synthetic signals."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cardiolab.protocols.autonomic_tests import (
    EWING_LIMITS,
    AutonomicTestsResult,
    classify,
    deep_breathing_limits,
    deep_breathing_test,
    ratio_30_15,
    valsalva_ratio,
)
from cardiolab.protocols.orthostatic import orthostatic_hrv
from cardiolab.signals.rr import RRSeries


def _beats(hr_of_t, duration: float, noise: float = 0.0, seed: int = 0) -> np.ndarray:
    """RR intervals (ms) following a heart rate profile ``hr_of_t(t)`` in bpm."""
    rng = np.random.default_rng(seed)
    t, out = 0.0, []
    while t < duration:
        rr = 60000.0 / hr_of_t(t) + rng.normal(0, noise)
        out.append(rr)
        t += rr / 1000.0
    return np.array(out)


def _deep_breathing_rr(amplitude: float = 12.0, period: float = 10.0, seed: int = 0):
    """Heart rate 70 ± amplitude bpm, one cycle every ``period`` s, 62 s."""
    return _beats(
        lambda t: 70 + amplitude * np.sin(2 * np.pi * t / period), 62, 5.0, seed
    )


def _valsalva_hr(t: float, rise: float = 30.0, dip: float = 12.0) -> float:
    """65 bpm, +rise during the strain (30–45 s), bradycardia −dip after it."""
    if t < 30:
        return 65.0
    if t < 45:
        return 65.0 + rise * min(1.0, (t - 30) / 8)
    s = t - 45
    if s <= 2:
        return 65.0 + rise - (rise + 0) * s / 2
    return 65.0 - dip * math.exp(-(((s - 8) / 5) ** 2))


def _valsalva_rr(rise: float = 30.0, dip: float = 12.0, duration: float = 90.0):
    return _beats(lambda t: _valsalva_hr(t, rise, dip), duration, 3.0)


def _standing_hr(t: float, stand: float = 120.0, peak: float = 35.0) -> float:
    """Lying at 60 bpm, stand at ``stand``: peak near beat 15, dip near beat 30."""
    if t < stand:
        return 60.0
    s = t - stand
    return (
        60.0
        + peak * math.exp(-(((s - 9) / 4) ** 2))
        + 18.0 * (1 - math.exp(-s / 3))
        - 8.0 * math.exp(-(((s - 20) / 4) ** 2))
    )


def _standing_rr(peak: float = 35.0, seed: int = 1, stand: float = 120.0):
    return _beats(lambda t: _standing_hr(t, stand, peak), stand + 300, 4.0, seed)


# ======================
# Reference values
# ======================


class TestReferenceValues:
    """Ewing cut-offs and May 1999 age-corrected limits."""

    @pytest.mark.parametrize(
        ("value", "test", "expected"),
        [
            (15.0, "deep_breathing", "normal"),
            (12.0, "deep_breathing", "borderline"),
            (10.0, "deep_breathing", "abnormal"),
            (1.21, "valsalva", "normal"),
            (1.15, "valsalva", "borderline"),
            (1.10, "valsalva", "abnormal"),
            (1.04, "ratio_30_15", "normal"),
            (1.02, "ratio_30_15", "borderline"),
            (1.00, "ratio_30_15", "abnormal"),
            (math.nan, "valsalva", ""),
        ],
    )
    def test_ewing(self, value, test, expected):
        """Ewing et al. (1985): normal / borderline / abnormal."""
        assert classify(value, test) == expected

    def test_age_limit(self):
        """With an age limit: below → abnormal, up to 15 bpm → borderline."""
        assert classify(8.0, "deep_breathing", lower_limit=9.4) == "abnormal"
        assert classify(12.0, "deep_breathing", lower_limit=9.4) == "borderline"
        assert classify(16.0, "deep_breathing", lower_limit=9.4) == "normal"
        with pytest.raises(ValueError, match="Unknown test"):
            classify(1.0, "handgrip")

    @pytest.mark.parametrize(
        ("age", "diff", "ratio"),
        [(40, 9.42, 1.148), (60, 5.81, 1.100), (26, 12.48, 1.195)],
    )
    def test_may_1999(self, age, diff, ratio):
        """(4.39 − 0.033 × age)² and 1 + exp(−1.12 − 0.0198 × age)."""
        d, r = deep_breathing_limits(age)
        assert d == pytest.approx(diff, abs=0.01)
        assert r == pytest.approx(ratio, abs=0.001)

    def test_age_out_of_range(self):
        """Age outside 10–100 years."""
        with pytest.raises(ValueError, match="age"):
            deep_breathing_limits(5)


# ======================
# Deep breathing
# ======================


class TestDeepBreathing:
    """Heart rate difference and E/I ratio over the breathing cycles."""

    def test_known_amplitude(self):
        """70 ± 12 bpm: difference ≈ 24 bpm, E/I ≈ 82/58, 6 per minute."""
        res = deep_breathing_test(RRSeries(_deep_breathing_rr()))
        assert res.hr_difference == pytest.approx(24.0, abs=1.5)
        assert res.ei_ratio == pytest.approx(82 / 58, abs=0.04)
        assert res.breathing_rate == pytest.approx(6.0, abs=0.3)
        assert res.n_cycles >= 5
        assert (res.status, res.interpretation, res.reference) == (
            "ok",
            "normal",
            "ewing_1985",
        )

    def test_low_response(self):
        """70 ± 4 bpm: difference ≈ 8 bpm → abnormal for an adult (Ewing)."""
        res = deep_breathing_test(_deep_breathing_rr(amplitude=4.0))
        assert res.hr_difference == pytest.approx(8.0, abs=1.5)
        assert res.interpretation == "abnormal"

    def test_age_corrected(self):
        """The same 8 bpm at 65 years: above May's limit (≈ 5 bpm) → borderline."""
        res = deep_breathing_test(_deep_breathing_rr(amplitude=4.0), age=65)
        assert res.reference == "may_1999"
        assert res.hr_difference_limit == pytest.approx((4.39 - 0.033 * 65) ** 2)
        assert res.interpretation == "borderline"

    def test_age_outside_study_range_warns(self):
        """May et al. studied 40–67 years: extrapolation is reported."""
        with pytest.warns(UserWarning, match="extrapolated"):
            res = deep_breathing_test(_deep_breathing_rr(), age=26)
        assert res.ei_ratio_limit == pytest.approx(1.195, abs=0.001)

    def test_too_short(self):
        """20 s of breathing: fewer than 3 cycles → unreliable."""
        rr = _deep_breathing_rr()[:25]
        with pytest.warns(UserWarning, match="complete breathing cycle"):
            res = deep_breathing_test(rr)
        assert res.status == "unreliable"

    def test_wrong_rate(self):
        """Breathing every 7 s instead of 10: a warning."""
        with pytest.warns(UserWarning, match="Breathing rate"):
            deep_breathing_test(_deep_breathing_rr(period=7.0))

    def test_invalid(self):
        """Not RR intervals."""
        with pytest.raises(ValueError, match="RR intervals"):
            deep_breathing_test([800.0, -1.0, 800.0])


# ======================
# Valsalva
# ======================


class TestValsalva:
    """Longest RR after the strain / shortest RR during it."""

    def test_known_ratio(self):
        """95 bpm during, 53 bpm after: ratio ≈ 1.8, normal."""
        res = valsalva_ratio(_valsalva_rr(), 30.0)
        assert res.max_hr == pytest.approx(95.0, abs=2.0)
        assert res.min_hr == pytest.approx(53.0, abs=2.0)
        assert res.ratio == pytest.approx(res.max_hr / res.min_hr)
        assert res.ratio == pytest.approx(1.8, abs=0.08)
        assert res.baseline_hr == pytest.approx(65.0, abs=1.0)
        assert (res.strain_sec, res.status, res.interpretation) == (
            15.0,
            "ok",
            "normal",
        )

    def test_weak_strain(self):
        """No heart rate rise: warning, low ratio."""
        with pytest.warns(UserWarning, match="too weak"):
            res = valsalva_ratio(_valsalva_rr(rise=2.0, dip=3.0), 30.0)
        assert res.interpretation in ("borderline", "abnormal")

    def test_recording_too_short(self):
        """The recording stops 10 s after the strain → unreliable."""
        with pytest.warns(UserWarning, match="less than 20 s"):
            res = valsalva_ratio(_valsalva_rr(duration=55.0), 30.0)
        assert res.status == "unreliable"

    def test_strain_duration(self):
        """A 8-s strain is reported; under 5 s is refused."""
        with pytest.warns(UserWarning, match="15 s"):
            valsalva_ratio(_valsalva_rr(), 30.0, 38.0)
        with pytest.raises(ValueError, match="at least 5 s"):
            valsalva_ratio(_valsalva_rr(), 30.0, 33.0)

    def test_no_beat_in_strain(self):
        """Strain after the end of the recording."""
        with pytest.raises(ValueError, match="No beat"):
            valsalva_ratio(_valsalva_rr(), 500.0)


# ======================
# 30:15
# ======================


class TestRatio3015:
    """Beats counted from the moment of standing."""

    def test_known_stand(self):
        """Stand at 120 s: shortest RR near beat 15, longest near beat 30."""
        res = ratio_30_15(_standing_rr(), stand_sec=120.0)
        assert not res.stand_estimated
        assert 5 <= res.shortest_beat <= 25 and 20 <= res.longest_beat <= 40
        assert res.ratio > 1.3
        assert res.interpretation == "normal"

    def test_estimated_stand(self):
        """Estimated moment of standing within a few beats, same ratio."""
        rr = _standing_rr()
        known = ratio_30_15(rr, stand_sec=120.0)
        estimated = ratio_30_15(RRSeries(rr))
        assert estimated.stand_estimated
        assert abs(estimated.stand_sec - 120.0) < 6.0
        assert estimated.ratio == pytest.approx(known.ratio, rel=0.05)

    def test_from_orthostatic_result(self):
        """The three phases of an orthostatic test give the whole recording."""
        rr = RRSeries(_standing_rr(stand=260.0))
        assert ratio_30_15(orthostatic_hrv(rr)).ratio == pytest.approx(
            ratio_30_15(rr).ratio
        )

    def test_flat_response(self):
        """No peak and no dip after standing: ratio ≈ 1 → not normal."""
        flat = _beats(lambda t: 60.0 if t < 120 else 80.0, 420, 0.5)
        res = ratio_30_15(flat, stand_sec=120.0)
        assert res.ratio == pytest.approx(1.0, abs=0.03)
        assert res.interpretation != "normal"

    def test_too_few_beats_after_standing(self):
        """Fewer than 40 beats after standing."""
        with pytest.raises(ValueError, match="40 beats"):
            ratio_30_15(_standing_rr(), stand_sec=400.0)


# ======================
# Battery
# ======================


def test_to_dict_columns():
    """Flat dict with every column, None for a test not done."""
    result = AutonomicTestsResult(
        "2099-12-05", valsalva=valsalva_ratio(_valsalva_rr(), 30.0)
    )
    row = result.to_dict()
    assert row["date"] == "2099-12-05"
    assert row["db_hr_difference"] is None and row["ratio_30_15"] is None
    assert row["valsalva_interpretation"] == "normal"
    assert len(row) == 19
    assert set(EWING_LIMITS) == {"deep_breathing", "valsalva", "ratio_30_15"}
