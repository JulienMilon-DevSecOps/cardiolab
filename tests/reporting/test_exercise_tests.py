"""Tests for the v0.6.0 exercise-test tables and exports."""

from __future__ import annotations

import csv
import json
from contextlib import nullcontext

import numpy as np
import pandas as pd
import pytest

from cardiolab.io import (
    dfa_thresholds_to_csv,
    dfa_thresholds_to_json,
    lsct_to_csv,
    lsct_to_json,
)
from cardiolab.labels import LABELS_FR
from cardiolab.protocols.dfa_thresholds import ThresholdRecord, dfa_thresholds
from cardiolab.protocols.lsct import lsct
from cardiolab.reporting import table_dfa_thresholds_history, table_lsct_history
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries
from tests.protocols.test_dfa_thresholds import _power, _ramp_test
from tests.protocols.test_lsct import HR_MAX, _session


@pytest.fixture(scope="module")
def records():
    """Return a DFA test and a manual entry."""
    result = dfa_thresholds(
        RRSeries(_ramp_test(minutes=16)), intensity=_power(16), intensity_unit="W"
    )
    return [
        ThresholdRecord.from_result(result, "2099-10-01", sport="cycling"),
        ThresholdRecord.manual("2099-11-01", 146, 169, sport="cycling"),
    ]


def _lsct(powers, pct3=90, rpe=(3, 5, 7), date="2099-11-01"):
    t, hr, pw = _session(powers=powers, pcts=(60, 80, pct3))
    ctx = pytest.warns(PhysiologicalWarning) if pct3 < 90 else nullcontext()
    with ctx:
        return lsct(t, hr, pw, HR_MAX, start_sec=300.0, rpe=rpe, date=date)


@pytest.fixture(scope="module")
def tests_history():
    """Return four weekly LSCTs: reference, reference, better, fatigued."""
    return [
        _lsct((120, 220, 280), date="2099-11-01"),
        _lsct((120, 222, 282), date="2099-11-08"),
        _lsct((130, 238, 302), date="2099-11-15"),
        _lsct((110, 205, 262), date="2099-11-22"),
    ]


@pytest.mark.unit
class TestThresholdsTable:
    """``table_dfa_thresholds_history``."""

    def test_one_row_per_record(self, records):
        """Rows, statuses kept as codes, displayed translated."""
        styler = table_dfa_thresholds_history(records, labels=LABELS_FR)
        assert isinstance(styler, pd.io.formats.style.Styler)
        assert list(styler.data["source"]) == ["dfa", "manual"]
        assert "Détecté" in styler.to_html()

    def test_validation(self):
        """Empty list or wrong item type."""
        with pytest.raises(ValueError):
            table_dfa_thresholds_history([])
        with pytest.raises(TypeError):
            table_dfa_thresholds_history([object()])


@pytest.mark.unit
class TestLsctTable:
    """``table_lsct_history`` — each test against the previous ones."""

    def test_interpretation_per_test(self, tests_history):
        """First test without reference, then stable, improving, fatigue."""
        df = table_lsct_history(tests_history).data
        assert list(df["interpretation"]) == [
            "",
            "stable",
            "improving",
            "fatigue_possible",
        ]
        assert np.isnan(df["power_change_pct"][0])

    def test_translated_display(self, tests_history):
        """Interpretation shown with the French label."""
        html = table_lsct_history(tests_history, labels=LABELS_FR).to_html()
        assert "En progrès" in html

    def test_validation(self):
        """Empty list or wrong item type."""
        with pytest.raises(ValueError):
            table_lsct_history([])
        with pytest.raises(TypeError):
            table_lsct_history([object()])


@pytest.mark.unit
class TestExports:
    """CSV and JSON exports."""

    def test_thresholds_csv_json(self, records, tmp_path):
        """One row per record, quality reduced to its grade."""
        dfa_thresholds_to_csv(records, tmp_path / "t.csv")
        rows = list(csv.DictReader((tmp_path / "t.csv").open()))
        assert [r["source"] for r in rows] == ["dfa", "manual"]
        dfa_thresholds_to_json(records[0], tmp_path / "t.json")
        data = json.loads((tmp_path / "t.json").read_text())
        assert data[0]["quality"] in ("good", "acceptable", "poor")

    def test_lsct_csv_json(self, tests_history, tmp_path):
        """Flat columns per stage."""
        lsct_to_csv(tests_history, tmp_path / "l.csv")
        rows = list(csv.DictReader((tmp_path / "l.csv").open()))
        assert len(rows) == 4
        assert "stage3_power" in rows[0]
        lsct_to_json(tests_history[0], tmp_path / "l.json")
        assert json.loads((tmp_path / "l.json").read_text())[0]["stage2_rpe"] == 5
