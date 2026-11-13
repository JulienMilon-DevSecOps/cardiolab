"""Tests for cardiolab.reporting._core helpers shared by the table modules."""

from __future__ import annotations

import pytest

from cardiolab.reporting._core import validate_list


class _Item:
    """Stand-in result type."""


class TestValidateList:
    """Non-empty list of one type, same messages as before v0.11.0."""

    def test_not_a_list(self) -> None:
        """TypeError when the argument is not a list."""
        with pytest.raises(TypeError, match="results must be a list, got str"):
            validate_list("not a list", _Item, "results")

    def test_empty(self) -> None:
        """ValueError on an empty list."""
        with pytest.raises(ValueError, match="at least one element"):
            validate_list([], _Item, "results")

    def test_wrong_type(self) -> None:
        """TypeError naming the index of the wrong item."""
        with pytest.raises(TypeError, match=r"results\[1\] must be a _Item, got str"):
            validate_list([_Item(), "bad"], _Item, "results")

    def test_ok(self) -> None:
        """A valid list passes silently."""
        validate_list([_Item()], _Item, "results")
