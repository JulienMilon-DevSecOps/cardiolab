"""Tests for cardiolab.visualization.dashboard_plots."""

import math

import matplotlib
import numpy as np
import pytest
from matplotlib.figure import Figure

matplotlib.use("Agg")

from cardiolab.protocols.cardiac_coherence import CoherenceResult, cardiac_coherence
from cardiolab.protocols.cardiac_drift import DriftResult
from cardiolab.protocols.hrr import HRRResult
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.protocols.vo2max import VO2maxResult
from cardiolab.signals.rr import RRSeries
from cardiolab.visualization.dashboard_plots import (
    plot_coherence_mini,
    plot_drift_mini,
    plot_hrr_mini,
    plot_longitudinal_heatmap,
    plot_readiness_evolution,
    plot_resting_mini,
    plot_score_evolution,
    plot_session_dashboard,
    plot_vo2max_mini,
)

# ── RR series factories ───────────────────────────────────────────────────────


def _resting_rr(n: int = 300, seed: int = 42) -> RRSeries:
    """Return a synthetic resting RRSeries (≈ 800 ms mean)."""
    rng = np.random.default_rng(seed)
    return RRSeries(rng.normal(800, 45, n).clip(400, 1200))


def _recovery_rr(n: int = 250, seed: int = 7) -> RRSeries:
    """Return a synthetic post-exercise RRSeries recovering from 500 ms to 900 ms."""
    rng = np.random.default_rng(seed)
    trend = np.linspace(500, 900, n)
    noise = rng.normal(0, 20, n)
    return RRSeries(np.clip(trend + noise, 400, 1200))


def _exercise_rr(n: int = 500, seed: int = 13) -> RRSeries:
    """Return a synthetic exercise RRSeries with mild HR drift."""
    rng = np.random.default_rng(seed)
    trend = np.linspace(700, 640, n)
    noise = rng.normal(0, 15, n)
    return RRSeries(np.clip(trend + noise, 400, 1200))


def _coherence_rr(n: int = 300, seed: int = 99) -> RRSeries:
    """Return a synthetic paced-breathing RRSeries at ≈ 0.1 Hz."""
    t = np.linspace(0, n * 0.8, n)
    base = 800.0 + 80.0 * np.sin(2 * math.pi * 0.1 * t)
    rng = np.random.default_rng(seed)
    return RRSeries(np.clip(base + rng.normal(0, 10, n), 400, 1200))


# ── Result factories ──────────────────────────────────────────────────────────


def _make_features(score: float = 55.0, seed: int = 42) -> HRVFeatures:
    """Return an HRVFeatures dataclass with configurable score."""
    return HRVFeatures(
        date="2024-06-01",
        rmssd=45.0,
        ln_rmssd=math.log(45.0),
        sdnn=50.0,
        pnn50=25.0,
        mean_hr=62.0,
        vlf=200.0,
        lf=800.0,
        hf=1200.0,
        lf_hf=0.67,
        hf_pct=55.0,
        lf_nu=40.0,
        hf_nu=60.0,
        hf_hr=None,
        sd1=30.0,
        sd2=65.0,
        sd_ratio=2.17,
        dfa_alpha1=1.05,
        apen=1.2,
        sampen=1.1,
        duration=300.0,
        score=score,
        method="oura",
    )


def _make_hrr_result(hrr_60: float = 22.0, category: str = "good") -> HRRResult:
    """Return a synthetic HRRResult."""
    return HRRResult(
        date="2024-06-01",
        hr_peak=175.0,
        hr_at_60s=175.0 - hrr_60,
        hr_at_120s=175.0 - hrr_60 - 10.0,
        hrr_60=hrr_60,
        hrr_120=hrr_60 + 10.0,
        hrr_60_category=category,
        hrr_120_category=category,
        duration=180.0,
    )


def _make_drift_result(
    drift_rate: float = 1.2, interpretation: str = "mild"
) -> DriftResult:
    """Return a synthetic DriftResult."""
    return DriftResult(
        date="2024-06-01",
        drift_rate=drift_rate,
        drift_magnitude=drift_rate * 5.0,
        r_squared=0.85,
        drift_detected=abs(drift_rate) >= 0.5,
        initial_hr=80.0,
        final_hr=80.0 + drift_rate * 5.0,
        n_windows=6,
        interpretation=interpretation,
        duration=360.0,
    )


def _make_vo2max_result(
    category: str = "good",
    with_uth: bool = True,
) -> VO2maxResult:
    """Return a synthetic VO2maxResult."""
    return VO2maxResult(
        date="2024-06-01",
        vo2max_uth=45.0 if with_uth else float("nan"),
        vo2max_esco_flatt=43.0,
        vo2max_ln_rmssd=44.5,
        hr_rest=58.0,
        hr_max=185.0 if with_uth else float("nan"),
        rmssd_used=42.0,
        ln_rmssd_used=math.log(42.0),
        fitness_category=category,
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def rr_rest() -> RRSeries:
    """Resting RRSeries."""
    return _resting_rr()


@pytest.fixture()
def rr_rec() -> RRSeries:
    """Recovery RRSeries."""
    return _recovery_rr()


@pytest.fixture()
def rr_ex() -> RRSeries:
    """Exercise RRSeries."""
    return _exercise_rr()


@pytest.fixture()
def rr_coh() -> RRSeries:
    """Coherence RRSeries."""
    return _coherence_rr()


@pytest.fixture()
def feats() -> HRVFeatures:
    """HRVFeatures with score=55."""
    return _make_features(score=55.0)


@pytest.fixture()
def hrr_res() -> HRRResult:
    """HRRResult (good category)."""
    return _make_hrr_result()


@pytest.fixture()
def drift_res() -> DriftResult:
    """DriftResult (mild drift)."""
    return _make_drift_result()


@pytest.fixture()
def vo2max_res() -> VO2maxResult:
    """VO2maxResult (good category, with Uth)."""
    return _make_vo2max_result()


@pytest.fixture()
def coherence_res(rr_coh: RRSeries) -> CoherenceResult:
    """CoherenceResult computed from the coherence RRSeries."""
    return cardiac_coherence(rr_coh)


# ── plot_session_dashboard ────────────────────────────────────────────────────


class TestPlotSessionDashboard:
    """Tests for plot_session_dashboard."""

    def test_returns_figure(self, rr_rest: RRSeries, feats: HRVFeatures) -> None:
        """Return a matplotlib Figure."""
        fig = plot_session_dashboard(rr_rest, feats)
        assert isinstance(fig, Figure)

    def test_six_axes(self, rr_rest: RRSeries, feats: HRVFeatures) -> None:
        """Produce exactly 6 axes (2×3 grid)."""
        fig = plot_session_dashboard(rr_rest, feats)
        assert len(fig.axes) == 6

    def test_custom_title(self, rr_rest: RRSeries, feats: HRVFeatures) -> None:
        """Accept and apply a custom suptitle."""
        fig = plot_session_dashboard(rr_rest, feats, title="My Dashboard")
        assert fig.texts[0].get_text() == "My Dashboard"

    def test_custom_figsize(self, rr_rest: RRSeries, feats: HRVFeatures) -> None:
        """Accept and apply a custom figure size."""
        fig = plot_session_dashboard(rr_rest, feats, figsize=(12, 6))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(12.0)
        assert h == pytest.approx(6.0)

    def test_full_data_all_protocols(
        self,
        rr_rest: RRSeries,
        feats: HRVFeatures,
        rr_rec: RRSeries,
        hrr_res: HRRResult,
        rr_ex: RRSeries,
        drift_res: DriftResult,
        vo2max_res: VO2maxResult,
    ) -> None:
        """Accept all optional protocols without error."""
        fig = plot_session_dashboard(
            rr_rest,
            feats,
            rr_recovery=rr_rec,
            hrr_result=hrr_res,
            rr_exercise=rr_ex,
            drift_result=drift_res,
            vo2max_result=vo2max_res,
        )
        assert isinstance(fig, Figure)

    def test_hrr_summary_only(
        self, rr_rest: RRSeries, feats: HRVFeatures, hrr_res: HRRResult
    ) -> None:
        """Show HRR summary panel when only hrr_result (no rr_recovery) provided."""
        fig = plot_session_dashboard(rr_rest, feats, hrr_result=hrr_res)
        assert isinstance(fig, Figure)

    def test_drift_summary_only(
        self, rr_rest: RRSeries, feats: HRVFeatures, drift_res: DriftResult
    ) -> None:
        """Show drift summary panel when only drift_result (no rr_exercise) provided."""
        fig = plot_session_dashboard(rr_rest, feats, drift_result=drift_res)
        assert isinstance(fig, Figure)

    def test_no_protocol_data(self, rr_rest: RRSeries, feats: HRVFeatures) -> None:
        """Show no-data placeholders when no optional protocols provided."""
        fig = plot_session_dashboard(rr_rest, feats)
        assert isinstance(fig, Figure)

    def test_type_error_rr(self, feats: HRVFeatures) -> None:
        """Raise TypeError when rr is not an RRSeries."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_session_dashboard([800] * 300, feats)  # type: ignore[arg-type]

    def test_type_error_features(self, rr_rest: RRSeries) -> None:
        """Raise TypeError when features is not an HRVFeatures."""
        with pytest.raises(TypeError, match="HRVFeatures"):
            plot_session_dashboard(rr_rest, {"score": 55.0})  # type: ignore[arg-type]


# ── plot_longitudinal_heatmap ─────────────────────────────────────────────────


class TestPlotLongitudinalHeatmap:
    """Tests for plot_longitudinal_heatmap."""

    def test_returns_figure(self, feats: HRVFeatures) -> None:
        """Return a matplotlib Figure."""
        fig = plot_longitudinal_heatmap([feats])
        assert isinstance(fig, Figure)

    def test_single_axis(self, feats: HRVFeatures) -> None:
        """Produce at least one axes (plus colorbar)."""
        fig = plot_longitudinal_heatmap([feats])
        assert len(fig.axes) >= 1

    def test_custom_title(self, feats: HRVFeatures) -> None:
        """Accept and apply a custom suptitle."""
        fig = plot_longitudinal_heatmap([feats], title="My Heatmap")
        assert fig.texts[0].get_text() == "My Heatmap"

    def test_custom_figsize(self, feats: HRVFeatures) -> None:
        """Accept and apply a custom figure size."""
        fig = plot_longitudinal_heatmap([feats], figsize=(10, 4))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(10.0)
        assert h == pytest.approx(4.0)

    def test_multi_session_resting_only(self) -> None:
        """Accept multiple sessions with only resting features."""
        feats_list = [_make_features(score=40.0 + i * 10) for i in range(4)]
        fig = plot_longitudinal_heatmap(feats_list)
        assert isinstance(fig, Figure)

    def test_with_all_protocols(
        self, hrr_res: HRRResult, drift_res: DriftResult, vo2max_res: VO2maxResult
    ) -> None:
        """Accept all optional protocol result lists without error."""
        feats_list = [_make_features(score=50.0), _make_features(score=60.0)]
        hrr_list = [_make_hrr_result(hrr_60=22.0), _make_hrr_result(hrr_60=26.0)]
        drift_list = [
            _make_drift_result(drift_rate=1.0),
            _make_drift_result(drift_rate=0.3),
        ]
        vo2max_list = [_make_vo2max_result("good"), _make_vo2max_result("very_good")]
        fig = plot_longitudinal_heatmap(
            feats_list,
            hrr_results=hrr_list,
            drift_results=drift_list,
            vo2max_results=vo2max_list,
        )
        assert isinstance(fig, Figure)

    def test_custom_labels(self, feats: HRVFeatures) -> None:
        """Display custom session labels on y-axis ticks."""
        feats_list = [feats, _make_features(score=70.0)]
        fig = plot_longitudinal_heatmap(feats_list, session_labels=["Day A", "Day B"])
        tick_texts = [t.get_text() for t in fig.axes[0].get_yticklabels()]
        assert "Day A" in tick_texts
        assert "Day B" in tick_texts

    def test_type_error_not_list(self, feats: HRVFeatures) -> None:
        """Raise TypeError when features is not a list."""
        with pytest.raises(TypeError, match="list"):
            plot_longitudinal_heatmap(feats)  # type: ignore[arg-type]

    def test_value_error_empty(self) -> None:
        """Raise ValueError when features is empty."""
        with pytest.raises(ValueError, match="at least one"):
            plot_longitudinal_heatmap([])

    def test_type_error_bad_element(self) -> None:
        """Raise TypeError when a features element is not HRVFeatures."""
        with pytest.raises(TypeError, match="HRVFeatures"):
            plot_longitudinal_heatmap([{"score": 50.0}])  # type: ignore[list-item]

    def test_value_error_length_mismatch(self, feats: HRVFeatures) -> None:
        """Raise ValueError when a protocol list length mismatches features."""
        with pytest.raises(ValueError, match="length"):
            plot_longitudinal_heatmap(
                [feats],
                hrr_results=[_make_hrr_result(), _make_hrr_result()],
            )


# ── plot_readiness_evolution ──────────────────────────────────────────────────


class TestPlotReadinessEvolution:
    """Tests for plot_readiness_evolution."""

    def test_returns_figure(self, feats: HRVFeatures) -> None:
        """Return a matplotlib Figure."""
        fig = plot_readiness_evolution([feats])
        assert isinstance(fig, Figure)

    def test_single_axis(self, feats: HRVFeatures) -> None:
        """Produce exactly one axes."""
        fig = plot_readiness_evolution([feats])
        assert len(fig.axes) == 1

    def test_custom_title(self, feats: HRVFeatures) -> None:
        """Accept and apply a custom suptitle."""
        fig = plot_readiness_evolution([feats], title="My Readiness")
        assert fig.texts[0].get_text() == "My Readiness"

    def test_custom_figsize(self, feats: HRVFeatures) -> None:
        """Accept and apply a custom figure size."""
        fig = plot_readiness_evolution([feats], figsize=(8, 3))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(8.0)
        assert h == pytest.approx(3.0)

    def test_score_line_present(self) -> None:
        """Draw at least one Line2D (score line)."""
        feats_list = [_make_features(score=s) for s in [40.0, 55.0, 70.0]]
        fig = plot_readiness_evolution(feats_list)
        assert len(fig.axes[0].lines) >= 1

    def test_rolling_band_present_when_enough_sessions(self) -> None:
        """Draw a fill_between band when sessions ≥ 3."""
        from matplotlib.collections import PolyCollection

        feats_list = [_make_features(score=s) for s in [40.0, 55.0, 70.0]]
        fig = plot_readiness_evolution(feats_list)
        poly = [c for c in fig.axes[0].collections if isinstance(c, PolyCollection)]
        assert len(poly) >= 1

    def test_custom_labels(self) -> None:
        """Display custom labels on x-axis ticks."""
        feats_list = [_make_features(score=50.0), _make_features(score=65.0)]
        labels = ["Mon", "Tue"]
        fig = plot_readiness_evolution(feats_list, session_labels=labels)
        tick_texts = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert "Mon" in tick_texts
        assert "Tue" in tick_texts

    def test_ylim_zero_to_hundred(self, feats: HRVFeatures) -> None:
        """Y-axis spans 0–100."""
        fig = plot_readiness_evolution([feats])
        lo, hi = fig.axes[0].get_ylim()
        assert lo == pytest.approx(0.0)
        assert hi == pytest.approx(100.0)

    def test_type_error_not_list(self, feats: HRVFeatures) -> None:
        """Raise TypeError when features is not a list."""
        with pytest.raises(TypeError, match="list"):
            plot_readiness_evolution(feats)  # type: ignore[arg-type]

    def test_value_error_empty(self) -> None:
        """Raise ValueError when features is empty."""
        with pytest.raises(ValueError, match="at least one"):
            plot_readiness_evolution([])

    def test_type_error_bad_element(self) -> None:
        """Raise TypeError when a features element is not HRVFeatures."""
        with pytest.raises(TypeError, match="HRVFeatures"):
            plot_readiness_evolution([{"score": 55.0}])  # type: ignore[list-item]

    def test_value_error_labels_mismatch(self, feats: HRVFeatures) -> None:
        """Raise ValueError when labels length mismatches features."""
        with pytest.raises(ValueError, match="labels length"):
            plot_readiness_evolution([feats], session_labels=["A", "B"])


# ── plot_score_evolution ──────────────────────────────────────────────────────


class _ScoreResult:
    """Minimal stand-in for any protocol result carrying .score and .date."""

    def __init__(self, score: float, date: str | None = None) -> None:
        self.score = score
        self.date = date


class TestPlotScoreEvolution:
    """Tests for the generic plot_score_evolution function."""

    def test_returns_figure(self) -> None:
        """Return a matplotlib Figure."""
        fig = plot_score_evolution([_ScoreResult(55.0)])
        assert isinstance(fig, Figure)

    def test_single_axis(self) -> None:
        """Produce exactly one axes."""
        fig = plot_score_evolution([_ScoreResult(55.0)])
        assert len(fig.axes) == 1

    def test_ylim_zero_to_hundred(self) -> None:
        """Y-axis must span exactly [0, 100]."""
        fig = plot_score_evolution([_ScoreResult(70.0)])
        lo, hi = fig.axes[0].get_ylim()
        assert lo == pytest.approx(0.0)
        assert hi == pytest.approx(100.0)

    def test_custom_title(self) -> None:
        """Custom title must be applied as suptitle."""
        fig = plot_score_evolution([_ScoreResult(50.0)], title="My custom title")
        assert fig.texts[0].get_text() == "My custom title"

    def test_default_title_uses_protocol_name(self) -> None:
        """Default title must be '<protocol_name> — Score Evolution'."""
        fig = plot_score_evolution([_ScoreResult(50.0)], protocol_name="HRR")
        assert fig.texts[0].get_text() == "HRR — Score Evolution"

    def test_custom_figsize(self) -> None:
        """Custom figsize must be applied to the figure."""
        fig = plot_score_evolution([_ScoreResult(50.0)], figsize=(10, 4))
        w, h = fig.get_size_inches()
        assert w == pytest.approx(10.0)
        assert h == pytest.approx(4.0)

    def test_score_line_present(self) -> None:
        """The figure must contain at least one Line2D (score line)."""
        results = [_ScoreResult(s) for s in [40.0, 55.0, 70.0]]
        fig = plot_score_evolution(results)
        assert len(fig.axes[0].lines) >= 1

    def test_rolling_band_present_when_enough_sessions(self) -> None:
        """A fill_between band (PolyCollection) must appear when n ≥ _ROLLING_WIN."""
        from matplotlib.collections import PolyCollection

        results = [_ScoreResult(s) for s in [40.0, 55.0, 70.0]]  # n = 3 = _ROLLING_WIN
        fig = plot_score_evolution(results)
        poly = [c for c in fig.axes[0].collections if isinstance(c, PolyCollection)]
        assert len(poly) >= 1

    def test_no_rolling_band_below_threshold(self) -> None:
        """No fill_between band when n < _ROLLING_WIN."""
        from matplotlib.collections import PolyCollection

        results = [_ScoreResult(50.0), _ScoreResult(65.0)]  # n = 2 < _ROLLING_WIN
        fig = plot_score_evolution(results)
        poly = [c for c in fig.axes[0].collections if isinstance(c, PolyCollection)]
        assert len(poly) == 0

    def test_custom_labels(self) -> None:
        """Custom labels must appear on the x-axis ticks."""
        results = [_ScoreResult(50.0), _ScoreResult(60.0)]
        fig = plot_score_evolution(results, session_labels=["Lun", "Mar"])
        tick_texts = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert "Lun" in tick_texts
        assert "Mar" in tick_texts

    def test_fallback_labels_use_date(self) -> None:
        """When labels is None, result.date must be used as the tick label."""
        results = [_ScoreResult(50.0, date="2099-01-01")]
        fig = plot_score_evolution(results)
        tick_texts = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert "2099-01-01" in tick_texts

    def test_fallback_labels_session_n_when_no_date(self) -> None:
        """When result.date is None and labels is None, use 'Session N'."""
        results = [_ScoreResult(50.0, date=None)]
        fig = plot_score_evolution(results)
        tick_texts = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        assert "Session 1" in tick_texts

    def test_works_with_hrr_result(self) -> None:
        """Must accept HRRResult objects with a .score attribute."""
        result = HRRResult(date="2099-01-01", hrr_60=22.0, score=75.0)
        fig = plot_score_evolution([result], protocol_name="HRR")
        assert isinstance(fig, Figure)

    def test_works_with_coherence_result(self) -> None:
        """Must accept CoherenceResult objects with a .score attribute."""
        from cardiolab.protocols.cardiac_coherence import CoherenceResult

        result = CoherenceResult(date="2099-01-01", coherence_score=65.0, score=78.0)
        fig = plot_score_evolution([result], protocol_name="Cohérence")
        assert isinstance(fig, Figure)

    def test_value_error_empty(self) -> None:
        """Raise ValueError when results is empty."""
        with pytest.raises(ValueError, match="at least one"):
            plot_score_evolution([])

    def test_value_error_labels_mismatch(self) -> None:
        """Raise ValueError when labels length mismatches results length."""
        with pytest.raises(ValueError, match="labels length"):
            plot_score_evolution([_ScoreResult(50.0)], session_labels=["A", "B"])


# ── plot_resting_mini ─────────────────────────────────────────────────────────


class TestPlotRestingMini:
    """Tests for plot_resting_mini."""

    def test_returns_figure(self, rr_rest: RRSeries, feats: HRVFeatures) -> None:
        """Return a matplotlib Figure."""
        fig = plot_resting_mini(rr_rest, feats)
        assert isinstance(fig, Figure)

    def test_four_axes(self, rr_rest: RRSeries, feats: HRVFeatures) -> None:
        """Produce exactly 4 axes (2×2 grid)."""
        fig = plot_resting_mini(rr_rest, feats)
        assert len(fig.axes) == 4

    def test_custom_title(self, rr_rest: RRSeries, feats: HRVFeatures) -> None:
        """Accept and apply a custom suptitle."""
        fig = plot_resting_mini(rr_rest, feats, title="My Resting")
        assert fig.texts[0].get_text() == "My Resting"

    def test_tachogram_has_line(self, rr_rest: RRSeries, feats: HRVFeatures) -> None:
        """Top-left panel (tachogram) draws at least one Line2D."""
        fig = plot_resting_mini(rr_rest, feats)
        assert len(fig.axes[0].lines) >= 1

    def test_poincare_has_scatter(self, rr_rest: RRSeries, feats: HRVFeatures) -> None:
        """Top-right panel (Poincaré) draws at least one PathCollection."""
        from matplotlib.collections import PathCollection

        fig = plot_resting_mini(rr_rest, feats)
        dots = [c for c in fig.axes[1].collections if isinstance(c, PathCollection)]
        assert len(dots) >= 1

    def test_type_error_rr(self, feats: HRVFeatures) -> None:
        """Raise TypeError when rr is not an RRSeries."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_resting_mini([800] * 300, feats)  # type: ignore[arg-type]

    def test_type_error_features(self, rr_rest: RRSeries) -> None:
        """Raise TypeError when features is not an HRVFeatures."""
        with pytest.raises(TypeError, match="HRVFeatures"):
            plot_resting_mini(rr_rest, {"score": 55.0})  # type: ignore[arg-type]


# ── plot_hrr_mini ─────────────────────────────────────────────────────────────


class TestPlotHrrMini:
    """Tests for plot_hrr_mini."""

    def test_returns_figure(self, rr_rec: RRSeries, hrr_res: HRRResult) -> None:
        """Return a matplotlib Figure."""
        fig = plot_hrr_mini(rr_rec, hrr_res)
        assert isinstance(fig, Figure)

    def test_two_axes(self, rr_rec: RRSeries, hrr_res: HRRResult) -> None:
        """Produce exactly 2 axes (1×2 grid)."""
        fig = plot_hrr_mini(rr_rec, hrr_res)
        assert len(fig.axes) == 2

    def test_custom_title(self, rr_rec: RRSeries, hrr_res: HRRResult) -> None:
        """Accept and apply a custom suptitle."""
        fig = plot_hrr_mini(rr_rec, hrr_res, title="HRR Mini")
        assert fig.texts[0].get_text() == "HRR Mini"

    def test_curve_has_line(self, rr_rec: RRSeries, hrr_res: HRRResult) -> None:
        """Left panel (curve) draws at least one Line2D."""
        fig = plot_hrr_mini(rr_rec, hrr_res)
        assert len(fig.axes[0].lines) >= 1

    def test_type_error_rr(self, hrr_res: HRRResult) -> None:
        """Raise TypeError when rr is not an RRSeries."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_hrr_mini([500] * 200, hrr_res)  # type: ignore[arg-type]

    def test_type_error_result(self, rr_rec: RRSeries) -> None:
        """Raise TypeError when result is not an HRRResult."""
        with pytest.raises(TypeError, match="HRRResult"):
            plot_hrr_mini(rr_rec, {"hrr_60": 22.0})  # type: ignore[arg-type]


# ── plot_drift_mini ───────────────────────────────────────────────────────────


class TestPlotDriftMini:
    """Tests for plot_drift_mini."""

    def test_returns_figure(self, rr_ex: RRSeries, drift_res: DriftResult) -> None:
        """Return a matplotlib Figure."""
        fig = plot_drift_mini(rr_ex, drift_res)
        assert isinstance(fig, Figure)

    def test_two_axes(self, rr_ex: RRSeries, drift_res: DriftResult) -> None:
        """Produce exactly 2 axes (1×2 grid)."""
        fig = plot_drift_mini(rr_ex, drift_res)
        assert len(fig.axes) == 2

    def test_custom_title(self, rr_ex: RRSeries, drift_res: DriftResult) -> None:
        """Accept and apply a custom suptitle."""
        fig = plot_drift_mini(rr_ex, drift_res, title="Drift Mini")
        assert fig.texts[0].get_text() == "Drift Mini"

    def test_type_error_rr(self, drift_res: DriftResult) -> None:
        """Raise TypeError when rr is not an RRSeries."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_drift_mini([700] * 500, drift_res)  # type: ignore[arg-type]

    def test_type_error_result(self, rr_ex: RRSeries) -> None:
        """Raise TypeError when result is not a DriftResult."""
        with pytest.raises(TypeError, match="DriftResult"):
            plot_drift_mini(rr_ex, {"drift_rate": 1.0})  # type: ignore[arg-type]


# ── plot_vo2max_mini ──────────────────────────────────────────────────────────


class TestPlotVo2maxMini:
    """Tests for plot_vo2max_mini."""

    def test_returns_figure(self, vo2max_res: VO2maxResult) -> None:
        """Return a matplotlib Figure."""
        fig = plot_vo2max_mini(vo2max_res)
        assert isinstance(fig, Figure)

    def test_two_axes(self, vo2max_res: VO2maxResult) -> None:
        """Produce exactly 2 axes (1×2 grid)."""
        fig = plot_vo2max_mini(vo2max_res)
        assert len(fig.axes) == 2

    def test_custom_title(self, vo2max_res: VO2maxResult) -> None:
        """Accept and apply a custom suptitle."""
        fig = plot_vo2max_mini(vo2max_res, title="VO2max Mini")
        assert fig.texts[0].get_text() == "VO2max Mini"

    def test_bars_present(self, vo2max_res: VO2maxResult) -> None:
        """Left panel (comparison) draws at least one bar (Rectangle patch)."""
        fig = plot_vo2max_mini(vo2max_res)
        ax = fig.axes[0]
        assert len(ax.patches) >= 1

    def test_type_error_result(self) -> None:
        """Raise TypeError when result is not a VO2maxResult."""
        with pytest.raises(TypeError, match="VO2maxResult"):
            plot_vo2max_mini({"fitness_category": "good"})  # type: ignore[arg-type]


# ── plot_coherence_mini ───────────────────────────────────────────────────────


class TestPlotCoherenceMini:
    """Tests for plot_coherence_mini."""

    def test_returns_figure(
        self, rr_coh: RRSeries, coherence_res: CoherenceResult
    ) -> None:
        """Return a matplotlib Figure."""
        fig = plot_coherence_mini(rr_coh, coherence_res)
        assert isinstance(fig, Figure)

    def test_two_axes(self, rr_coh: RRSeries, coherence_res: CoherenceResult) -> None:
        """Produce exactly 2 axes (1×2 grid)."""
        fig = plot_coherence_mini(rr_coh, coherence_res)
        assert len(fig.axes) == 2

    def test_custom_title(
        self, rr_coh: RRSeries, coherence_res: CoherenceResult
    ) -> None:
        """Accept and apply a custom suptitle."""
        fig = plot_coherence_mini(rr_coh, coherence_res, title="Coherence Mini")
        assert fig.texts[0].get_text() == "Coherence Mini"

    def test_psd_has_line(
        self, rr_coh: RRSeries, coherence_res: CoherenceResult
    ) -> None:
        """Left panel (PSD) draws at least one Line2D."""
        fig = plot_coherence_mini(rr_coh, coherence_res)
        assert len(fig.axes[0].lines) >= 1

    def test_tachogram_has_line(
        self, rr_coh: RRSeries, coherence_res: CoherenceResult
    ) -> None:
        """Right panel (tachogram) draws at least one Line2D."""
        fig = plot_coherence_mini(rr_coh, coherence_res)
        assert len(fig.axes[1].lines) >= 1

    def test_type_error_rr(self, coherence_res: CoherenceResult) -> None:
        """Raise TypeError when rr is not an RRSeries."""
        with pytest.raises(TypeError, match="RRSeries"):
            plot_coherence_mini([800] * 300, coherence_res)  # type: ignore[arg-type]

    def test_type_error_result(self, rr_coh: RRSeries) -> None:
        """Raise TypeError when result is not a CoherenceResult."""
        with pytest.raises(TypeError, match="CoherenceResult"):
            plot_coherence_mini(rr_coh, {"coherence_score": 75.0})  # type: ignore[arg-type]
