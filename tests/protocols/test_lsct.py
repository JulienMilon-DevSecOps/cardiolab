"""Unit tests for the Lamberts submaximal cycle test (LSCT)."""

from __future__ import annotations

from contextlib import nullcontext

import numpy as np
import pytest

from cardiolab.protocols.lsct import (
    LSCTResult,
    compare_lsct,
    lsct,
    lsct_from_records,
)
from cardiolab.signals.rr import PhysiologicalWarning

# ======================
# FIXTURES
# ======================

HR_MAX = 190.0


def _session(
    powers=(120.0, 220.0, 280.0),
    pcts=(60.0, 80.0, 90.0),
    hrr=25.0,
    warmup=300.0,
    recovery=120.0,
    seed=0,
):
    """1-Hz LSCT recording: warm-up, 3 stages at their target HR, seated recovery."""
    rng = np.random.default_rng(seed)
    t_parts, hr_parts, pw_parts = [], [], []
    t = 0.0

    def add(duration, hr, pw):
        nonlocal t
        n = int(duration)
        t_parts.append(t + np.arange(n))
        hr_parts.append(np.full(n, hr, dtype=float) + rng.normal(0, 0.8, n))
        pw_parts.append(np.full(n, pw, dtype=float) + rng.normal(0, 5, n))
        t += n

    add(warmup, 0.55 * HR_MAX, 100.0)
    for pct, pw, duration in zip(pcts, powers, (360, 360, 180), strict=True):
        add(duration, pct / 100 * HR_MAX, pw)
    if recovery:
        n = int(recovery)
        t_parts.append(t + np.arange(n))
        hr_end = pcts[2] / 100 * HR_MAX
        hr_parts.append(hr_end - hrr * np.clip(np.arange(n) / 60.0, 0, 1.5))
        pw_parts.append(np.zeros(n))
    return np.concatenate(t_parts), np.concatenate(hr_parts), np.concatenate(pw_parts)


@pytest.fixture
def result() -> LSCTResult:
    """LSCT of the default session: start after a 5-min warm-up, RPE 3 / 5 / 7."""
    t, hr, pw = _session()
    return lsct(t, hr, pw, HR_MAX, start_sec=300.0, rpe=(3, 5, 7), date="2099-11-06")


# ======================
# ANALYSIS
# ======================


@pytest.mark.unit
class TestLsct:
    """``lsct`` — stages, targets, HRR60."""

    def test_stage_power_and_heart_rate(self, result):
        """Mean power and heart rate of each stage."""
        powers = [s.mean_power for s in result.stages]
        assert powers == pytest.approx([120, 220, 280], abs=2)
        assert result.stage(2).mean_hr == pytest.approx(0.8 * HR_MAX, abs=1)

    def test_targets(self, result):
        """Targets at 60 / 80 / 90 % of HRmax, all reached."""
        assert [s.target_hr for s in result.stages] == pytest.approx([114, 152, 171])
        assert all(s.target_reached for s in result.stages)

    def test_hrr_60(self, result):
        """Heart rate drop 60 s after stage 3."""
        assert result.hrr_60 == pytest.approx(25.0, abs=1.5)

    def test_rpe_and_metadata(self, result):
        """RPE per stage, HRmax, start and date kept."""
        assert [s.rpe for s in result.stages] == [3, 5, 7]
        assert (result.hr_max, result.start_sec, result.date) == (
            HR_MAX,
            300.0,
            "2099-11-06",
        )

    def test_wrong_start_changes_stages(self):
        """start_sec decides where stage 1 begins (warm-up excluded)."""
        t, hr, pw = _session()
        with pytest.warns(PhysiologicalWarning):  # stage 3 lands on stage 2
            res = lsct(t, hr, pw, HR_MAX, start_sec=0.0)
        assert res.stage(1).mean_power < 115  # warm-up at 100 W mixed in

    def test_stage3_target_not_reached_warns(self):
        """HR held at 85 % instead of 90 %: flagged."""
        t, hr, pw = _session(pcts=(60, 80, 85))
        with pytest.warns(PhysiologicalWarning, match="Stage 3 target"):
            res = lsct(t, hr, pw, HR_MAX, start_sec=300.0)
        assert not res.stage(3).target_reached
        assert "stage3_target_not_reached" in res.warnings

    def test_stage_off_target_warns(self):
        """Stage 1 ridden at 70 % instead of 60 %: not comparable."""
        t, hr, pw = _session(pcts=(70, 80, 90))
        with pytest.warns(PhysiologicalWarning, match="Stage 1 held at"):
            res = lsct(t, hr, pw, HR_MAX, start_sec=300.0)
        assert res.warnings == ["stage1_off_target"]

    def test_missing_recovery_warns(self):
        """Recording stopped at the end of stage 3: HRR60 is nan."""
        t, hr, pw = _session(recovery=0)
        with pytest.warns(PhysiologicalWarning, match="HRR60"):
            res = lsct(t, hr, pw, HR_MAX, start_sec=300.0)
        assert np.isnan(res.hrr_60)

    def test_too_short_raises(self):
        """Recording shorter than the three stages: refused."""
        t, hr, pw = _session()
        with pytest.raises(ValueError, match="end of stage 3"):
            lsct(t[:800], hr[:800], pw[:800], HR_MAX, start_sec=300.0)

    def test_invalid_inputs(self):
        """Length mismatch, HRmax not positive, stage without power."""
        t, hr, pw = _session()
        with pytest.raises(ValueError, match="same length"):
            lsct(t, hr[:-1], pw, HR_MAX)
        with pytest.raises(ValueError, match="hr_max"):
            lsct(t, hr, pw, 0)
        pw2 = pw.copy()
        pw2[300:660] = np.nan
        with pytest.raises(ValueError, match="Stage 1"):
            lsct(t, hr, pw2, HR_MAX, start_sec=300.0)

    def test_to_dict_flat(self, result):
        """Flat dict: one key per stage value."""
        d = result.to_dict()
        assert d["stage2_power"] == pytest.approx(220, abs=2)
        assert d["stage3_target_reached"] is True
        assert d["stage1_rpe"] == 3
        assert "hrr_60" in d

    def test_from_records(self):
        """Works on FitRecords-like objects (time, heart rate, power, start)."""
        from datetime import datetime

        t, hr, pw = _session()

        class _Rec:
            time_sec, heart_rate, power = t, hr, pw
            start = datetime(2099, 11, 6, 7, 0)

        res = lsct_from_records(_Rec(), HR_MAX, start_sec=300.0)
        assert res.date == "2099-11-06"
        assert res.stage(3).mean_power == pytest.approx(280, abs=2)


# ======================
# COMPARISON
# ======================


def _test(powers, rpe=(3, 5, 7), pcts=(60, 80, 90)):
    t, hr, pw = _session(powers=powers, pcts=pcts)
    with pytest.warns(PhysiologicalWarning) if pcts[2] < 90 else nullcontext():
        return lsct(t, hr, pw, HR_MAX, start_sec=300.0, rpe=rpe)


@pytest.mark.unit
class TestCompareLsct:
    """``compare_lsct`` — reading the change against previous tests."""

    def test_improving(self):
        """+8 % power, same RPE."""
        cmp = compare_lsct(_test((130, 238, 302)), _test((120, 220, 280)))
        assert cmp.power_change_pct == pytest.approx(8.0, abs=0.5)
        assert cmp.interpretation == "improving"

    def test_fatigue(self):
        """−8 % power."""
        cmp = compare_lsct(_test((110, 202, 258)), _test((120, 220, 280)))
        assert cmp.interpretation == "fatigue_possible"

    def test_overreaching_power_and_rpe_up(self):
        """More power but higher RPE (Decroix et al.)."""
        cmp = compare_lsct(
            _test((130, 238, 302), rpe=(3, 6, 8)), _test((120, 220, 280))
        )
        assert cmp.rpe_change == pytest.approx(1.0)
        assert cmp.interpretation == "overreaching_possible"

    def test_overreaching_target_not_reached(self):
        """Stage 3 target not reached."""
        cmp = compare_lsct(
            _test((120, 220, 280), pcts=(60, 80, 85)), _test((120, 220, 280))
        )
        assert not cmp.target_reached
        assert cmp.interpretation == "overreaching_possible"

    def test_stable_against_mean_of_tests(self):
        """Within 5 % of the mean of several tests."""
        refs = [_test((120, 220, 280)), _test((124, 226, 286))]
        cmp = compare_lsct(_test((122, 224, 284)), refs)
        assert abs(cmp.power_change_pct) < 5
        assert cmp.interpretation == "stable"

    def test_without_rpe(self):
        """RPE not entered: rpe_change is None."""
        cmp = compare_lsct(
            _test((120, 220, 280), rpe=None), _test((120, 220, 280), rpe=None)
        )
        assert cmp.rpe_change is None

    def test_empty_reference(self):
        """An empty list of references is refused."""
        with pytest.raises(ValueError, match="at least one"):
            compare_lsct(_test((120, 220, 280)), [])
