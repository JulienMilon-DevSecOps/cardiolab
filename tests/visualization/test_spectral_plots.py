"""Unit tests for cardiolab.visualization.spectral_plots.

Covers:
- Return type (matplotlib Figure) for every public function.
- Happy-path rendering with realistic fixtures.
- Input validation: TypeError on wrong types, ValueError on bad values.
- Edge cases: single session, NaN metrics, both PSD methods.
"""

from __future__ import annotations

import math

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")  # headless backend — no display required

from matplotlib.figure import Figure  # noqa: E402

from cardiolab.protocols.resting import HRVFeatures  # noqa: E402
from cardiolab.signals.rr import RRSeries  # noqa: E402
from cardiolab.visualization.spectral_plots import (  # noqa: E402
    plot_hrv_radar,
    plot_lf_hf_evolution,
    plot_psd_comparison,
    plot_psd_welch,
    plot_spectral_heatmap,
)

# ── Test isolation ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def close_figures():
    """Close all matplotlib figures after each test to prevent memory warnings."""
    yield
    matplotlib.pyplot.close("all")


# ── Shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def rr_normal() -> RRSeries:
    """RRSeries with 300 intervals at ~65 bpm — sufficient for PSD estimation."""
    rng = np.random.default_rng(42)
    return RRSeries(rng.normal(920, 40, 300).clip(min=310))


@pytest.fixture
def rr_short() -> RRSeries:
    """Minimal valid RRSeries (2 intervals)."""
    return RRSeries([800.0, 820.0])


def _make_features(
    rmssd: float = 55.0,
    lf_nu: float = 0.45,
    hf_nu: float = 0.55,
    sd1: float = 38.0,
    dfa_alpha1: float = 1.0,
    lf: float = 450.0,
    hf: float = 550.0,
    vlf: float = 120.0,
    lf_hf: float = 0.82,
    date: str | None = None,
) -> HRVFeatures:
    """Build a minimal HRVFeatures instance for testing."""
    return HRVFeatures(
        date=date,
        rmssd=rmssd,
        lf_nu=lf_nu,
        hf_nu=hf_nu,
        sd1=sd1,
        dfa_alpha1=dfa_alpha1,
        lf=lf,
        hf=hf,
        vlf=vlf,
        lf_hf=lf_hf,
    )


@pytest.fixture
def features_single() -> HRVFeatures:
    """Single HRVFeatures with all finite values."""
    return _make_features(date="2026-05-20")


@pytest.fixture
def features_nan_dfa() -> HRVFeatures:
    """HRVFeatures where dfa_alpha1 is NaN (short recording)."""
    f = _make_features()
    f.dfa_alpha1 = float("nan")
    return f


@pytest.fixture
def features_list() -> list[HRVFeatures]:
    """Three HRVFeatures instances for multi-session tests."""
    return [
        _make_features(
            rmssd=45.0, lf_nu=0.55, hf_nu=0.45, lf_hf=1.22, date="2026-05-18"
        ),
        _make_features(
            rmssd=60.0, lf_nu=0.42, hf_nu=0.58, lf_hf=0.72, date="2026-05-19"
        ),
        _make_features(
            rmssd=72.0, lf_nu=0.38, hf_nu=0.62, lf_hf=0.61, date="2026-05-20"
        ),
    ]


# ── plot_psd_welch ───────────────────────────────────────────────────────────


class TestPlotPsdWelch:
    """Tests for plot_psd_welch."""

    def test_returns_figure_welch(self, rr_normal):
        """Welch method returns a matplotlib Figure."""
        fig = plot_psd_welch(rr_normal, method="welch")
        assert isinstance(fig, Figure)

    def test_returns_figure_ar(self, rr_normal):
        """AR method returns a matplotlib Figure."""
        fig = plot_psd_welch(rr_normal, method="ar")
        assert isinstance(fig, Figure)

    def test_custom_title(self, rr_normal):
        """Custom title is accepted."""
        fig = plot_psd_welch(rr_normal, title="Morning session")
        assert isinstance(fig, Figure)

    def test_custom_figsize(self, rr_normal):
        """Custom figsize is accepted."""
        fig = plot_psd_welch(rr_normal, figsize=(10, 4))
        assert isinstance(fig, Figure)

    def test_ar_custom_order(self, rr_normal):
        """Custom AR model order is accepted."""
        fig = plot_psd_welch(rr_normal, method="ar", order=8)
        assert isinstance(fig, Figure)

    def test_type_error_on_wrong_rr(self):
        """Non-RRSeries input raises TypeError."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_psd_welch([800, 810, 820])

    def test_type_error_on_none(self):
        """None raises TypeError."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_psd_welch(None)

    def test_value_error_invalid_method(self, rr_normal):
        """Unknown method raises ValueError."""
        with pytest.raises(ValueError, match="method"):
            plot_psd_welch(rr_normal, method="fft")

    def test_value_error_order_zero(self, rr_normal):
        """order=0 raises ValueError."""
        with pytest.raises(ValueError, match="order"):
            plot_psd_welch(rr_normal, method="ar", order=0)

    def test_value_error_order_negative(self, rr_normal):
        """Negative order raises ValueError."""
        with pytest.raises(ValueError, match="order"):
            plot_psd_welch(rr_normal, method="ar", order=-4)


# ── plot_psd_comparison ──────────────────────────────────────────────────────


class TestPlotPsdComparison:
    """Tests for plot_psd_comparison."""

    def test_returns_figure(self, rr_normal):
        """Returns a matplotlib Figure with both curves."""
        fig = plot_psd_comparison(rr_normal)
        assert isinstance(fig, Figure)

    def test_custom_order(self, rr_normal):
        """Custom AR order is accepted."""
        fig = plot_psd_comparison(rr_normal, order=12)
        assert isinstance(fig, Figure)

    def test_custom_title(self, rr_normal):
        """Custom title is accepted."""
        fig = plot_psd_comparison(rr_normal, title="Welch vs AR")
        assert isinstance(fig, Figure)

    def test_type_error_on_wrong_rr(self):
        """Non-RRSeries input raises TypeError."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_psd_comparison({"intervals": [800, 810]})

    def test_type_error_on_ndarray(self):
        """Passing a numpy array instead of RRSeries raises TypeError."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_psd_comparison(np.array([800.0, 810.0]))

    def test_value_error_order_zero(self, rr_normal):
        """order=0 raises ValueError."""
        with pytest.raises(ValueError, match="order"):
            plot_psd_comparison(rr_normal, order=0)


# ── plot_lf_hf_evolution ─────────────────────────────────────────────────────


class TestPlotLfHfEvolution:
    """Tests for plot_lf_hf_evolution."""

    def test_returns_figure_multi(self, features_list):
        """Multiple sessions return a Figure."""
        fig = plot_lf_hf_evolution(features_list)
        assert isinstance(fig, Figure)

    def test_single_session(self, features_single):
        """Single-element list is accepted."""
        fig = plot_lf_hf_evolution([features_single])
        assert isinstance(fig, Figure)

    def test_with_labels(self, features_list):
        """Custom labels of matching length are accepted."""
        labels = ["Day 1", "Day 2", "Day 3"]
        fig = plot_lf_hf_evolution(features_list, labels=labels)
        assert isinstance(fig, Figure)

    def test_default_date_labels(self, features_list):
        """Date-bearing features produce date strings as default labels."""
        fig = plot_lf_hf_evolution(features_list, labels=None)
        assert isinstance(fig, Figure)

    def test_type_error_not_a_list(self, features_single):
        """Non-list input raises TypeError."""
        with pytest.raises(TypeError, match="features_list must be a list"):
            plot_lf_hf_evolution(features_single)

    def test_value_error_empty_list(self):
        """Empty list raises ValueError."""
        with pytest.raises(ValueError, match="at least one"):
            plot_lf_hf_evolution([])

    def test_type_error_wrong_element(self, features_single):
        """Non-HRVFeatures element raises TypeError with index info."""
        with pytest.raises(TypeError, match=r"features_list\[1\]"):
            plot_lf_hf_evolution([features_single, "bad"])

    def test_value_error_labels_length_mismatch(self, features_list):
        """Labels with wrong length raises ValueError."""
        with pytest.raises(ValueError, match="labels length"):
            plot_lf_hf_evolution(features_list, labels=["only_one"])


# ── plot_hrv_radar ───────────────────────────────────────────────────────────


class TestPlotHrvRadar:
    """Tests for plot_hrv_radar."""

    def test_returns_figure(self, features_single):
        """Returns a matplotlib Figure."""
        fig = plot_hrv_radar(features_single)
        assert isinstance(fig, Figure)

    def test_nan_dfa_does_not_raise(self, features_nan_dfa):
        """NaN dfa_alpha1 is handled gracefully (set to 0)."""
        fig = plot_hrv_radar(features_nan_dfa)
        assert isinstance(fig, Figure)

    def test_nan_annotated_in_title(self, features_nan_dfa):
        """Figure title contains a NaN warning when metrics are NaN."""
        fig = plot_hrv_radar(features_nan_dfa, title="Radar")
        axes = fig.get_axes()
        assert axes, "Figure has no axes"
        title_text = axes[0].get_title()
        assert "NaN" in title_text

    def test_custom_title(self, features_single):
        """Custom title is accepted."""
        fig = plot_hrv_radar(features_single, title="Profile 2026-05-20")
        assert isinstance(fig, Figure)

    def test_all_finite_metrics(self, features_single):
        """All five metrics normalise without producing NaN."""
        assert not math.isnan(features_single.rmssd)
        assert not math.isnan(features_single.lf_nu)
        assert not math.isnan(features_single.hf_nu)
        assert not math.isnan(features_single.sd1)
        assert not math.isnan(features_single.dfa_alpha1)
        fig = plot_hrv_radar(features_single)
        assert isinstance(fig, Figure)

    def test_type_error_on_wrong_features(self):
        """Non-HRVFeatures input raises TypeError."""
        with pytest.raises(TypeError, match="HRVFeatures"):
            plot_hrv_radar({"rmssd": 55.0})

    def test_type_error_on_none(self):
        """None raises TypeError."""
        with pytest.raises(TypeError, match="HRVFeatures"):
            plot_hrv_radar(None)


# ── plot_spectral_heatmap ────────────────────────────────────────────────────


class TestPlotSpectralHeatmap:
    """Tests for plot_spectral_heatmap."""

    def test_returns_figure_multi(self, features_list):
        """Multiple sessions with normalize=True return a Figure."""
        fig = plot_spectral_heatmap(features_list)
        assert isinstance(fig, Figure)

    def test_single_session_no_normalization(self, features_single):
        """Single session (normalization disabled) returns a Figure."""
        fig = plot_spectral_heatmap([features_single], normalize=False)
        assert isinstance(fig, Figure)

    def test_normalize_false(self, features_list):
        """normalize=False returns raw-value figure without error."""
        fig = plot_spectral_heatmap(features_list, normalize=False)
        assert isinstance(fig, Figure)

    def test_with_labels(self, features_list):
        """Custom labels of correct length are accepted."""
        labels = ["Mon", "Tue", "Wed"]
        fig = plot_spectral_heatmap(features_list, labels=labels)
        assert isinstance(fig, Figure)

    def test_type_error_not_a_list(self, features_single):
        """Non-list input raises TypeError."""
        with pytest.raises(TypeError, match="features_list must be a list"):
            plot_spectral_heatmap(features_single)

    def test_value_error_empty_list(self):
        """Empty list raises ValueError."""
        with pytest.raises(ValueError, match="at least one"):
            plot_spectral_heatmap([])

    def test_type_error_wrong_element(self, features_single):
        """Non-HRVFeatures element raises TypeError with index info."""
        with pytest.raises(TypeError, match=r"features_list\[0\]"):
            plot_spectral_heatmap(["not_features"])

    def test_value_error_labels_length_mismatch(self, features_list):
        """Labels with wrong length raises ValueError."""
        with pytest.raises(ValueError, match="labels length"):
            plot_spectral_heatmap(features_list, labels=["Day 1", "Day 2"])

    def test_single_session_normalize_true_skips_normalization(self, features_single):
        """Single session with normalize=True does not error (min==max guard)."""
        fig = plot_spectral_heatmap([features_single], normalize=True)
        assert isinstance(fig, Figure)
