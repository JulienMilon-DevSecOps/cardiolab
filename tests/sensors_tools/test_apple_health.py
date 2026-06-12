"""Unit tests for the Apple Health XML parser."""

from __future__ import annotations

import pytest

from cardiolab.sensors_tools.apple_health import (
    extract_hrv_samples,
    parse_apple_health_export,
)

# ======================
# FIXTURES XML
# ======================

# Export minimal avec 2 jours : 3 mesures SDNN + 1 resting HR + 1 type ignoré
HEALTH_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="fr_FR">
  <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
          sourceName="Apple Watch de Julien"
          unit="ms"
          startDate="2026-01-10 07:30:00 +0100"
          endDate="2026-01-10 07:30:00 +0100"
          value="45.2"/>
  <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
          sourceName="Apple Watch de Julien"
          unit="ms"
          startDate="2026-01-10 20:00:00 +0100"
          endDate="2026-01-10 20:00:00 +0100"
          value="51.0"/>
  <Record type="HKQuantityTypeIdentifierRestingHeartRate"
          sourceName="Apple Watch de Julien"
          unit="count/min"
          startDate="2026-01-10 07:30:00 +0100"
          endDate="2026-01-10 07:30:00 +0100"
          value="56"/>
  <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
          sourceName="Apple Watch de Julien"
          unit="ms"
          startDate="2026-01-11 07:15:00 +0100"
          endDate="2026-01-11 07:15:00 +0100"
          value="52.8"/>
  <Record type="HKQuantityTypeIdentifierStepCount"
          sourceName="iPhone"
          unit="count"
          startDate="2026-01-10 08:00:00 +0100"
          endDate="2026-01-10 09:00:00 +0100"
          value="1200"/>
</HealthData>
"""

# XML avec racine incorrecte
BAD_ROOT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<NotHealthData>
  <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN" value="45"/>
</NotHealthData>
"""

# XML invalide (malformé)
MALFORMED_XML = "<?xml version='1.0'?><HealthData><Record unclosed"

# Export vide (aucun Record)
EMPTY_EXPORT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="fr_FR">
</HealthData>
"""

# Record avec value non numérique
BAD_VALUE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="fr_FR">
  <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
          sourceName="Watch"
          startDate="2026-01-10 07:30:00 +0100"
          endDate="2026-01-10 07:30:00 +0100"
          value="N/A"/>
  <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
          sourceName="Watch"
          startDate="2026-01-10 08:00:00 +0100"
          endDate="2026-01-10 08:00:00 +0100"
          value="48.0"/>
</HealthData>
"""


# ======================
# parse_apple_health_export
# ======================


class TestParseAppleHealthExport:
    """Tests for parse_apple_health_export()."""

    def test_returns_list(self, tmp_path):
        """Returns a list for a valid export."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = parse_apple_health_export(f)
        assert isinstance(result, list)

    def test_ignores_non_hrv_records(self, tmp_path):
        """StepCount and other record types are ignored."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = parse_apple_health_export(f)
        # 2 SDNN (10 jan) + 1 resting HR (10 jan) + 1 SDNN (11 jan) = 4 records
        assert len(result) == 4

    def test_record_keys(self, tmp_path):
        """Every record has the five expected keys."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = parse_apple_health_export(f)
        for rec in result:
            assert set(rec.keys()) == {"date", "sdnn", "rmssd", "resting_hr", "source"}

    def test_sdnn_records_have_sdnn(self, tmp_path):
        """SDNN records carry a float sdnn and None resting_hr."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        sdnn_recs = [r for r in parse_apple_health_export(f) if r["sdnn"] is not None]
        assert len(sdnn_recs) == 3
        for rec in sdnn_recs:
            assert isinstance(rec["sdnn"], float)
            assert rec["resting_hr"] is None

    def test_resting_hr_records(self, tmp_path):
        """Resting HR records carry a float resting_hr and None sdnn."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        hr_recs = [
            r for r in parse_apple_health_export(f) if r["resting_hr"] is not None
        ]
        assert len(hr_recs) == 1
        assert hr_recs[0]["resting_hr"] == pytest.approx(56.0)
        assert hr_recs[0]["sdnn"] is None

    def test_rmssd_always_none(self, tmp_path):
        """Rmssd is always None — not available in standard exports."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = parse_apple_health_export(f)
        assert all(r["rmssd"] is None for r in result)

    def test_date_extracted_from_startdate(self, tmp_path):
        """Date is the YYYY-MM-DD portion of startDate."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        dates = {r["date"] for r in parse_apple_health_export(f)}
        assert "2026-01-10" in dates
        assert "2026-01-11" in dates

    def test_source_name_preserved(self, tmp_path):
        """SourceName attribute is stored in the 'source' key."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = parse_apple_health_export(f)
        assert all(r["source"] == "Apple Watch de Julien" for r in result)

    def test_skips_invalid_value(self, tmp_path):
        """Records with non-numeric value are silently skipped."""
        f = tmp_path / "export.xml"
        f.write_text(BAD_VALUE_XML)
        result = parse_apple_health_export(f)
        # Only the valid record (48.0) survives
        assert len(result) == 1
        assert result[0]["sdnn"] == pytest.approx(48.0)

    def test_empty_export_returns_empty_list(self, tmp_path):
        """An export with no HRV records returns an empty list."""
        f = tmp_path / "export.xml"
        f.write_text(EMPTY_EXPORT_XML)
        result = parse_apple_health_export(f)
        assert result == []

    def test_accepts_string_path(self, tmp_path):
        """Accepts a string path as well as a Path object."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = parse_apple_health_export(str(f))
        assert isinstance(result, list)

    def test_file_not_found(self, tmp_path):
        """Raises FileNotFoundError for a missing file."""
        with pytest.raises(FileNotFoundError):
            parse_apple_health_export(tmp_path / "missing.xml")

    def test_malformed_xml_raises(self, tmp_path):
        """Raises ValueError for a malformed XML file."""
        f = tmp_path / "export.xml"
        f.write_text(MALFORMED_XML)
        with pytest.raises(ValueError, match="Cannot parse XML"):
            parse_apple_health_export(f)

    def test_wrong_root_raises(self, tmp_path):
        """Raises ValueError when the root element is not <HealthData>."""
        f = tmp_path / "export.xml"
        f.write_text(BAD_ROOT_XML)
        with pytest.raises(ValueError, match="HealthData"):
            parse_apple_health_export(f)


# ======================
# extract_hrv_samples
# ======================


class TestExtractHrvSamples:
    """Tests for extract_hrv_samples()."""

    def test_returns_list(self, tmp_path):
        """Returns a list of dicts."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = extract_hrv_samples(f)
        assert isinstance(result, list)

    def test_one_entry_per_day(self, tmp_path):
        """Returns exactly one entry per calendar day."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = extract_hrv_samples(f)
        dates = [r["date"] for r in result]
        assert len(dates) == len(set(dates))
        assert set(dates) == {"2026-01-10", "2026-01-11"}

    def test_record_keys(self, tmp_path):
        """Each entry has exactly date, sdnn, rmssd."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = extract_hrv_samples(f)
        for rec in result:
            assert set(rec.keys()) == {"date", "sdnn", "rmssd"}

    def test_sdnn_averaged_per_day(self, tmp_path):
        """SDNN is the mean of all measurements for the day."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = extract_hrv_samples(f)
        day10 = next(r for r in result if r["date"] == "2026-01-10")
        # 45.2 + 51.0 → mean = 48.1
        assert day10["sdnn"] == pytest.approx((45.2 + 51.0) / 2)

    def test_single_sdnn_unchanged(self, tmp_path):
        """A day with one measurement returns that value directly."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = extract_hrv_samples(f)
        day11 = next(r for r in result if r["date"] == "2026-01-11")
        assert day11["sdnn"] == pytest.approx(52.8)

    def test_rmssd_always_none(self, tmp_path):
        """Rmssd is always None (Apple Health limitation)."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = extract_hrv_samples(f)
        assert all(r["rmssd"] is None for r in result)

    def test_sorted_by_date(self, tmp_path):
        """Entries are sorted in ascending date order."""
        f = tmp_path / "export.xml"
        f.write_text(HEALTH_XML)
        result = extract_hrv_samples(f)
        dates = [r["date"] for r in result]
        assert dates == sorted(dates)

    def test_empty_export_returns_empty_list(self, tmp_path):
        """An export with no HRV records returns an empty list."""
        f = tmp_path / "export.xml"
        f.write_text(EMPTY_EXPORT_XML)
        result = extract_hrv_samples(f)
        assert result == []

    def test_file_not_found(self, tmp_path):
        """Raises FileNotFoundError for a missing file."""
        with pytest.raises(FileNotFoundError):
            extract_hrv_samples(tmp_path / "missing.xml")
