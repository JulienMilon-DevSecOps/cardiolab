"""Shared formatting and styling helpers for reporting tables.

All helpers accept and return a :class:`~pandas.io.formats.style.Styler`
so they can be chained fluently::

    styler = (
        gradient_good(df.style, ["rmssd", "sd1"])
        .pipe(gradient_bad, ["mean_hr"])
        .pipe(caption, "My table")
    )
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pandas as pd

# ── Colour palettes for category cells ───────────────────────────────────────

_HRR_CAT_COLORS: dict[str, str] = {
    "excellent": "#d5f5e3",
    "good":      "#fef9e7",
    "normal":    "#fdebd0",
    "impaired":  "#fadbd8",
}

_DRIFT_CAT_COLORS: dict[str, str] = {
    "no_drift": "#d5f5e3",
    "mild":     "#fef9e7",
    "moderate": "#fdebd0",
    "strong":   "#fadbd8",
}

_ORTHO_CAT_COLORS: dict[str, str] = {
    "normal":   "#d5f5e3",
    "impaired": "#fadbd8",
    "elevated": "#fdebd0",
}

_VO2_CAT_COLORS: dict[str, str] = {
    "poor":      "#fadbd8",
    "fair":      "#fdebd0",
    "good":      "#fef9e7",
    "very_good": "#d6eaf8",
    "excellent": "#d5f5e3",
}

_COH_CAT_COLORS: dict[str, str] = {
    "low":      "#fadbd8",
    "moderate": "#fef9e7",
    "high":     "#d5f5e3",
}


# ── Value formatters ──────────────────────────────────────────────────────────


def fmt_float(decimals: int = 2) -> Callable[[float], str]:
    """Return a formatter that renders ``decimals`` decimal places."""
    spec = f"{{:.{decimals}f}}"
    return lambda x: spec.format(x)


def fmt_nan(decimals: int = 3) -> Callable[[float], str]:
    """Return a formatter that renders ``decimals`` places or 'n/a' for NaN."""
    spec = f"{{:.{decimals}f}}"

    def _fmt(x: float) -> str:
        try:
            return "n/a" if math.isnan(float(x)) else spec.format(x)
        except (TypeError, ValueError):
            return "n/a"

    return _fmt


def fmt_category(val: str) -> str:
    """Convert snake_case category strings to Title Case."""
    return str(val).replace("_", " ").title()


# ── Styler builders ───────────────────────────────────────────────────────────


def gradient_good(
    styler: pd.Styler,
    cols: list[str],
    vmin: float | None = None,
    vmax: float | None = None,
    cmap: str = "RdYlGn",
) -> pd.Styler:
    """Apply a red → yellow → green gradient: higher values are better."""
    existing = [c for c in cols if c in styler.data.columns]
    if existing:
        styler = styler.background_gradient(
            subset=existing, cmap=cmap, vmin=vmin, vmax=vmax
        )
    return styler


def gradient_bad(
    styler: pd.Styler,
    cols: list[str],
    vmin: float | None = None,
    vmax: float | None = None,
    cmap: str = "RdYlGn_r",
) -> pd.Styler:
    """Apply a green → yellow → red gradient: lower values are better."""
    existing = [c for c in cols if c in styler.data.columns]
    if existing:
        styler = styler.background_gradient(
            subset=existing, cmap=cmap, vmin=vmin, vmax=vmax
        )
    return styler


def highlight_category(
    styler: pd.Styler,
    col: str,
    palette: dict[str, str],
) -> pd.Styler:
    """Colour cells in ``col`` by category using ``palette``."""
    if col not in styler.data.columns:
        return styler

    def _colour(val: str) -> str:
        key = str(val).lower().replace(" ", "_")
        bg = palette.get(key, "")
        return f"background-color: {bg}" if bg else ""

    return styler.map(_colour, subset=[col])


def caption(styler: pd.Styler, text: str) -> pd.Styler:
    """Set the table caption."""
    return styler.set_caption(text)
