"""Unit and integration tests for analytics.training_load."""

from __future__ import annotations

import math
import os
from unittest.mock import MagicMock

import numpy as np
import pytest

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.training_load import (
    TrainingLoad,
    _ema,
    compute_atl,
    compute_ctl,
    compute_tsb,
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


def _test_table_drop(table: str) -> None:
    """Drop *table* unconditionally — forces schema refresh on CREATE IF NOT EXISTS."""
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
            cur.execute(f"DROP TABLE IF EXISTS {table};")  # noqa: S608
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
    result.hf_hr_pct_change = 65.0
    result.lf_hr_pct_change = 35.0
    result.delta_rmssd = 12.0
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
        _test_table_drop(self._RESTING_TABLE)
        _test_table_drop(self._ORTHO_TABLE)
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


# ======================
# UNIT — compute_atl / compute_ctl / compute_tsb
# ======================


def _const_trimp(n: int, value: float = 40.0) -> np.ndarray:
    return np.full(n, value, dtype=float)


@pytest.mark.unit
class TestComputeAtl:
    """Unit tests for compute_atl()."""

    def test_zero_trimp_gives_zero_atl(self):
        """All rest days → ATL stays at 0."""
        atl = compute_atl(np.zeros(30))
        assert np.allclose(atl, 0.0)

    def test_atl_rises_then_decays(self):
        """ATL increases during training block then decays during rest."""
        trimp = np.concatenate([_const_trimp(14), np.zeros(14)])
        atl = compute_atl(trimp)
        assert atl[13] > atl[0]
        assert atl[-1] < atl[13]

    def test_constant_trimp_converges_to_trimp(self):
        """Long constant TRIMP series → ATL converges to TRIMP value."""
        t = 40.0
        atl = compute_atl(_const_trimp(200, t))
        assert atl[-1] == pytest.approx(t, rel=0.01)

    def test_length_preserved(self):
        """Output array has the same length as input."""
        trimp = np.array([10.0, 20.0, 30.0])
        assert len(compute_atl(trimp)) == 3

    def test_returns_numpy_array(self):
        """Return type must be a numpy ndarray."""
        result = compute_atl(np.array([40.0, 0.0]))
        assert isinstance(result, np.ndarray)

    def test_custom_tau_decays_slower(self):
        """Larger tau → slower decay during rest block."""
        trimp = np.concatenate([_const_trimp(30), np.zeros(20)])
        atl_fast = compute_atl(trimp, tau=7)
        atl_slow = compute_atl(trimp, tau=14)
        assert atl_slow[-1] > atl_fast[-1]

    def test_first_day_atl_equals_trimp_times_k(self):
        """Day 0 ATL = trimp[0] * k (initial condition is 0)."""
        t = 50.0
        k = 1.0 - math.exp(-1.0 / 7)
        atl = compute_atl(np.array([t]))
        assert atl[0] == pytest.approx(t * k)

    def test_non_negative_with_positive_trimp(self):
        """ATL must be ≥ 0 when all TRIMP values are ≥ 0."""
        trimp = np.random.default_rng(0).uniform(0, 60, 50)
        assert np.all(compute_atl(trimp) >= 0.0)


@pytest.mark.unit
class TestComputeCtl:
    """Unit tests for compute_ctl()."""

    def test_zero_trimp_gives_zero_ctl(self):
        """All rest days → CTL stays at 0."""
        assert np.allclose(compute_ctl(np.zeros(60)), 0.0)

    def test_ctl_rises_slower_than_atl(self):
        """Same TRIMP series: CTL must be lower than ATL during early build."""
        trimp = _const_trimp(20)
        atl = compute_atl(trimp)
        ctl = compute_ctl(trimp)
        assert np.all(ctl[:15] <= atl[:15])

    def test_ctl_decays_slower_than_atl(self):
        """During rest, CTL must decay slower than ATL (relative drop)."""
        trimp = np.concatenate([_const_trimp(60), np.zeros(30)])
        atl = compute_atl(trimp)
        ctl = compute_ctl(trimp)
        ctl_drop = (ctl[59] - ctl[-1]) / ctl[59]
        atl_drop = (atl[59] - atl[-1]) / atl[59]
        assert atl_drop > ctl_drop

    def test_length_preserved(self):
        """Output array has the same length as input."""
        assert len(compute_ctl(np.zeros(10))) == 10

    def test_constant_trimp_converges_to_trimp(self):
        """Long constant TRIMP series → CTL converges to TRIMP value."""
        t = 35.0
        ctl = compute_ctl(_const_trimp(500, t))
        assert ctl[-1] == pytest.approx(t, rel=0.01)


@pytest.mark.unit
class TestComputeTsb:
    """Unit tests for compute_tsb()."""

    def test_tsb_equals_ctl_minus_atl(self):
        """TSB must be exactly CTL − ATL element-wise."""
        trimp = _const_trimp(20)
        atl = compute_atl(trimp)
        ctl = compute_ctl(trimp)
        assert np.allclose(compute_tsb(ctl, atl), ctl - atl)

    def test_tsb_negative_during_active_training(self):
        """During a training block ATL > CTL, so TSB < 0."""
        trimp = _const_trimp(20, 60.0)
        atl = compute_atl(trimp)
        ctl = compute_ctl(trimp)
        assert compute_tsb(ctl, atl)[-1] < 0.0

    def test_tsb_rises_during_rest(self):
        """TSB must increase (less negative) during a rest period."""
        trimp = np.concatenate([_const_trimp(30, 50.0), np.zeros(14)])
        atl = compute_atl(trimp)
        ctl = compute_ctl(trimp)
        tsb = compute_tsb(ctl, atl)
        assert tsb[-1] > tsb[29]

    def test_tsb_zero_when_atl_equals_ctl(self):
        """When ATL == CTL arrays, TSB must be 0."""
        arr = np.array([10.0, 20.0])
        assert np.allclose(compute_tsb(arr, arr), 0.0)

    def test_returns_numpy_array(self):
        """Return type must be a numpy ndarray."""
        a = np.array([5.0])
        assert isinstance(compute_tsb(a, a), np.ndarray)


# ======================
# UNIT — TrainingLoad
# ======================


def _make_session(date: str, trimp: float | None = 40.0) -> dict:
    return {
        "date": date,
        "trimp": trimp,
        "duration_min": 60.0,
        "sport_type": "running",
        "notes": None,
    }


@pytest.mark.unit
class TestTrainingLoad:
    """Unit tests for TrainingLoad.from_sessions() and to_dataframe()."""

    def test_from_sessions_empty_returns_empty(self):
        """Empty session list → empty TrainingLoad."""
        tl = TrainingLoad.from_sessions([])
        assert tl.dates == []
        assert len(tl.trimp) == 0

    def test_from_sessions_single_session(self):
        """A single session must produce a one-element series."""
        tl = TrainingLoad.from_sessions([_make_session("2026-01-01", trimp=30.0)])
        assert len(tl.dates) == 1
        assert tl.dates[0] == "2026-01-01"
        assert tl.trimp[0] == pytest.approx(30.0)

    def test_from_sessions_fills_gap_with_zero(self):
        """Sessions 3 days apart produce 3 rows; the gap day has TRIMP=0."""
        sessions = [
            _make_session("2026-01-01", trimp=40.0),
            _make_session("2026-01-03", trimp=30.0),
        ]
        tl = TrainingLoad.from_sessions(sessions)
        assert len(tl.dates) == 3
        assert tl.trimp[1] == pytest.approx(0.0)

    def test_from_sessions_none_trimp_treated_as_zero(self):
        """trimp=None (readiness not yet computed) must be treated as 0."""
        tl = TrainingLoad.from_sessions([_make_session("2026-01-01", trimp=None)])
        assert tl.trimp[0] == pytest.approx(0.0)

    def test_from_sessions_dates_are_consecutive(self):
        """Output dates must form a consecutive daily sequence."""
        from datetime import date, timedelta

        sessions = [
            _make_session("2026-03-01", trimp=30.0),
            _make_session("2026-03-05", trimp=25.0),
        ]
        tl = TrainingLoad.from_sessions(sessions)
        for i, d in enumerate(tl.dates):
            assert d == str(date(2026, 3, 1) + timedelta(days=i))

    def test_from_sessions_tsb_invariant(self):
        """TSB must equal CTL − ATL at every position."""
        sessions = [_make_session(f"2026-01-{d:02d}", trimp=35.0) for d in range(1, 15)]
        tl = TrainingLoad.from_sessions(sessions)
        assert np.allclose(tl.tsb, tl.ctl - tl.atl)

    def test_from_sessions_arrays_same_length_as_dates(self):
        """trimp, atl, ctl, tsb must all have the same length as dates."""
        sessions = [_make_session("2026-02-01"), _make_session("2026-02-10")]
        tl = TrainingLoad.from_sessions(sessions)
        n = len(tl.dates)
        assert len(tl.trimp) == len(tl.atl) == len(tl.ctl) == len(tl.tsb) == n

    def test_from_sessions_custom_tau_affects_atl(self):
        """Custom tau_atl must forward to ATL computation (larger tau → lower ATL)."""
        sessions = [_make_session(f"2026-04-{d:02d}") for d in range(1, 15)]
        tl_default = TrainingLoad.from_sessions(sessions)
        tl_slow = TrainingLoad.from_sessions(sessions, tau_atl=14, tau_ctl=84)
        assert tl_slow.atl[-1] < tl_default.atl[-1]

    def test_to_dataframe_columns(self):
        """DataFrame must have exactly the five expected columns."""
        tl = TrainingLoad.from_sessions([_make_session("2026-01-01")])
        df = tl.to_dataframe()
        assert list(df.columns) == ["date", "trimp", "atl", "ctl", "tsb"]

    def test_to_dataframe_length_matches_date_range(self):
        """DataFrame must have one row per day in the date range."""
        sessions = [_make_session("2026-01-01"), _make_session("2026-01-05")]
        tl = TrainingLoad.from_sessions(sessions)
        assert len(tl.to_dataframe()) == 5

    def test_to_dataframe_empty_has_correct_columns(self):
        """to_dataframe() on empty TrainingLoad must return an empty DataFrame."""
        df = TrainingLoad().to_dataframe()
        assert len(df) == 0
        assert list(df.columns) == ["date", "trimp", "atl", "ctl", "tsb"]

    def test_to_dataframe_tsb_consistent(self):
        """DataFrame TSB column must equal CTL − ATL."""
        sessions = [_make_session(f"2026-05-{d:02d}") for d in range(1, 20)]
        df = TrainingLoad.from_sessions(sessions).to_dataframe()
        assert np.allclose(df["tsb"].values, df["ctl"].values - df["atl"].values)

    # ── Multi-activity aggregation ─────────────────────────────────────────────

    def test_two_activities_same_day_produce_one_date_entry(self):
        """Two activities on the same day collapse to one date in the series."""
        sessions = [
            _make_session("2026-06-01", trimp=30.0),
            _make_session("2026-06-01", trimp=20.0),
        ]
        tl = TrainingLoad.from_sessions(sessions)
        assert tl.dates.count("2026-06-01") == 1

    def test_two_activities_same_day_trimp_is_summed(self):
        """TRIMP for a day with two activities equals their sum."""
        sessions = [
            _make_session("2026-06-01", trimp=30.0),
            _make_session("2026-06-01", trimp=20.0),
        ]
        tl = TrainingLoad.from_sessions(sessions)
        idx = tl.dates.index("2026-06-01")
        assert tl.trimp[idx] == pytest.approx(50.0)

    def test_two_activities_same_day_atl_higher_than_single(self):
        """Summing two activities on one day produces higher ATL than one alone."""
        single = TrainingLoad.from_sessions([_make_session("2026-06-01", trimp=30.0)])
        double = TrainingLoad.from_sessions(
            [
                _make_session("2026-06-01", trimp=30.0),
                _make_session("2026-06-01", trimp=20.0),
            ]
        )
        assert double.atl[-1] > single.atl[-1]

    def test_null_trimp_activity_contributes_zero_to_sum(self):
        """A second activity with trimp=None adds 0 to the day's total."""
        sessions = [
            _make_session("2026-06-01", trimp=40.0),
            _make_session("2026-06-01", trimp=None),
        ]
        tl = TrainingLoad.from_sessions(sessions)
        idx = tl.dates.index("2026-06-01")
        assert tl.trimp[idx] == pytest.approx(40.0)

    def test_mixed_day_does_not_shift_other_dates(self):
        """Multiple activities on one day must not displace neighbouring dates."""
        sessions = [
            _make_session("2026-06-01", trimp=30.0),
            _make_session("2026-06-01", trimp=20.0),
            _make_session("2026-06-03", trimp=40.0),
        ]
        tl = TrainingLoad.from_sessions(sessions)
        assert "2026-06-01" in tl.dates
        assert "2026-06-02" in tl.dates  # gap filled with 0
        assert "2026-06-03" in tl.dates

    def test_gap_day_between_multi_activity_days(self):
        """A rest day between two multi-activity days receives TRIMP=0."""
        sessions = [
            _make_session("2026-06-01", trimp=30.0),
            _make_session("2026-06-01", trimp=20.0),
            _make_session("2026-06-03", trimp=40.0),
        ]
        tl = TrainingLoad.from_sessions(sessions)
        idx = tl.dates.index("2026-06-02")
        assert tl.trimp[idx] == pytest.approx(0.0)


# ======================
# UNIT — _ema (lfilter vectorisation)
# ======================


@pytest.mark.unit
class TestEmaVectorised:
    """Unit tests verifying that the lfilter-based _ema matches the recurrence.

    The old loop: EMA[i] = k * trimp[i] + (1-k) * EMA[i-1], initial = 0.
    The new impl uses scipy.signal.lfilter which is mathematically equivalent.
    These tests protect against regressions from the vectorisation.
    """

    def _loop_ema(self, trimp: np.ndarray, tau: int) -> np.ndarray:
        """Return EMA computed by the original Python loop (reference oracle)."""
        k = 1.0 - math.exp(-1.0 / tau)
        result = np.zeros(len(trimp))
        for i, t in enumerate(trimp):
            prev = result[i - 1] if i > 0 else 0.0
            result[i] = t * k + prev * (1.0 - k)
        return result

    def test_matches_loop_constant_trimp_tau7(self):
        """Lfilter result equals Python loop for constant TRIMP, tau=7."""
        trimp = np.full(30, 40.0)
        assert np.allclose(_ema(trimp, 7), self._loop_ema(trimp, 7))

    def test_matches_loop_constant_trimp_tau42(self):
        """Lfilter result equals Python loop for constant TRIMP, tau=42."""
        trimp = np.full(90, 40.0)
        assert np.allclose(_ema(trimp, 42), self._loop_ema(trimp, 42))

    def test_matches_loop_variable_trimp(self):
        """Lfilter result equals Python loop for random TRIMP series."""
        rng = np.random.default_rng(0)
        trimp = rng.uniform(0, 80, 60)
        assert np.allclose(_ema(trimp, 7), self._loop_ema(trimp, 7))

    def test_matches_loop_sparse_trimp(self):
        """Lfilter result equals Python loop for sparse (mostly-zero) TRIMP."""
        trimp = np.zeros(30)
        trimp[0] = 50.0
        trimp[15] = 70.0
        assert np.allclose(_ema(trimp, 7), self._loop_ema(trimp, 7))

    def test_initial_condition_zero(self):
        """First-day EMA = trimp[0] * k (initial condition = 0)."""
        k = 1.0 - math.exp(-1.0 / 7)
        assert _ema(np.array([50.0]), 7)[0] == pytest.approx(50.0 * k)

    def test_all_zeros_gives_zeros(self):
        """All-zero TRIMP → all-zero EMA."""
        assert np.allclose(_ema(np.zeros(10), 7), 0.0)

    def test_returns_ndarray(self):
        """Return type is numpy ndarray."""
        assert isinstance(_ema(np.array([40.0, 0.0]), 7), np.ndarray)

    def test_length_preserved(self):
        """Output length equals input length."""
        trimp = np.array([10.0, 20.0, 30.0])
        assert len(_ema(trimp, 7)) == 3
