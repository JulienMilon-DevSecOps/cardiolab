"""Backward-compatibility shim — content moved to resting_plots.py."""

from cardiolab.visualization.resting_plots import (
    plot_resting_evolution,
    plot_resting_evolution_rolling,
)

__all__ = [
    "plot_resting_evolution",
    "plot_resting_evolution_rolling",
]
