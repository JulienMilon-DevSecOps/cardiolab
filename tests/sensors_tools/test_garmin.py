"""Unit tests for the Garmin FIT and CSV parsers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from cardiolab.sensors_tools.garmin import (
    _require_fitparse,
    extract_training_session_garmin,
    parse_garmin_csv,
    parse_garmin_fit,
)
from cardiolab.signals.rr import RRSeries

# ======================
# HELPERS — FIT mocks
# ======================

# RR intervals in seconds (representative resting session at ~70 bpm)
_RR_SEC = [0.800, 0.810, 0.795, 0.820, 0.805, 0.790, 0.815, 0.800, 0.810, 0.795]
_RR_MS = [v * 1000.0 for v in _RR_SEC]

# HR samples for a training session
_HR_SAMPLES = [140.0, 145.0, 150.0, 148.0, 152.0, 147.0, 143.0, 138.0]
_T0 = datetime(2026, 1, 10, 7, 30, 0, tzinfo=UTC)
_TIMESTAMPS = [_T0 + timedelta(seconds=i * 5) for i in range(len(_HR_SAMPLES))]


def _make_hrv_fitfile():
    """Return a mock FitFile with HRV messages."""
    hrv_data = MagicMock()
    hrv_data.name = "time"
    hrv_data.value = tuple(_RR_SEC)

    hrv_msg = MagicMock()
    hrv_msg.__iter__ = MagicMock(return_value=iter([hrv_data]))

    fitfile = MagicMock()
    fitfile.get_messages.side_effect = lambda name: (
        iter([hrv_msg]) if name == "hrv" else iter([])
    )
    return fitfile


def _make_training_fitfile():
    """Return a mock FitFile with record messages (training session)."""

    def _make_record(hr, ts):
        rec = MagicMock()
        rec.get_value.side_effect = lambda field: (
            hr if field == "heart_rate" else ts if field == "timestamp" else None
        )
        return rec

    records = [
        _make_record(hr, ts) for hr, ts in zip(_HR_SAMPLES, _TIMESTAMPS, strict=False)
    ]

    fitfile = MagicMock()
    fitfile.get_messages.side_effect = lambda name: (
        iter(records) if name == "record" else iter([])
    )
    return fitfile


# ======================
# CSV fixture
# ======================

GARMIN_CSV = """\
Timestamp,RR Interval (ms),HR (bpm)
2026-01-10T07:30:00,800,75
2026-01-10T07:30:01,810,74
2026-01-10T07:30:01,795,76
2026-01-10T07:30:02,820,73
2026-01-10T07:30:03,805,74
2026-01-10T07:30:04,790,76
2026-01-10T07:30:05,815,74
"""

GARMIN_CSV_NO_RR = """\
Timestamp,HR (bpm)
2026-01-10T07:30:00,75
"""

GARMIN_CSV_WITH_NEGATIVES = """\
Timestamp,RR Interval (ms)
2026-01-10T07:30:00,800
2026-01-10T07:30:01,-50
2026-01-10T07:30:01,0
2026-01-10T07:30:02,810
"""


# ======================
# parse_garmin_fit
# ======================


class TestParseGarminFit:
    """Tests for parse_garmin_fit()."""

    @pytest.fixture(autouse=True)
    def _fitparse_available(self):
        with patch("cardiolab.sensors_tools.garmin._FITPARSE_AVAILABLE", True):
            yield

    def test_returns_rrseries(self, tmp_path):
        """Returns a valid RRSeries from a FIT file with HRV messages."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")  # content read by mock

        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = _make_hrv_fitfile()
            rr = parse_garmin_fit(fit_file)

        assert isinstance(rr, RRSeries)

    def test_rr_values_converted_to_ms(self, tmp_path):
        """RR intervals are converted from seconds to milliseconds."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = _make_hrv_fitfile()
            rr = parse_garmin_fit(fit_file)

        import numpy as np

        assert np.allclose(sorted(rr.intervals), sorted(_RR_MS), atol=0.1)

    def test_length_matches_intervals(self, tmp_path):
        """RRSeries length matches the number of HRV intervals in the FIT."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = _make_hrv_fitfile()
            rr = parse_garmin_fit(fit_file)

        assert len(rr) == len(_RR_SEC)

    def test_file_not_found(self, tmp_path):
        """Raises FileNotFoundError for a missing file."""
        with (
            patch("cardiolab.sensors_tools.garmin._fitparse"),
            pytest.raises(FileNotFoundError),
        ):
            parse_garmin_fit(tmp_path / "missing.fit")

    def test_no_hrv_messages_raises(self, tmp_path):
        """Raises ValueError when the FIT file has no HRV messages."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        empty_fitfile = MagicMock()
        empty_fitfile.get_messages.return_value = iter([])

        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = empty_fitfile
            with pytest.raises(ValueError, match="No HRV messages"):
                parse_garmin_fit(fit_file)

    def test_accepts_string_path(self, tmp_path):
        """Accepts a string path as well as a Path object."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = _make_hrv_fitfile()
            rr = parse_garmin_fit(str(fit_file))

        assert isinstance(rr, RRSeries)

    def test_fitparse_not_available_raises(self, tmp_path):
        """Raises ImportError when fitparse is not installed."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        with (
            patch("cardiolab.sensors_tools.garmin._FITPARSE_AVAILABLE", False),
            pytest.raises(ImportError, match="fitparse"),
        ):
            parse_garmin_fit(fit_file)


# ======================
# parse_garmin_csv
# ======================


class TestParseGarminCsv:
    """Tests for parse_garmin_csv()."""

    def test_returns_rrseries(self, tmp_path):
        """Returns a valid RRSeries from a Garmin CSV."""
        f = tmp_path / "garmin.csv"
        f.write_text(GARMIN_CSV)
        rr = parse_garmin_csv(f)
        assert isinstance(rr, RRSeries)

    def test_length_matches_rows(self, tmp_path):
        """RRSeries length matches the number of valid data rows."""
        f = tmp_path / "garmin.csv"
        f.write_text(GARMIN_CSV)
        rr = parse_garmin_csv(f)
        assert len(rr) == 7

    def test_rr_values_correct(self, tmp_path):
        """First RR interval matches the CSV value."""
        f = tmp_path / "garmin.csv"
        f.write_text(GARMIN_CSV)
        rr = parse_garmin_csv(f)
        assert rr.intervals[0] == pytest.approx(800.0)

    def test_negative_values_filtered(self, tmp_path):
        """Negative and zero RR values are silently skipped."""
        f = tmp_path / "garmin.csv"
        f.write_text(GARMIN_CSV_WITH_NEGATIVES)
        rr = parse_garmin_csv(f)
        assert len(rr) == 2
        assert all(v > 0 for v in rr.intervals)

    def test_no_rr_column_raises(self, tmp_path):
        """Raises ValueError when no RR column is found."""
        f = tmp_path / "garmin.csv"
        f.write_text(GARMIN_CSV_NO_RR)
        with pytest.raises(ValueError, match="No RR interval column"):
            parse_garmin_csv(f)

    def test_file_not_found(self, tmp_path):
        """Raises FileNotFoundError for a missing file."""
        with pytest.raises(FileNotFoundError):
            parse_garmin_csv(tmp_path / "missing.csv")

    def test_empty_file_raises(self, tmp_path):
        """Raises ValueError for an empty file."""
        f = tmp_path / "garmin.csv"
        f.write_text("")
        with pytest.raises(ValueError):
            parse_garmin_csv(f)

    def test_accepts_string_path(self, tmp_path):
        """Accepts a string path as well as a Path object."""
        f = tmp_path / "garmin.csv"
        f.write_text(GARMIN_CSV)
        rr = parse_garmin_csv(str(f))
        assert isinstance(rr, RRSeries)


# ======================
# extract_training_session_garmin
# ======================


class TestExtractTrainingSessionGarmin:
    """Tests for extract_training_session_garmin()."""

    @pytest.fixture(autouse=True)
    def _fitparse_available(self):
        with patch("cardiolab.sensors_tools.garmin._FITPARSE_AVAILABLE", True):
            yield

    def test_returns_dict(self, tmp_path):
        """Returns a dict with the three expected keys."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = _make_training_fitfile()
            result = extract_training_session_garmin(fit_file)

        assert set(result.keys()) == {"duration_min", "hr_mean", "hr_max"}

    def test_hr_mean_computed(self, tmp_path):
        """hr_mean is the mean of all recorded HR values."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = _make_training_fitfile()
            result = extract_training_session_garmin(fit_file)

        expected_mean = sum(_HR_SAMPLES) / len(_HR_SAMPLES)
        assert result["hr_mean"] == pytest.approx(expected_mean, abs=0.1)

    def test_hr_max_computed(self, tmp_path):
        """hr_max is the maximum HR value."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = _make_training_fitfile()
            result = extract_training_session_garmin(fit_file)

        assert result["hr_max"] == max(_HR_SAMPLES)

    def test_duration_computed(self, tmp_path):
        """duration_min is derived from first and last timestamps."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = _make_training_fitfile()
            result = extract_training_session_garmin(fit_file)

        # 8 samples × 5 s apart = 35 s total = 35/60 min
        expected_min = (len(_HR_SAMPLES) - 1) * 5 / 60.0
        assert result["duration_min"] == pytest.approx(expected_min, abs=0.01)

    def test_file_not_found(self, tmp_path):
        """Raises FileNotFoundError for a missing file."""
        with (
            patch("cardiolab.sensors_tools.garmin._fitparse"),
            pytest.raises(FileNotFoundError),
        ):
            extract_training_session_garmin(tmp_path / "missing.fit")

    def test_no_hr_data_raises(self, tmp_path):
        """Raises ValueError when the FIT file has no heart rate records."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        empty_fitfile = MagicMock()
        empty_fitfile.get_messages.return_value = iter([])

        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = empty_fitfile
            with pytest.raises(ValueError, match="No heart rate data"):
                extract_training_session_garmin(fit_file)

    def test_fitparse_not_available_raises(self, tmp_path):
        """Raises ImportError when fitparse is not installed."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        with (
            patch("cardiolab.sensors_tools.garmin._FITPARSE_AVAILABLE", False),
            pytest.raises(ImportError, match="fitparse"),
        ):
            extract_training_session_garmin(fit_file)


# ======================
# _require_fitparse
# ======================


class TestRequireFitparse:
    """Tests for the internal _require_fitparse guard."""

    def test_raises_when_unavailable(self):
        """Raises ImportError with install hint when fitparse is missing."""
        with (
            patch("cardiolab.sensors_tools.garmin._FITPARSE_AVAILABLE", False),
            pytest.raises(ImportError, match="cardiolab\\[garmin\\]"),
        ):
            _require_fitparse()

    def test_passes_when_available(self):
        """Does not raise when fitparse is available."""
        with patch("cardiolab.sensors_tools.garmin._FITPARSE_AVAILABLE", True):
            _require_fitparse()  # must not raise
