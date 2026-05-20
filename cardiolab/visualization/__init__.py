"""Visualization — HRV and signal plots.

Modules
-------
resting_plots
    RMSSD and readiness score evolution over time (resting HRV sessions).
rr_plots
    Raw RR interval signal: tachogram, distribution, filtered view,
    multi-session comparison, and compound summary figure.
spectral_plots
    Frequency-domain HRV: PSD (Welch/AR), LF/HF evolution, radar chart,
    and spectral heatmap.
"""

from cardiolab.visualization.resting_plots import (
    plot_resting_evolution,
    plot_resting_evolution_rolling,
)
from cardiolab.visualization.rr_plots import (
    plot_rr_comparison,
    plot_rr_distribution,
    plot_rr_filtered,
    plot_rr_summary,
    plot_rr_tachogram,
)
from cardiolab.visualization.spectral_plots import (
    plot_hrv_radar,
    plot_lf_hf_evolution,
    plot_psd_comparison,
    plot_psd_welch,
    plot_spectral_heatmap,
)

__all__ = [
    # resting_plots
    "plot_resting_evolution",
    "plot_resting_evolution_rolling",
    # rr_plots
    "plot_rr_tachogram",
    "plot_rr_distribution",
    "plot_rr_filtered",
    "plot_rr_comparison",
    "plot_rr_summary",
    # spectral_plots
    "plot_psd_welch",
    "plot_psd_comparison",
    "plot_lf_hf_evolution",
    "plot_hrv_radar",
    "plot_spectral_heatmap",
]
