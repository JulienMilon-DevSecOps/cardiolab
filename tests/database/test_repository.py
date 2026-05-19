"""Unit tests for the HRV repository module.

All tests in this file are pure Python — no PostgreSQL required. The database
connection is replaced by ``unittest.mock`` patches so that:

* SQL construction and parameter binding logic is exercised.
* Column-to-field mapping is verified.
* Guard rails (bad identifiers, outside-context-manager calls) are tested.

Integration tests (full DB round-trip) are in a separate class, marked with
``@pytest.mark.integration`` and skipped by default.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from cardiolab.database.repository import (
    _DATA_COLUMNS,
    _HRV_COLUMNS,
    _ORTHO_COLUMNS,
    _ORTHO_DATA_COLUMNS,
    HRVRepository,
    OrthostaticRecord,
    _build_ortho_row,
    _features_from_row,
    _hrv_fields,
    _validate_identifier,
)
from cardiolab.protocols.resting import HRVFeatures

# ======================
# FIXTURES & HELPERS
# ======================


@pytest.fixture
def sample_features():
    """Minimal HRVFeatures instance for save/load tests."""
    return HRVFeatures(
        date="2026-05-15",
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
        sd_ratio=0.405,
        dfa_alpha1=1.05,
        duration=300.0,
        score=72.5,
    )


def _mock_hrv_features() -> MagicMock:
    """Return a MagicMock with all HRVFeatures numeric attributes set."""
    f = MagicMock()
    f.rmssd = 60.0
    f.ln_rmssd = 4.09
    f.sdnn = 80.0
    f.pnn50 = 25.0
    f.mean_hr = 70.0
    f.vlf = 500.0
    f.lf = 1500.0
    f.hf = 2000.0
    f.lf_hf = 0.75
    f.hf_pct = 0.4
    f.lf_nu = 0.4
    f.hf_nu = 0.6
    f.hf_hr = 2857.1
    f.sd1 = 42.43
    f.sd2 = 104.88
    f.sd_ratio = 0.405
    f.dfa_alpha1 = 1.05
    f.apen = 1.5
    f.sampen = 1.3
    f.method = "welch"
    return f


def _mock_ortho_result() -> MagicMock:
    """Return a minimal OrthostaticResult mock for row-building tests."""
    feat = _mock_hrv_features()

    supine = MagicMock()
    supine.features = feat
    supine.duration_sec = 305.0

    transition = MagicMock()
    transition.features = feat
    transition.start_sec = 305.0
    transition.end_sec = 342.0
    transition.duration_sec = 37.0
    transition.delta_hr = 20.0
    transition.peak_hr = 90.0

    standing = MagicMock()
    standing.features = feat
    standing.duration_sec = 310.0

    phases = MagicMock()
    phases.supine = supine
    phases.transition = transition
    phases.standing = standing

    result = MagicMock()
    result.phases = phases
    result.hr_response = 20.0
    result.lf_hf_ratio_change = 1.5
    result.hf_response_pct = -40.0
    result.hf_hr_pct_change = -65.0
    result.interpretation = "normal"

    return result


def _mock_repo_conn(repo: HRVRepository):
    """Inject a mock connection and cursor into an HRVRepository instance.

    Returns the mock cursor so callers can inspect what was executed.
    """
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    repo._conn = mock_conn
    return mock_cursor


# ======================
# _validate_identifier
# ======================


class TestValidateIdentifier:
    """Tests for the SQL injection guard."""

    @pytest.mark.parametrize(
        "name",
        [
            "hrv_features",
            "hrv_orthostatic",
            "_private",
            "table1",
            "MyTable",
            "a",
        ],
    )
    def test_valid_identifiers_do_not_raise(self, name):
        """Valid SQL identifiers must not raise."""
        _validate_identifier(name)  # no exception

    @pytest.mark.parametrize(
        "name",
        [
            "1table",  # starts with digit
            "table name",  # space
            "table; DROP",  # injection attempt
            "table-name",  # hyphen
            "",  # empty
            "tàble",  # non-ASCII
            "table.name",  # dot
        ],
    )
    def test_invalid_identifiers_raise_value_error(self, name):
        """Invalid identifiers must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            _validate_identifier(name)


# ======================
# _hrv_fields
# ======================


class TestHrvFields:
    """Tests for the per-phase column name generator."""

    def test_returns_twelve_columns(self):
        """_hrv_fields must return exactly 19 columns."""
        assert len(_hrv_fields("supine")) == 19  # noqa: PLR2004

    def test_all_values_are_float(self):
        """All SQL types must be FLOAT."""
        for sql_type in _hrv_fields("standing").values():
            assert sql_type == "FLOAT"

    def test_keys_start_with_prefix(self):
        """Every key must begin with the given prefix."""
        prefix = "transition"
        for key in _hrv_fields(prefix):
            assert key.startswith(f"{prefix}_")

    def test_expected_metric_names(self):
        """The 19 expected metric names must be present (prefix stripped)."""
        expected_suffixes = {
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
        }
        fields = _hrv_fields("supine")
        actual_suffixes = {k.removeprefix("supine_") for k in fields}
        assert actual_suffixes == expected_suffixes

    def test_different_prefixes_produce_distinct_keys(self):
        """Column sets for different phases must not overlap."""
        supine_keys = set(_hrv_fields("supine"))
        standing_keys = set(_hrv_fields("standing"))
        assert supine_keys.isdisjoint(standing_keys)


# ======================
# Column registry invariants
# ======================


class TestColumnRegistries:
    """Structural checks on the column registries to prevent silent mismatches."""

    def test_hrv_columns_contains_mandatory_keys(self):
        """user_id and date must always be present in _HRV_COLUMNS."""
        assert "user_id" in _HRV_COLUMNS
        assert "date" in _HRV_COLUMNS

    def test_data_columns_excludes_user_id_and_date(self):
        """_DATA_COLUMNS must not include the conflict-target columns."""
        assert "user_id" not in _DATA_COLUMNS
        assert "date" not in _DATA_COLUMNS

    def test_data_columns_is_subset_of_hrv_columns(self):
        """Every column in _DATA_COLUMNS must exist in _HRV_COLUMNS."""
        assert set(_DATA_COLUMNS).issubset(_HRV_COLUMNS)

    def test_ortho_columns_contains_mandatory_keys(self):
        """user_id and date must always be present in _ORTHO_COLUMNS."""
        assert "user_id" in _ORTHO_COLUMNS
        assert "date" in _ORTHO_COLUMNS

    def test_ortho_data_columns_excludes_user_id_and_date(self):
        """_ORTHO_DATA_COLUMNS must not include the conflict-target columns."""
        assert "user_id" not in _ORTHO_DATA_COLUMNS
        assert "date" not in _ORTHO_DATA_COLUMNS

    def test_ortho_data_columns_count(self):
        """_ORTHO_DATA_COLUMNS must have the expected count.

        3 phases × 19 HRV metrics = 57
        + supine_duration_sec, standing_duration_sec = 2
        + transition timing (start, end, duration, delta_hr, peak_hr) = 5
        + derived (hr_response, lf_hf_ratio_change, hf_response_pct,
                   hf_hr_pct_change, interpretation) = 5
        + spectral_method = 1
        Total = 70
        """
        assert len(_ORTHO_DATA_COLUMNS) == 70  # noqa: PLR2004

    def test_ortho_data_columns_is_subset_of_ortho_columns(self):
        """Every column in _ORTHO_DATA_COLUMNS must exist in _ORTHO_COLUMNS."""
        assert set(_ORTHO_DATA_COLUMNS).issubset(_ORTHO_COLUMNS)

    def test_ortho_columns_has_all_three_phase_prefixes(self):
        """All three phase prefixes must appear in _ORTHO_COLUMNS."""
        for prefix in ("supine", "transition", "standing"):
            assert any(k.startswith(f"{prefix}_") for k in _ORTHO_COLUMNS)

    def test_no_duplicate_column_names(self):
        """Column names must be unique within each registry."""
        assert len(_HRV_COLUMNS) == len(set(_HRV_COLUMNS))
        assert len(_ORTHO_COLUMNS) == len(set(_ORTHO_COLUMNS))


# ======================
# _features_from_row
# ======================


class TestFeaturesFromRow:
    """Tests for the DB-row → HRVFeatures mapping helper."""

    def _make_row(self, n: int = 50) -> tuple:
        """Return a row of floats equal to their own index for easy verification."""
        return tuple(float(i) for i in range(n))

    def test_maps_rmssd_at_offset(self):
        """Rmssd must be read from row[offset]."""
        row = self._make_row()
        f = _features_from_row(row, offset=3)
        assert f.rmssd == 3.0

    def test_maps_hf_nu_at_offset_plus_eleven(self):
        """hf_nu is the 12th field — must be at row[offset + 11]."""
        row = self._make_row()
        f = _features_from_row(row, offset=5)
        assert f.hf_nu == 16.0  # 5 + 11

    def test_field_order_matches_hrv_fields_order(self):
        """All 17 fields must be read in the same order as _hrv_fields()."""
        row = tuple(range(20))
        f = _features_from_row(row, offset=0)
        assert f.rmssd == row[0]
        assert f.ln_rmssd == row[1]
        assert f.sdnn == row[2]
        assert f.pnn50 == row[3]
        assert f.mean_hr == row[4]
        assert f.vlf == row[5]
        assert f.lf == row[6]
        assert f.hf == row[7]
        assert f.lf_hf == row[8]
        assert f.hf_pct == row[9]
        assert f.lf_nu == row[10]
        assert f.hf_nu == row[11]
        assert f.hf_hr == row[12]
        assert f.sd1 == row[13]
        assert f.sd2 == row[14]
        assert f.sd_ratio == row[15]
        assert f.dfa_alpha1 == row[16]

    def test_date_attached(self):
        """The date parameter must be forwarded to HRVFeatures.date."""
        row = self._make_row()
        f = _features_from_row(row, offset=0, date="2026-05-15")
        assert f.date == "2026-05-15"

    def test_duration_attached(self):
        """The duration parameter must be forwarded to HRVFeatures.duration."""
        row = self._make_row()
        f = _features_from_row(row, offset=0, duration=305.0)
        assert f.duration == 305.0

    def test_returns_hrv_features_instance(self):
        """Return type must be HRVFeatures."""
        row = self._make_row()
        assert isinstance(_features_from_row(row, offset=0), HRVFeatures)


# ======================
# _build_ortho_row
# ======================


class TestBuildOrthoRow:
    """Tests for the OrthostaticResult → DB tuple flattening helper.

    The critical invariant is that the tuple length and position of
    ``user_id`` / ``date`` / ``interpretation`` are stable and match
    ``_ORTHO_DATA_COLUMNS``.
    """

    def test_row_length_matches_all_columns(self):
        """Row must have exactly 2 + len(_ORTHO_DATA_COLUMNS) values."""
        result = _mock_ortho_result()
        row = _build_ortho_row(result, user_id="uid", date="2026-05-15")
        expected_len = 2 + len(_ORTHO_DATA_COLUMNS)
        assert len(row) == expected_len

    def test_first_element_is_user_id(self):
        """row[0] must be the user_id."""
        result = _mock_ortho_result()
        row = _build_ortho_row(result, user_id="test-uuid", date="2026-05-15")
        assert row[0] == "test-uuid"

    def test_second_element_is_date(self):
        """row[1] must be the date."""
        result = _mock_ortho_result()
        row = _build_ortho_row(result, user_id="uid", date="2026-05-15")
        assert row[1] == "2026-05-15"

    def test_last_element_is_interpretation(self):
        """interpretation must be second-to-last; spectral_method is last."""
        result = _mock_ortho_result()
        result.interpretation = "elevated_response"
        row = _build_ortho_row(result, user_id="uid", date="2026-05-15")
        assert row[-2] == "elevated_response"
        assert isinstance(row[-1], str)  # spectral_method

    def test_hr_response_in_row(self):
        """hr_response must appear in the row."""
        result = _mock_ortho_result()
        result.hr_response = 18.5
        row = _build_ortho_row(result, user_id="uid", date="2026-05-15")
        assert 18.5 in row

    def test_all_elements_are_scalar(self):
        """Every element must be a str or numeric type, not a nested object."""
        result = _mock_ortho_result()
        row = _build_ortho_row(result, user_id="uid", date="2026-05-15")
        for val in row:
            assert isinstance(val, (str, int, float)), f"Unexpected type: {type(val)}"


# ======================
# OrthostaticRecord
# ======================


class TestOrthostaticRecord:
    """Tests for the DB read-side dataclass."""

    def test_instantiation(self, sample_features):
        """OrthostaticRecord must be creatable with all required fields."""
        rec = OrthostaticRecord(
            date="2026-05-15",
            supine=sample_features,
            standing=sample_features,
            transition_features=sample_features,
            transition_start_sec=305.0,
            transition_end_sec=342.0,
            transition_duration_sec=37.0,
            transition_delta_hr=20.0,
            transition_peak_hr=90.0,
            hr_response=20.0,
            lf_hf_ratio_change=1.5,
            hf_response_pct=-40.0,
            hf_hr_pct_change=-65.0,
            interpretation="normal",
        )
        assert rec.date == "2026-05-15"
        assert rec.interpretation == "normal"

    def test_supine_is_hrv_features(self, sample_features):
        """OrthostaticRecord.supine must be an HRVFeatures instance."""
        rec = OrthostaticRecord(
            date="2026-05-15",
            supine=sample_features,
            standing=sample_features,
            transition_features=sample_features,
            transition_start_sec=0.0,
            transition_end_sec=0.0,
            transition_duration_sec=0.0,
            transition_delta_hr=0.0,
            transition_peak_hr=0.0,
            hr_response=0.0,
            lf_hf_ratio_change=0.0,
            hf_response_pct=0.0,
            hf_hr_pct_change=0.0,
            interpretation="normal",
        )
        assert isinstance(rec.supine, HRVFeatures)
        assert rec.supine.rmssd == 60.0

    def test_supine_hrv_fields_accessible(self, sample_features):
        """All HRVFeatures fields must be accessible on record.supine."""
        rec = OrthostaticRecord(
            date="2026-05-15",
            supine=sample_features,
            standing=sample_features,
            transition_features=sample_features,
            transition_start_sec=0.0,
            transition_end_sec=0.0,
            transition_duration_sec=0.0,
            transition_delta_hr=0.0,
            transition_peak_hr=0.0,
            hr_response=0.0,
            lf_hf_ratio_change=0.0,
            hf_response_pct=0.0,
            hf_hr_pct_change=0.0,
            interpretation="normal",
        )
        assert rec.supine.sdnn == 80.0
        assert rec.supine.hf_nu == 0.6
        assert rec.supine.lf_hf == 0.75


# ======================
# HRVRepository — init & guards
# ======================


class TestHRVRepositoryInit:
    """Tests for constructor-level validation."""

    def test_valid_table_names_succeed(self):
        """Valid table names must not raise during init."""
        repo = HRVRepository("h", "db", "u", "p", table_name="hrv_features")
        assert repo.table_name == "hrv_features"

    def test_invalid_table_name_raises(self):
        """An invalid table name must raise ValueError at init time."""
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            HRVRepository("h", "db", "u", "p", table_name="bad-name")

    def test_invalid_ortho_table_name_raises(self):
        """An invalid ortho_table_name must raise ValueError at init time."""
        with pytest.raises(ValueError, match="Invalid SQL identifier"):
            HRVRepository("h", "db", "u", "p", ortho_table_name="bad name")

    def test_default_table_names(self):
        """Default table names must be the documented values."""
        repo = HRVRepository("h", "db", "u", "p")
        assert repo.table_name == "hrv_features"
        assert repo.ortho_table_name == "hrv_orthostatic"

    def test_conn_is_none_before_enter(self):
        """Before entering the context manager, _conn must be None."""
        repo = HRVRepository("h", "db", "u", "p")
        assert repo._conn is None


class TestHRVRepositoryGuards:
    """Tests for the outside-context-manager guard."""

    def test_conn_or_raise_outside_context(self):
        """Calling _conn_or_raise outside a with block must raise RuntimeError."""
        repo = HRVRepository("h", "db", "u", "p")
        with pytest.raises(RuntimeError, match="context manager"):
            repo._conn_or_raise()

    def test_save_features_outside_context_raises(self, sample_features):
        """save_features must raise RuntimeError when called outside with."""
        repo = HRVRepository("h", "db", "u", "p")
        with pytest.raises(RuntimeError):
            repo.save_features(sample_features, user_id="uid")

    def test_load_features_outside_context_raises(self):
        """load_features must raise RuntimeError when called outside with."""
        repo = HRVRepository("h", "db", "u", "p")
        with pytest.raises(RuntimeError):
            repo.load_features(user_id="uid")

    def test_save_orthostatic_outside_context_raises(self):
        """save_orthostatic must raise RuntimeError when called outside with."""
        repo = HRVRepository("h", "db", "u", "p")
        result = _mock_ortho_result()
        with pytest.raises(RuntimeError):
            repo.save_orthostatic(result, user_id="uid", date="2026-05-15")

    def test_load_orthostatic_outside_context_raises(self):
        """load_orthostatic must raise RuntimeError when called outside with."""
        repo = HRVRepository("h", "db", "u", "p")
        with pytest.raises(RuntimeError):
            repo.load_orthostatic(user_id="uid")


# ======================
# HRVRepository — from_env
# ======================


class TestHRVRepositoryFromEnv:
    """Tests for the environment-variable factory."""

    def test_from_env_reads_required_variables(self):
        """from_env must read DB_HOST, DB_NAME, DB_USER, DB_PASSWORD."""
        env = {
            "DB_HOST": "myhost",
            "DB_NAME": "mydb",
            "DB_USER": "myuser",
            "DB_PASSWORD": "mypass",
        }
        with patch.dict(os.environ, env, clear=False):
            repo = HRVRepository.from_env()

        assert repo._dsn["host"] == "myhost"
        assert repo._dsn["database"] == "mydb"
        assert repo._dsn["user"] == "myuser"
        assert repo._dsn["password"] == "mypass"  # noqa: S105

    def test_from_env_default_port(self):
        """DB_PORT defaults to 5432 when absent."""
        env = {
            "DB_HOST": "h",
            "DB_NAME": "db",
            "DB_USER": "u",
            "DB_PASSWORD": "p",
        }
        with patch.dict(os.environ, env, clear=False):
            # Remove DB_PORT if set
            env_clean = {k: v for k, v in os.environ.items() if k != "DB_PORT"}
            with patch.dict(os.environ, env_clean, clear=True):
                repo = HRVRepository.from_env()

        assert repo._dsn["port"] == 5432  # noqa: PLR2004

    def test_from_env_custom_port(self):
        """DB_PORT must be parsed as an integer."""
        env = {
            "DB_HOST": "h",
            "DB_NAME": "db",
            "DB_USER": "u",
            "DB_PASSWORD": "p",
            "DB_PORT": "5433",
        }
        with patch.dict(os.environ, env, clear=False):
            repo = HRVRepository.from_env()

        assert repo._dsn["port"] == 5433  # noqa: PLR2004

    def test_from_env_missing_variable_raises(self):
        """A missing required variable must raise KeyError."""
        with patch.dict(os.environ, {}, clear=True), pytest.raises(KeyError):
            HRVRepository.from_env()


# ======================
# HRVRepository — context manager
# ======================


class TestHRVRepositoryContextManager:
    """Tests for commit/rollback behaviour on __exit__."""

    @patch("cardiolab.database.repository.connect")
    def test_commit_on_clean_exit(self, mock_connect):
        """Connection must be committed when no exception is raised."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        with HRVRepository("h", "db", "u", "p"):
            pass

        mock_conn.commit.assert_called_once()
        mock_conn.rollback.assert_not_called()
        mock_conn.close.assert_called_once()

    @patch("cardiolab.database.repository.connect")
    def test_rollback_on_exception(self, mock_connect):
        """Connection must be rolled back when an exception propagates."""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        with pytest.raises(ValueError), HRVRepository("h", "db", "u", "p"):
            raise ValueError("test error")

        mock_conn.rollback.assert_called_once()
        mock_conn.commit.assert_not_called()
        mock_conn.close.assert_called_once()

    @patch("cardiolab.database.repository.connect")
    def test_conn_is_none_after_exit(self, mock_connect):
        """_conn must be reset to None after the context manager exits."""
        mock_connect.return_value = MagicMock()

        repo = HRVRepository("h", "db", "u", "p")
        with repo:
            assert repo._conn is not None

        assert repo._conn is None


# ======================
# HRVRepository — save_features
# ======================


class TestSaveFeatures:
    """Tests for the resting-protocol upsert."""

    def test_executemany_called_once(self, sample_features):
        """Executemany must be called exactly once per save_features call."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)

        repo.save_features(sample_features, user_id="uid")

        cur.executemany.assert_called_once()

    def test_row_tuple_length(self, sample_features):
        """Each row passed to executemany must have the correct column count."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)

        repo.save_features(sample_features, user_id="uid")

        _, rows = cur.executemany.call_args[0]
        expected = 2 + len(_DATA_COLUMNS)  # user_id + date + data cols
        assert len(rows[0]) == expected

    def test_row_first_element_is_user_id(self, sample_features):
        """row[0] must be the user_id string."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)

        repo.save_features(sample_features, user_id="my-uuid")

        _, rows = cur.executemany.call_args[0]
        assert rows[0][0] == "my-uuid"

    def test_accepts_list_of_features(self, sample_features):
        """A list of HRVFeatures must be saved as multiple rows."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)

        repo.save_features([sample_features, sample_features], user_id="uid")

        _, rows = cur.executemany.call_args[0]
        assert len(rows) == 2  # noqa: PLR2004

    def test_single_feature_wrapped_in_list(self, sample_features):
        """A single HRVFeatures must be normalised to a one-element list."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)

        repo.save_features(sample_features, user_id="uid")

        _, rows = cur.executemany.call_args[0]
        assert len(rows) == 1


# ======================
# HRVRepository — load_features
# ======================


class TestLoadFeatures:
    """Tests for resting-protocol row → HRVFeatures reconstruction."""

    def _make_resting_row(self) -> tuple:
        """Build a fake DB row with 23 values (date + 22 metrics).

        Layout mirrors load_features SELECT order:
        [0] date, [1..5] temporal, [6..13] frequency, [14..17] nonlinear,
        [18] apen, [19] sampen, [20] duration, [21] score, [22] method
        """
        return (
            "2026-05-15",  # [0]  date
            60.0,
            4.09,
            80.0,
            25.0,
            70.0,   # [1..5]  rmssd…mean_hr
            500.0,
            1500.0,
            2000.0,  # [6..8]  vlf, lf, hf
            0.75,
            0.4,
            0.4,
            0.6,
            2857.1,  # [9..13] lf_hf, hf_pct, lf_nu, hf_nu, hf_hr
            42.43,
            104.88,
            0.405,
            1.05,    # [14..17] sd1, sd2, sd_ratio, dfa_alpha1
            1.5,     # [18]  apen
            1.3,     # [19]  sampen
            300.0,   # [20]  duration
            72.5,    # [21]  score
            "welch", # [22]  method
        )

    def test_returns_list_of_hrv_features(self):
        """load_features must return a list of HRVFeatures."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        cur.fetchall.return_value = [self._make_resting_row()]

        result = repo.load_features(user_id="uid")

        assert len(result) == 1
        assert isinstance(result[0], HRVFeatures)

    def test_maps_rmssd_correctly(self):
        """Rmssd in the result must match the value in the DB row."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        cur.fetchall.return_value = [self._make_resting_row()]

        result = repo.load_features(user_id="uid")

        assert result[0].rmssd == 60.0

    def test_maps_date_correctly(self):
        """Date in the result must be a string equal to the stored value."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        cur.fetchall.return_value = [self._make_resting_row()]

        result = repo.load_features(user_id="uid")

        assert result[0].date == "2026-05-15"

    def test_empty_result_returns_empty_list(self):
        """An empty DB response must return an empty list."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        cur.fetchall.return_value = []

        result = repo.load_features(user_id="uid")

        assert result == []

    def test_multiple_rows_returned(self):
        """Two DB rows must produce two HRVFeatures."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        cur.fetchall.return_value = [
            self._make_resting_row(),
            self._make_resting_row(),
        ]

        result = repo.load_features(user_id="uid")

        assert len(result) == 2  # noqa: PLR2004


# ======================
# HRVRepository — save_orthostatic
# ======================


class TestSaveOrthostatic:
    """Tests for the orthostatic-protocol upsert."""

    def test_execute_called_once(self):
        """cursor.execute must be called exactly once per save."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        result = _mock_ortho_result()

        repo.save_orthostatic(result, user_id="uid", date="2026-05-15")

        cur.execute.assert_called_once()

    def test_row_length_matches_all_ortho_columns(self):
        """The row passed to execute must have 2 + len(_ORTHO_DATA_COLUMNS) values."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        result = _mock_ortho_result()

        repo.save_orthostatic(result, user_id="uid", date="2026-05-15")

        _, row = cur.execute.call_args[0]
        expected = 2 + len(_ORTHO_DATA_COLUMNS)
        assert len(row) == expected

    def test_row_user_id_and_date(self):
        """row[0] must be user_id and row[1] must be date."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        result = _mock_ortho_result()

        repo.save_orthostatic(result, user_id="my-uuid", date="2026-05-15")

        _, row = cur.execute.call_args[0]
        assert row[0] == "my-uuid"
        assert row[1] == "2026-05-15"


# ======================
# HRVRepository — load_orthostatic
# ======================


class TestLoadOrthostatic:
    """Tests for orthostatic DB row → OrthostaticRecord reconstruction."""

    def _make_ortho_row(self) -> tuple:
        """Build a fake DB row matching the load_orthostatic SELECT order.

        Row layout (71 values):
        [0]      date
        [1..19]  supine HRV (19)
        [20]     supine_duration_sec
        [21..25] transition timing (5)
        [26..44] transition HRV (19)
        [45..63] standing HRV (19)
        [64]     standing_duration_sec
        [65..69] derived metrics (5)
        [70]     spectral_method
        """
        hrv_block = (
            60.0,
            4.09,
            80.0,
            25.0,
            70.0,
            500.0,
            1500.0,
            2000.0,
            0.75,
            0.4,
            0.4,
            0.6,
            2857.1,  # hf_hr
            42.43,
            104.88,
            0.405,
            1.05,   # dfa_alpha1
            1.5,    # apen
            1.3,    # sampen
        )
        return (
            "2026-05-15",  # [0]     date
            *hrv_block,    # [1..19] supine HRV
            305.0,         # [20]    supine_duration_sec
            305.0,
            342.0,
            37.0,
            20.0,
            90.0,          # [21..25] transition timing
            *hrv_block,    # [26..44] transition HRV
            *hrv_block,    # [45..63] standing HRV
            310.0,         # [64]     standing_duration_sec
            20.0,
            1.5,
            -40.0,
            -65.0,
            "normal",      # [65..69] derived
            "welch",       # [70]     spectral_method
        )

    def test_returns_list_of_orthostatic_records(self):
        """load_orthostatic must return a list of OrthostaticRecord."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        cur.fetchall.return_value = [self._make_ortho_row()]

        result = repo.load_orthostatic(user_id="uid")

        assert len(result) == 1
        assert isinstance(result[0], OrthostaticRecord)

    def test_supine_is_hrv_features(self):
        """record.supine must be an HRVFeatures instance."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        cur.fetchall.return_value = [self._make_ortho_row()]

        record = repo.load_orthostatic(user_id="uid")[0]

        assert isinstance(record.supine, HRVFeatures)

    def test_supine_rmssd_maps_correctly(self):
        """record.supine.rmssd must equal the stored supine_rmssd value."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        cur.fetchall.return_value = [self._make_ortho_row()]

        record = repo.load_orthostatic(user_id="uid")[0]

        assert record.supine.rmssd == 60.0

    def test_interpretation_maps_correctly(self):
        """record.interpretation must equal the stored interpretation."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        cur.fetchall.return_value = [self._make_ortho_row()]

        record = repo.load_orthostatic(user_id="uid")[0]

        assert record.interpretation == "normal"

    def test_transition_timing_maps_correctly(self):
        """Transition timing fields must be read from the correct row positions."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        cur.fetchall.return_value = [self._make_ortho_row()]

        record = repo.load_orthostatic(user_id="uid")[0]

        assert record.transition_start_sec == 305.0
        assert record.transition_end_sec == 342.0
        assert record.transition_duration_sec == 37.0
        assert record.transition_delta_hr == 20.0
        assert record.transition_peak_hr == 90.0

    def test_hr_response_maps_correctly(self):
        """record.hr_response must equal the stored hr_response value."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        cur.fetchall.return_value = [self._make_ortho_row()]

        record = repo.load_orthostatic(user_id="uid")[0]

        assert record.hr_response == 20.0

    def test_empty_result_returns_empty_list(self):
        """An empty DB response must return an empty list."""
        repo = HRVRepository("h", "db", "u", "p")
        cur = _mock_repo_conn(repo)
        cur.fetchall.return_value = []

        result = repo.load_orthostatic(user_id="uid")

        assert result == []


# ======================
# Integration tests (skipped by default)
# ======================


@pytest.mark.integration
@pytest.mark.skip(
    reason="Requires a running PostgreSQL instance — set up DB_* env vars and remove this skip to run."
)
class TestHRVRepositoryIntegration:
    """Full round-trip tests against a real PostgreSQL database.

    These tests are skipped by default. To run them:
    1. Start a PostgreSQL server.
    2. Set DB_HOST, DB_NAME, DB_USER, DB_PASSWORD in your environment.
    3. Remove the @pytest.mark.skip decorator (or run with -m integration).
    """

    def test_resting_round_trip(self):
        """save_features followed by load_features must return identical data."""
        features = HRVFeatures(
            date="2099-01-01",
            rmssd=55.0,
            ln_rmssd=4.0,
            sdnn=75.0,
            pnn50=20.0,
            mean_hr=65.0,
            vlf=400.0,
            lf=1200.0,
            hf=1800.0,
            lf_hf=0.67,
            hf_pct=0.45,
            lf_nu=0.38,
            hf_nu=0.62,
            duration=301.0,
            score=68.0,
        )

        with HRVRepository.from_env(table_name="test_hrv") as repo:
            repo.create_table()
            repo.save_features(features, user_id="integration-test-user")
            loaded = repo.load_features(user_id="integration-test-user")

        assert any(f.date == "2099-01-01" and f.rmssd == 55.0 for f in loaded)

    def test_upsert_does_not_duplicate(self):
        """Saving the same session twice must not create two rows."""
        features = HRVFeatures(date="2099-01-02", rmssd=60.0, mean_hr=70.0)

        with HRVRepository.from_env(table_name="test_hrv") as repo:
            repo.create_table()
            repo.save_features(features, user_id="integration-test-user")
            repo.save_features(features, user_id="integration-test-user")
            loaded = repo.load_features(user_id="integration-test-user")

        matching = [f for f in loaded if f.date == "2099-01-02"]
        assert len(matching) == 1
