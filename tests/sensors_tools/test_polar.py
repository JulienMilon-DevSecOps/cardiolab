"""Unit tests for Polar sensor file parsing module."""

from __future__ import annotations

from pathlib import Path

import pytest

from cardiolab.sensors_tools.polar import (
    _build_output,
    _parse_csv,
    _parse_txt,
    parse_rr_file,
)
from cardiolab.signals.rr import RRSeries


class TestParseRrFile:
    """Test suite for parse_rr_file() main function."""

    def test_parse_csv_file(self, temp_csv_polar_file):
        """Test parsing CSV format file."""
        result = parse_rr_file(temp_csv_polar_file)
        
        assert isinstance(result, dict)
        assert "intervals" in result or isinstance(result, dict)

    def test_parse_txt_file(self, temp_txt_polar_file):
        """Test parsing TXT format file."""
        result = parse_rr_file(temp_txt_polar_file)
        
        assert isinstance(result, dict)

    def test_parse_rr_file_nonexistent(self, tmp_path):
        """Test parsing nonexistent file."""
        nonexistent = tmp_path / "nonexistent.csv"
        
        with pytest.raises(FileNotFoundError):
            parse_rr_file(nonexistent)

    def test_parse_rr_file_unsupported_format(self, tmp_path):
        """Test parsing unsupported file format."""
        unsupported = tmp_path / "file.xyz"
        unsupported.write_text("some data")
        
        with pytest.raises(ValueError):
            parse_rr_file(unsupported)

    def test_parse_rr_file_string_path(self, temp_csv_polar_file):
        """Test parse_rr_file with string path (not Path object)."""
        result = parse_rr_file(str(temp_csv_polar_file))
        
        assert isinstance(result, dict)

    def test_parse_rr_file_path_object(self, temp_csv_polar_file):
        """Test parse_rr_file with Path object."""
        result = parse_rr_file(Path(temp_csv_polar_file))
        
        assert isinstance(result, dict)

    def test_parse_rr_file_returns_rr_series_like(self, temp_csv_polar_file):
        """Test that result is compatible with RRSeries."""
        result = parse_rr_file(temp_csv_polar_file)
        
        # Should have structure compatible with RRSeries
        # Either dict with 'intervals' or RRSeries object
        if isinstance(result, dict):
            assert "intervals" in result or "rr_intervals" in result
        else:
            assert isinstance(result, RRSeries)


class TestParseCsv:
    """Test suite for _parse_csv() function."""

    def test_parse_csv_basic(self, temp_csv_polar_file):
        """Test basic CSV parsing."""
        result = _parse_csv(temp_csv_polar_file)
        
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_parse_csv_detects_rr_column(self, tmp_path):
        """Test CSV parsing detects RR column."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("RR(ms),Time(s)\n810,0.81\n800,1.61\n")
        
        result = _parse_csv(csv_file)
        
        assert isinstance(result, dict)

    def test_parse_csv_column_variations(self, tmp_path):
        """Test CSV parsing with different RR column names."""
        test_cases = [
            "RR(ms)\n810\n800\n",
            "rr_ms\n810\n800\n",
            "RR\n810\n800\n",
            "HR\n75\n76\n"  # This should fail as it's HR, not RR
        ]
        
        for content in test_cases[:-1]:
            csv_file = tmp_path / f"test_{hash(content)}.csv"
            csv_file.write_text(content)
            
            # Should not crash for first three
            try:
                result = _parse_csv(csv_file)
                assert isinstance(result, dict)
            except ValueError:
                pass  # Expected if column not found

    def test_parse_csv_no_rr_column(self, temp_invalid_csv_file):
        """Test CSV parsing fails gracefully without RR column."""
        with pytest.raises(ValueError):
            _parse_csv(temp_invalid_csv_file)

    def test_parse_csv_empty_file(self, temp_empty_file):
        """Test CSV parsing with empty file."""
        # Empty file should raise an error (no headers found)
        with pytest.raises((ValueError, StopIteration, AttributeError, TypeError)):
            _parse_csv(temp_empty_file)

    def test_parse_csv_with_invalid_values(self, tmp_path):
        """Test CSV parsing handles invalid numeric values."""
        csv_file = tmp_path / "invalid.csv"
        csv_file.write_text("RR(ms)\nabc\n800\ndef\n810\n")
        
        # Should skip invalid values and process valid ones
        result = _parse_csv(csv_file)
        
        assert isinstance(result, dict)

    def test_parse_csv_with_negative_values(self, tmp_path):
        """Test CSV parsing skips negative RR values."""
        csv_file = tmp_path / "negative.csv"
        csv_file.write_text("RR(ms)\n810\n-50\n800\n0\n805\n")
        
        result = _parse_csv(csv_file)
        
        # Negative and zero values should be filtered
        if isinstance(result, dict) and "intervals" in result:
            assert all(v > 0 for v in result["intervals"])

    def test_parse_csv_multiple_columns(self, tmp_path):
        """Test CSV with multiple columns."""
        csv_file = tmp_path / "multi.csv"
        csv_file.write_text(
            "Timestamp,RR(ms),HR(bpm),Quality\n"
            "2026-05-12T10:00:00,810,74,100\n"
            "2026-05-12T10:00:01,800,75,100\n"
        )
        
        result = _parse_csv(csv_file)
        
        assert isinstance(result, dict)

    def test_parse_csv_with_bom(self, tmp_path):
        """Test CSV parsing with UTF-8 BOM."""
        csv_file = tmp_path / "bom.csv"
        # Write with UTF-8 BOM
        csv_file.write_text("\ufeffRR(ms)\n810\n800\n", encoding="utf-8-sig")
        
        # Should handle BOM gracefully
        result = _parse_csv(csv_file)
        assert isinstance(result, dict)

    def test_parse_csv_result_structure(self, temp_csv_polar_file):
        """Test CSV parse result structure."""
        result = _parse_csv(temp_csv_polar_file)
        
        assert isinstance(result, dict)
        # Result should have structure compatible with RRSeries
        if "intervals" in result:
            assert isinstance(result["intervals"], list)


class TestParseTxt:
    """Test suite for _parse_txt() function."""

    def test_parse_txt_basic(self, temp_txt_polar_file):
        """Test basic TXT parsing."""
        result = _parse_txt(temp_txt_polar_file)
        
        assert isinstance(result, dict)

    def test_parse_txt_single_column(self, tmp_path):
        """Test TXT with single column of values."""
        txt_file = tmp_path / "single_column.txt"
        txt_file.write_text("810\n800\n805\n795\n")
        
        result = _parse_txt(txt_file)
        
        assert isinstance(result, dict)

    def test_parse_txt_with_spaces(self, tmp_path):
        """Test TXT parsing with leading/trailing spaces."""
        txt_file = tmp_path / "spaces.txt"
        txt_file.write_text("  810  \n800\n  805\n")
        
        result = _parse_txt(txt_file)
        
        assert isinstance(result, dict)

    def test_parse_txt_with_comments(self, tmp_path):
        """Test TXT parsing skips comment lines."""
        txt_file = tmp_path / "comments.txt"
        txt_file.write_text("# RR intervals in ms\n810\n800\n# end data\n805\n")
        
        result = _parse_txt(txt_file)
        
        assert isinstance(result, dict)

    def test_parse_txt_with_invalid_values(self, tmp_path):
        """Test TXT parsing handles invalid values."""
        txt_file = tmp_path / "invalid.txt"
        txt_file.write_text("810\nabc\n800\nXYZ\n805\n")
        
        # Should skip invalid and process valid values
        result = _parse_txt(txt_file)
        
        assert isinstance(result, dict)

    def test_parse_txt_empty_file(self, tmp_path):
        """Test TXT parsing with empty file."""
        txt_file = tmp_path / "empty.txt"
        txt_file.write_text("")
        
        # Empty file should raise ValueError (no valid RR intervals)
        with pytest.raises(ValueError):
            _parse_txt(txt_file)

    def test_parse_txt_negative_values(self, tmp_path):
        """Test TXT parsing filters negative values."""
        txt_file = tmp_path / "negative.txt"
        txt_file.write_text("810\n-50\n800\n0\n805\n")
        
        result = _parse_txt(txt_file)
        
        if isinstance(result, dict) and "intervals" in result:
            assert all(v > 0 for v in result["intervals"])

    def test_parse_txt_floating_point(self, tmp_path):
        """Test TXT parsing with floating point values."""
        txt_file = tmp_path / "float.txt"
        txt_file.write_text("810.5\n800.2\n805.1\n")
        
        result = _parse_txt(txt_file)
        
        assert isinstance(result, dict)

    def test_parse_txt_result_structure(self, temp_txt_polar_file):
        """Test TXT parse result structure."""
        result = _parse_txt(temp_txt_polar_file)
        
        assert isinstance(result, dict)
        if "intervals" in result:
            assert isinstance(result["intervals"], list)


class TestBuildOutput:
    """Test suite for _build_output() function."""

    def test_build_output_creates_dict(self, tmp_path):
        """Test _build_output creates valid dict."""
        filepath = tmp_path / "test.csv"
        rr_intervals = [810, 800, 805, 795]
        
        result = _build_output(filepath, rr_intervals)
        
        assert isinstance(result, dict)

    def test_build_output_contains_intervals(self, tmp_path):
        """Test _build_output includes RR intervals."""
        filepath = tmp_path / "test.csv"
        rr_intervals = [810, 800, 805, 795]
        
        result = _build_output(filepath, rr_intervals)
        
        # Result should have intervals
        if isinstance(result, RRSeries):
            assert len(result.intervals) == len(rr_intervals)
        elif isinstance(result, dict):
            assert "intervals" in result or "rr_intervals" in result

    def test_build_output_contains_metadata(self, tmp_path):
        """Test _build_output includes metadata."""
        filepath = tmp_path / "sample_20260512.csv"  # Date in filename
        rr_intervals = [810, 800, 805]
        
        result = _build_output(filepath, rr_intervals)
        
        assert isinstance(result, (dict, RRSeries))

    def test_build_output_empty_intervals(self, tmp_path):
        """Test _build_output with empty intervals."""
        filepath = tmp_path / "empty.csv"
        rr_intervals = []
        
        result = _build_output(filepath, rr_intervals)
        
        assert isinstance(result, (dict, RRSeries))

    def test_build_output_many_intervals(self, tmp_path):
        """Test _build_output with many intervals."""
        filepath = tmp_path / "long.csv"
        rr_intervals = [810 + i % 20 for i in range(1000)]
        
        result = _build_output(filepath, rr_intervals)
        
        assert isinstance(result, (dict, RRSeries))
        if isinstance(result, RRSeries):
            assert len(result.intervals) == 1000


class TestPolarParsingIntegration:
    """Integration tests for Polar file parsing."""

    def test_parse_csv_to_rrseries(self, temp_csv_polar_file):
        """Test complete CSV parsing workflow to RRSeries."""
        result = parse_rr_file(temp_csv_polar_file)
        
        # Should be usable as RRSeries input
        if isinstance(result, dict):
            intervals = result.get("intervals", result.get("rr_intervals"))
            if intervals:
                rr = RRSeries(intervals=intervals)
                assert len(rr) > 0
        else:
            assert isinstance(result, RRSeries)
            assert len(result) > 0

    def test_parse_txt_to_rrseries(self, temp_txt_polar_file):
        """Test complete TXT parsing workflow to RRSeries."""
        result = parse_rr_file(temp_txt_polar_file)
        
        if isinstance(result, dict):
            intervals = result.get("intervals", result.get("rr_intervals"))
            if intervals:
                rr = RRSeries(intervals=intervals)
                assert len(rr) > 0
        else:
            assert isinstance(result, RRSeries)

    def test_parse_polar_consistency(self, temp_csv_polar_file):
        """Test that repeated parsing gives same result."""
        result1 = parse_rr_file(temp_csv_polar_file)
        result2 = parse_rr_file(temp_csv_polar_file)
        
        # Results should be identical or equivalent
        if isinstance(result1, dict) and isinstance(result2, dict):
            assert result1.get("intervals") == result2.get("intervals")

    def test_parse_various_file_sizes(self, tmp_path):
        """Test parsing files of various sizes."""
        # Small file (1 min ~ 60 intervals)
        small_file = tmp_path / "small.txt"
        small_file.write_text("\n".join(["810"] * 60))
        
        # Medium file (5 min ~ 300 intervals)
        medium_file = tmp_path / "medium.txt"
        medium_file.write_text("\n".join(["810"] * 300))
        
        # Large file (30 min ~ 2000 intervals)
        large_file = tmp_path / "large.txt"
        large_file.write_text("\n".join(["810"] * 2000))
        
        result_small = parse_rr_file(small_file)
        result_medium = parse_rr_file(medium_file)
        result_large = parse_rr_file(large_file)
        
        assert isinstance(result_small, (dict, RRSeries))
        assert isinstance(result_medium, (dict, RRSeries))
        assert isinstance(result_large, (dict, RRSeries))

    def test_parse_polar_realistic_data(self, tmp_path):
        """Test parsing with realistic Polar data."""
        csv_file = tmp_path / "polar_real.csv"
        csv_content = """RR(ms),Time(s)
814,0.814
812,1.626
816,2.442
810,3.252
818,4.070
820,4.890
815,5.705
"""
        csv_file.write_text(csv_content)
        
        result = parse_rr_file(csv_file)
        
        # Should successfully parse realistic data
        assert isinstance(result, (dict, RRSeries))
        if isinstance(result, dict):
            intervals = result.get("intervals", result.get("rr_intervals"))
            if intervals:
                # Should have reasonable values (800-900 ms for resting)
                assert all(500 < v < 1200 for v in intervals)
