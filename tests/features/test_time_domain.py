"""
FR :
Tests unitaires pour les métriques HRV du domaine temporel.

EN :
Unit tests for time-domain HRV metrics.
"""


from cardiolab.features.time_domain import pnn50, rmssd, sdnn
from cardiolab.signals.rr import RRSeries


def test_rmssd_known_values():
    """
    FR :
    Vérifie que RMSSD est nul pour une série constante.

    EN :
    Ensures RMSSD is zero for a constant RR series.
    """
    rr = RRSeries([1000, 1000, 1000])
    assert rmssd(rr) == 0.0


def test_sdnn_known_values():
    """
    FR :
    Vérifie que SDNN est nul pour une série constante.

    EN :
    Ensures SDNN is zero for a constant RR series.
    """
    rr = RRSeries([1000, 1000, 1000])
    assert sdnn(rr) == 0.0


def test_pnn50_zero():
    """
    FR :
    Vérifie que pNN50 est nul pour une série constante.

    EN :
    Ensures pNN50 is zero for a constant RR series.
    """
    rr = RRSeries([1000, 1000, 1000])
    assert pnn50(rr) == 0.0


def test_pnn50_positive():
    """
    FR :
    Vérifie que pNN50 est positif lorsque les variations sont importantes.

    EN :
    Ensures pNN50 is positive when differences exceed threshold.
    """
    rr = RRSeries([1000, 1100, 1000])
    assert pnn50(rr) > 0


def test_rmssd_positive():
    """
    FR :
    Vérifie que RMSSD est positif pour une série variable.

    EN :
    Ensures RMSSD is positive for a variable RR series.
    """
    rr = RRSeries([800, 810, 790])
    assert rmssd(rr) > 0