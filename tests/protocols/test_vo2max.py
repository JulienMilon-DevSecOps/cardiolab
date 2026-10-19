"""Unit tests for VO2max estimation protocol."""

from __future__ import annotations

import math

import numpy as np
import pytest

from cardiolab.analytics.scoring import session_score, vo2max_score
from cardiolab.protocols.vo2max import (
    FRIEND_PERCENTILES,
    VO2maxResult,
    _fitness_category,
    age_at,
    tanaka_hr_max,
    vo2max_category,
    vo2max_from_hrv,
    vo2max_percentile,
)
from cardiolab.signals.quality import quality_columns
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
    """Tests for the VO2maxResult dataclass."""

    def test_default_values(self):
        """All fields initialise to their documented zero/nan/None defaults."""
        r = VO2maxResult()
        assert r.date is None
        assert math.isnan(r.vo2max_uth)
        assert math.isnan(r.vo2max_esco_flatt)  # deprecated model (0.4.0)
        assert r.vo2max_ln_rmssd == 0.0
        assert r.hr_rest == 0.0
        assert math.isnan(r.hr_max)
        assert r.rmssd_used == 0.0
        assert r.ln_rmssd_used == 0.0
        assert r.fitness_category == "poor"

    def test_to_dict_keys(self):
        """to_dict returns exactly the expected set of keys."""
        r = VO2maxResult()
        expected = {
            "date",
            "vo2max_uth",
            "vo2max_esco_flatt",
            "vo2max_ln_rmssd",
            "hr_rest",
            "hr_max",
            "hr_max_source",
            "rmssd_used",
            "ln_rmssd_used",
            "fitness_category",
            "score",
            *quality_columns(None),
        }
        assert set(r.to_dict().keys()) == expected

    def test_to_dict_values_match(self):
        """to_dict values match the fields set at construction."""
        r = VO2maxResult(vo2max_esco_flatt=42.0, fitness_category="good")
        d = r.to_dict()
        assert d["vo2max_esco_flatt"] == 42.0
        assert d["fitness_category"] == "good"


# ======================
# _fitness_category()
# ======================


class TestFitnessCategory:
    """Tests for the _fitness_category() helper."""

    def test_poor(self):
        """VO2max < 28 mL/kg/min is classified as poor."""
        assert _fitness_category(20.0) == "poor"
        assert _fitness_category(27.9) == "poor"

    def test_fair(self):
        """VO2max in [28, 38) mL/kg/min is classified as fair."""
        assert _fitness_category(28.0) == "fair"
        assert _fitness_category(37.9) == "fair"

    def test_good(self):
        """VO2max in [38, 48) mL/kg/min is classified as good."""
        assert _fitness_category(38.0) == "good"
        assert _fitness_category(47.9) == "good"

    def test_very_good(self):
        """VO2max in [48, 58) mL/kg/min is classified as very_good."""
        assert _fitness_category(48.0) == "very_good"
        assert _fitness_category(57.9) == "very_good"

    def test_excellent(self):
        """VO2max >= 58 mL/kg/min is classified as excellent."""
        assert _fitness_category(58.0) == "excellent"
        assert _fitness_category(75.0) == "excellent"


# ======================
# vo2max_from_hrv()
# ======================


class TestVO2maxFromHRV:
    """Tests for the vo2max_from_hrv() function."""

    def test_raises_on_too_few_intervals(self):
        """Fewer than 30 RR intervals raises ValueError."""
        rr = RRSeries(np.full(10, 800.0))
        with pytest.raises(ValueError, match="Too few"):
            vo2max_from_hrv(rr)

    def test_returns_vo2max_result(self):
        """Function returns a VO2maxResult instance."""
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert isinstance(result, VO2maxResult)

    def test_esco_flatt_no_longer_computed(self):
        """The Esco-Flatt RMSSD model was removed in 0.4.0: always NaN."""
        rr = _make_rr()
        assert math.isnan(vo2max_from_hrv(rr).vo2max_esco_flatt)

    def test_ln_rmssd_non_nan(self):
        """ln-RMSSD VO2max estimate is a positive finite number."""
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert not math.isnan(result.vo2max_ln_rmssd)
        assert result.vo2max_ln_rmssd > 0.0

    def test_uth_nan_without_hr_max(self):
        """Uth estimate and hr_max are NaN when hr_max is not provided."""
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert math.isnan(result.vo2max_uth)
        assert math.isnan(result.hr_max)

    def test_uth_computed_with_hr_max(self):
        """Uth estimate is a positive finite number when hr_max is provided."""
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

    def test_ln_rmssd_formula(self):
        """Verify ln-RMSSD formula: 24.89 + 5.97 × ln(RMSSD)."""
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        expected = 24.89 + 5.97 * math.log(result.rmssd_used)
        assert abs(result.vo2max_ln_rmssd - expected) < 0.01

    def test_hr_rest_derived_from_rr(self):
        """HR rest is correctly derived from the mean RR interval."""
        rr = RRSeries(np.full(60, 1000.0))  # 60 bpm exactly
        result = vo2max_from_hrv(rr)
        assert abs(result.hr_rest - 60.0) < 0.01

    def test_fitness_category_valid(self):
        """Fitness category is always one of the five valid labels."""
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert result.fitness_category in (
            "poor",
            "fair",
            "good",
            "very_good",
            "excellent",
        )

    def test_fitness_category_uses_uth_when_available(self):
        """Fitness category is derived from Uth when hr_max is provided."""
        rr = _make_rr(n=300, mean_ms=1100)  # low HR → high VO2max estimate
        result_with = vo2max_from_hrv(rr, hr_max=200.0)
        result_without = vo2max_from_hrv(rr)
        assert result_with.fitness_category == _fitness_category(result_with.vo2max_uth)
        assert result_without.fitness_category == _fitness_category(
            result_without.vo2max_ln_rmssd
        )

    def test_higher_rmssd_higher_ln_rmssd_estimate(self):
        """Higher RMSSD → higher ln-RMSSD VO2max estimate (monotone relationship)."""
        rr_low = _make_rr(n=300, mean_ms=857, std_ms=10)
        rr_high = _make_rr(n=300, mean_ms=857, std_ms=80)
        res_low = vo2max_from_hrv(rr_low)
        res_high = vo2max_from_hrv(rr_high)
        assert res_high.vo2max_ln_rmssd >= res_low.vo2max_ln_rmssd

    @pytest.mark.parametrize("sample", range(6))
    def test_plausible_without_hr_max(self, sample):
        """Bug v0.4.0-05: a trained athlete without hr_max is no longer "poor".

        The author's recordings (RMSSD 41–75 ms, resting HR ≈ 50–60 bpm) gave
        ≈ 21 mL/kg/min with the removed Esco-Flatt model (category "poor").
        """
        from cardiolab.datasets import load_sample

        rr, _ = load_sample("resting", sample).correct_artifacts()
        result = vo2max_from_hrv(rr)
        assert 40.0 < result.vo2max_ln_rmssd < 60.0
        assert result.fitness_category in ("good", "very_good", "excellent")

    def test_models_agree_on_athlete_profile(self):
        """Uth and ln-RMSSD stay within 25 % on a realistic athlete profile."""
        from cardiolab.datasets import load_sample

        rr, _ = load_sample("resting", 1).correct_artifacts()
        result = vo2max_from_hrv(rr, hr_max=185.0)
        ratio = result.vo2max_ln_rmssd / result.vo2max_uth
        assert 0.75 < ratio < 1.25

    def test_rmssd_used_positive(self):
        """RMSSD used in the estimate is positive."""
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert result.rmssd_used > 0.0

    def test_ln_rmssd_used_consistent(self):
        """ln_rmssd_used equals log(rmssd_used) to floating-point precision."""
        rr = _make_rr()
        result = vo2max_from_hrv(rr)
        assert abs(result.ln_rmssd_used - math.log(result.rmssd_used)) < 1e-6

    def test_minimum_30_intervals_passes(self):
        """Exactly 30 intervals does not raise."""
        rr = RRSeries(np.full(30, 857.0))
        result = vo2max_from_hrv(rr)
        assert isinstance(result, VO2maxResult)

    def test_to_dict_round_trip(self):
        """to_dict preserves fitness_category and hr_max."""
        rr = _make_rr()
        result = vo2max_from_hrv(rr, hr_max=185.0)
        d = result.to_dict()
        assert d["fitness_category"] == result.fitness_category
        assert d["hr_max"] == result.hr_max


# ======================
# AGE AND SEX (0.5.0)
# ======================


@pytest.mark.unit
class TestAgeSexNorms:
    """FRIEND norms by age and sex, Tanaka HRmax."""

    def test_tanaka(self):
        """208 − 0.7 × age."""
        assert tanaka_hr_max(40) == pytest.approx(180.0)

    def test_age_at(self):
        """Age in the year of the measurement; None when unknown."""
        assert age_at(1990, "2026-10-19") == 36
        assert age_at(None, "2026-10-19") is None

    @pytest.mark.parametrize("sex", ["male", "female"])
    @pytest.mark.parametrize("decade", [20, 30, 40, 50, 60, 70])
    def test_percentile_reproduces_table(self, sex, decade):
        """Exact at the five table percentiles, monotonic in the tails."""
        p10, p25, p50, p75, p90 = FRIEND_PERCENTILES[sex][decade]
        age = decade + 5
        assert vo2max_percentile(p50, age, sex) == pytest.approx(50.0)
        assert vo2max_percentile(p10, age, sex) == pytest.approx(10.0, abs=1e-3)
        assert vo2max_percentile(p90, age, sex) == pytest.approx(90.0, abs=1e-3)
        assert vo2max_percentile(p25, age, sex) == pytest.approx(25.0)
        assert vo2max_percentile(p75, age, sex) == pytest.approx(75.0)
        assert 0 < vo2max_percentile(p10 - 3, age, sex) < 10
        assert 90 < vo2max_percentile(p90 + 3, age, sex) < 100

    def test_category_by_age_and_sex(self):
        """42 mL/kg/min: fair for a man of 25, excellent for a woman of 55."""
        assert vo2max_category(42.0, 25, "male") == "good"
        assert vo2max_category(35.0, 25, "male") == "fair"
        assert vo2max_category(42.0, 55, "female") == "excellent"
        assert vo2max_category(42.0) == "good"  # fixed scale

    def test_ages_outside_table_clamped(self):
        """Under 20 → 20–29 norms, 80 and over → 70–79."""
        assert vo2max_percentile(48.0, 16, "male") == pytest.approx(50.0)
        assert vo2max_percentile(24.4, 85, "male") == pytest.approx(50.0)

    def test_unknown_sex_uses_fixed_scale(self):
        """No percentile without a known sex."""
        assert vo2max_percentile(40.0, 30, None) is None
        assert vo2max_score(40.0, 30, None) == pytest.approx(vo2max_score(40.0))

    def test_score_is_percentile(self):
        """With age and sex, the score is the percentile."""
        assert vo2max_score(37.8, 45, "male") == pytest.approx(50.0)

    def test_from_hrv_tanaka(self):
        """Without hr_max, the age gives a Tanaka HRmax and a Uth estimate."""
        result = vo2max_from_hrv(_make_rr(), age=40, sex="male")
        assert result.hr_max_source == "tanaka"
        assert result.hr_max == pytest.approx(180.0)
        assert result.vo2max_uth == pytest.approx(15.3 * 180.0 / result.hr_rest)
        assert result.best_estimate == result.vo2max_uth

    def test_from_hrv_provided_hr_max_wins(self):
        """A provided hr_max is used even when the age is known."""
        result = vo2max_from_hrv(_make_rr(), hr_max=190.0, age=40)
        assert result.hr_max_source == "provided"
        assert result.hr_max == 190.0

    def test_from_hrv_nothing(self):
        """Neither hr_max nor age: no Uth, indicative ln-RMSSD estimate."""
        result = vo2max_from_hrv(_make_rr())
        assert result.hr_max_source is None
        assert result.best_estimate == result.vo2max_ln_rmssd

    def test_session_score_uses_norms(self):
        """session_score('vo2max') scores against the result's age and sex."""
        result = vo2max_from_hrv(_make_rr(), age=40, sex="female")
        assert session_score("vo2max", result) == pytest.approx(result.percentile)

    def test_fixed_scale_alias(self):
        """_fitness_category stays the fixed adult scale."""
        assert _fitness_category(42.0) == vo2max_category(42.0)
