"""Unit tests for the DFA α1 thresholds protocol."""

from __future__ import annotations

import numpy as np
import pytest

from cardiolab.protocols.dfa_thresholds import (
    ALPHA_VT1,
    ALPHA_VT2,
    DFAThresholdsResult,
    _estimate,
    dfa_alpha1_series,
    dfa_thresholds,
)
from cardiolab.signals.rr import PhysiologicalWarning, RRSeries

# ======================
# FIXTURES
# ======================

_GRID = np.round(np.arange(0.0, 1.51, 0.05), 2)


def _fractal_series(n: int, seed: int) -> dict[float, np.ndarray]:
    """Unit-variance series with a power spectrum ∝ 1/f^(2α−1), one per α of the grid.

    All share the same random draw, so cross-fading between neighbouring
    levels changes α smoothly.
    """
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n)
    f[0] = f[1]
    z = rng.normal(size=len(f)) + 1j * rng.normal(size=len(f))
    out = {}
    for a in _GRID:
        x = np.fft.irfft(z / f ** ((2 * a - 1) / 2), n)
        out[float(a)] = x / x.std()
    return out


def _ramp_test(
    minutes: float = 20.0,
    hr0: float = 100.0,
    hr1: float = 185.0,
    a0: float = 1.2,
    a1: float = 0.0,
    seed: int = 1,
) -> np.ndarray:
    """Incremental test: HR rises linearly from hr0 to hr1, target α from a0 to a1."""
    series = _fractal_series(int(minutes * 60 * 3.5), seed)
    rr: list[float] = []
    t, i, total = 0.0, 0, minutes * 60.0
    while t < total:
        p = t / total
        hr = hr0 + (hr1 - hr0) * p
        a = a0 + (a1 - a0) * p
        k = int(np.clip(np.searchsorted(_GRID, a), 1, len(_GRID) - 1))
        lo, hi = float(_GRID[k - 1]), float(_GRID[k])
        w = float(np.clip((a - lo) / (hi - lo), 0.0, 1.0))
        z = (1 - w) * series[lo][i] + w * series[hi][i]
        x = 60_000.0 / hr * (1 + 0.03 * (1 - 0.7 * p) * z)
        rr.append(x)
        t += x / 1000.0
        i += 1
    return np.array(rr)


def _power(minutes: float = 20.0) -> tuple[np.ndarray, np.ndarray]:
    """Power ramp 100 → 400 W sampled at 1 Hz."""
    t = np.arange(0.0, minutes * 60.0, 1.0)
    return t, 100.0 + 300.0 * t / (minutes * 60.0)


@pytest.fixture(scope="module")
def ramp_result() -> DFAThresholdsResult:
    """Thresholds of the default synthetic ramp test, with power."""
    return dfa_thresholds(
        RRSeries(_ramp_test()), intensity=_power(), intensity_unit="W"
    )


# ======================
# TIME-VARYING α1
# ======================


@pytest.mark.unit
class TestDfaAlpha1Series:
    """``dfa_alpha1_series`` — α1 over a sliding 2-min window."""

    def test_window_centres_every_step(self):
        """Centres start half a window in and are step_sec apart."""
        rr = RRSeries(
            np.full(1000, 600.0) + np.random.default_rng(0).normal(0, 10, 1000)
        )
        times, alpha, hr = dfa_alpha1_series(rr)
        assert times[0] == pytest.approx(60.0)
        assert np.allclose(np.diff(times), 5.0)
        assert len(times) == len(alpha) == len(hr)

    def test_white_noise_near_half(self):
        """Uncorrelated intervals give α1 ≈ 0.5."""
        rng = np.random.default_rng(3)
        times, alpha, _ = dfa_alpha1_series(RRSeries(600 + 15 * rng.normal(size=2000)))
        assert np.nanmedian(alpha) == pytest.approx(0.5, abs=0.12)

    def test_correlated_signal_near_one(self):
        """A 1/f signal gives α1 ≈ 1."""
        x = _fractal_series(2000, seed=5)[1.0]
        _, alpha, _ = dfa_alpha1_series(RRSeries(700 + 20 * x))
        assert np.nanmedian(alpha) == pytest.approx(1.0, abs=0.15)

    def test_mean_hr_per_window(self):
        """The window heart rate is 60 000 / mean RR."""
        _, _, hr = dfa_alpha1_series(RRSeries(np.full(600, 500.0)))
        assert np.allclose(hr, 120.0)

    def test_too_short_raises(self):
        """A recording shorter than one window is refused."""
        with pytest.raises(ValueError, match="too short"):
            dfa_alpha1_series(RRSeries(np.full(100, 600.0)))


# ======================
# THRESHOLD DETECTION
# ======================


@pytest.mark.unit
class TestDfaThresholds:
    """``dfa_thresholds`` on synthetic incremental tests."""

    def test_both_thresholds_detected(self, ramp_result):
        """α1 falls from 1.2 to below 0.5: both thresholds are found."""
        assert ramp_result.vt1.detected
        assert ramp_result.vt2.detected
        assert ramp_result.vt1.hr < ramp_result.vt2.hr < ramp_result.hr_peak

    def test_vt1_heart_rate(self, ramp_result):
        """Target α = 0.75 at 37.5 % of the test, i.e. HR ≈ 132 bpm."""
        assert ramp_result.vt1.hr == pytest.approx(132.0, abs=6.0)

    def test_intensity_read_at_threshold_time(self, ramp_result):
        """The power at the threshold is the power of the ramp at that moment."""
        vt1 = ramp_result.vt1
        assert vt1.intensity == pytest.approx(100 + 300 * vt1.time_sec / 1200, abs=5.0)
        assert ramp_result.intensity_unit == "W"

    def test_regression_fit(self, ramp_result):
        """α1 decreases clearly with heart rate around each threshold."""
        assert ramp_result.vt1.r_squared > 0.5
        assert ramp_result.vt1.n_windows * 5 >= 60

    def test_not_reached_without_decline(self):
        """α1 stays near 1: no threshold, nothing extrapolated."""
        res = dfa_thresholds(RRSeries(_ramp_test(minutes=12, a0=1.2, a1=1.0)))
        assert res.vt1.status == "not_reached"
        assert res.vt2.status == "not_reached"
        assert np.isnan(res.vt1.hr)

    def test_recovery_ignored(self, ramp_result):
        """Beats after the peak heart rate (α1 rising again) do not change the result."""
        rng = np.random.default_rng(9)
        recovery = 60_000.0 / np.linspace(180, 110, 300) + rng.normal(0, 5, 300)
        rr = np.concatenate([_ramp_test(), recovery])
        res = dfa_thresholds(RRSeries(rr))
        assert res.vt1.hr == pytest.approx(ramp_result.vt1.hr, abs=1.0)

    def test_without_intensity(self):
        """Without intensity data, thresholds are given in heart rate only."""
        res = dfa_thresholds(RRSeries(_ramp_test(minutes=14)))
        assert res.intensity is None
        assert np.isnan(res.vt1.intensity)

    def test_intensity_length_mismatch(self):
        """Time and values of the intensity must match."""
        with pytest.raises(ValueError, match="same length"):
            dfa_thresholds(
                RRSeries(_ramp_test(minutes=4)),
                intensity=(np.arange(10.0), np.arange(5.0)),
            )

    def test_many_artefacts_warn(self):
        """Above 5 % of corrected beats, the thresholds are flagged."""
        rr = _ramp_test(minutes=10)
        rr[::12] *= 2.0  # one missed beat every 12 beats ≈ 8 %
        with pytest.warns(PhysiologicalWarning, match="corrected"):
            res = dfa_thresholds(RRSeries(rr))
        assert res.quality.artifact_pct > 5.0

    def test_to_dict(self, ramp_result):
        """Scalar results only, JSON-ready."""
        d = ramp_result.to_dict()
        assert d["vt1_status"] == "detected"
        assert d["vt1_hr"] == pytest.approx(ramp_result.vt1.hr)
        assert d["intensity_unit"] == "W"
        assert d["n_windows"] > 0
        assert "quality" in d


@pytest.mark.unit
class TestEstimate:
    """``_estimate`` — guards on the regression."""

    @staticmethod
    def _arrays(alpha):
        alpha = np.asarray(alpha, dtype=float)
        n = len(alpha)
        return np.arange(n) * 5.0, alpha, np.linspace(120, 180, n), np.ones(n, bool)

    def test_too_few_windows_unreliable(self):
        """Less than 60 s of windows in the band: unreliable."""
        times, alpha, hr, valid = self._arrays([1.2] * 20 + [0.9, 0.8, 0.7] + [0.2] * 5)
        est = _estimate(ALPHA_VT1, times, alpha, hr, valid, None, 5.0)
        assert est.status == "unreliable"

    def test_rising_alpha_unreliable(self):
        """α1 increasing with heart rate in the band: unreliable."""
        alpha = [1.2] + list(np.linspace(0.55, 0.95, 30)) + [0.7]
        times, alpha, hr, valid = self._arrays(alpha)
        est = _estimate(ALPHA_VT1, times, alpha, hr, valid, None, 5.0)
        assert est.status == "unreliable"

    def test_exact_linear_decline(self):
        """α1 linear in HR: the threshold HR is exact."""
        hr = np.linspace(120, 180, 61)
        alpha = 1.25 - (hr - 120) / 60  # 0.75 at 150 bpm, 0.5 at 165 bpm
        times = np.arange(61) * 5.0
        valid = np.ones(61, bool)
        vt1 = _estimate(ALPHA_VT1, times, alpha, hr, valid, None, 5.0)
        vt2 = _estimate(ALPHA_VT2, times, alpha, hr, valid, None, 5.0)
        assert vt1.hr == pytest.approx(150.0)
        assert vt2.hr == pytest.approx(165.0)
        assert vt1.r_squared == pytest.approx(1.0)


@pytest.mark.unit
class TestResultZones:
    """``DFAThresholdsResult.zones`` and the maximal heart rate of the test."""

    def test_hr_max_observed(self, ramp_result):
        """The 5-s maximal heart rate is above the 2-min window peak, near 185 bpm."""
        assert ramp_result.hr_max_observed >= ramp_result.hr_peak
        assert ramp_result.hr_max_observed == pytest.approx(185.0, abs=5.0)

    def test_five_zones_from_test(self, ramp_result):
        """Zones anchored on the detected thresholds and the test HRmax."""
        zones = ramp_result.zones()
        assert len(zones) == 5
        assert zones[1].hr_high == pytest.approx(ramp_result.vt1.hr)
        assert zones[2].hr_high == pytest.approx(ramp_result.vt2.hr)
        assert zones[4].hr_high == pytest.approx(ramp_result.hr_max_observed)

    def test_three_zones_with_given_hr_max(self, ramp_result):
        """An HRmax from the profile can replace the test maximum."""
        zones = ramp_result.zones(hr_max=195.0, model=3)
        assert [z.zone for z in zones] == [1, 2, 3]
        assert zones[-1].hr_high == 195.0

    def test_missing_threshold_refused(self):
        """No zones without both thresholds."""
        res = dfa_thresholds(RRSeries(_ramp_test(minutes=12, a0=1.2, a1=1.0)))
        with pytest.raises(ValueError, match="Both thresholds"):
            res.zones()

    def test_bad_model_refused(self, ramp_result):
        """Only the 3- and 5-zone models exist."""
        with pytest.raises(ValueError, match="3 or 5"):
            ramp_result.zones(model=4)
