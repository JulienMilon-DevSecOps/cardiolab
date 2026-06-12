"""Unit tests for the RRSeries class.

FR :
Tests unitaires pour la classe RRSeries.
Ces tests valident la création, les conversions et les métriques de base.
EN :
Unit tests for the RRSeries class.
These tests validate creation, conversions, and basic HRV metrics.
"""

import numpy as np
import pytest

from cardiolab.signals.rr import PhysiologicalWarning, RRSeries


def test_rrseries_creation():
    """Ensure RRSeries can be instantiated with valid data.

    FR :
    Vérifie que RRSeries peut être instanciée avec des données valides.
    EN :
    Ensures RRSeries can be instantiated with valid data.
    """
    rr = RRSeries([800, 810, 790])
    assert len(rr) == 3


def test_rrseries_creation_with_timestamp():
    """Ensure RRSeries can be instantiated with valid datawith timestamp parameter.

    FR :
    Vérifie que RRSeries peut être instanciée avec des données valides avec l'argument timestamp.
    EN :
    Ensures RRSeries can be instantiated with valid datawith timestamp parameter.
    """
    rr = RRSeries(intervals=[800, 810, 790], timestamps=[0.2, 0.4, 0.6])
    assert len(rr) == 3


def test_rrseries_creation_with_timestamp_error():
    """Ensure RRSeries raise error if intervals and timestamps doesn't have the same size.

    FR :
    Vérifie que RRSeries renvoit une erreur si intervals et timestamp sont pas de la même taille.
    EN :
    Ensures RRSeries raise error if intervals and timestamps doesn't have the same size.
    """
    with pytest.raises(
        ValueError, match="timestamps and intervals must have the same length"
    ):
        RRSeries(intervals=[800, 810, 790], timestamps=[0.2, 0.4])


def test_rrseries_invalid_values():
    """Ensure an error is raised for invalid RR intervals.

    FR :
    Vérifie qu'une erreur est levée si les intervalles RR sont invalides.
    EN :
    Ensures an error is raised for invalid RR intervals.
    """
    with pytest.raises(ValueError, match="RR intervals must be positive"):
        RRSeries([800, -10, 790])


def test_rrseries_one_value():
    """Ensure an error is raised if RR intervals has only one value.

    FR :
    Vérifie qu'une erreur est levée si les intervalles RR n'ont qu'une valeur.
    EN :
    Ensures an error is raised if RR intervals has only one value.
    """
    with pytest.raises(ValueError, match="RRSeries must contain at least 2 intervals"):
        RRSeries([800])


def test_mean_hr():
    """Ensure mean heart rate is correctly computed.

    FR :
    Vérifie que la fréquence cardiaque moyenne est correcte.
    EN :
    Ensures mean heart rate is correctly computed.
    """
    rr = RRSeries([1000, 1000, 1000])  # 60 bpm
    assert rr.mean_hr == 60.0


def test_remove_outliers():
    """Ensure outliers are removed correctly.

    FR :
    Vérifie que les valeurs aberrantes sont supprimées.
    EN :
    Ensures outliers are removed correctly.
    """
    rr = RRSeries([800, 810, 3000, 790])
    clean = rr.remove_outliers()
    assert len(clean) < len(rr)


def test_remove_outliers_zscore_constant_series():
    """remove_outliers(zscore) on a constant series (std=0) returns the original unchanged."""
    rr = RRSeries(np.full(50, 800.0))
    result = rr.remove_outliers(method="zscore")
    assert len(result) == 50
    assert np.all(result.intervals == 800.0)


def test_segment_preserves_timestamps():
    """segment() propagates timestamps to every produced segment."""
    intervals = np.full(20, 800.0)
    timestamps = np.cumsum(intervals) / 1000.0
    rr = RRSeries(intervals=intervals, timestamps=timestamps)
    segments = rr.segment(window_sec=8.0)
    assert len(segments) > 0
    for seg in segments:
        assert seg.timestamps is not None
        assert len(seg.timestamps) == len(seg.intervals)


def test_segment_without_timestamps_has_no_timestamps():
    """segment() on a series without timestamps produces segments without timestamps."""
    rr = RRSeries(np.full(20, 800.0))
    segments = rr.segment(window_sec=8.0)
    assert len(segments) > 0
    for seg in segments:
        assert seg.timestamps is None


def test_interpolation():
    """Ensure interpolation returns consistent arrays.

    FR :
    Vérifie que l'interpolation retourne des séries cohérentes.
    EN :
    Ensures interpolation returns consistent arrays.
    """
    rr = RRSeries([800, 810, 790])
    t, interp = rr.interpolate()
    assert len(t) == len(interp)


def test_from_hr_basic():
    """Check that HR → RR conversion works correctly for a simple known value.

    FR :
    Vérifie que la conversion HR → RR fonctionne correctement
    pour une valeur simple.
    EN :
    Checks that HR → RR conversion works correctly
    for a simple known value.
    """
    hr = np.array([60.0, 60.0])  # 60 bpm → 1000 ms
    rr = RRSeries.from_hr(hr)

    assert np.isclose(rr.intervals[0], 1000.0)


def test_from_hr_basic_error():
    """Check that HR → RR put an error with a single value.

    FR :
    Vérifie que la conversion HR → RR renvoi une erreur
    dans le cas d'une valeur unique.
    EN :
    Checks that HR → RR put an error with a single value.
    """
    hr = np.array([60.0])  # 60 bpm → 1000 ms
    with pytest.raises(ValueError, match="RRSeries must contain at least 2 intervals"):
        RRSeries.from_hr(hr)


def test_from_hr_multiple_values():
    """Check conversion for multiple HR values.

    FR :
    Vérifie la conversion pour plusieurs valeurs.
    EN :
    Checks conversion for multiple HR values.
    """
    hr = np.array([60.0, 75.0, 100.0])

    rr = RRSeries.from_hr(hr)

    expected = 60000.0 / hr

    assert np.allclose(rr.intervals, expected)


def test_from_hr_invalid_values():
    """Ensure invalid HR values raise an error.

    FR :
    Vérifie que des valeurs HR invalides lèvent une erreur.
    EN :
    Ensures invalid HR values raise an error.
    """
    hr = np.array([60.0, 0.0, -10.0])

    with pytest.raises(ValueError):
        RRSeries.from_hr(hr)


def test_from_hr_round_trip():
    """Check round-trip consistency HR → RR → HR.

    FR :
    Vérifie la cohérence HR → RR → HR.
    EN :
    Checks round-trip consistency HR → RR → HR.
    """
    hr = np.array([60.0, 80.0, 100.0])

    rr = RRSeries.from_hr(hr)
    hr_back = rr.to_hr()

    assert np.allclose(hr, hr_back)


def test_from_hr_shape():
    """Ensure output shape matches input.

    FR :
    Vérifie que la taille des données est conservée.
    EN :
    Ensures output shape matches input.
    """
    hr = np.array([60.0, 70.0, 80.0, 90.0])

    rr = RRSeries.from_hr(hr)

    assert len(rr) == len(hr)


# ======================
# PhysiologicalWarning
# ======================


class TestPhysiologicalWarning:
    """Tests for physiological bounds validation in RRSeries."""

    def test_no_warning_for_normal_intervals(self):
        """No PhysiologicalWarning for intervals in [300, 2000] ms."""
        with pytest.warns(PhysiologicalWarning) as rec:
            RRSeries([150, 800, 810])  # 150 ms triggers a warning
        assert len(rec) == 1

    def test_clean_series_raises_no_warning(self):
        """Intervals strictly inside physiological bounds raise no warning."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error", PhysiologicalWarning)
            RRSeries([800, 810, 820])  # all normal — must not raise

    def test_warning_on_low_interval(self):
        """An interval below 300 ms triggers PhysiologicalWarning."""
        with pytest.warns(PhysiologicalWarning, match="below 300 ms"):
            RRSeries([200, 800, 810])

    def test_warning_on_high_interval(self):
        """An interval above 2000 ms triggers PhysiologicalWarning."""
        with pytest.warns(PhysiologicalWarning, match="above 2000 ms"):
            RRSeries([800, 810, 2500])

    def test_warning_count_reflects_outlier_count(self):
        """Warning message includes the correct count of suspicious intervals."""
        with pytest.warns(PhysiologicalWarning, match="2 interval"):
            RRSeries([150, 100, 800, 810])

    def test_both_bounds_warn_independently(self):
        """Low and high outliers each produce a separate warning."""
        with pytest.warns(PhysiologicalWarning) as rec:
            RRSeries([200, 800, 2500])
        assert len(rec) == 2

    def test_physiological_warning_is_user_warning(self):
        """PhysiologicalWarning must be a subclass of UserWarning."""
        assert issubclass(PhysiologicalWarning, UserWarning)


# ======================
# Properties
# ======================


class TestRRSeriesProperties:
    """Tests for basic scalar properties of RRSeries."""

    def test_duration(self):
        """Duration returns total recording time in seconds."""
        rr = RRSeries([1000, 1000, 1000])
        assert rr.duration == pytest.approx(3.0)

    def test_mean_rr(self):
        """mean_rr returns the arithmetic mean of intervals in ms."""
        rr = RRSeries([800, 900, 1000])
        assert rr.mean_rr == pytest.approx(900.0)

    def test_min_hr(self):
        """min_hr corresponds to the longest interval."""
        rr = RRSeries([1000, 800, 600])
        assert rr.min_hr == pytest.approx(60.0)  # 60000 / 1000

    def test_max_hr(self):
        """max_hr corresponds to the shortest interval."""
        rr = RRSeries([1000, 800, 600])
        assert rr.max_hr == pytest.approx(100.0)  # 60000 / 600

    def test_min_hr_lt_max_hr(self):
        """min_hr is always less than max_hr for a non-constant series."""
        rr = RRSeries([600, 800, 1000])
        assert rr.min_hr < rr.max_hr


# ======================
# Summary & repr
# ======================


class TestRRSeriesDebug:
    """Tests for summary() and __repr__."""

    def test_summary_keys(self):
        """summary() returns a dict with the four expected keys."""
        rr = RRSeries([800, 810, 790])
        s = rr.summary()
        assert set(s.keys()) == {"n", "duration_s", "mean_rr", "mean_hr"}

    def test_summary_values(self):
        """summary() values are consistent with direct property access."""
        rr = RRSeries([1000, 1000, 1000])
        s = rr.summary()
        assert s["n"] == 3
        assert s["duration_s"] == pytest.approx(3.0)
        assert s["mean_rr"] == pytest.approx(1000.0)
        assert s["mean_hr"] == pytest.approx(60.0)

    def test_repr_contains_n_and_hr(self):
        """__repr__ produces a non-empty string referencing n and mean_hr."""
        rr = RRSeries([1000, 1000, 1000])
        r = repr(rr)
        assert "RRSeries" in r
        assert "n=3" in r
        assert "mean_hr=60.0" in r


# ======================
# interpolate with timestamps
# ======================


def test_interpolate_with_timestamps():
    """interpolate() uses the provided timestamps when available."""
    intervals = np.array([800.0, 810.0, 790.0, 820.0])
    timestamps = np.cumsum(intervals) / 1000.0
    rr = RRSeries(intervals=intervals, timestamps=timestamps)
    t, interp = rr.interpolate()
    assert len(t) == len(interp)
    assert t[0] >= timestamps[0]
    assert t[-1] <= timestamps[-1]


# ======================
# remove_outliers — error branch
# ======================


def test_remove_outliers_unknown_method():
    """remove_outliers raises ValueError for an unknown method."""
    rr = RRSeries([800, 810, 790])
    with pytest.raises(ValueError, match="Method unknown"):
        rr.remove_outliers(method="median")
