"""Tests for training adaptation monitoring (issue v0.5.0-01) — cardiolab.analytics.monitoring."""

from __future__ import annotations

import math
from datetime import date, timedelta

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.monitoring import (
    SWCBand,
    baseline_relative_score,
    daily_ln_rmssd,
    dfa_alpha1_score,
    interpret_trend_state,
    ln_rmssd_day_score,
    ln_rmssd_trend_score,
    monitoring_series,
    resting_hr_score,
    rolling_cv,
    rolling_ln_rmssd,
    sd_ratio_score,
    swc_band,
)
from cardiolab.analytics.scoring import readiness_score_multi
from cardiolab.labels import LABELS_FR
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.reporting.monitoring import (
    table_weekly_monitoring,
    weekly_monitoring_rows,
)
from cardiolab.signals.quality import SignalQuality
from cardiolab.visualization.monitoring_plots import plot_ln_rmssd_monitoring

START = date(2026, 1, 5)


def _session(day: int, ln: float, **kw) -> HRVFeatures:
    return HRVFeatures(
        date=(START + timedelta(days=day)).isoformat(),
        rmssd=math.exp(ln),
        ln_rmssd=ln,
        mean_hr=55.0,
        **kw,
    )


def _history(values: dict[int, float]) -> list[HRVFeatures]:
    return [_session(day, ln) for day, ln in sorted(values.items())]


# Known lnRMSSD values: alternating 4.0 / 4.2 every day for 4 weeks
ALTERNATING = {d: 4.0 if d % 2 == 0 else 4.2 for d in range(28)}


@pytest.fixture(autouse=True)
def _close():
    yield
    plt.close("all")


# ======================
# Daily series and rolling statistics — exact values
# ======================


@pytest.mark.unit
class TestRollingStatistics:
    """Exact values on a known history."""

    def test_daily_mean_of_same_day(self):
        """Several sessions on one day → their mean; undated sessions skipped."""
        sessions = [_session(0, 4.0), _session(0, 4.2), HRVFeatures(rmssd=60.0)]
        assert daily_ln_rmssd(sessions) == [(START, pytest.approx(4.1))]

    def test_ln_from_rmssd_when_missing(self):
        """LnRMSSD is derived from RMSSD when the field is empty."""
        s = HRVFeatures(date=START.isoformat(), rmssd=math.e**4)
        assert daily_ln_rmssd([s])[0][1] == pytest.approx(4.0)

    def test_poor_sessions_excluded(self):
        """A Baseline leaves poor sessions out of the daily series."""
        poor = SignalQuality("poor", 9.0, True, 300, 300.0)
        sessions = [_session(0, 4.0), _session(1, 2.0, quality=poor)]
        assert len(daily_ln_rmssd(Baseline.from_features(sessions))) == 1

    def test_rolling_mean_and_cv_exact(self):
        """7-day mean and CV over (d − 7, d] match a direct computation."""
        history = _history(ALTERNATING)
        means = dict(rolling_ln_rmssd(history))
        cvs = dict(rolling_cv(history))
        day = (START + timedelta(days=10)).isoformat()
        window = [ALTERNATING[d] for d in range(4, 11)]
        assert means[day] == pytest.approx(np.mean(window))
        assert cvs[day] == pytest.approx(100 * np.std(window, ddof=1) / np.mean(window))

    def test_fewer_than_three_measures_is_nan(self):
        """Fewer than 3 measurements in the window → nan."""
        history = _history({0: 4.0, 1: 4.1, 9: 4.2})
        means = dict(rolling_ln_rmssd(history))
        assert math.isnan(means[START.isoformat()])
        assert math.isnan(means[(START + timedelta(days=9)).isoformat()])

    def test_gaps_use_calendar_days(self):
        """The window is in calendar days, not in number of sessions."""
        history = _history({0: 4.0, 1: 4.0, 2: 4.0, 20: 5.0, 21: 5.0, 22: 5.0})
        means = dict(rolling_ln_rmssd(history))
        assert means[(START + timedelta(days=22)).isoformat()] == pytest.approx(5.0)

    def test_swc_band_exact(self):
        """SWC band = mean ± 0.5 × SD of the 28 days BEFORE the 7-day window."""
        band = swc_band(_history(ALTERNATING))  # window = days 21..27
        values = [ALTERNATING[d] for d in range(21)]  # baseline = days 0..20
        swc = 0.5 * np.std(values, ddof=1)
        assert band.mean == pytest.approx(np.mean(values))
        assert band.swc == pytest.approx(swc)
        assert (band.low, band.high) == pytest.approx(
            (band.mean - swc, band.mean + swc)
        )
        assert band.n == 21

    def test_swc_band_without_gap(self):
        """window=0 → baseline ending on the day itself (28 days)."""
        band = swc_band(_history(ALTERNATING), window=0)
        assert band.mean == pytest.approx(4.1)
        assert band.n == 28

    def test_evaluated_week_not_in_its_baseline(self):
        """A drop in the last week does not pull its own band down."""
        values = {d: 4.0 if d % 2 == 0 else 4.2 for d in range(28)}
        values |= {d: 3.6 for d in range(28, 35)}
        last = monitoring_series(_history(values))[-1]
        assert last.band.mean == pytest.approx(4.1)
        assert last.state in ("maladaptation", "overreaching_risk")

    def test_swc_band_needs_six_measures(self):
        """Fewer than 6 measurements in the baseline → None."""
        assert swc_band(_history({d: 4.0 + 0.01 * d for d in range(5)})) is None


# ======================
# Interpretation
# ======================


@pytest.mark.unit
class TestInterpretation:
    """Decision grid and states on designed histories."""

    BAND = SWCBand(mean=4.0, swc=0.05, low=3.95, high=4.05, n=28)

    @pytest.mark.parametrize(
        ("mean", "cv", "state"),
        [
            (4.10, 2.0, "coping"),
            (4.00, 2.0, "normal"),
            (3.90, 2.0, "maladaptation"),
            (3.90, 9.0, "overreaching_risk"),
        ],
    )
    def test_grid(self, mean, cv, state):
        """Above / inside / below the band, with or without elevated CV."""
        assert interpret_trend_state(mean, self.BAND, cv, cv_threshold=5.0) == state

    def test_not_assessable(self):
        """No band or no mean → None."""
        assert interpret_trend_state(4.0, None) is None
        assert interpret_trend_state(math.nan, self.BAND) is None

    def test_decline_with_unstable_values(self):
        """Stable month then a drop with large day-to-day swings → overreaching risk."""
        rng = np.random.default_rng(0)
        values = {d: 4.2 + rng.normal(0, 0.03) for d in range(28)}
        values |= {d: 3.9 + (0.25 if d % 2 else -0.25) for d in range(28, 35)}
        assert monitoring_series(_history(values))[-1].state == "overreaching_risk"

    def test_decline_stable_values(self):
        """A steady drop with low variability → maladaptation."""
        rng = np.random.default_rng(1)
        values = {d: 4.2 + rng.normal(0, 0.03) for d in range(28)}
        values |= {d: 4.0 + rng.normal(0, 0.005) for d in range(28, 35)}
        assert monitoring_series(_history(values))[-1].state == "maladaptation"

    def test_rise(self):
        """A sustained rise above the band → coping."""
        rng = np.random.default_rng(2)
        values = {d: 4.0 + rng.normal(0, 0.03) for d in range(28)}
        values |= {d: 4.2 + rng.normal(0, 0.03) for d in range(28, 35)}
        assert monitoring_series(_history(values))[-1].state == "coping"


# ======================
# Readiness trend component
# ======================


@pytest.mark.unit
class TestTrendScore:
    """ln_rmssd_trend_score and its use in readiness_score_multi."""

    def test_neutral_before_two_weeks(self):
        """Neutral (50) without two valid weeks."""
        history = _history({d: 4.0 + 0.01 * d for d in range(9)})
        assert ln_rmssd_trend_score(_session(9, 4.5), history) == 50.0

    def test_neutral_without_date(self):
        """A session without date → 50."""
        assert (
            ln_rmssd_trend_score(HRVFeatures(rmssd=60.0), _history(ALTERNATING)) == 50.0
        )

    def test_exact_value(self):
        """Score = 50 + 50 tanh(|x| − 1) with x = Δ(7-day mean) / SWC."""
        values = {d: 4.0 if d % 2 == 0 else 4.2 for d in range(21)}
        values |= {d: 4.3 if d % 2 == 0 else 4.5 for d in range(21, 28)}
        history = _history(values)
        current = history[-1]
        score = ln_rmssd_trend_score(current, history[:-1])
        now = np.mean([values[d] for d in range(21, 28)])
        before = np.mean([values[d] for d in range(14, 21)])
        swc = 0.5 * np.std(
            [values[d] for d in range(21)], ddof=1
        )  # days before the window
        x = (now - before) / swc
        assert score == pytest.approx(50 + 50 * math.tanh(abs(x) - 1))
        assert score > 90

    def test_within_swc_is_neutral(self):
        """A change smaller than one SWC → exactly 50."""
        history = _history(ALTERNATING)
        assert ln_rmssd_trend_score(history[-1], history[:-1]) == pytest.approx(50.0)

    def test_decline_below_50(self):
        """A sustained decline → below 50."""
        values = {d: 4.0 if d % 2 == 0 else 4.2 for d in range(21)}
        values |= {d: 3.7 if d % 2 == 0 else 3.9 for d in range(21, 28)}
        history = _history(values)
        assert ln_rmssd_trend_score(history[-1], history[:-1]) < 10

    def test_readiness_uses_trend(self):
        """The 20 % trend component moves the readiness score (0.5.0)."""
        rise = {d: 4.0 if d % 2 == 0 else 4.2 for d in range(21)}
        rise |= {d: 4.3 if d % 2 == 0 else 4.5 for d in range(21, 28)}
        history = _history(rise)
        current = history[-1]
        with_trend = readiness_score_multi(
            current, Baseline.from_features(history[:-1])
        )
        undated = HRVFeatures(rmssd=current.rmssd, mean_hr=current.mean_hr)
        neutral = readiness_score_multi(undated, Baseline.from_features(history[:-1]))
        trend = ln_rmssd_trend_score(current, history[:-1])
        assert with_trend - neutral == pytest.approx(0.20 * (trend - 50.0))


# ======================
# Chart and table
# ======================


@pytest.mark.unit
class TestOutputs:
    """plot_ln_rmssd_monitoring and table_weekly_monitoring."""

    def test_plot(self):
        """Figure with two axes (lnRMSSD, CV) and translated legend."""
        fig = plot_ln_rmssd_monitoring(
            Baseline.from_features(_history(ALTERNATING)), labels=LABELS_FR
        )
        assert len(fig.axes) == 2
        legend = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
        assert "Moyenne 7 jours" in legend
        assert "CV 7 jours (%)" in legend

    def test_plot_empty(self):
        """No dated session → ValueError."""
        with pytest.raises(ValueError, match="No dated session"):
            plot_ln_rmssd_monitoring([])

    def test_weekly_rows(self):
        """One row per ISO week, values of the last measurement day."""
        rows = weekly_monitoring_rows(_history(ALTERNATING))
        assert len(rows) == 4
        assert [r["n_measures"] for r in rows] == [7, 7, 7, 7]
        assert rows[-1]["last_date"] == (START + timedelta(days=27)).isoformat()
        assert rows[-1]["state"] == "normal"

    def test_weekly_table_translated(self):
        """States translated and coloured."""
        html = table_weekly_monitoring(
            _history(ALTERNATING), labels=LABELS_FR
        ).to_html()
        assert "Normal" in html
        assert "Semaine" in html


# ======================
# Day components of the readiness score (0.5.0)
# ======================


@pytest.mark.unit
class TestDayComponents:
    """baseline_relative_score, ln_rmssd_day_score, dfa_alpha1_score."""

    REF = [4.0, 4.2] * 5  # mean 4.1, SD ≈ 0.105

    @pytest.mark.parametrize(
        ("sds", "expected"), [(0, 50.0), (0.5, 62.25), (1, 73.11), (2, 88.08)]
    )
    def test_scale(self, sds, expected):
        """+½ SD (1 SWC) → 62, +1 SD → 73, +2 SD → 88."""
        sd = np.std(self.REF, ddof=1)
        score = baseline_relative_score(4.1 + sds * sd, self.REF)
        assert score == pytest.approx(expected, abs=0.01)

    def test_direction_and_neutral(self):
        """Lower-is-better mirrors the score; fewer than 6 values → 50."""
        sd = np.std(self.REF, ddof=1)
        assert baseline_relative_score(4.1 + sd, self.REF, higher_is_better=False) == (
            pytest.approx(100 - 73.11, abs=0.01)
        )
        assert baseline_relative_score(5.0, self.REF[:5]) == 50.0

    def test_sd_floor(self):
        """Identical previous values: the 0.05 SD floor keeps the score finite."""
        assert baseline_relative_score(4.15, [4.1] * 8) == pytest.approx(
            50 + 50 * math.tanh(0.5)
        )

    def test_ln_rmssd_day_score_previous_days_only(self):
        """Reference = the 28 days before today; today's value excluded."""
        history = _history({d: 4.0 if d % 2 == 0 else 4.2 for d in range(30)})
        current = _session(30, 4.1 + np.std([4.0, 4.2] * 14, ddof=1))
        assert ln_rmssd_day_score(current, history) == pytest.approx(73.11, abs=0.2)

    def test_ln_rmssd_day_score_undated(self):
        """Undated session: the last 28 sessions are the reference."""
        sessions = [HRVFeatures(rmssd=math.exp(v)) for v in self.REF]
        assert ln_rmssd_day_score(
            HRVFeatures(rmssd=math.exp(4.1)), sessions
        ) == pytest.approx(50.0)

    def test_dfa_lower_is_better(self):
        """α1 above the usual level → below 50; not computed → 50."""
        history = [_session(d, 4.1, dfa_alpha1=1.0 + 0.02 * (d % 3)) for d in range(10)]
        assert dfa_alpha1_score(_session(10, 4.1, dfa_alpha1=1.3), history) < 50
        assert dfa_alpha1_score(_session(10, 4.1, dfa_alpha1=0.8), history) > 50
        assert dfa_alpha1_score(_session(10, 4.1, dfa_alpha1=0.0), history) == 50.0

    def test_resting_hr_lower_is_better(self):
        """HR vs the previous 28 days in SD units: +1 SD → 27, −1 SD → 73."""
        hrs = [53.0, 57.0] * 5  # SD ≈ 2.1 bpm, above the floor
        history = [_session(d, 4.1) for d in range(10)]
        for s, hr in zip(history, hrs, strict=True):
            s.mean_hr = hr
        sd = np.std(hrs, ddof=1)
        above = _session(10, 4.1)
        above.mean_hr = 55.0 + sd
        below = _session(10, 4.1)
        below.mean_hr = 55.0 - sd
        assert resting_hr_score(above, history) == pytest.approx(26.89, abs=0.01)
        assert resting_hr_score(below, history) == pytest.approx(73.11, abs=0.01)

    def test_resting_hr_floor_and_neutral(self):
        """Identical HRs: 1.5 bpm SD floor; fewer than 6 days → 50."""
        history = [_session(d, 4.1) for d in range(8)]
        current = _session(8, 4.1)
        current.mean_hr = 56.5
        assert resting_hr_score(current, history) == pytest.approx(
            50 - 50 * math.tanh(1.5 / 3.0)
        )
        assert resting_hr_score(current, history[:5]) == 50.0

    def test_readiness_hr_component_is_relative(self):
        """+3 bpm weighs more for a very stable athlete than for a variable one."""
        stable = [_session(d, 4.1) for d in range(10)]
        variable = [_session(d, 4.1) for d in range(10)]
        for i, s in enumerate(variable):
            s.mean_hr = 55.0 + (5.0 if i % 2 else -5.0)
        current = _session(10, 4.1)
        current.mean_hr = 58.0
        assert readiness_score_multi(current, Baseline.from_features(stable)) < (
            readiness_score_multi(current, Baseline.from_features(variable))
        )

    def test_sd_ratio_higher_is_better(self):
        """SD1/SD2 below the usual level → below 50; not computed → 50."""
        history = [_session(d, 4.1, sd_ratio=0.40 + 0.02 * (d % 3)) for d in range(10)]
        assert sd_ratio_score(_session(10, 4.1, sd_ratio=0.30), history) < 50
        assert sd_ratio_score(_session(10, 4.1, sd_ratio=0.50), history) > 50
        assert sd_ratio_score(_session(10, 4.1, sd_ratio=0.0), history) == 50.0
