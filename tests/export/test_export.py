"""Tests for the cardiolab.io export functions and to_dataframe() methods."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

pandas = pytest.importorskip("pandas")  # skip entire module if pandas absent

from cardiolab.analytics.baseline import Baseline  # noqa: E402
from cardiolab.io.export import (  # noqa: E402
    features_to_csv,
    features_to_json,
    orthostatic_to_csv,
    orthostatic_to_json,
)
from cardiolab.protocols.orthostatic import (  # noqa: E402
    orthostatic_hrv,
)
from cardiolab.protocols.resting import HRVFeatures  # noqa: E402
from cardiolab.signals.rr import RRSeries  # noqa: E402

# ======================
# SHARED HELPERS
# ======================

_HRV_FIELD_COUNT = 22  # matches HRVFeatures field count (date + 19 metrics + duration + score)


def _make_features(**kw) -> HRVFeatures:
    """Return a fully-populated HRVFeatures for testing."""
    defaults = dict(
        date="2026-05-18",
        rmssd=60.0,
        ln_rmssd=4.09,
        sdnn=80.0,
        pnn50=25.0,
        mean_hr=70.0,
        vlf=500.0,
        lf=1500.0,
        hf=2000.0,
        lf_hf=0.75,
        hf_pct=0.4,
        lf_nu=0.4,
        hf_nu=0.6,
        hf_hr=2000.0 / 70.0,
        sd1=42.43,
        sd2=104.88,
        sd_ratio=0.40,
        dfa_alpha1=1.0,
        duration=300.0,
        score=75.0,
    )
    defaults.update(kw)
    return HRVFeatures(**defaults)


def _make_ortho_rr(
    supine_bpm: float = 65.0,
    standing_bpm: float = 85.0,
    supine_sec: float = 310.0,
    standing_sec: float = 310.0,
    rng_seed: int = 42,
) -> RRSeries:
    """Return a synthetic RR series spanning a postural change."""
    rng = np.random.default_rng(rng_seed)
    supine_rr = 60000.0 / supine_bpm
    n_sup = int(supine_sec / (supine_rr / 1000.0))
    supine = rng.normal(supine_rr, 20.0, n_sup).clip(300, 2000)

    standing_rr = 60000.0 / standing_bpm
    n_sta = int(standing_sec / (standing_rr / 1000.0))
    standing = rng.normal(standing_rr, 15.0, n_sta).clip(300, 2000)

    n_trans = 40
    trans = np.linspace(supine_rr, standing_rr, n_trans) + rng.normal(0, 10, n_trans)
    return RRSeries(np.concatenate([supine, trans, standing]).clip(300, 2000))


@pytest.fixture
def single_features():
    """Return a single HRVFeatures instance."""
    return _make_features()


@pytest.fixture
def features_list():
    """Return a list of 3 HRVFeatures sessions."""
    return [
        _make_features(date=f"2026-05-{16 + i:02d}", rmssd=55.0 + i * 5)
        for i in range(3)
    ]


@pytest.fixture
def baseline_with_history(features_list):
    """Return a Baseline built from features_list."""
    return Baseline(history=features_list)


@pytest.fixture
def ortho_result():
    """Return a real OrthostaticResult from synthetic data."""
    rr = _make_ortho_rr()
    return orthostatic_hrv(rr, min_phase_duration=60.0)


# ======================
# HRVFeatures.to_dataframe()
# ======================


class TestHRVFeaturesToDataframe:
    """Tests for HRVFeatures.to_dataframe()."""

    def test_returns_dataframe(self, single_features):
        """to_dataframe() must return a pandas DataFrame."""
        df = single_features.to_dataframe()
        assert isinstance(df, pandas.DataFrame)

    def test_one_row(self, single_features):
        """to_dataframe() must produce exactly one row."""
        df = single_features.to_dataframe()
        assert len(df) == 1

    def test_column_count(self, single_features):
        """Column count must match the number of HRVFeatures fields."""
        df = single_features.to_dataframe()
        assert len(df.columns) == _HRV_FIELD_COUNT

    def test_column_names_match_to_dict(self, single_features):
        """Column names must be the same keys as to_dict()."""
        df = single_features.to_dataframe()
        assert list(df.columns) == list(single_features.to_dict().keys())

    def test_values_match_to_dict(self, single_features):
        """Numeric values in the DataFrame must match to_dict()."""
        df = single_features.to_dataframe()
        d = single_features.to_dict()
        assert df["rmssd"].iloc[0] == pytest.approx(d["rmssd"])
        assert df["dfa_alpha1"].iloc[0] == pytest.approx(d["dfa_alpha1"])
        assert df["date"].iloc[0] == d["date"]

    def test_nan_dfa_alpha1_preserved(self):
        """NaN in dfa_alpha1 must survive round-trip through DataFrame."""
        f = _make_features(dfa_alpha1=float("nan"))
        df = f.to_dataframe()
        assert math.isnan(df["dfa_alpha1"].iloc[0])


# ======================
# Baseline.to_dataframe()
# ======================


class TestBaselineToDataframe:
    """Tests for Baseline.to_dataframe()."""

    def test_returns_dataframe(self, baseline_with_history):
        """to_dataframe() must return a pandas DataFrame."""
        df = baseline_with_history.to_dataframe()
        assert isinstance(df, pandas.DataFrame)

    def test_row_count_equals_history_length(self, baseline_with_history):
        """Number of rows must equal the number of sessions in history."""
        df = baseline_with_history.to_dataframe()
        assert len(df) == len(baseline_with_history.history)

    def test_column_names(self, baseline_with_history):
        """Columns must match HRVFeatures.to_dict() keys."""
        df = baseline_with_history.to_dataframe()
        expected = list(HRVFeatures().to_dict().keys())
        assert list(df.columns) == expected

    def test_empty_history_returns_empty_dataframe(self):
        """to_dataframe() must return an empty DataFrame for empty history."""
        df = Baseline(history=[]).to_dataframe()
        assert isinstance(df, pandas.DataFrame)
        assert len(df) == 0

    def test_values_are_correct(self, features_list, baseline_with_history):
        """RMSSD column must match the history order."""
        df = baseline_with_history.to_dataframe()
        expected_rmssds = [f.rmssd for f in features_list]
        assert list(df["rmssd"]) == pytest.approx(expected_rmssds)


# ======================
# OrthostaticResult.to_dict() (nested, recursive)
# ======================


class TestOrthostaticResultToDict:
    """Tests for OrthostaticResult.to_dict() — recursive nested structure."""

    def test_returns_dict(self, ortho_result):
        """to_dict() must return a plain dict."""
        d = ortho_result.to_dict()
        assert isinstance(d, dict)

    def test_top_level_keys(self, ortho_result):
        """to_dict() must have the expected top-level keys."""
        d = ortho_result.to_dict()
        assert set(d.keys()) == {
            "phases",
            "hr_response",
            "lf_hf_ratio_change",
            "hf_response_pct",
            "hf_hr_pct_change",
            "interpretation",
        }

    def test_phases_keys(self, ortho_result):
        """Phases must contain supine, transition, standing."""
        d = ortho_result.to_dict()
        assert set(d["phases"].keys()) == {"supine", "transition", "standing"}

    def test_supine_nested_features(self, ortho_result):
        """Supine phase must contain a nested features dict."""
        d = ortho_result.to_dict()
        assert "features" in d["phases"]["supine"]
        assert isinstance(d["phases"]["supine"]["features"], dict)

    def test_transition_hr_dynamics(self, ortho_result):
        """Transition phase must carry delta_hr and peak_hr."""
        d = ortho_result.to_dict()
        trans = d["phases"]["transition"]
        assert "delta_hr" in trans
        assert "peak_hr" in trans

    def test_all_numeric_values_are_float_or_none(self, ortho_result):
        """All leaf numeric values must be float (NaN allowed)."""
        d = ortho_result.to_dict()
        sup_feats = d["phases"]["supine"]["features"]
        for key, val in sup_feats.items():
            if key != "date":
                assert isinstance(val, float), f"{key} is not float: {type(val)}"


# ======================
# OrthostaticResult.to_flat_dict() + to_dataframe()
# ======================


class TestOrthostaticResultToDataframe:
    """Tests for OrthostaticResult.to_flat_dict() and to_dataframe()."""

    def test_to_flat_dict_returns_dict(self, ortho_result):
        """to_flat_dict() must return a plain dict."""
        d = ortho_result.to_flat_dict()
        assert isinstance(d, dict)

    def test_flat_dict_has_prefixed_columns(self, ortho_result):
        """Flat dict must contain supine_, transition_, standing_ prefixes."""
        d = ortho_result.to_flat_dict()
        assert any(k.startswith("supine_") for k in d)
        assert any(k.startswith("transition_") for k in d)
        assert any(k.startswith("standing_") for k in d)

    def test_flat_dict_has_derived_metrics(self, ortho_result):
        """Flat dict must contain the four derived clinical metrics."""
        d = ortho_result.to_flat_dict()
        for key in (
            "hr_response",
            "lf_hf_ratio_change",
            "hf_response_pct",
            "hf_hr_pct_change",
        ):
            assert key in d, f"Missing key: {key}"

    def test_flat_dict_has_timing_fields(self, ortho_result):
        """Flat dict must include timing fields for each phase."""
        d = ortho_result.to_flat_dict()
        for prefix in ("supine", "transition", "standing"):
            assert f"{prefix}_start_sec" in d
            assert f"{prefix}_end_sec" in d
            assert f"{prefix}_duration_sec" in d

    def test_flat_dict_transition_hr_dynamics(self, ortho_result):
        """Flat dict must include transition_delta_hr and transition_peak_hr."""
        d = ortho_result.to_flat_dict()
        assert "transition_delta_hr" in d
        assert "transition_peak_hr" in d

    def test_to_dataframe_returns_dataframe(self, ortho_result):
        """to_dataframe() must return a pandas DataFrame."""
        df = ortho_result.to_dataframe()
        assert isinstance(df, pandas.DataFrame)

    def test_to_dataframe_one_row(self, ortho_result):
        """to_dataframe() must produce exactly one row."""
        df = ortho_result.to_dataframe()
        assert len(df) == 1

    def test_to_dataframe_column_count(self, ortho_result):
        """Column count must match the number of keys in to_flat_dict()."""
        df = ortho_result.to_dataframe()
        d = ortho_result.to_flat_dict()
        assert len(df.columns) == len(d)

    def test_hr_response_value(self, ortho_result):
        """hr_response column must match OrthostaticResult.hr_response."""
        df = ortho_result.to_dataframe()
        assert df["hr_response"].iloc[0] == pytest.approx(ortho_result.hr_response)

    def test_interpretation_in_dataframe(self, ortho_result):
        """Interpretation column must be present and a string."""
        df = ortho_result.to_dataframe()
        assert isinstance(df["interpretation"].iloc[0], str)


# ======================
# features_to_csv
# ======================


class TestFeaturesToCsv:
    """Tests for features_to_csv()."""

    def test_creates_file(self, tmp_path, single_features):
        """features_to_csv() must create the destination file."""
        path = tmp_path / "out.csv"
        features_to_csv(single_features, path)
        assert path.exists()

    def test_single_features_one_data_row(self, tmp_path, single_features):
        """A single HRVFeatures must produce a CSV with one data row."""
        path = tmp_path / "out.csv"
        features_to_csv(single_features, path)
        df = pandas.read_csv(path)
        assert len(df) == 1

    def test_list_features_multiple_rows(self, tmp_path, features_list):
        """A list of 3 sessions must produce a CSV with 3 data rows."""
        path = tmp_path / "out.csv"
        features_to_csv(features_list, path)
        df = pandas.read_csv(path)
        assert len(df) == len(features_list)

    def test_column_names_match(self, tmp_path, single_features):
        """CSV column names must match HRVFeatures.to_dict() keys."""
        path = tmp_path / "out.csv"
        features_to_csv(single_features, path)
        df = pandas.read_csv(path)
        expected = list(single_features.to_dict().keys())
        assert list(df.columns) == expected

    def test_rmssd_value_roundtrip(self, tmp_path, single_features):
        """RMSSD written then read must equal the original value."""
        path = tmp_path / "out.csv"
        features_to_csv(single_features, path)
        df = pandas.read_csv(path)
        assert df["rmssd"].iloc[0] == pytest.approx(single_features.rmssd)

    def test_nan_written_as_empty(self, tmp_path):
        """NaN values must be written as empty cells (not 'nan' strings)."""
        f = _make_features(dfa_alpha1=float("nan"))
        path = tmp_path / "out.csv"
        features_to_csv(f, path)
        content = path.read_text()
        assert "nan" not in content.lower()


# ======================
# features_to_json
# ======================


class TestFeaturesToJson:
    """Tests for features_to_json()."""

    def test_creates_file(self, tmp_path, single_features):
        """features_to_json() must create the destination file."""
        path = tmp_path / "out.json"
        features_to_json(single_features, path)
        assert path.exists()

    def test_output_is_valid_json_array(self, tmp_path, single_features):
        """Output must be a parseable JSON array."""
        path = tmp_path / "out.json"
        features_to_json(single_features, path)
        data = json.loads(path.read_text())
        assert isinstance(data, list)

    def test_single_features_one_element(self, tmp_path, single_features):
        """A single HRVFeatures must produce a JSON array with one element."""
        path = tmp_path / "out.json"
        features_to_json(single_features, path)
        data = json.loads(path.read_text())
        assert len(data) == 1

    def test_list_features_multiple_elements(self, tmp_path, features_list):
        """A list of 3 sessions must produce a JSON array with 3 elements."""
        path = tmp_path / "out.json"
        features_to_json(features_list, path)
        data = json.loads(path.read_text())
        assert len(data) == len(features_list)

    def test_nan_serialised_as_null(self, tmp_path):
        """NaN values must be serialised as JSON null."""
        f = _make_features(dfa_alpha1=float("nan"))
        path = tmp_path / "out.json"
        features_to_json(f, path)
        data = json.loads(path.read_text())
        assert data[0]["dfa_alpha1"] is None

    def test_rmssd_value_roundtrip(self, tmp_path, single_features):
        """RMSSD written then read must equal the original value."""
        path = tmp_path / "out.json"
        features_to_json(single_features, path)
        data = json.loads(path.read_text())
        assert data[0]["rmssd"] == pytest.approx(single_features.rmssd)

    def test_custom_indent(self, tmp_path, single_features):
        """indent=4 must produce correctly indented JSON."""
        path = tmp_path / "out.json"
        features_to_json(single_features, path, indent=4)
        content = path.read_text()
        assert "    " in content  # 4-space indent present


# ======================
# orthostatic_to_json
# ======================


class TestOrthostaticToJson:
    """Tests for orthostatic_to_json()."""

    def test_creates_file(self, tmp_path, ortho_result):
        """orthostatic_to_json() must create the destination file."""
        path = tmp_path / "ortho.json"
        orthostatic_to_json(ortho_result, path)
        assert path.exists()

    def test_output_is_valid_json(self, tmp_path, ortho_result):
        """Output must be valid JSON."""
        path = tmp_path / "ortho.json"
        orthostatic_to_json(ortho_result, path)
        data = json.loads(path.read_text())
        assert isinstance(data, dict)

    def test_top_level_keys_preserved(self, tmp_path, ortho_result):
        """JSON must contain the top-level keys of to_dict()."""
        path = tmp_path / "ortho.json"
        orthostatic_to_json(ortho_result, path)
        data = json.loads(path.read_text())
        assert "phases" in data
        assert "hr_response" in data
        assert "interpretation" in data

    def test_nested_phases_present(self, tmp_path, ortho_result):
        """Phases dict must contain supine / transition / standing."""
        path = tmp_path / "ortho.json"
        orthostatic_to_json(ortho_result, path)
        data = json.loads(path.read_text())
        assert set(data["phases"].keys()) == {"supine", "transition", "standing"}

    def test_nan_serialised_as_null(self, tmp_path, ortho_result):
        """NaN values must not break JSON serialisation (serialised as null)."""
        path = tmp_path / "ortho.json"
        orthostatic_to_json(ortho_result, path)
        content = path.read_text()
        assert "NaN" not in content


# ======================
# orthostatic_to_csv
# ======================


class TestOrthostaticToCsv:
    """Tests for orthostatic_to_csv()."""

    def test_creates_file(self, tmp_path, ortho_result):
        """orthostatic_to_csv() must create the destination file."""
        path = tmp_path / "ortho.csv"
        orthostatic_to_csv(ortho_result, path)
        assert path.exists()

    def test_one_data_row(self, tmp_path, ortho_result):
        """The CSV must have exactly one data row."""
        path = tmp_path / "ortho.csv"
        orthostatic_to_csv(ortho_result, path)
        df = pandas.read_csv(path)
        assert len(df) == 1

    def test_prefixed_columns_present(self, tmp_path, ortho_result):
        """CSV must have supine_, transition_, and standing_ prefixed columns."""
        path = tmp_path / "ortho.csv"
        orthostatic_to_csv(ortho_result, path)
        df = pandas.read_csv(path)
        assert any(c.startswith("supine_") for c in df.columns)
        assert any(c.startswith("transition_") for c in df.columns)
        assert any(c.startswith("standing_") for c in df.columns)

    def test_hr_response_value_roundtrip(self, tmp_path, ortho_result):
        """hr_response value must survive CSV roundtrip."""
        path = tmp_path / "ortho.csv"
        orthostatic_to_csv(ortho_result, path)
        df = pandas.read_csv(path)
        assert df["hr_response"].iloc[0] == pytest.approx(ortho_result.hr_response)

    def test_interpretation_column(self, tmp_path, ortho_result):
        """Interpretation column must be present and match the result."""
        path = tmp_path / "ortho.csv"
        orthostatic_to_csv(ortho_result, path)
        df = pandas.read_csv(path)
        assert df["interpretation"].iloc[0] == ortho_result.interpretation
