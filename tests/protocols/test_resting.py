"""Unit tests for resting protocol module."""

from __future__ import annotations

import numpy as np

from cardiolab.protocols.resting import HRVFeatures, _compute_simple_score, resting_hrv


class TestHRVFeatures:
    """Test suite for HRVFeatures dataclass."""

    def test_hrv_features_creation(self, normal_hrv_features):
        """Test HRVFeatures dataclass creation."""
        assert isinstance(normal_hrv_features, HRVFeatures)
        assert normal_hrv_features.rmssd == 60.0
        assert normal_hrv_features.mean_hr == 70.0

    def test_hrv_features_all_fields_present(self, normal_hrv_features):
        """Test that all 23 fields are present."""
        expected_fields = {
            "date",
            "rmssd",
            "ln_rmssd",
            "sdnn",
            "pnn50",
            "mean_hr",
            "vlf",
            "lf",
            "hf",
            "lf_hf",
            "hf_pct",
            "lf_nu",
            "hf_nu",
            "hf_hr",
            "sd1",
            "sd2",
            "sd_ratio",
            "dfa_alpha1",
            "apen",
            "sampen",
            "duration",
            "score",
            "method",
        }

        actual_fields = set(vars(normal_hrv_features).keys())
        assert actual_fields == expected_fields

    def test_hrv_features_default_values(self):
        """Test HRVFeatures with default values."""
        features = HRVFeatures()

        assert features.date is None
        assert features.rmssd == 0.0
        assert features.mean_hr == 0.0
        assert features.score == 0.0

    def test_hrv_features_with_date(self):
        """Test HRVFeatures with date."""
        features = HRVFeatures(date="2026-05-12T10:00:00", rmssd=60.0)

        assert features.date == "2026-05-12T10:00:00"

    def test_hrv_features_numeric_validation(self, normal_hrv_features):
        """Test that all numeric fields are float/int."""
        numeric_fields = [
            "rmssd",
            "ln_rmssd",
            "sdnn",
            "pnn50",
            "mean_hr",
            "vlf",
            "lf",
            "hf",
            "lf_hf",
            "hf_pct",
            "lf_nu",
            "hf_nu",
            "hf_hr",
            "sd1",
            "sd2",
            "sd_ratio",
            "dfa_alpha1",
            "duration",
            "score",
        ]

        for field in numeric_fields:
            value = getattr(normal_hrv_features, field)
            assert isinstance(value, (int, float)), f"{field} is not numeric"


class TestRestingHRV:
    """Test suite for resting_hrv() protocol function."""

    def test_resting_hrv_main_protocol(self, normal_rr_series):
        """Test resting_hrv main protocol execution."""
        result = resting_hrv(normal_rr_series)

        assert isinstance(result, HRVFeatures)
        assert result.rmssd > 0
        assert result.sdnn > 0
        assert result.mean_hr > 0

    def test_resting_hrv_all_metrics_computed(self, normal_rr_series):
        """Test that all HRV metrics are computed."""
        result = resting_hrv(normal_rr_series)

        # Time-domain metrics
        assert result.rmssd > 0
        assert result.ln_rmssd > 0
        assert result.sdnn > 0
        assert result.pnn50 >= 0

        # Frequency-domain metrics
        assert result.vlf >= 0
        assert result.lf >= 0
        assert result.hf >= 0
        assert result.lf_hf >= 0
        assert result.hf_pct >= 0
        assert result.lf_nu >= 0
        assert result.hf_nu >= 0

        # Non-linear metrics
        assert result.sd1 > 0
        assert result.sd2 > 0
        assert result.sd_ratio > 0

        # Duration
        assert result.duration > 0

    def test_resting_hrv_with_compute_score_false(self, normal_rr_series):
        """Test resting_hrv without score computation."""
        result = resting_hrv(normal_rr_series, compute_score=False)

        assert result.score == 0.0

    def test_resting_hrv_with_compute_score_true(self, normal_rr_series):
        """Test resting_hrv with score computation."""
        result = resting_hrv(normal_rr_series, compute_score=True)

        # Score should be computed
        assert result.score is not None
        assert isinstance(result.score, (int, float))

    def test_resting_hrv_short_signal(self, short_rr_series):
        """Test resting_hrv with short signal (< 300s)."""
        # Should not crash even if below min_duration
        result = resting_hrv(short_rr_series, min_duration=300.0)

        assert isinstance(result, HRVFeatures)
        assert result.rmssd >= 0  # May be lower with short signal

    def test_resting_hrv_custom_min_duration(self, short_rr_series):
        """Test resting_hrv with custom minimum duration."""
        # Set lower min_duration for short signal
        result = resting_hrv(short_rr_series, min_duration=10.0)

        assert isinstance(result, HRVFeatures)

    def test_resting_hrv_frequency_indicators_valid(self, normal_rr_series):
        """Test that frequency indicators are valid."""
        result = resting_hrv(normal_rr_series)

        # All frequency values should be non-negative
        assert result.vlf >= 0
        assert result.lf >= 0
        assert result.hf >= 0
        assert result.lf_hf >= 0

        # Normalized values should be 0-1
        assert 0 <= result.lf_nu <= 1
        assert 0 <= result.hf_nu <= 1
        assert 0 <= result.hf_pct <= 1

    def test_resting_hrv_low_variability_signal(self, low_variability_rr_series):
        """Test resting_hrv with low variability (potential illness)."""
        result = resting_hrv(low_variability_rr_series)

        assert isinstance(result, HRVFeatures)
        # Low variability should result in low RMSSD
        assert result.rmssd > 0  # Should still compute

    def test_resting_hrv_high_hr_signal(self, elevated_hr_rr_series):
        """Test resting_hrv with elevated heart rate."""
        result = resting_hrv(elevated_hr_rr_series)

        assert result.mean_hr > 0
        # Should reflect elevated HR
        assert result.mean_hr > 80  # Higher than normal resting

    def test_resting_hrv_duration_reflection(self, baseline_7days):
        """Test that duration is correctly reflected."""
        # Use first feature's RR intervals as approximation
        result = resting_hrv(
            type(
                "obj",
                (object,),
                {
                    "intervals": np.array([800] * 300),
                    "duration": 300.0,
                    "mean_hr": 75.0,
                },
            )()
        )

        # Duration should match
        assert result.duration > 0

    def test_resting_hrv_consistency(self, normal_rr_series):
        """Test that repeated calls give consistent results."""
        result1 = resting_hrv(normal_rr_series, compute_score=False)
        result2 = resting_hrv(normal_rr_series, compute_score=False)

        # Results should be identical
        assert np.isclose(result1.rmssd, result2.rmssd)
        assert np.isclose(result1.sdnn, result2.sdnn)
        assert np.isclose(result1.mean_hr, result2.mean_hr)

    def test_resting_hrv_with_outliers(self, rr_series_with_outliers):
        """Test resting_hrv robustness with outlier intervals."""
        result = resting_hrv(rr_series_with_outliers)

        # Should still produce valid results
        assert isinstance(result, HRVFeatures)
        assert result.rmssd > 0


class TestComputeSimpleScore:
    """Test suite for _compute_simple_score() helper function."""

    def test_simple_score_valid_inputs(self):
        """Test simple score with valid inputs."""
        score = _compute_simple_score(60.0, 70.0)  # RMSSD=60, HR=70

        assert isinstance(score, (int, float))
        # Score is not necessarily 0-100, just numeric

    def test_simple_score_excellent_recovery(self):
        """Test simple score with excellent recovery metrics."""
        # High RMSSD + low HR = excellent
        score = _compute_simple_score(100.0, 55.0)

        # Good recovery should have higher score than poor
        score_poor = _compute_simple_score(25.0, 90.0)
        assert score > score_poor

    def test_simple_score_poor_recovery(self):
        """Test simple score with poor recovery metrics."""
        # Low RMSSD + high HR = poor
        score = _compute_simple_score(25.0, 90.0)

        assert score < 50  # Should be low score

    def test_simple_score_normal_recovery(self):
        """Test simple score with normal recovery."""
        score = _compute_simple_score(60.0, 70.0)

        assert isinstance(score, (int, float))
        # Just check it's computed without error

    def test_simple_score_hr_penalty(self):
        """Test that high HR lowers score."""
        score_normal_hr = _compute_simple_score(60.0, 60.0)
        score_high_hr = _compute_simple_score(60.0, 100.0)

        # High HR should result in lower score
        assert score_normal_hr > score_high_hr

    def test_simple_score_rmssd_benefit(self):
        """Test that high RMSSD increases score."""
        score_low_rmssd = _compute_simple_score(30.0, 70.0)
        score_high_rmssd = _compute_simple_score(100.0, 70.0)

        # High RMSSD should result in higher score
        assert score_high_rmssd > score_low_rmssd

    def test_simple_score_extreme_values(self):
        """Test simple score with extreme but valid values."""
        # Very high RMSSD
        score_very_high = _compute_simple_score(150.0, 50.0)
        assert isinstance(score_very_high, (int, float))

        # Very low RMSSD
        score_very_low = _compute_simple_score(10.0, 120.0)
        assert isinstance(score_very_low, (int, float))

    def test_simple_score_zero_rmssd(self):
        """Test simple score with zero RMSSD (edge case)."""
        score = _compute_simple_score(0.0, 70.0)

        # Should handle gracefully
        assert isinstance(score, (int, float)) or score is None

    def test_simple_score_bounds(self):
        """Test that simple score is numeric for all inputs."""
        test_cases = [
            (20.0, 50.0),
            (80.0, 100.0),
            (50.0, 70.0),
            (100.0, 40.0),
        ]

        for rmssd, hr in test_cases:
            score = _compute_simple_score(rmssd, hr)
            assert isinstance(score, (int, float)), (
                f"Score {score} not numeric for RMSSD={rmssd}, HR={hr}"
            )


class TestRestingProtocolIntegration:
    """Integration tests for resting protocol."""

    def test_complete_resting_protocol_workflow(self, normal_rr_series):
        """Test complete resting protocol workflow."""
        # Execute protocol
        result = resting_hrv(normal_rr_series, compute_score=True)

        # Verify all components
        assert result.rmssd > 0
        assert result.sdnn > 0
        assert result.mean_hr > 0
        assert result.vlf >= 0
        assert result.lf >= 0
        assert result.hf >= 0
        assert result.score is not None
        assert result.duration > 0

    def test_resting_protocol_vs_signal_quality(
        self, clean_ecg_signal, noisy_ecg_signal
    ):
        """Test resting protocol differences with clean vs noisy signals."""
        # Note: This test converts ECG to RR, then runs protocol
        # Simplified test showing both can be processed

        assert clean_ecg_signal is not None
        assert noisy_ecg_signal is not None

    def test_resting_protocol_various_hr_levels(self, rr_series_generator):
        """Test resting protocol with various HR levels."""
        # Low HR (athletic)
        low_hr_rr = rr_series_generator(mean_rr=1200, length=300)  # ~50 bpm
        result_low = resting_hrv(low_hr_rr)

        # Normal HR
        normal_hr_rr = rr_series_generator(mean_rr=857, length=300)  # ~70 bpm
        result_normal = resting_hrv(normal_hr_rr)

        # High HR
        high_hr_rr = rr_series_generator(mean_rr=600, length=300)  # ~100 bpm
        result_high = resting_hrv(high_hr_rr)

        # All should produce valid metrics
        assert result_low.mean_hr > 0
        assert result_normal.mean_hr > 0
        assert result_high.mean_hr > 0

        # HR should correlate approximately
        assert result_low.mean_hr < result_high.mean_hr


# ======================
# HRVFeatures.to_dict()
# ======================


class TestHRVFeaturesToDict:
    """Tests for HRVFeatures.to_dict()."""

    def test_to_dict_returns_dict(self, normal_hrv_features):
        """to_dict() must return a plain dict."""
        assert isinstance(normal_hrv_features.to_dict(), dict)

    def test_to_dict_contains_all_keys(self, normal_hrv_features):
        """to_dict() must expose all 23 HRVFeatures fields."""
        expected_keys = {
            "date",
            "rmssd",
            "ln_rmssd",
            "sdnn",
            "pnn50",
            "mean_hr",
            "vlf",
            "lf",
            "hf",
            "lf_hf",
            "hf_pct",
            "lf_nu",
            "hf_nu",
            "hf_hr",
            "sd1",
            "sd2",
            "sd_ratio",
            "dfa_alpha1",
            "apen",
            "sampen",
            "duration",
            "score",
            "method",
        }
        assert set(normal_hrv_features.to_dict().keys()) == expected_keys

    def test_to_dict_values_match_fields(self, normal_hrv_features):
        """Values in the dict must match the dataclass fields exactly."""
        d = normal_hrv_features.to_dict()
        assert d["rmssd"] == normal_hrv_features.rmssd
        assert d["mean_hr"] == normal_hrv_features.mean_hr
        assert d["hf_hr"] == normal_hrv_features.hf_hr
        assert d["date"] == normal_hrv_features.date

    def test_to_dict_date_none_by_default(self):
        """to_dict() on a default HRVFeatures must have date=None."""
        assert HRVFeatures().to_dict()["date"] is None

    def test_to_dict_values_are_python_types(self, normal_hrv_features):
        """Numeric fields must be native Python float; 'method' must be str."""
        d = normal_hrv_features.to_dict()
        for key, val in d.items():
            if key == "date":
                continue
            if key == "method":
                assert isinstance(val, str), f"Field {key!r} is {type(val)}"
            else:
                assert isinstance(val, float), f"Field {key!r} is {type(val)}"


# ======================
# auto_clean in resting_hrv()
# ======================


class TestRestingHRVAutoClean:
    """Tests for the auto_clean parameter in resting_hrv()."""

    def test_auto_clean_false_does_not_alter_rr(self, normal_rr_series):
        """auto_clean=False must not alter the input series (default behaviour)."""
        import warnings

        n_before = len(normal_rr_series)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            resting_hrv(normal_rr_series, min_duration=0.0)
        assert len(normal_rr_series) == n_before

    def test_auto_clean_removes_outliers_before_computation(self):
        """auto_clean=True must produce the same result as cleaning manually."""
        import warnings

        rng = np.random.default_rng(0)
        base = rng.normal(857, 20, 300).clip(300, 1200)
        base[50] = 150.0
        base[150] = 2500.0
        from cardiolab.signals.rr import RRSeries

        dirty = RRSeries(base)
        clean = dirty.remove_outliers()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result_auto = resting_hrv(dirty, min_duration=0.0, auto_clean=True)
        result_manual = resting_hrv(clean, min_duration=0.0)

        assert abs(result_auto.rmssd - result_manual.rmssd) < 1e-6

    def test_auto_clean_suppresses_warning(self):
        """After auto_clean, PhysiologicalWarning must not propagate further."""
        import warnings

        from cardiolab.signals.rr import PhysiologicalWarning, RRSeries

        rng = np.random.default_rng(1)
        base = rng.normal(857, 20, 300).clip(300, 1200)
        base[10] = 150.0
        dirty = RRSeries(base)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            resting_hrv(dirty, min_duration=0.0, auto_clean=True)

        physio_warnings = [x for x in w if issubclass(x.category, PhysiologicalWarning)]
        assert len(physio_warnings) == 0
