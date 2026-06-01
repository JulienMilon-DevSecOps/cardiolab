"""Unit and integration tests for analytics.training_load."""

from __future__ import annotations

import math
import os
from unittest.mock import MagicMock

import pytest

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.training_load import (
    load_readiness_for_date,
    trimp_banister,
    trimp_hrv_based,
)
from cardiolab.protocols.resting import HRVFeatures

# ======================
# SHARED TEST HELPERS
# ======================


def _make_features(
    rmssd: float = 60.0,
    mean_hr: float = 70.0,
    date: str = "2099-10-01",
) -> HRVFeatures:
    """Build a minimal HRVFeatures with the given RMSSD, HR, and date."""
    return HRVFeatures(
        date=date,
        rmssd=rmssd,
        ln_rmssd=math.log(rmssd),
        sdnn=rmssd * 1.3,
        pnn50=25.0,
        mean_hr=mean_hr,
        vlf=500.0,
        lf=1500.0,
        hf=2000.0,
        lf_hf=0.75,
        hf_pct=0.4,
        lf_nu=0.4,
        hf_nu=0.6,
        hf_hr=2000.0 / mean_hr,
        sd1=rmssd / math.sqrt(2),
        sd2=rmssd * 0.9,
        sd_ratio=0.40,
        dfa_alpha1=1.05,
        apen=1.5,
        sampen=1.3,
        duration=300.0,
        score=75.0,
    )


def _baseline_from(*features: HRVFeatures) -> Baseline:
    return Baseline.from_features(list(features))


# ======================
# UNIT — trimp_hrv_based
# ======================


@pytest.mark.unit
class TestTrimpHrvBased:
    """Unit tests for trimp_hrv_based()."""

    def test_formula_basic(self):
        """60 min × (1 − 70/100) = 18.0."""
        result = trimp_hrv_based(duration_min=60.0, readiness_score=70.0)
        assert result == pytest.approx(18.0)

    def test_readiness_100_gives_zero(self):
        """Fully recovered athlete → TRIMP = 0 regardless of duration."""
        assert trimp_hrv_based(
            duration_min=45.0, readiness_score=100.0
        ) == pytest.approx(0.0)

    def test_readiness_0_gives_full_duration(self):
        """Completely depleted athlete → TRIMP = duration."""
        assert trimp_hrv_based(duration_min=45.0, readiness_score=0.0) == pytest.approx(
            45.0
        )

    def test_readiness_50_neutral(self):
        """Neutral readiness → TRIMP = half the duration."""
        assert trimp_hrv_based(
            duration_min=60.0, readiness_score=50.0
        ) == pytest.approx(30.0)

    def test_result_is_non_negative(self):
        """TRIMP must always be ≥ 0."""
        assert trimp_hrv_based(duration_min=30.0, readiness_score=99.0) >= 0.0

    def test_short_session_low_readiness(self):
        """30 min, readiness 20 → 30 × 0.80 = 24.0."""
        assert trimp_hrv_based(
            duration_min=30.0, readiness_score=20.0
        ) == pytest.approx(24.0)

    def test_raises_on_non_positive_duration(self):
        """duration_min ≤ 0 must raise ValueError."""
        with pytest.raises(ValueError, match="duration_min"):
            trimp_hrv_based(duration_min=0.0, readiness_score=50.0)

    def test_raises_on_negative_duration(self):
        """Negative duration must raise ValueError."""
        with pytest.raises(ValueError, match="duration_min"):
            trimp_hrv_based(duration_min=-10.0, readiness_score=50.0)

    def test_raises_on_readiness_above_100(self):
        """readiness_score > 100 must raise ValueError."""
        with pytest.raises(ValueError, match="readiness_score"):
            trimp_hrv_based(duration_min=60.0, readiness_score=101.0)

    def test_raises_on_negative_readiness(self):
        """readiness_score < 0 must raise ValueError."""
        with pytest.raises(ValueError, match="readiness_score"):
            trimp_hrv_based(duration_min=60.0, readiness_score=-1.0)

    def test_returns_float(self):
        """Result must always be a Python float."""
        result = trimp_hrv_based(duration_min=60.0, readiness_score=70.0)
        assert isinstance(result, float)

    def test_proportional_to_duration(self):
        """Doubling the duration must double the TRIMP."""
        t1 = trimp_hrv_based(duration_min=30.0, readiness_score=60.0)
        t2 = trimp_hrv_based(duration_min=60.0, readiness_score=60.0)
        assert t2 == pytest.approx(2 * t1)


# ======================
# UNIT — trimp_banister
# ======================


@pytest.mark.unit
class TestTrimpBanister:
    """Unit tests for trimp_banister()."""

    def test_formula_male_basic(self):
        """Verify manual computation for a standard male case.

        HRR = (150 − 60) / (190 − 60) = 90/130 ≈ 0.6923
        TRIMP = 60 × 0.6923 × exp(1.92 × 0.6923)
        """
        hrr = (150.0 - 60.0) / (190.0 - 60.0)
        expected = 60.0 * hrr * math.exp(1.92 * hrr)
        result = trimp_banister(
            duration_min=60.0, hr_mean=150.0, hr_max=190.0, hr_rest=60.0, sex="male"
        )
        assert result == pytest.approx(expected, rel=1e-6)

    def test_formula_female_uses_lower_b(self):
        """Female coefficient b=1.67 must give lower TRIMP than male b=1.92."""
        male = trimp_banister(
            60.0, hr_mean=150.0, hr_max=190.0, hr_rest=60.0, sex="male"
        )
        female = trimp_banister(
            60.0, hr_mean=150.0, hr_max=190.0, hr_rest=60.0, sex="female"
        )
        assert female < male

    def test_default_sex_is_male(self):
        """Omitting sex must use the male coefficient."""
        default = trimp_banister(60.0, hr_mean=150.0, hr_max=190.0, hr_rest=60.0)
        male = trimp_banister(
            60.0, hr_mean=150.0, hr_max=190.0, hr_rest=60.0, sex="male"
        )
        assert default == pytest.approx(male)

    def test_hr_mean_at_rest_gives_zero_trimp(self):
        """hr_mean = hr_rest → HRR = 0 → TRIMP = 0."""
        result = trimp_banister(
            duration_min=60.0, hr_mean=60.0, hr_max=190.0, hr_rest=60.0
        )
        assert result == pytest.approx(0.0)

    def test_hrr_clamped_above_one(self):
        """hr_mean > hr_max → HRR clamped to 1.0, no crash."""
        result = trimp_banister(
            duration_min=60.0, hr_mean=200.0, hr_max=190.0, hr_rest=60.0
        )
        expected = 60.0 * 1.0 * math.exp(1.92 * 1.0)
        assert result == pytest.approx(expected, rel=1e-6)

    def test_raises_on_non_positive_duration(self):
        """duration_min ≤ 0 must raise ValueError."""
        with pytest.raises(ValueError, match="duration_min"):
            trimp_banister(0.0, hr_mean=150.0, hr_max=190.0, hr_rest=60.0)

    def test_raises_when_hr_max_equals_hr_rest(self):
        """hr_max = hr_rest causes division by zero → must raise ValueError."""
        with pytest.raises(ValueError, match="hr_max"):
            trimp_banister(60.0, hr_mean=150.0, hr_max=60.0, hr_rest=60.0)

    def test_raises_when_hr_max_less_than_hr_rest(self):
        """hr_max < hr_rest is physiologically impossible → must raise ValueError."""
        with pytest.raises(ValueError, match="hr_max"):
            trimp_banister(60.0, hr_mean=150.0, hr_max=50.0, hr_rest=60.0)

    def test_result_is_non_negative(self):
        """TRIMP must always be ≥ 0."""
        result = trimp_banister(30.0, hr_mean=130.0, hr_max=185.0, hr_rest=55.0)
        assert result >= 0.0

    def test_proportional_to_duration(self):
        """Doubling the duration must double the TRIMP."""
        t1 = trimp_banister(30.0, hr_mean=145.0, hr_max=185.0, hr_rest=55.0)
        t2 = trimp_banister(60.0, hr_mean=145.0, hr_max=185.0, hr_rest=55.0)
        assert t2 == pytest.approx(2 * t1)


# ======================
# INTEGRATION HELPERS
# ======================

_integration_skipif = pytest.mark.skipif(
    not os.getenv("DB_HOST_TEST"),
    reason=(
        "Requires a running PostgreSQL test instance. "
        "Set DB_HOST_TEST (+ DB_NAME_TEST, DB_USER_TEST, DB_PASSWORD_TEST) "
        "in your .env — skipped automatically in GitLab CI."
    ),
)


def _repo_from_test_env(**kwargs):
    """Build an HRVRepository from DB_*_TEST environment variables."""
    from cardiolab.database.repository import HRVRepository

    return HRVRepository(
        host=os.environ["DB_HOST_TEST"],
        database=os.environ["DB_NAME_TEST"],
        user=os.environ["DB_USER_TEST"],
        password=os.environ["DB_PASSWORD_TEST"],
        port=int(os.environ.get("DB_PORT_TEST", "5432")),
        **kwargs,
    )


def _test_db_cleanup(table: str, user: str) -> None:
    """Delete test rows from *table* using a direct psycopg2 connection."""
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(
        host=os.environ["DB_HOST_TEST"],
        dbname=os.environ["DB_NAME_TEST"],
        user=os.environ["DB_USER_TEST"],
        password=os.environ["DB_PASSWORD_TEST"],
        port=int(os.environ.get("DB_PORT_TEST", "5432")),
    )
    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table} WHERE user_id = %s;", (user,))  # noqa: S608
        conn.commit()
    finally:
        conn.close()


def _mock_ortho_result(rmssd: float = 60.0, mean_hr: float = 70.0) -> MagicMock:
    """Build a minimal OrthostaticResult mock suitable for save_orthostatic."""
    feat = MagicMock()
    feat.rmssd = rmssd
    feat.ln_rmssd = math.log(rmssd)
    feat.sdnn = rmssd * 1.3
    feat.pnn50 = 25.0
    feat.mean_hr = mean_hr
    feat.vlf = 500.0
    feat.lf = 1500.0
    feat.hf = 2000.0
    feat.lf_hf = 0.75
    feat.hf_pct = 0.4
    feat.lf_nu = 0.4
    feat.hf_nu = 0.6
    feat.hf_hr = 2000.0 / mean_hr
    feat.sd1 = rmssd / math.sqrt(2)
    feat.sd2 = rmssd * 0.9
    feat.sd_ratio = 0.40
    feat.dfa_alpha1 = 1.05
    feat.apen = 1.5
    feat.sampen = 1.3
    feat.method = "welch"

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
    result.hr_response = 18.0
    result.lf_hf_ratio_change = 1.5
    result.hf_response_pct = -40.0
    result.hf_hr_pct_change = -65.0
    result.interpretation = "normal"
    result.score = 75.0
    return result


# ======================
# INTEGRATION — load_readiness_for_date
# ======================


@pytest.mark.integration
@_integration_skipif
class TestLoadReadinessForDateIntegration:
    """Integration tests for load_readiness_for_date against a real PostgreSQL DB."""

    _USER = "test-integration-trimp-user"
    _RESTING_TABLE = "_cardiolab_test_trimp_resting"
    _ORTHO_TABLE = "_cardiolab_test_trimp_ortho"
    _DATE = "2099-10-01"

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        with _repo_from_test_env(
            table_name=self._RESTING_TABLE,
            ortho_table_name=self._ORTHO_TABLE,
        ) as repo:
            repo.create_table()
            repo.create_orthostatic_table()
        yield
        _test_db_cleanup(self._RESTING_TABLE, self._USER)
        _test_db_cleanup(self._ORTHO_TABLE, self._USER)

    # ── resting protocol ──────────────────────────────────────────────────────

    def test_resting_returns_float_in_range(self):
        """Resting protocol: date found → float in [0, 100]."""
        feat = _make_features(rmssd=60.0, mean_hr=70.0, date=self._DATE)
        baseline = _baseline_from(feat)

        with _repo_from_test_env(
            table_name=self._RESTING_TABLE,
            ortho_table_name=self._ORTHO_TABLE,
        ) as repo:
            repo.save_features(feat, user_id=self._USER)
            result = load_readiness_for_date(
                self._USER, self._DATE, repo, baseline, protocol="resting"
            )

        assert result is not None
        assert 0.0 <= result <= 100.0

    def test_resting_date_not_found_returns_none(self):
        """Resting protocol: no session for the date → None."""
        baseline = _baseline_from(_make_features())

        with _repo_from_test_env(
            table_name=self._RESTING_TABLE,
            ortho_table_name=self._ORTHO_TABLE,
        ) as repo:
            result = load_readiness_for_date(
                self._USER, "2099-01-01", repo, baseline, protocol="resting"
            )

        assert result is None

    def test_resting_neutral_baseline_returns_near_50(self):
        """Session equal to the baseline → readiness ≈ 50."""
        feat = _make_features(rmssd=60.0, mean_hr=70.0, date=self._DATE)
        baseline = Baseline(history=[feat] * 7)

        with _repo_from_test_env(
            table_name=self._RESTING_TABLE,
            ortho_table_name=self._ORTHO_TABLE,
        ) as repo:
            repo.save_features(feat, user_id=self._USER)
            result = load_readiness_for_date(
                self._USER, self._DATE, repo, baseline, protocol="resting"
            )

        assert result is not None
        assert 40.0 <= result <= 60.0

    # ── orthostatic protocol ──────────────────────────────────────────────────

    def test_orthostatic_returns_float_in_range(self):
        """Orthostatic protocol: date found → float in [0, 100]."""
        ortho = _mock_ortho_result(rmssd=60.0, mean_hr=70.0)
        supine_feat = _make_features(rmssd=60.0, mean_hr=70.0, date=self._DATE)
        baseline = _baseline_from(supine_feat)

        with _repo_from_test_env(
            table_name=self._RESTING_TABLE,
            ortho_table_name=self._ORTHO_TABLE,
        ) as repo:
            repo.save_orthostatic(ortho, user_id=self._USER, date=self._DATE)
            result = load_readiness_for_date(
                self._USER, self._DATE, repo, baseline, protocol="orthostatic"
            )

        assert result is not None
        assert 0.0 <= result <= 100.0

    def test_orthostatic_date_not_found_returns_none(self):
        """Orthostatic protocol: no session for the date → None."""
        baseline = _baseline_from(_make_features())

        with _repo_from_test_env(
            table_name=self._RESTING_TABLE,
            ortho_table_name=self._ORTHO_TABLE,
        ) as repo:
            result = load_readiness_for_date(
                self._USER, "2099-01-02", repo, baseline, protocol="orthostatic"
            )

        assert result is None

    def test_protocols_do_not_cross(self):
        """Resting session is invisible to orthostatic lookup and vice versa."""
        feat = _make_features(rmssd=60.0, mean_hr=70.0, date=self._DATE)
        baseline = _baseline_from(feat)

        with _repo_from_test_env(
            table_name=self._RESTING_TABLE,
            ortho_table_name=self._ORTHO_TABLE,
        ) as repo:
            repo.save_features(feat, user_id=self._USER)
            # orthostatic table is empty → must return None
            result = load_readiness_for_date(
                self._USER, self._DATE, repo, baseline, protocol="orthostatic"
            )

        assert result is None
