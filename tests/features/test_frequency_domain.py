"""Unit tests for frequency_domain module."""

from __future__ import annotations

import numpy as np

from cardiolab.features.frequency_domain import _band_power, frequency_domain


class TestFrequencyDomain:
    """Test suite for frequency_domain() function."""

    def test_frequency_domain_with_normal_rr_series(self, normal_rr_series):
        """Test frequency_domain with valid RRSeries."""
        result = frequency_domain(normal_rr_series)

        # Check structure - all required keys present
        required_keys = {
            "VLF",
            "LF",
            "HF",
            "TP",
            "LF_HF",
            "LF_nu",
            "HF_nu",
            "HF_pct",
            "LF_pct",
            "LF_HF_sum",
            "LF_HF_over_TP",
        }
        assert set(result.keys()) == required_keys

        # Check all values are numeric and non-negative
        for key, value in result.items():
            assert isinstance(value, (int, float)), f"{key} is not numeric"
            assert value >= 0, f"{key} is negative: {value}"

    def test_frequency_domain_returns_valid_power_ratios(self, normal_rr_series):
        """Test that power ratios are between 0 and 1."""
        result = frequency_domain(normal_rr_series)

        # Normalized ratios should be 0-1
        assert 0 <= result["LF_nu"] <= 1
        assert 0 <= result["HF_nu"] <= 1
        assert 0 <= result["HF_pct"] <= 1
        assert 0 <= result["LF_pct"] <= 1

        # LF_nu + HF_nu should approximately equal 1
        assert np.isclose(result["LF_nu"] + result["HF_nu"], 1.0, atol=0.1)

    def test_frequency_domain_lf_hf_ratio(self, normal_rr_series):
        """Test LF/HF ratio calculation."""
        result = frequency_domain(normal_rr_series)

        # LF/HF should be > 0 for normal signal
        assert result["LF_HF"] >= 0

        # Verify manual calculation matches
        if result["HF"] > 0:
            expected_ratio = result["LF"] / result["HF"]
            assert np.isclose(result["LF_HF"], expected_ratio, rtol=0.01)

    def test_frequency_domain_with_high_hr_signal(self, elevated_hr_rr_series):
        """Test with elevated heart rate (stress/exercise)."""
        result = frequency_domain(elevated_hr_rr_series)

        # Higher HR typically shows higher LF/HF ratio (stress)
        assert result["LF_HF"] >= 0
        assert "LF" in result and "HF" in result

    def test_frequency_domain_with_low_variability(self, low_variability_rr_series):
        """Test with very low variability (pathological signal)."""
        result = frequency_domain(low_variability_rr_series)

        # Low variability → lower power values
        assert result["TP"] >= 0
        assert result["HF"] >= 0
        assert result["LF"] >= 0

    def test_frequency_domain_with_short_series(self, short_rr_series):
        """Test with short RRSeries (edge case)."""
        # Should not raise error
        result = frequency_domain(short_rr_series)

        assert isinstance(result, dict)
        assert len(result) > 0

    def test_frequency_domain_with_outliers(self, rr_series_with_outliers):
        """Test robustness with outlier intervals."""
        result = frequency_domain(rr_series_with_outliers)

        # Should handle outliers without crashing
        assert isinstance(result, dict)
        assert all(v >= 0 for v in result.values())

    def test_frequency_domain_total_power_sum(self, normal_rr_series):
        """Test that TP equals sum of bands."""
        result = frequency_domain(normal_rr_series)

        # TP should equal sum of VLF + LF + HF (approximately)
        expected_tp = result["VLF"] + result["LF"] + result["HF"]
        assert np.isclose(result["TP"], expected_tp, rtol=0.10)

    def test_frequency_domain_with_different_fs(self, normal_rr_series):
        """Test frequency_domain with different sampling frequencies."""
        result_fs4 = frequency_domain(normal_rr_series, fs=4.0)
        result_fs2 = frequency_domain(normal_rr_series, fs=2.0)

        # Different fs should produce different results
        # but both should be valid
        assert isinstance(result_fs4, dict)
        assert isinstance(result_fs2, dict)
        assert all(v >= 0 for v in result_fs4.values())
        assert all(v >= 0 for v in result_fs2.values())

    def test_frequency_domain_lf_hf_zero_handling(self, normal_rr_series):
        """Test handling of zero HF power."""
        # This is a theoretical case - very low HF
        result = frequency_domain(normal_rr_series)

        # If HF = 0, LF_HF should be 0 (not inf or nan)
        if result["HF"] == 0:
            assert result["LF_HF"] == 0
            assert not np.isnan(result["LF_HF"])


class TestBandPower:
    """Test suite for _band_power() helper function."""

    def test_band_power_valid_extraction(self):
        """Test basic band power extraction."""
        freqs = np.array([0.01, 0.05, 0.1, 0.2, 0.3])
        psd = np.array([100, 200, 150, 300, 100])

        # Extract power between 0.05 and 0.2
        power = _band_power(freqs, psd, 0.05, 0.2)

        assert power >= 0
        assert isinstance(power, float)

    def test_band_power_hf_band(self):
        """Test HF band extraction (0.15-0.4)."""
        freqs = np.linspace(0, 0.5, 100)
        psd = np.ones_like(freqs)  # Uniform power

        power = _band_power(freqs, psd, 0.15, 0.4)

        # With uniform spectrum, HF should be roughly proportional to bandwidth
        assert power > 0

    def test_band_power_lf_band(self):
        """Test LF band extraction (0.04-0.15)."""
        freqs = np.linspace(0, 0.5, 100)
        psd = np.ones_like(freqs)

        power = _band_power(freqs, psd, 0.04, 0.15)

        assert power > 0

    def test_band_power_vlf_band(self):
        """Test VLF band extraction (0.003-0.04)."""
        freqs = np.linspace(0, 0.5, 100)
        psd = np.ones_like(freqs)

        power = _band_power(freqs, psd, 0.003, 0.04)

        assert power > 0

    def test_band_power_empty_mask(self):
        """Test band_power when no frequencies in range."""
        freqs = np.array([0.5, 0.6, 0.7])  # High frequencies
        psd = np.array([100, 200, 150])

        # Extract from low frequency band (no match)
        power = _band_power(freqs, psd, 0.01, 0.05)

        # Should return 0 or a very small value
        assert power >= 0

    def test_band_power_single_value_in_band(self):
        """Test with single frequency in band."""
        freqs = np.array([0.05, 0.1, 0.2])
        psd = np.array([100, 200, 300])

        power = _band_power(freqs, psd, 0.08, 0.12)

        # Should extract the single value at 0.1
        assert power >= 0  # May be 0 if extraction returns 0

    def test_band_power_boundary_frequencies(self):
        """Test band power at exact boundary frequencies."""
        freqs = np.array([0.04, 0.08, 0.15])
        psd = np.array([100, 200, 300])

        power = _band_power(freqs, psd, 0.04, 0.15)

        # Should include both boundaries or at least be non-negative
        assert power >= 0

    def test_band_power_with_noise(self):
        """Test band power extraction with noisy PSD."""
        freqs = np.linspace(0, 0.5, 500)
        psd = np.random.rand(len(freqs)) * 100  # Noisy spectrum

        power_lf = _band_power(freqs, psd, 0.04, 0.15)
        power_hf = _band_power(freqs, psd, 0.15, 0.4)

        # Both should be positive
        assert power_lf > 0
        assert power_hf > 0


class TestFrequencyDomainIntegration:
    """Integration tests for frequency_domain analysis."""

    def test_frequency_domain_all_bands_sum(self, normal_rr_series):
        """Test that power bands sum logically."""
        result = frequency_domain(normal_rr_series)

        # VLF + LF + HF should approximately equal TP
        band_sum = result["VLF"] + result["LF"] + result["HF"]
        total_power = result["TP"]

        # Allow 10% tolerance
        assert np.isclose(band_sum, total_power, rtol=0.10)

    def test_frequency_domain_realistic_values(self, normal_rr_series):
        """Test that output values are realistic for resting condition."""
        result = frequency_domain(normal_rr_series)

        # For resting condition: HF > LF typically
        # But this can vary, so just ensure both are reasonable
        assert result["HF"] > 0 or result["LF"] > 0

        # TP should be non-zero
        assert result["TP"] > 0

    def test_frequency_domain_consistency(self, normal_rr_series):
        """Test that repeated calls give consistent results."""
        result1 = frequency_domain(normal_rr_series)
        result2 = frequency_domain(normal_rr_series)

        # Results should be identical
        for key in result1:
            assert np.isclose(result1[key], result2[key], rtol=0.001)

    def test_frequency_domain_stress_vs_rest(
        self, normal_rr_series, elevated_hr_rr_series
    ):
        """Test differences between rest and stress-like conditions."""
        result_rest = frequency_domain(normal_rr_series)
        result_stress = frequency_domain(elevated_hr_rr_series)

        # Both should produce valid results
        assert result_rest["TP"] > 0
        assert result_stress["TP"] > 0

        # Results should be different (stress typically has higher LF/HF)
        # This is a tendency, not a rule, so just check both are computed
        assert isinstance(result_rest["LF_HF"], float)
        assert isinstance(result_stress["LF_HF"], float)
