"""Unit tests for the Garmin FIT and CSV parsers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cardiolab.sensors_tools.garmin import (
    FitRecords,
    _require_fitparse,
    extract_training_session_garmin,
    parse_fit_records,
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


def _make_training_fitfile(session=None, sport_msg=None):
    """Return a mock FitFile with record messages (training session).

    ``session`` / ``sport_msg``: optional ``(sport, sub_sport)`` tuples for the
    FIT ``session`` and ``sport`` messages.
    """

    def _make_record(hr, ts):
        rec = MagicMock()
        rec.get_value.side_effect = lambda field: (
            hr if field == "heart_rate" else ts if field == "timestamp" else None
        )
        return rec

    records = [
        _make_record(hr, ts) for hr, ts in zip(_HR_SAMPLES, _TIMESTAMPS, strict=False)
    ]

    def _make_sport_msg(values):
        sport, sub_sport = values
        msg = MagicMock()
        msg.get_value.side_effect = lambda field: (
            sport if field == "sport" else sub_sport if field == "sub_sport" else None
        )
        return msg

    messages = {
        "record": records,
        "session": [_make_sport_msg(session)] if session else [],
        "sport": [_make_sport_msg(sport_msg)] if sport_msg else [],
    }
    fitfile = MagicMock()
    fitfile.get_messages.side_effect = lambda name: iter(messages.get(name, []))
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
        """Returns a dict with the expected keys (sport fields added in v0.3.4)."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = _make_training_fitfile()
            result = extract_training_session_garmin(fit_file)

        assert set(result.keys()) == {
            "duration_min",
            "hr_mean",
            "hr_max",
            "power_mean",
            "power_max",
            "sport",
            "sport_raw",
        }

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

    def test_no_records_raises(self, tmp_path):
        """Raises ValueError when the FIT file has no record message."""
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")

        empty_fitfile = MagicMock()
        empty_fitfile.get_messages.return_value = iter([])

        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = empty_fitfile
            with pytest.raises(ValueError, match="No timestamped record"):
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


class TestExtractTrainingSessionGarminSport:
    """Sport read from the FIT session / sport messages (v0.3.4)."""

    @pytest.fixture(autouse=True)
    def _fitparse_available(self):
        with patch("cardiolab.sensors_tools.garmin._FITPARSE_AVAILABLE", True):
            yield

    def _extract(self, tmp_path, **messages):
        fit_file = tmp_path / "activity.fit"
        fit_file.write_bytes(b"")
        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = _make_training_fitfile(**messages)
            return extract_training_session_garmin(fit_file)

    @pytest.mark.parametrize(
        ("session", "expected"),
        [
            (("running", "generic"), "running"),
            (("running", "trail"), "trail"),
            (("cycling", "mountain"), "mountain_bike"),
            (("swimming", "lap_swimming"), "swimming"),
            (("training", "strength_training"), "strength"),
            (("soccer", None), "football"),
        ],
    )
    def test_sport_from_session_message(self, tmp_path, session, expected):
        """FIT sport + sub-sport are normalised to a reference code."""
        result = self._extract(tmp_path, session=session)
        assert result["sport"] == expected
        assert result["sport_raw"] == session[0]

    def test_falls_back_to_sport_message(self, tmp_path):
        """Without a session sport, the sport message is used."""
        result = self._extract(tmp_path, sport_msg=("cycling", "road"))
        assert result["sport"] == "cycling"

    def test_session_message_takes_priority(self, tmp_path):
        """The session message wins over the sport message."""
        result = self._extract(
            tmp_path, session=("running", "trail"), sport_msg=("cycling", None)
        )
        assert result["sport"] == "trail"

    def test_no_sport_gives_other(self, tmp_path):
        """A file without sport information gives "other" and no error."""
        result = self._extract(tmp_path)
        assert result["sport"] == "other"
        assert result["sport_raw"] is None

    def test_unknown_sport_gives_other(self, tmp_path):
        """An unknown FIT sport value gives "other", raw value kept."""
        result = self._extract(tmp_path, session=("kitesurfing", None))
        assert result["sport"] == "other"
        assert result["sport_raw"] == "kitesurfing"


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


# ======================
# parse_fit_records — per-second samples (power, HR, cadence, speed)
# ======================


def _make_records_fitfile(rows, session=("cycling", "virtual_activity")):
    """Return a mock FitFile whose records carry the given field dicts."""

    def _record(values):
        rec = MagicMock()
        rec.get_value.side_effect = values.get
        return rec

    def _sport(values):
        msg = MagicMock()
        msg.get_value.side_effect = {"sport": values[0], "sub_sport": values[1]}.get
        return msg

    messages = {
        "record": [_record(r) for r in rows],
        "session": [_sport(session)] if session else [],
    }
    fitfile = MagicMock()
    fitfile.get_messages.side_effect = lambda name: iter(messages.get(name, []))
    return fitfile


def _indoor_rows(n=6, hr=True):
    """Indoor-trainer records at 1 Hz: power, cadence, speed, optional HR."""
    rows = []
    for i in range(n):
        row = {
            "timestamp": _T0 + timedelta(seconds=i),
            "power": 150 + 10 * i,
            "cadence": 85,
            "speed": 8.0,
        }
        if hr:
            row["heart_rate"] = 120 + i
        rows.append(row)
    return rows


class TestParseFitRecords:
    """parse_fit_records() — the per-second samples of any FIT activity."""

    @pytest.fixture(autouse=True)
    def _fitparse_available(self):
        with patch("cardiolab.sensors_tools.garmin._FITPARSE_AVAILABLE", True):
            yield

    def _parse(self, tmp_path, rows, **kwargs):
        fit_file = tmp_path / "ride.fit"
        fit_file.write_bytes(b"")
        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = _make_records_fitfile(rows, **kwargs)
            return parse_fit_records(fit_file)

    def test_series_and_time(self, tmp_path):
        """One value per record, time in seconds from the first record."""
        rec = self._parse(tmp_path, _indoor_rows())
        assert isinstance(rec, FitRecords)
        assert rec.start == _T0
        assert list(rec.time_sec) == [0, 1, 2, 3, 4, 5]
        assert list(rec.power) == [150, 160, 170, 180, 190, 200]
        assert list(rec.heart_rate) == [120, 121, 122, 123, 124, 125]
        assert rec.duration_sec == 5.0
        assert rec.sport == "cycling"

    def test_heart_rate_zero_is_missing(self, tmp_path):
        """A heart rate of 0 is a drop-out (nan); a power of 0 is kept."""
        rows = _indoor_rows()
        rows[2]["heart_rate"] = 0
        rows[3]["power"] = 0
        rec = self._parse(tmp_path, rows)
        assert np.isnan(rec.heart_rate[2])
        assert rec.power[3] == 0

    def test_missing_field_is_nan(self, tmp_path):
        """Without heart rate (indoor app only): nan series, has() is False."""
        rec = self._parse(tmp_path, _indoor_rows(hr=False))
        assert not rec.has("heart_rate")
        assert rec.has("power")
        assert np.all(np.isnan(rec.heart_rate))

    def test_enhanced_speed_preferred(self, tmp_path):
        """enhanced_speed is used when present."""
        rows = _indoor_rows()
        for r in rows:
            r["enhanced_speed"] = 9.5
        rec = self._parse(tmp_path, rows)
        assert np.all(rec.speed == 9.5)

    def test_records_without_timestamp_skipped(self, tmp_path):
        """Records without timestamp are left out."""
        rows = _indoor_rows()
        rows.insert(1, {"power": 999})
        rec = self._parse(tmp_path, rows)
        assert 999 not in rec.power
        assert len(rec.power) == 6

    def test_intensity_for_dfa_thresholds(self, tmp_path):
        """intensity() gives (time_sec, values) without missing samples."""
        rows = _indoor_rows()
        del rows[4]["power"]
        t, v = self._parse(tmp_path, rows).intensity("power")
        assert list(t) == [0, 1, 2, 3, 5]
        assert list(v) == [150, 160, 170, 180, 200]

    def test_intensity_errors(self, tmp_path):
        """Unknown field or field never recorded: ValueError."""
        rec = self._parse(tmp_path, _indoor_rows(hr=False))
        with pytest.raises(ValueError, match="Unknown"):
            rec.intensity("altitude")
        with pytest.raises(ValueError, match="No heart_rate"):
            rec.intensity("heart_rate")

    def test_no_records_raises(self, tmp_path):
        """A file without timestamped records is refused."""
        with pytest.raises(ValueError, match="No timestamped record"):
            self._parse(tmp_path, [])

    def test_file_not_found(self, tmp_path):
        """Missing file: FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_fit_records(tmp_path / "missing.fit")


class TestExtractTrainingSessionWithoutHeartRate:
    """extract_training_session_garmin() on indoor files (since 0.6.0)."""

    @pytest.fixture(autouse=True)
    def _fitparse_available(self):
        with patch("cardiolab.sensors_tools.garmin._FITPARSE_AVAILABLE", True):
            yield

    def _extract(self, tmp_path, rows):
        fit_file = tmp_path / "ride.fit"
        fit_file.write_bytes(b"")
        with patch("cardiolab.sensors_tools.garmin._fitparse") as mock_fp:
            mock_fp.FitFile.return_value = _make_records_fitfile(rows)
            return extract_training_session_garmin(fit_file)

    def test_without_heart_rate(self, tmp_path):
        """Power only: hr_mean / hr_max are None, the session is still read."""
        res = self._extract(tmp_path, _indoor_rows(hr=False))
        assert res["hr_mean"] is None
        assert res["hr_max"] is None
        assert res["power_mean"] == pytest.approx(175.0)
        assert res["power_max"] == 200.0
        assert res["sport"] == "cycling"

    def test_heart_rate_dropouts_ignored(self, tmp_path):
        """Heart rate values of 0 do not lower the mean."""
        rows = _indoor_rows()
        rows[0]["heart_rate"] = 0
        res = self._extract(tmp_path, rows)
        assert res["hr_mean"] == pytest.approx(123.0)
