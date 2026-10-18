"""Shared marker for sessions whose signal quality is ``poor`` (v0.4.0)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from cardiolab.labels import lbl
from cardiolab.signals.quality import SignalQuality

_POOR_COLOR = "#c0392b"


def poor_indices(qualities: list) -> list[int]:
    """Return the positions of ``poor`` quality indexes (``None`` = unknown, skipped)."""
    return [
        i for i, q in enumerate(qualities) if isinstance(q, SignalQuality) and q.is_poor
    ]


def session_qualities(results: list) -> list:
    """Return the ``quality`` attribute of each result (``None`` when absent)."""
    return [getattr(r, "quality", None) for r in results]


def supine_qualities(results: list) -> list:
    """Return the supine-phase quality of orthostatic results or records."""
    out = []
    for r in results:
        supine = getattr(r, "supine", None)  # OrthostaticRecord
        if supine is None and hasattr(r, "phases"):  # OrthostaticResult
            supine = r.phases.supine.features
        out.append(getattr(supine, "quality", None))
    return out


def mark_poor_sessions(
    ax: plt.Axes,
    x,
    y,
    qualities: list,
    labels: dict[str, str] | None = None,
) -> bool:
    """Overlay a red cross on the sessions whose signal quality is ``poor``.

    Their values come from a faulty recording (more than 5 % of corrected
    beats, or uncorrected artefacts) and are left out of the baseline.

    Args:
        ax: Axes holding the session series.
        x: X positions of the sessions.
        y: Plotted values of the sessions.
        qualities: :class:`~cardiolab.signals.quality.SignalQuality` (or
            ``None``) per session.
        labels: Translation dict, for the legend entry.

    Returns:
        ``True`` if at least one session was marked.

    """
    idx = poor_indices(qualities)
    if not idx:
        return False
    ax.scatter(
        np.asarray(x)[idx],
        np.asarray(y, dtype=float)[idx],
        marker="X",
        s=110,
        color=_POOR_COLOR,
        edgecolors="white",
        linewidths=0.8,
        zorder=7,
        label=lbl(labels, "quality_poor_marker", "Poor signal quality"),
    )
    return True
