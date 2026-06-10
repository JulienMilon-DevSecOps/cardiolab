"""Tests for cardiolab.visualization.orthostatic_plots."""

from __future__ import annotations

import numpy as np
import pytest
from matplotlib.figure import Figure

from cardiolab.labels import LABELS_EN, LABELS_FR
from cardiolab.protocols.orthostatic import (
    OrthostaticPhases,
    OrthostaticResult,
    PhaseSegment,
    TransitionSegment,
)
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.signals.rr import RRSeries
from cardiolab.visualization.orthostatic_plots import (
    _default_session_labels,
    _get_phases,
    _safe,
    plot_orthostatic_dual_score_evolution,
    plot_orthostatic_phases_evolution,
)

# ── Factories ─────────────────────────────────────────────────────────────────


def _make_features(rmssd: float = 45.0, mean_hr: float = 62.0) -> HRVFeatures:
    """Return an HRVFeatures instance with default physiological values."""
    return HRVFeatures(
        rmssd=rmssd,
        ln_rmssd=np.log(rmssd),
        sdnn=50.0,
        pnn50=25.0,
        mean_hr=mean_hr,
        vlf=150.0,
        lf=400.0,
        hf=700.0,
        lf_hf=0.57,
        hf_pct=0.52,
        lf_nu=0.36,
        hf_nu=0.60,
        sd1=28.0,
        sd2=65.0,
        sd_ratio=0.43,
        dfa_alpha1=1.0,
        apen=1.1,
        sampen=1.2,
        score=68.0,
        method="welch",
    )


def _make_rr() -> RRSeries:
    """Return a flat 300-interval RRSeries."""
    return RRSeries(intervals=np.full(300, 1000.0))


def _make_result(
    supine_hr: float = 60.0,
    standing_hr: float = 75.0,
    hr_response: float = 15.0,
    interpretation: str = "normal",
    seed: int = 42,
) -> OrthostaticResult:
    """Build a minimal OrthostaticResult with a random supine RMSSD."""
    rng = np.random.default_rng(seed)
    supine_rmssd = float(rng.uniform(35.0, 65.0))
    r = OrthostaticResult(
        phases=OrthostaticPhases(
            supine=PhaseSegment(
                rr=_make_rr(),
                start_sec=0.0,
                end_sec=300.0,
                duration_sec=300.0,
                features=_make_features(rmssd=supine_rmssd, mean_hr=supine_hr),
            ),
            transition=TransitionSegment(
                rr=_make_rr(),
                start_sec=300.0,
                end_sec=360.0,
                duration_sec=60.0,
                delta_hr=hr_response * 0.6,
                peak_hr=supine_hr + hr_response,
                features=_make_features(mean_hr=supine_hr + hr_response * 0.5),
            ),
            standing=PhaseSegment(
                rr=_make_rr(),
                start_sec=360.0,
                end_sec=660.0,
                duration_sec=300.0,
                features=_make_features(rmssd=25.0, mean_hr=standing_hr),
            ),
        ),
        hr_response=hr_response,
        lf_hf_ratio_change=1.4,
        hf_response_pct=35.0,
        hf_hr_pct_change=55.0,
        lf_hr_pct_change=30.0,
        delta_rmssd=supine_rmssd - 25.0,
        interpretation=interpretation,
    )
    r.score = 65.0
    r.date = f"2026-0{seed % 9 + 1}-01"
    return r


def _make_sessions(n: int) -> list[OrthostaticResult]:
    """Return a list of n OrthostaticResult objects."""
    return [_make_result(seed=i + 1) for i in range(n)]


# ── Helpers ───────────────────────────────────────────────────────────────────


class TestGetPhases:
    """Tests for the _get_phases() helper."""

    def test_live_result(self) -> None:
        """OrthostaticResult (has .phases) returns the three phase features."""
        r = _make_result()
        sup, tra, sta = _get_phases(r)
        assert sup.rmssd > 0
        assert tra.mean_hr > 0
        assert sta.rmssd > 0

    def test_record_like(self) -> None:
        """OrthostaticRecord-style object (no .phases, flat attributes)."""

        class FakeRecord:
            supine = _make_features()
            transition_features = _make_features(mean_hr=75.0)
            standing = _make_features(mean_hr=80.0)

        sup, tra, sta = _get_phases(FakeRecord())
        assert sup is FakeRecord.supine


class TestSafe:
    """Tests for the _safe() nan-guard helper."""

    def test_normal_value(self) -> None:
        """Finite float passes through unchanged."""
        assert _safe(42.0) == 42.0

    def test_nan_returns_zero(self) -> None:
        """NaN is replaced with 0.0."""
        assert _safe(float("nan")) == 0.0

    def test_none_returns_zero(self) -> None:
        """None is replaced with 0.0."""
        assert _safe(None) == 0.0  # type: ignore[arg-type]


class TestDefaultSessionLabels:
    """Tests for the _default_session_labels() helper."""

    def test_uses_date_attribute(self) -> None:
        """Uses r.date when present."""
        r = _make_result()
        labels = _default_session_labels([r])
        assert labels[0] == r.date

    def test_fallback_without_date(self) -> None:
        """Falls back to 'Session N' when r.date is absent."""
        r = _make_result()
        del r.date
        labels = _default_session_labels([r])
        assert labels[0] == "Session 1"


# ── plot_orthostatic_phases_evolution ─────────────────────────────────────────


class TestPlotOrthostaticPhasesEvolution:
    """Tests for plot_orthostatic_phases_evolution()."""

    def test_returns_figure(self) -> None:
        """Must return a matplotlib Figure."""
        results = _make_sessions(1)
        fig = plot_orthostatic_phases_evolution(results)
        assert isinstance(fig, Figure)

    def test_two_sessions(self) -> None:
        """Accepted with two sessions."""
        fig = plot_orthostatic_phases_evolution(_make_sessions(2))
        assert isinstance(fig, Figure)

    def test_five_sessions(self) -> None:
        """Accepted with five sessions."""
        fig = plot_orthostatic_phases_evolution(_make_sessions(5))
        assert isinstance(fig, Figure)

    def test_with_labels_fr(self) -> None:
        """Accepted with French labels."""
        fig = plot_orthostatic_phases_evolution(_make_sessions(3), labels=LABELS_FR)
        assert isinstance(fig, Figure)

    def test_with_labels_en(self) -> None:
        """Accepted with English labels."""
        fig = plot_orthostatic_phases_evolution(_make_sessions(3), labels=LABELS_EN)
        assert isinstance(fig, Figure)

    def test_custom_session_labels(self) -> None:
        """Accepted with explicit session_labels."""
        results = _make_sessions(2)
        fig = plot_orthostatic_phases_evolution(results, session_labels=["J-1", "J-2"])
        assert isinstance(fig, Figure)

    def test_custom_title(self) -> None:
        """Accepted with a custom title."""
        fig = plot_orthostatic_phases_evolution(_make_sessions(1), title="Mon titre")
        assert isinstance(fig, Figure)

    def test_custom_figsize(self) -> None:
        """Respects the figsize parameter."""
        fig = plot_orthostatic_phases_evolution(_make_sessions(1), figsize=(10, 7))
        assert fig.get_size_inches()[0] == pytest.approx(10.0)

    def test_empty_raises(self) -> None:
        """Empty results list raises ValueError."""
        with pytest.raises(ValueError, match="at least one item"):
            plot_orthostatic_phases_evolution([])

    def test_session_labels_length_mismatch_raises(self) -> None:
        """Mismatched session_labels length raises ValueError."""
        with pytest.raises(ValueError, match="session_labels length"):
            plot_orthostatic_phases_evolution(
                _make_sessions(2), session_labels=["only_one"]
            )

    def test_four_axes(self) -> None:
        """Figure must have at least 4 Axes."""
        fig = plot_orthostatic_phases_evolution(_make_sessions(2))
        assert len(fig.axes) >= 4


# ── plot_orthostatic_dual_score_evolution ─────────────────────────────────────


class TestPlotOrthostaticDualScoreEvolution:
    """Tests for plot_orthostatic_dual_score_evolution()."""

    def _readiness(self, n: int, base: float = 55.0) -> list[float]:
        """Generate n readiness scores around base."""
        rng = np.random.default_rng(0)
        return list(np.clip(rng.normal(base, 8.0, n), 0.0, 100.0))

    def test_returns_figure(self) -> None:
        """Must return a matplotlib Figure."""
        results = _make_sessions(2)
        fig = plot_orthostatic_dual_score_evolution(results, self._readiness(2))
        assert isinstance(fig, Figure)

    def test_three_sessions_rolling_mean(self) -> None:
        """Rolling mean is drawn when n >= 3."""
        results = _make_sessions(3)
        fig = plot_orthostatic_dual_score_evolution(results, self._readiness(3))
        assert isinstance(fig, Figure)

    def test_seven_sessions(self) -> None:
        """Accepted with seven sessions."""
        results = _make_sessions(7)
        fig = plot_orthostatic_dual_score_evolution(results, self._readiness(7))
        assert isinstance(fig, Figure)

    def test_with_labels_fr(self) -> None:
        """Accepted with French labels."""
        results = _make_sessions(3)
        fig = plot_orthostatic_dual_score_evolution(
            results, self._readiness(3), labels=LABELS_FR
        )
        assert isinstance(fig, Figure)

    def test_with_labels_en(self) -> None:
        """Accepted with English labels."""
        results = _make_sessions(3)
        fig = plot_orthostatic_dual_score_evolution(
            results, self._readiness(3), labels=LABELS_EN
        )
        assert isinstance(fig, Figure)

    def test_custom_session_labels(self) -> None:
        """Accepted with explicit session_labels."""
        results = _make_sessions(2)
        fig = plot_orthostatic_dual_score_evolution(
            results, self._readiness(2), session_labels=["S1", "S2"]
        )
        assert isinstance(fig, Figure)

    def test_custom_title(self) -> None:
        """Accepted with a custom title."""
        results = _make_sessions(2)
        fig = plot_orthostatic_dual_score_evolution(
            results, self._readiness(2), title="Test titre"
        )
        assert isinstance(fig, Figure)

    def test_default_title_uses_label(self) -> None:
        """Default title is derived from the labels dict."""
        results = _make_sessions(2)
        fig = plot_orthostatic_dual_score_evolution(
            results, self._readiness(2), labels=LABELS_FR
        )
        assert isinstance(fig, Figure)

    def test_custom_figsize(self) -> None:
        """Respects the figsize parameter."""
        results = _make_sessions(2)
        fig = plot_orthostatic_dual_score_evolution(
            results, self._readiness(2), figsize=(10, 6)
        )
        assert fig.get_size_inches()[0] == pytest.approx(10.0)

    def test_two_axes(self) -> None:
        """Figure must have exactly 2 Axes (readiness + autonomic)."""
        results = _make_sessions(2)
        fig = plot_orthostatic_dual_score_evolution(results, self._readiness(2))
        assert len(fig.axes) == 2

    def test_low_readiness_scores(self) -> None:
        """Accepted with scores below the normal zone."""
        results = _make_sessions(3)
        fig = plot_orthostatic_dual_score_evolution(results, [20.0, 30.0, 25.0])
        assert isinstance(fig, Figure)

    def test_high_readiness_scores(self) -> None:
        """Accepted with scores in the excellent zone."""
        results = _make_sessions(3)
        fig = plot_orthostatic_dual_score_evolution(results, [80.0, 85.0, 90.0])
        assert isinstance(fig, Figure)

    def test_empty_results_raises(self) -> None:
        """Empty results list raises ValueError."""
        with pytest.raises(ValueError, match="at least one item"):
            plot_orthostatic_dual_score_evolution([], [])

    def test_readiness_length_mismatch_raises(self) -> None:
        """Mismatched readiness_scores length raises ValueError."""
        results = _make_sessions(3)
        with pytest.raises(ValueError, match="readiness_scores length"):
            plot_orthostatic_dual_score_evolution(results, [50.0, 55.0])

    def test_session_labels_length_mismatch_raises(self) -> None:
        """Mismatched session_labels length raises ValueError."""
        results = _make_sessions(2)
        with pytest.raises(ValueError, match="session_labels length"):
            plot_orthostatic_dual_score_evolution(
                results, self._readiness(2), session_labels=["only_one"]
            )

    def test_score_attribute_missing_defaults_zero(self) -> None:
        """Missing .score attribute defaults to 0 without raising."""
        results = _make_sessions(2)
        for r in results:
            del r.score
        fig = plot_orthostatic_dual_score_evolution(results, self._readiness(2))
        assert isinstance(fig, Figure)

    def test_all_zone_colors_readiness(self) -> None:
        """Cover all five readiness colour zones."""
        results = _make_sessions(5)
        readiness = [20.0, 40.0, 50.0, 60.0, 75.0]
        fig = plot_orthostatic_dual_score_evolution(results, readiness)
        assert isinstance(fig, Figure)

    def test_all_zone_colors_autonomic(self) -> None:
        """Cover all three autonomic dot colours."""
        results = _make_sessions(3)
        for r, score in zip(results, [15.0, 50.0, 80.0], strict=True):
            r.score = score
        fig = plot_orthostatic_dual_score_evolution(results, self._readiness(3))
        assert isinstance(fig, Figure)
