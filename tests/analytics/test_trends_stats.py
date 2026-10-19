"""Statistically qualified trends (issue v0.5.0-02) — cardiolab.analytics.trends."""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pytest

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.trends import (
    detect_sustained_decline,
    linear_trend,
    trend_report,
    trend_rmssd,
)
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.signals.quality import SignalQuality

START = date(2026, 1, 5)


def _dated(values, step: int = 1) -> list[tuple[str, float]]:
    return [
        ((START + timedelta(days=i * step)).isoformat(), v)
        for i, v in enumerate(values)
    ]


# ======================
# linear_trend — acceptance criteria
# ======================


@pytest.mark.unit
class TestLinearTrend:
    """Known slope recovered; pure noise not significant."""

    def test_known_slope_exact(self):
        """Y = 50 + 0.5 × day → slope 0.5/day, r² = 1, change = 29 days × 0.5 / mean."""
        values = [50 + 0.5 * d for d in range(30)]
        result = linear_trend(_dated(values))
        assert result.slope == pytest.approx(0.5)
        assert result.intercept == pytest.approx(50.0)
        assert result.r2 == pytest.approx(1.0)
        assert result.p_value < 1e-10
        assert result.change_pct == pytest.approx(100 * 0.5 * 29 / np.mean(values))
        assert result.label == "increasing"
        assert result.significant

    def test_known_slope_with_noise(self):
        """Noisy decline: slope within 0.05 of the truth, labelled decreasing."""
        rng = np.random.default_rng(7)
        values = [60 - 0.4 * d + rng.normal(0, 2) for d in range(60)]
        result = linear_trend(_dated(values))
        assert result.slope == pytest.approx(-0.4, abs=0.05)
        assert result.label == "decreasing"

    @pytest.mark.parametrize("seed", range(5))
    def test_pure_noise_not_significant(self, seed):
        """Pure noise (fixed seeds): p > 0.05, label stable."""
        rng = np.random.default_rng(seed)
        result = linear_trend(_dated(rng.normal(55, 8, 40)))
        assert result.p_value > 0.05
        assert result.label == "stable"

    def test_false_positive_rate(self):
        """Over 300 noise series, about 5 % are significant (alpha = 0.05)."""
        rng = np.random.default_rng(123)
        hits = sum(
            linear_trend(_dated(rng.normal(55, 8, 30))).significant for _ in range(300)
        )
        assert 0.02 < hits / 300 < 0.09

    def test_relative_threshold(self):
        """Significant but tiny (< 5 % of the mean) → stable."""
        values = [100 + 0.01 * d for d in range(60)]  # +0.6 % over the window
        result = linear_trend(_dated(values))
        assert result.significant
        assert result.label == "stable"
        assert linear_trend(_dated(values), min_change_pct=0.5).label == "increasing"

    def test_window_days(self):
        """Only the last window_days days are used."""
        values = [50.0] * 30 + [50 + 2 * d for d in range(10)]
        series = _dated(values)
        assert linear_trend(series, 10).slope == pytest.approx(2.0)
        assert linear_trend(series).slope < 1.0
        assert linear_trend(series, 10, end=series[29][0]).label == "stable"

    def test_calendar_days(self):
        """X is in calendar days: a measure every 2 days halves the daily slope."""
        values = [50 + d for d in range(20)]
        assert linear_trend(_dated(values, step=2)).slope == pytest.approx(0.5)

    def test_plain_values_use_session_index(self):
        """Values without dates → slope per session."""
        assert linear_trend([1.0, 2.0, 3.0, 4.0, 5.0]).slope == pytest.approx(1.0)

    def test_insufficient_and_flat(self):
        """< 5 values → insufficient_data; flat series → stable, p = 1."""
        assert linear_trend(_dated([1.0, 2.0, 3.0])).label == "insufficient_data"
        flat = linear_trend(_dated([50.0] * 10))
        assert (flat.label, flat.slope, flat.p_value) == ("stable", 0.0, 1.0)

    def test_nan_dropped(self):
        """None / nan values are ignored."""
        series = _dated([1.0, math.nan, 2.0, 3.0, 4.0, 5.0, 6.0])
        series[2] = (series[2][0], None)
        assert linear_trend(series).n == 5


# ======================
# detect_sustained_decline
# ======================


@pytest.mark.unit
class TestSustainedDecline:
    """Run of values below mean − 0.5 SD of the reference."""

    def _stable(self, n: int = 20, seed: int = 0) -> list[float]:
        return list(np.random.default_rng(seed).normal(60, 4, n))

    def test_detected(self):
        """5 consecutive low values → detected."""
        result = detect_sustained_decline(self._stable() + [50, 49, 51, 48, 50])
        assert result.detected
        assert result.run_length == 5
        assert result.limit == pytest.approx(
            result.reference_mean - 0.5 * result.reference_sd
        )

    def test_four_not_enough(self):
        """Only 4 low values at the end → not detected."""
        assert not detect_sustained_decline(
            self._stable() + [70, 50, 49, 51, 48]
        ).detected

    def test_recovery_breaks_run(self):
        """A last value back in range → run of 0."""
        result = detect_sustained_decline(self._stable() + [50, 49, 51, 48, 50, 65])
        assert result.run_length == 0
        assert not result.detected

    def test_short_series(self):
        """Fewer than 2 × min_sessions values → not detected."""
        assert not detect_sustained_decline([60, 50, 49, 48, 47, 46]).detected

    def test_dated_series(self):
        """Accepts (date, value) pairs."""
        assert detect_sustained_decline(_dated(self._stable() + [50] * 5)).detected


# ======================
# trend_report and trend_rmssd
# ======================


def _features(values, poor_at=None) -> list[HRVFeatures]:
    poor = SignalQuality("poor", 9.0, True, 300, 300.0)
    return [
        HRVFeatures(
            date=(START + timedelta(days=i)).isoformat(),
            rmssd=v,
            score=v,
            quality=poor if i == poor_at else None,
        )
        for i, v in enumerate(values)
    ]


@pytest.mark.unit
class TestReport:
    """trend_report() and the trend_rmssd() wrapper."""

    def test_columns_and_values(self):
        """One row per session, rolling 7 / 30-day slopes."""
        df = trend_report(_features([50 + d for d in range(40)]))
        assert list(df.columns) == [
            "date",
            "score",
            "slope_7d",
            "slope_30d",
            "change_30d_pct",
            "p_30d",
            "trend_label",
        ]
        assert len(df) == 40
        assert math.isnan(df["slope_7d"].iloc[2])  # fewer than 5 values
        assert df["slope_30d"].iloc[-1] == pytest.approx(1.0)
        assert df["trend_label"].iloc[-1] == "increasing"

    def test_metric_and_poor_excluded(self):
        """Other metric; a Baseline leaves poor sessions out."""
        history = Baseline.from_features(_features([50.0] * 10, poor_at=3))
        df = trend_report(history, metric="rmssd")
        assert "rmssd" in df.columns
        assert len(df) == 9

    def test_trend_rmssd_wrapper(self):
        """Former keys kept; slope per session; new statistics added."""
        result = trend_rmssd(
            Baseline.from_features(_features([50 + 2 * d for d in range(10)]))
        )
        assert result["slope"] == pytest.approx(2.0)
        assert result["trend"] == "increasing"
        assert result["p_value"] < 0.05
        assert result["change_pct"] > 5

    def test_trend_rmssd_noise_is_stable(self):
        """Noise whose slope exceeds the former ±1 ms threshold is no longer a trend."""
        values = list(60 + np.random.default_rng(0).normal(0, 12, 8))
        result = trend_rmssd(Baseline.from_features(_features(values)))
        assert result["slope"] > 1.0  # labelled "increasing" before 0.5.0
        assert result["p_value"] > 0.05
        assert result["trend"] == "stable"
