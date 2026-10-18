"""Accuracy of the spectral estimators (issue v0.4.0-02) — known synthetic spectra."""

from __future__ import annotations

import numpy as np
import pytest

from cardiolab.datasets import load_sample
from cardiolab.features.frequency_domain import (
    VLF_MIN_DURATION_SEC,
    _ar_psd,
    _interpolate,
    _lomb_psd,
    _welch_psd,
    frequency_domain,
)
from cardiolab.signals.rr import RRSeries

METHODS = ("welch", "ar", "lomb")

# Two sinusoids: 40 ms at 0.10 Hz (LF) and 25 ms at 0.25 Hz (HF).
# Expected band power = amplitude² / 2 → LF 800 ms², HF 312.5 ms².
LF_FREQ, LF_AMP = 0.10, 40.0
HF_FREQ, HF_AMP = 0.25, 25.0


def _synthetic(duration: float = 300.0, seed: int = 0, noise: float = 3.0) -> RRSeries:
    """RR series whose values follow two sinusoids of the beat time (uneven sampling)."""
    rng = np.random.default_rng(seed)
    rr, t = [], 0.0
    while t < duration:
        v = (
            900
            + LF_AMP * np.sin(2 * np.pi * LF_FREQ * t)
            + HF_AMP * np.sin(2 * np.pi * HF_FREQ * t)
            + rng.normal(0, noise)
        )
        rr.append(v)
        t += v / 1000.0
    return RRSeries(np.asarray(rr))


def _psd(rr: RRSeries, method: str) -> tuple[np.ndarray, np.ndarray]:
    if method == "lomb":
        return _lomb_psd(rr)
    _, signal = _interpolate(rr, 4.0)
    if method == "welch":
        return _welch_psd(signal, 4.0)
    return _ar_psd(signal, 4.0, order=16)


def _peak(freqs: np.ndarray, psd: np.ndarray, low: float, high: float) -> float:
    mask = (freqs >= low) & (freqs < high)
    return float(freqs[mask][np.argmax(psd[mask])])


# ======================
# Acceptance criteria
# ======================


@pytest.mark.unit
class TestKnownSpectrum:
    """Peaks and band powers of a known spectrum are recovered by every method."""

    @pytest.mark.parametrize("method", METHODS)
    def test_peaks_within_0_005_hz(self, method):
        """LF and HF peaks found within ±0.005 Hz of 0.10 and 0.25 Hz."""
        freqs, psd = _psd(_synthetic(), method)
        assert _peak(freqs, psd, 0.04, 0.15) == pytest.approx(LF_FREQ, abs=0.005)
        assert _peak(freqs, psd, 0.15, 0.40) == pytest.approx(HF_FREQ, abs=0.005)

    @pytest.mark.parametrize("method", METHODS)
    def test_band_powers_match_theory(self, method):
        """LF ≈ 800 ms² and HF ≈ 312.5 ms² within 10 %; VLF ≈ 0."""
        result = frequency_domain(_synthetic(), method=method)
        assert result["LF"] == pytest.approx(LF_AMP**2 / 2, rel=0.10)
        assert result["HF"] == pytest.approx(HF_AMP**2 / 2, rel=0.10)
        assert result["VLF"] < 0.02 * result["TP"]

    @pytest.mark.parametrize("method", ["welch", "lomb"])
    def test_parseval(self, method):
        """Integrated PSD equals the variance of the RR series within 10 %."""
        rr = _synthetic()
        freqs, psd = _psd(rr, method)
        assert np.trapezoid(psd, freqs) == pytest.approx(np.var(rr.intervals), rel=0.10)

    @pytest.mark.parametrize("seed", range(5))
    def test_methods_agree(self, seed):
        """Welch, AR and Lomb-Scargle give LF/HF within 15 % of each other."""
        rr = _synthetic(seed=seed, noise=8.0)
        ratios = [frequency_domain(rr, method=m)["LF_HF"] for m in METHODS]
        assert max(ratios) / min(ratios) < 1.15


def _random_spectrum(duration: float, seed: int) -> tuple[RRSeries, dict]:
    """RR series with known band powers spread over many random-phase sinusoids.

    VLF 1 500 ms² (flat), LF 1 200 ms² (centred on 0.10 Hz), HF 600 ms²
    (centred on 0.25 Hz), sampled at the beat times.
    """
    rng = np.random.default_rng(seed)
    bands = [
        (0.005, 0.04, 1500.0, None),
        (0.04, 0.15, 1200.0, 0.10),
        (0.15, 0.40, 600.0, 0.25),
    ]
    comps = []
    for low, high, power, centre in bands:
        f = np.linspace(low, high, 60)[:-1] + (high - low) / 120
        w = np.exp(-(((f - centre) / 0.03) ** 2)) if centre else np.ones_like(f)
        comps.append(
            (f, np.sqrt(2 * power * w / w.sum()), rng.uniform(0, 2 * np.pi, len(f)))
        )
    rr, t = [], 0.0
    while t < duration:
        v = 900 + sum(np.sum(a * np.sin(2 * np.pi * f * t + p)) for f, a, p in comps)
        v += rng.normal(0, 5)
        rr.append(v)
        t += v / 1000.0
    return RRSeries(np.asarray(rr)), {"LF": 1200.0, "HF": 600.0}


@pytest.mark.unit
class TestDefaultMethod:
    """Why Lomb-Scargle is the default: bias and variability on 5-minute recordings."""

    @staticmethod
    def _lf_hf_errors(method: str) -> np.ndarray:
        ratios = []
        for seed in range(30):
            rr, true = _random_spectrum(300.0, seed)
            ratios.append(
                frequency_domain(rr, method=method)["LF_HF"] / (true["LF"] / true["HF"])
            )
        return np.asarray(ratios)

    def test_default_is_lomb(self):
        """frequency_domain() uses Lomb-Scargle by default."""
        rr = _synthetic()
        assert frequency_domain(rr) == frequency_domain(rr, method="lomb")

    def test_lomb_unbiased_and_stable(self):
        """Lomb LF/HF: median within 10 % of the truth, dispersion below 20 %."""
        r = self._lf_hf_errors("lomb")
        assert np.median(r) == pytest.approx(1.0, abs=0.10)
        assert np.std(r) / np.mean(r) < 0.20

    def test_lomb_more_stable_than_welch(self):
        """On 5 minutes, Welch (single 256 s window) disperses more than Lomb."""
        lomb, welch = self._lf_hf_errors("lomb"), self._lf_hf_errors("welch")
        assert np.std(lomb) / np.mean(lomb) < np.std(welch) / np.mean(welch)

    def test_ar_biased_upwards(self):
        """AR (order 16) overestimates LF/HF — VLF leaks into LF."""
        assert np.median(self._lf_hf_errors("ar")) > 1.05


# ======================
# Parameters and flags
# ======================


@pytest.mark.unit
class TestParameters:
    """window_sec, VLF_reliable and method validation."""

    def test_vlf_reliable_flag(self):
        """VLF flagged unreliable below 5 minutes."""
        assert not frequency_domain(_synthetic(duration=200))["VLF_reliable"]
        long = _synthetic(duration=VLF_MIN_DURATION_SEC + 10)
        assert frequency_domain(long)["VLF_reliable"]

    def test_window_sets_resolution(self):
        """A 256 s window at 4 Hz gives a 1/256 Hz resolution."""
        _, signal = _interpolate(_synthetic(), 4.0)
        freqs, _ = _welch_psd(signal, 4.0, window_sec=256.0)
        assert freqs[1] - freqs[0] == pytest.approx(1 / 256)
        freqs_short, _ = _welch_psd(signal, 4.0, window_sec=64.0)
        assert freqs_short[1] - freqs_short[0] == pytest.approx(1 / 64)

    def test_window_sec_parameter(self):
        """window_sec is passed through frequency_domain()."""
        rr = _synthetic()
        short = frequency_domain(rr, method="welch", window_sec=64.0)
        assert short != frequency_domain(rr, method="welch")

    def test_unknown_method(self):
        """Unknown method → ValueError."""
        with pytest.raises(ValueError, match="Unknown method"):
            frequency_domain(_synthetic(), method="fft")

    def test_flat_signal_ar(self):
        """A constant signal gives a zero AR spectrum, not numerical noise."""
        _, psd = _ar_psd(np.full(1200, 850.0), 4.0, order=16)
        assert np.all(psd == 0)


# ======================
# Real recordings
# ======================


@pytest.mark.unit
class TestRealSamples:
    """Author's Polar H10 recordings (cardiolab.datasets)."""

    @pytest.mark.parametrize("method", METHODS)
    def test_lf_hf_plausible(self, method):
        """Corrected resting recordings give finite, positive LF/HF for every method."""
        rr, _ = load_sample("resting", 0).correct_artifacts()
        result = frequency_domain(rr, method=method)
        assert result["LF"] > 0
        assert result["HF"] > 0
        assert 0.2 < result["LF_HF"] < 10
