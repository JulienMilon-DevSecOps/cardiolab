"""Tests of the multivariate anomaly detection (Mahalanobis distance)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.multivariate import (
    DEFAULT_FEATURES,
    MIN_REFERENCE_SESSIONS,
    _squared_distances,
    anomaly_report,
    chi2_threshold,
    is_multivariate_anomaly,
    mahalanobis_distance,
    prediction_threshold,
    robust_covariance,
)
from cardiolab.protocols.resting import HRVFeatures

# Usual mornings: lnRMSSD, mean HR, DFA α1, SD ratio — lnRMSSD and HR negatively
# correlated, DFA α1 and HR positively
_MEAN = np.array([4.0, 55.0, 1.0, 0.45])
_SD = np.array([0.15, 3.0, 0.1, 0.05])
_CORR = np.array(
    [
        [1.0, -0.6, -0.3, 0.4],
        [-0.6, 1.0, 0.4, -0.2],
        [-0.3, 0.4, 1.0, -0.1],
        [0.4, -0.2, -0.1, 1.0],
    ]
)
_COV = _CORR * np.outer(_SD, _SD)
_DAY0 = date(2026, 6, 1)


def _cloud(n: int, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).multivariate_normal(_MEAN, _COV, size=n)


def _session(values, day: date) -> HRVFeatures:
    ln_rmssd, mean_hr, dfa, ratio = (float(v) for v in values)
    return HRVFeatures(
        date=day.isoformat(),
        rmssd=float(np.exp(ln_rmssd)),
        ln_rmssd=ln_rmssd,
        mean_hr=mean_hr,
        dfa_alpha1=dfa,
        sd_ratio=ratio,
    )


def _history(n: int, seed: int = 0) -> list[HRVFeatures]:
    return [
        _session(v, _DAY0 + timedelta(days=i)) for i, v in enumerate(_cloud(n, seed))
    ]


class TestRobustCovariance:
    """robust_covariance(): MCD core, then screened classical estimate."""

    def test_clean_cloud_close_to_truth(self):
        """Without outliers: close to the true mean and covariance."""
        est = robust_covariance(_cloud(2000))
        np.testing.assert_allclose(est.centre, _MEAN, atol=0.02 * np.abs(_MEAN).max())
        np.testing.assert_allclose(np.diag(est.covariance), _SD**2, rtol=0.15)

    def test_outliers_set_aside(self):
        """15 % of sick mornings neither move the centre nor widen the cloud."""
        x = _cloud(200)
        x[:30] += np.array([-0.6, 12.0, -0.4, 0.0])  # low HRV, high HR, low DFA
        est = robust_covariance(x)
        assert not est.support[:30].any()
        assert est.n_used >= 160
        assert abs(est.centre[1] - _MEAN[1]) < 1.0
        assert np.sqrt(est.covariance[1, 1]) < 1.3 * _SD[1]

    def test_reproducible(self):
        """Fixed seed: same result twice."""
        x = _cloud(60)
        a, b = robust_covariance(x, seed=3), robust_covariance(x, seed=3)
        np.testing.assert_array_equal(a.covariance, b.covariance)

    @pytest.mark.parametrize(
        ("data", "match"),
        [
            (np.zeros(5), "2-D"),
            (np.full((10, 2), np.nan), "missing"),
            (np.ones((3, 2)), "At least"),
        ],
    )
    def test_invalid_data(self, data, match):
        """Wrong shape, missing values, too few sessions."""
        with pytest.raises(ValueError, match=match):
            robust_covariance(data)

    def test_constant_metric(self):
        """A metric that never varies: singular covariance."""
        x = _cloud(50)
        x[:, 3] = 0.45
        with pytest.raises(ValueError, match="does not vary"):
            robust_covariance(x)


class TestDistance:
    """mahalanobis_distance() and thresholds."""

    def test_point_at_centre_is_zero(self):
        """A point equal to the mean of the cloud: distance 0."""
        x = _cloud(100)
        assert mahalanobis_distance(x, x.mean(axis=0), robust=False) == pytest.approx(
            0.0
        )

    def test_clear_outlier_beyond_threshold(self):
        """High HR with high HRV — unusual combination, each value plausible alone."""
        x = _cloud(100)
        point = _MEAN + np.array([2.0, 2.0, 0.0, 0.0]) * _SD
        assert mahalanobis_distance(x, point) > prediction_threshold(100, 4)

    def test_correlation_matters(self):
        """Same deviations, but in the usual direction (low HRV, high HR): normal."""
        x = _cloud(100)
        usual = _MEAN + np.array([-2.0, 2.0, 0.0, 0.0]) * _SD
        unusual = _MEAN + np.array([2.0, 2.0, 0.0, 0.0]) * _SD
        assert mahalanobis_distance(x, usual) < mahalanobis_distance(x, unusual)

    def test_shape_mismatch(self):
        """One value per metric is required."""
        with pytest.raises(ValueError, match="one value per column"):
            mahalanobis_distance(_cloud(50), np.zeros(3))

    def test_thresholds(self):
        """F prediction threshold above χ², and tends to it."""
        assert chi2_threshold(4) == pytest.approx(3.338, abs=1e-3)
        assert prediction_threshold(40, 4) == pytest.approx(3.750, abs=1e-3)
        assert prediction_threshold(90, 4) > chi2_threshold(4)
        assert prediction_threshold(100_000, 4) == pytest.approx(
            chi2_threshold(4), abs=1e-3
        )
        with pytest.raises(ValueError):
            prediction_threshold(4, 4)

    def test_false_alarm_rate_calibrated(self):
        """New normal sessions: about 2.5 % above the threshold (40 sessions)."""
        rates = []
        for seed in range(20):
            est = robust_covariance(_cloud(40, seed))
            thr = prediction_threshold(est.n_used, 4)
            new = np.random.default_rng(1000 + seed).multivariate_normal(
                _MEAN, _COV, 2000
            )
            d = np.sqrt(_squared_distances(new, est.centre, est.covariance))
            rates.append(np.mean(d > thr))
        assert 0.01 < np.mean(rates) < 0.06


class TestIsMultivariateAnomaly:
    """is_multivariate_anomaly(): one session against the previous 90 days."""

    def test_normal_session(self):
        """A usual morning is normal."""
        history = _history(80)
        res = is_multivariate_anomaly(
            _session(_MEAN, _DAY0 + timedelta(days=80)), history
        )
        assert res.status == "normal"
        assert not res.is_anomaly
        assert res.distance < res.threshold
        assert res.features == DEFAULT_FEATURES

    def test_anomaly_and_driver(self):
        """High HR with high HRV: anomaly, explained by both metrics."""
        history = _history(80)
        point = _MEAN + np.array([2.5, 3.0, 0.0, 0.0]) * _SD
        res = is_multivariate_anomaly(
            _session(point, _DAY0 + timedelta(days=80)), history
        )
        assert res.is_anomaly
        assert res.main_driver in ("mean_hr", "ln_rmssd")
        assert res.z_scores["mean_hr"] > 2
        assert set(res.to_dict()) >= {"distance", "threshold", "z_mean_hr", "n_used"}

    def test_insufficient_data(self):
        """Fewer than 40 previous sessions."""
        history = _history(MIN_REFERENCE_SESSIONS - 1)
        res = is_multivariate_anomaly(
            _session(_MEAN, _DAY0 + timedelta(days=60)), history
        )
        assert res.status == "insufficient_data"
        assert np.isnan(res.distance)

    def test_only_previous_days_used(self):
        """Later sessions and sessions older than 90 days are not in the reference."""
        history = _history(200)
        res = is_multivariate_anomaly(history[100], history)
        assert res.n_reference == 90

    def test_missing_feature(self):
        """A session without DFA α1 (0.0 = not computed)."""
        current = _session(_MEAN, _DAY0 + timedelta(days=80))
        current.dfa_alpha1 = 0.0
        assert (
            is_multivariate_anomaly(current, _history(80)).status == "missing_features"
        )

    def test_no_variability(self):
        """A metric constant in the reference."""
        history = _history(60)
        for s in history:
            s.sd_ratio = 0.45
        res = is_multivariate_anomaly(
            _session(_MEAN, _DAY0 + timedelta(days=60)), history
        )
        assert res.status == "no_variability"

    def test_custom_threshold_and_baseline(self):
        """Explicit threshold; Baseline accepted."""
        baseline = Baseline.from_features(_history(80))
        res = is_multivariate_anomaly(
            _session(_MEAN, _DAY0 + timedelta(days=80)), baseline, threshold=3.0
        )
        assert res.threshold == 3.0


class TestAnomalyReport:
    """anomaly_report(): one row per session, previous sessions only."""

    def test_columns_and_rows(self):
        """Insufficient at the start, then a distance for each session."""
        pytest.importorskip("pandas")
        history = _history(60)
        sick = _MEAN + np.array([-0.8, 12.0, -0.5, 0.0])  # lnRMSSD −5.3 SD, HR +4 SD
        history.append(_session(sick, _DAY0 + timedelta(days=60)))
        report = anomaly_report(history)
        assert len(report) == 61
        assert list(report.columns[:7]) == [
            "date",
            "zscore",
            "mahalanobis",
            "threshold",
            "is_anomaly",
            "status",
            "main_driver",
        ]
        assert (
            report["status"].iloc[:MIN_REFERENCE_SESSIONS] == "insufficient_data"
        ).all()
        assert report["mahalanobis"].iloc[MIN_REFERENCE_SESSIONS:].notna().all()
        assert bool(report["is_anomaly"].iloc[-1])
        assert report["main_driver"].iloc[-1] == "ln_rmssd"
