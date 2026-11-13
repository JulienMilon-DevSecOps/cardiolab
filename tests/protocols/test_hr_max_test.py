"""Tests of the HRmax field test, observed HRmax and the profile proposal."""

from __future__ import annotations

import math
import warnings
from datetime import datetime

import numpy as np
import pytest

from cardiolab.analytics.hr_max import (
    held_heart_rate,
    observed_hr_max,
    propose_hr_max_update,
    round_bpm,
    sustained_peak,
)
from cardiolab.protocols.hr_max_test import hr_max_test


def _test_session(
    peak: float = 188.0,
    final_sec: int = 180,
    spike_at: int | None = None,
    seed: int = 0,
):
    """Olympiatoppen session, second by second; the last repetition holds ``peak``.

    15 min warm-up, 2 × (3 min + 2 min jog), then the last repetition rising to
    ``peak`` and holding it for its last 40 s (when ``final_sec`` ≥ 60), then a
    walk.
    """
    rng = np.random.default_rng(seed)
    hr: list[float] = list(np.linspace(110, 140, 900))
    for top in (168.0, 179.0):
        hr += list(top - (top - 150) * np.exp(-np.arange(180) / 40))
        hr += list(np.linspace(top, 140, 120))
    rise = max(final_sec - 40, 1)
    hr += list(np.linspace(150, peak, rise)) + [peak] * min(40, final_sec)
    hr += list(np.maximum(110, peak - 0.4 * np.arange(1, 301)))
    values = np.asarray(hr) + rng.normal(0, 0.6, len(hr))
    if spike_at is not None:
        values[spike_at] = 205.0
    return np.arange(len(values), dtype=float), values


# ======================
# Sustained peak
# ======================


class TestSustainedPeak:
    """Highest heart rate held 5 s."""

    def test_plateau_found(self):
        """A 40-s plateau at 188 bpm: found within 1 bpm."""
        t, hr = _test_session()
        peak = sustained_peak(t, hr)
        assert peak.hr_max == pytest.approx(188.0, abs=1.0)
        assert not peak.isolated_spike

    def test_one_second_spike_ignored(self):
        """A 1-s spike at 205 bpm is not retained, but reported."""
        t, hr = _test_session(spike_at=1500)
        peak = sustained_peak(t, hr)
        assert peak.hr_max == pytest.approx(188.0, abs=1.0)
        assert peak.raw_max == 205.0
        assert peak.isolated_spike

    def test_four_seconds_not_enough(self):
        """Held 4 s at 200 bpm: not counted; held 5 s: counted."""
        t = np.arange(120, dtype=float)
        base = np.full(120, 150.0)
        four, six = base.copy(), base.copy()
        four[60:64] = 200.0
        six[60:65] = 200.0
        assert np.nanmax(held_heart_rate(t, four)) == 150.0
        assert np.nanmax(held_heart_rate(t, six)) == 200.0

    def test_implausible_and_dropouts(self):
        """Values outside 30–230 bpm and missing samples are skipped."""
        t = np.arange(60, dtype=float)
        hr = np.full(60, 160.0)
        hr[10] = 250.0
        hr[20:25] = np.nan
        assert sustained_peak(t, hr).hr_max == 160.0
        assert math.isnan(sustained_peak(t[:3], hr[:3]).hr_max)


# ======================
# Field test
# ======================


class TestHRMaxTest:
    """Olympiatoppen field test: value, criteria, status."""

    def test_valid_test(self):
        """Chest strap, long final effort, plateau → valid, 188 bpm."""
        t, hr = _test_session()
        res = hr_max_test(
            t, hr, sport="Course à pied", sensor="chest_strap", date="2026-09-02"
        )
        assert res.hr_max == pytest.approx(188.0, abs=1.0)
        assert res.sport == "running"
        assert res.final_effort_sec >= 60
        assert res.plateau_reached
        assert (res.status, res.warnings) == ("valid", [])
        assert res.can_update_profile
        assert set(res.to_dict()) >= {"hr_max", "sport", "status", "sensor"}

    def test_short_final_effort(self):
        """A 30-s final burst: doubtful, not proposed for the profile."""
        t, hr = _test_session(final_sec=30)
        with pytest.warns(UserWarning, match="Final effort"):
            res = hr_max_test(t, hr, sport="running", sensor="chest_strap")
        assert res.status == "doubtful"
        assert not res.can_update_profile

    def test_optical_sensor_invalid(self):
        """Wrist sensor: invalid."""
        t, hr = _test_session()
        with pytest.warns(UserWarning, match="chest strap"):
            res = hr_max_test(t, hr, sport="running", sensor="optical")
        assert res.status == "invalid"

    def test_sensor_not_given(self):
        """No sensor: a reminder, still valid."""
        t, hr = _test_session()
        with pytest.warns(UserWarning, match="needs a chest strap"):
            res = hr_max_test(t, hr, sport="cycling")
        assert res.status == "valid"

    def test_spike_reported(self):
        """The 205-bpm spike is reported, the value stays 188."""
        t, hr = _test_session(spike_at=1500)
        with pytest.warns(UserWarning, match="spike at 205"):
            res = hr_max_test(t, hr, sport="running", sensor="chest_strap")
        assert res.hr_max == pytest.approx(188.0, abs=1.0)

    def test_from_fit_records(self):
        """FitRecords: sport and date read from the file."""
        from cardiolab.sensors_tools.garmin import FitRecords

        t, hr = _test_session()
        nan = np.full(len(t), np.nan)
        records = FitRecords(
            start=datetime(2026, 9, 2, 8, 0),
            time_sec=t,
            heart_rate=hr,
            power=nan,
            cadence=nan,
            speed=nan,
            sport="running",
        )
        res = hr_max_test(records=records, sensor="chest_strap")
        assert (res.date, res.sport) == ("2026-09-02", "running")
        assert res.hr_max == pytest.approx(188.0, abs=1.0)

    def test_errors(self):
        """No series, unknown sensor, unknown sport, no plausible heart rate."""
        t, hr = _test_session()
        with pytest.raises(ValueError, match="time_sec and heart_rate"):
            hr_max_test()
        with pytest.raises(ValueError, match="Unknown sensor"):
            hr_max_test(t, hr, sensor="ear")
        with pytest.raises(ValueError):
            hr_max_test(t, hr, sport="runing")
        with pytest.raises(ValueError, match="plausible"):
            hr_max_test(t, np.full(len(t), 300.0), sensor="chest_strap")


# ======================
# Observed HRmax
# ======================


class TestObservedHRMax:
    """Highest heart rate held 5 s in the sessions, per sport."""

    def test_per_sport(self):
        """Running and cycling kept apart; the highest session per sport."""
        t, hr = _test_session()
        sessions = [
            {
                "time_sec": t,
                "heart_rate": hr - 10,
                "sport": "running",
                "date": "2026-08-01",
            },
            {
                "time_sec": t,
                "heart_rate": hr,
                "sport": "running",
                "date": "2026-09-06",
                "session_id": "10k",
            },
            {
                "time_sec": t,
                "heart_rate": hr - 8,
                "sport": "cycling",
                "date": "2026-09-07",
            },
        ]
        best = observed_hr_max(sessions)
        assert best["running"].hr_max == pytest.approx(188.0, abs=1.0)
        assert (best["running"].date, best["running"].session_id) == (
            "2026-09-06",
            "10k",
        )
        assert best["cycling"].hr_max == pytest.approx(180.0, abs=1.0)
        assert set(observed_hr_max(sessions, sport="cycling")) == {"cycling"}

    def test_spike_not_observed(self):
        """A session whose only high value is a 1-s spike adds nothing."""
        t = np.arange(600, dtype=float)
        hr = np.full(600, 150.0)
        hr[300] = 210.0
        assert (
            observed_hr_max([{"time_sec": t, "heart_rate": hr}])["other"].hr_max
            == 150.0
        )

    def test_optical_flag(self):
        """Optical sessions flagged, or left out on demand."""
        t, hr = _test_session()
        sessions = [
            {"time_sec": t, "heart_rate": hr, "sport": "running", "optical": True}
        ]
        assert observed_hr_max(sessions)["running"].optical
        assert observed_hr_max(sessions, include_optical=False) == {}


# ======================
# Profile proposal
# ======================


class TestProposal:
    """Never applied, never lowered; what changes is listed."""

    def test_higher_value(self):
        """185 → 189: proposed, with zones, LSCT targets, VO2max, reprocessing."""
        p = propose_hr_max_update(
            185,
            189,
            source="field_test",
            current_source="provided",
            hr_rest=56,
            load_method="banister",
        )
        assert p.propose and p.candidate == 189
        c = p.changes
        assert c["zone5_top"] == {"old": 185, "new": 189}
        assert c["lsct_targets"] == {"old": [111, 148, 167], "new": [113, 151, 170]}
        assert c["vo2max_uth"] == {"old": 50.5, "new": 51.6}
        assert c["reprocess_load"] is True
        assert c["lsct_comparable"] is False
        assert c["general_zones"]["new"][-1] == (174, 189)

    def test_lower_value_not_proposed(self):
        """182 under a provided 185: not proposed, profile to change by hand."""
        p = propose_hr_max_update(
            185, 182, source="observed", current_source="provided"
        )
        assert not p.propose
        assert "never lowered" in p.reason
        assert p.changes == {}

    def test_replaces_prediction_or_empty(self):
        """A measured value replaces an age prediction, even lower; or an empty profile."""
        assert propose_hr_max_update(
            190, 184, source="field_test", current_source="tanaka"
        ).propose
        p = propose_hr_max_update(None, 184, source="observed")
        assert p.propose and p.changes["lsct_targets"]["old"] is None
        assert "vo2max_uth" not in p.changes

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"source": "lab"}, "source"),
            ({"source": "observed", "current_source": "guess"}, "hr_max_source"),
            ({"source": "observed", "candidate": 260}, "plausible"),
        ],
    )
    def test_errors(self, kwargs, match):
        """Unknown sources, implausible value."""
        candidate = kwargs.pop("candidate", 189)
        with pytest.raises(ValueError, match=match):
            propose_hr_max_update(185, candidate, **kwargs)

    def test_round_half_up(self):
        """166.5 → 167 (Python's round gives 166)."""
        assert round_bpm(166.5) == 167
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert round_bpm(110.9) == 111
