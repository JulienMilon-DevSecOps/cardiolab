"""Tests for cardiolab.visualization._common, shared by the plotting modules."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from cardiolab.protocols.cardiac_coherence import CoherenceResult
from cardiolab.protocols.cardiac_drift import DriftResult
from cardiolab.protocols.hrr import HRRResult
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.protocols.vo2max import VO2maxResult
from cardiolab.signals.rr import RRSeries
from cardiolab.visualization._common import (
    _article,
    check_list,
    check_rr,
    check_type,
    default_labels,
)


@pytest.mark.parametrize(
    ("cls", "article"),
    [
        (RRSeries, "an"),
        (HRRResult, "an"),
        (HRVFeatures, "an"),
        (VO2maxResult, "a"),
        (DriftResult, "a"),
        (CoherenceResult, "a"),
    ],
)
def test_article(cls, article):
    """Same articles as the messages written by hand before v0.11.0."""
    assert _article(cls.__name__) == article


def test_check_type():
    """TypeError with the article and the actual type."""
    with pytest.raises(TypeError, match="result must be an HRRResult, got str"):
        check_type("x", HRRResult, "result")
    check_type(RRSeries([800.0] * 5), RRSeries, "rr")


class TestCheckList:
    """Non-empty list of one type."""

    def test_not_a_list(self):
        """A tuple is refused."""
        with pytest.raises(TypeError, match="features_list must be a list, got tuple"):
            check_list((), HRVFeatures, "features_list")

    def test_empty(self):
        """The class name is in the message."""
        with pytest.raises(
            ValueError, match=r"results must contain at least one DriftResult\."
        ):
            check_list([], DriftResult, "results")

    def test_wrong_item(self):
        """The index of the wrong item is given."""
        with pytest.raises(TypeError, match=r"results\[0\] must be a VO2maxResult"):
            check_list([1], VO2maxResult, "results")


def test_check_rr():
    """Type first, then the number of intervals."""
    with pytest.raises(TypeError, match="rr must be an RRSeries"):
        check_rr([800.0], 10)
    with pytest.raises(ValueError, match="at least 10 intervals, got 5"):
        check_rr(RRSeries([800.0] * 5), 10)
    check_rr(RRSeries([800.0] * 10), 10)


def test_default_labels():
    """Date when there is one, otherwise « Session N »."""
    items = [SimpleNamespace(date="2026-11-13"), SimpleNamespace(date=None)]
    assert default_labels(items) == ["2026-11-13", "Session 2"]
