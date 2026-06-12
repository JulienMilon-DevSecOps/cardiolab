"""Unit tests for the HRV4Training CSV parser."""

from __future__ import annotations

import pytest

from cardiolab.sensors_tools.hrv4training import (
    _find_col,
    parse_hrv4training_csv,
    to_rrseries,
)
from cardiolab.signals.rr import RRSeries

# ======================
# FIXTURES
# ======================

# Fixture CSV : ligne 1 complète (avec RR), ligne 2 sans RR, ligne 3 date vide
HRV4T_CSV_FULL = """\
date,rMSSD,resting HR,RR intervals
2026-01-10,55.2,56,800;810;795;820;805;790;815
2026-01-11,48.3,58,
2026-01-12,,60,830;840;825
,50.0,57,810;800
"""

# Export summary uniquement (pas de colonne RR intervals)
HRV4T_CSV_SUMMARY = """\
date,rMSSD,resting HR
2026-02-01,60.1,54
2026-02-02,52.4,57
"""

# CSV sans colonne date
HRV4T_CSV_NO_DATE = """\
rMSSD,resting HR
55.2,56
"""

# CSV vide
HRV4T_CSV_EMPTY = ""


# ======================
# parse_hrv4training_csv
# ======================


class TestParseHrv4trainingCsv:
    """Tests for parse_hrv4training_csv()."""

    def test_returns_list(self, tmp_path):
        """Returns a list even for a minimal CSV."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_FULL)
        result = parse_hrv4training_csv(f)
        assert isinstance(result, list)

    def test_skips_empty_date_rows(self, tmp_path):
        """Rows with an empty date are skipped."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_FULL)
        result = parse_hrv4training_csv(f)
        # ligne 1 (complète), ligne 2 (sans RR), ligne 3 (rmssd vide) → 3 valides
        # ligne 4 (date vide) → ignorée
        assert len(result) == 3

    def test_record_keys(self, tmp_path):
        """Each record has the three expected keys."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_FULL)
        result = parse_hrv4training_csv(f)
        for record in result:
            assert set(record.keys()) == {"date", "rmssd", "rr_intervals"}

    def test_rr_intervals_parsed(self, tmp_path):
        """RR intervals are parsed into a list of floats."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_FULL)
        records = parse_hrv4training_csv(f)
        first = records[0]
        assert first["rr_intervals"] is not None
        assert all(isinstance(v, float) for v in first["rr_intervals"])
        assert len(first["rr_intervals"]) == 7

    def test_missing_rr_column_gives_none(self, tmp_path):
        """Records from a summary-only CSV have rr_intervals = None."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_SUMMARY)
        records = parse_hrv4training_csv(f)
        assert all(r["rr_intervals"] is None for r in records)

    def test_empty_rr_cell_gives_none(self, tmp_path):
        """A row with an empty RR cell produces rr_intervals = None."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_FULL)
        records = parse_hrv4training_csv(f)
        second = records[1]  # ligne 2 : RR intervals vide
        assert second["rr_intervals"] is None

    def test_rmssd_parsed_as_float(self, tmp_path):
        """Rmssd is parsed as a float when the column exists."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_FULL)
        records = parse_hrv4training_csv(f)
        assert records[0]["rmssd"] == pytest.approx(55.2)

    def test_missing_rmssd_gives_none(self, tmp_path):
        """A row with an empty rmssd cell produces rmssd = None."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_FULL)
        records = parse_hrv4training_csv(f)
        third = records[2]  # ligne 3 : rmssd vide
        assert third["rmssd"] is None

    def test_summary_rmssd_parsed(self, tmp_path):
        """Summary-only CSV has correct rmssd values."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_SUMMARY)
        records = parse_hrv4training_csv(f)
        assert records[0]["rmssd"] == pytest.approx(60.1)
        assert records[1]["rmssd"] == pytest.approx(52.4)

    def test_accepts_string_path(self, tmp_path):
        """Accepts a string path as well as a Path object."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_SUMMARY)
        result = parse_hrv4training_csv(str(f))
        assert isinstance(result, list)

    def test_file_not_found(self, tmp_path):
        """Raises FileNotFoundError for a missing file."""
        with pytest.raises(FileNotFoundError):
            parse_hrv4training_csv(tmp_path / "missing.csv")

    def test_no_date_column_raises(self, tmp_path):
        """Raises ValueError when no 'date' column is found."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_NO_DATE)
        with pytest.raises(ValueError, match="No 'date' column"):
            parse_hrv4training_csv(f)

    def test_empty_file_raises(self, tmp_path):
        """Raises ValueError for an empty file."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_EMPTY)
        with pytest.raises(ValueError):
            parse_hrv4training_csv(f)

    def test_rr_negative_values_filtered(self, tmp_path):
        """Negative and zero RR values in the semicolon list are filtered out."""
        content = "date,rMSSD,RR intervals\n2026-01-01,50.0,800;-10;0;810\n"
        f = tmp_path / "hrv.csv"
        f.write_text(content)
        records = parse_hrv4training_csv(f)
        assert records[0]["rr_intervals"] == [800.0, 810.0]


# ======================
# to_rrseries
# ======================


class TestToRrseries:
    """Tests for to_rrseries()."""

    def test_returns_rrseries(self):
        """Returns a valid RRSeries from a complete record."""
        record = {
            "date": "2026-01-10",
            "rmssd": 55.2,
            "rr_intervals": [800.0, 810.0, 795.0],
        }
        rr = to_rrseries(record)
        assert isinstance(rr, RRSeries)

    def test_rrseries_length(self):
        """RRSeries length matches the number of RR intervals."""
        record = {
            "date": "2026-01-10",
            "rmssd": 55.2,
            "rr_intervals": [800.0, 810.0, 795.0, 820.0],
        }
        rr = to_rrseries(record)
        assert len(rr) == 4

    def test_raises_when_no_rr(self):
        """Raises ValueError when rr_intervals is None."""
        record = {"date": "2026-01-11", "rmssd": 48.3, "rr_intervals": None}
        with pytest.raises(ValueError, match="No RR intervals"):
            to_rrseries(record)

    def test_raises_when_rr_empty_list(self):
        """Raises ValueError when rr_intervals is an empty list."""
        record = {"date": "2026-01-11", "rmssd": 48.3, "rr_intervals": []}
        with pytest.raises(ValueError, match="No RR intervals"):
            to_rrseries(record)

    def test_integration_parse_then_convert(self, tmp_path):
        """Full workflow: parse CSV → to_rrseries on first complete record."""
        f = tmp_path / "hrv.csv"
        f.write_text(HRV4T_CSV_FULL)
        records = parse_hrv4training_csv(f)
        complete = next(r for r in records if r["rr_intervals"])
        rr = to_rrseries(complete)
        assert len(rr) > 0


# ======================
# _find_col (helper)
# ======================


class TestFindCol:
    """Tests for the internal _find_col helper."""

    def test_finds_exact_match(self):
        """Returns the original name for an exact lowercase match."""
        fields = {"date": "date", "rmssd": "rMSSD"}
        assert _find_col(fields, ["rmssd"]) == "rMSSD"

    def test_returns_none_when_missing(self):
        """Returns None when no candidate matches."""
        fields = {"date": "date"}
        assert _find_col(fields, ["rmssd", "rmssd recording"]) is None

    def test_first_candidate_wins(self):
        """Returns the first matching candidate."""
        fields = {"rmssd": "rMSSD", "rmssd recording": "rMSSD Recording"}
        assert _find_col(fields, ["rmssd", "rmssd recording"]) == "rMSSD"
