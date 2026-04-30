"""
FR :
Tests unitaires pour la classe RRSeries.
Ces tests valident la création, les conversions et les métriques de base.

EN :
Unit tests for the RRSeries class.
These tests validate creation, conversions, and basic HRV metrics.
"""

import numpy as np
import pytest

from cardiolab.signals.rr import RRSeries


def test_rrseries_creation():
    """
    FR :
    Vérifie que RRSeries peut être instanciée avec des données valides.

    EN :
    Ensures RRSeries can be instantiated with valid data.
    """
    rr = RRSeries([800, 810, 790])
    assert len(rr) == 3


def test_rrseries_creation_with_timestamp():
    """
    FR :
    Vérifie que RRSeries peut être instanciée avec des données valides avec l'argument timestamp.

    EN :
    Ensures RRSeries can be instantiated with valid datawith timestamp parameter.
    """
    rr = RRSeries(intervals=[800, 810, 790], timestamps=[0.2, 0.4, 0.6])
    assert len(rr) == 3


def test_rrseries_creation_with_timestamp_error():
    """
    FR :
    Vérifie que RRSeries renvoit une erreur si intervals et timestamp sont pas de la même taille.

    EN :
    Ensures RRSeries raise error if intervals and timestamps doesn't have the same size.
    """
    with pytest.raises(ValueError, match="timestamps and intervals must have same size"):
        RRSeries(intervals=[800, 810, 790], timestamps=[0.2, 0.4])


def test_rrseries_invalid_values():
    """
    FR :
    Vérifie qu'une erreur est levée si les intervalles RR sont invalides.

    EN :
    Ensures an error is raised for invalid RR intervals.
    """
    with pytest.raises(ValueError, match="RR intervals RR must be positive"):
        RRSeries([800, -10, 790])

def test_rrseries_one_value():
    """
    FR :
    Vérifie qu'une erreur est levée si les intervalles RR n'ont qu'une valeur.

    EN :
    Ensures an error is raised if RR intervals has only one value.
    """
    with pytest.raises(ValueError, match="RRSeries must contain at least 2 intervals"):
        RRSeries([800])


def test_mean_hr():
    """
    FR :
    Vérifie que la fréquence cardiaque moyenne est correcte.

    EN :
    Ensures mean heart rate is correctly computed.
    """
    rr = RRSeries([1000, 1000, 1000])  # 60 bpm
    assert rr.mean_hr == 60.0


def test_remove_outliers():
    """
    FR :
    Vérifie que les valeurs aberrantes sont supprimées.

    EN :
    Ensures outliers are removed correctly.
    """
    rr = RRSeries([800, 810, 3000, 790])
    clean = rr.remove_outliers()
    assert len(clean) < len(rr)


def test_interpolation():
    """
    FR :
    Vérifie que l'interpolation retourne des séries cohérentes.

    EN :
    Ensures interpolation returns consistent arrays.
    """
    rr = RRSeries([800, 810, 790])
    t, interp = rr.interpolate()
    assert len(t) == len(interp)


def test_from_hr_basic():
    """
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
    """
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
    """
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
    """
    FR :
    Vérifie que des valeurs HR invalides lèvent une erreur.

    EN :
    Ensures invalid HR values raise an error.
    """
    hr = np.array([60.0, 0.0, -10.0])

    with pytest.raises(ValueError):
        RRSeries.from_hr(hr)


def test_from_hr_round_trip():
    """
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
    """
    FR :
    Vérifie que la taille des données est conservée.

    EN :
    Ensures output shape matches input.
    """
    hr = np.array([60.0, 70.0, 80.0, 90.0])

    rr = RRSeries.from_hr(hr)

    assert len(rr) == len(hr)