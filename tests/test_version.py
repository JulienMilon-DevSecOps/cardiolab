"""Tests for the package version (single source of truth: pyproject.toml)."""

from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest

import cardiolab

_PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


@pytest.mark.unit
class TestVersion:
    """``cardiolab.__version__`` must never drift from the packaged version."""

    def test_matches_installed_distribution(self):
        """__version__ is read from the installed distribution metadata."""
        assert cardiolab.__version__ == version("cardiolab")

    def test_matches_pyproject(self):
        """The installed version is the one declared in pyproject.toml."""
        with _PYPROJECT.open("rb") as f:
            declared = tomllib.load(f)["project"]["version"]
        assert cardiolab.__version__ == declared, (
            "Installed metadata is stale (editable installs keep the version of "
            "their last install): run `pip install -e . --no-deps`."
        )
