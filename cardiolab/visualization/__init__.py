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
nonlinear_plots
    Non-linear HRV: Poincaré scatter with SD1/SD2 ellipse, supine vs standing
    comparison, and SD1/SD2 evolution over sessions.
coherence_plots
    Cardiac coherence: AR PSD with resonance band, score evolution over sessions,
    and RR tachogram with sinusoidal respiratory reference.
hrr_plots
    Heart Rate Recovery: recovery curve with HRR1/HRR2 markers, multi-session
    comparison of HR-drop curves, and semi-circular HRR1 gauge.
"""

from cardiolab.visualization.coherence_plots import (
    plot_coherence_psd,
    plot_coherence_score_evolution,
    plot_coherence_tachogram,
)
from cardiolab.visualization.hrr_plots import (
    plot_hrr_comparison,
    plot_hrr_curve,
    plot_hrr_gauge,
)
from cardiolab.visualization.nonlinear_plots import (
    plot_poincare,
    plot_poincare_comparison,
    plot_sd1_sd2_evolution,
)
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
    # coherence_plots
    "plot_coherence_psd",
    "plot_coherence_score_evolution",
    "plot_coherence_tachogram",
    # hrr_plots
    "plot_hrr_comparison",
    "plot_hrr_curve",
    "plot_hrr_gauge",
    # nonlinear_plots
    "plot_poincare",
    "plot_poincare_comparison",
    "plot_sd1_sd2_evolution",
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
