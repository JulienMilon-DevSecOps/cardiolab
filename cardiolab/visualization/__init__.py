"""Visualization — HRV and signal plots.

Modules
-------
training_load_plots
    ATL/CTL/TSB training load: dual-axis ATL/CTL/TSB chart, TRIMP bar history
    coloured by sport type, and TSB zone chart with physiological band backgrounds.
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
drift_plots
    Cardiac drift: windowed HR + regression curve with zone background,
    and multi-session drift-rate evolution with clinical zone bands.
hrr_plots
    Heart Rate Recovery: recovery curve with HRR1/HRR2 markers, multi-session
    comparison of HR-drop curves, and semi-circular HRR1 gauge.
vo2max_plots
    VO2max estimation from HRV: grouped model comparison bars with ACSM zone
    backgrounds, multi-session best-estimate evolution with ±10 % uncertainty
    band, and semi-circular fitness gauge (poor → excellent).
dashboard_plots
    Synthetic dashboards: multi-protocol session dashboard (2×3 grid), longitudinal
    heatmap (sessions × metrics), readiness score evolution, and per-protocol
    mini-dashboards (resting, HRR, drift, VO2max, coherence).
"""

from cardiolab.visualization.training_load_plots import (
    plot_atl_ctl_tsb,
    plot_trimp_history,
    plot_tsb_zones,
)
from cardiolab.visualization.coherence_plots import (
    plot_coherence_psd,
    plot_coherence_score_evolution,
    plot_coherence_tachogram,
)
from cardiolab.visualization.dashboard_plots import (
    plot_coherence_mini,
    plot_drift_mini,
    plot_hrr_mini,
    plot_longitudinal_heatmap,
    plot_readiness_evolution,
    plot_resting_mini,
    plot_score_evolution,
    plot_session_dashboard,
    plot_vo2max_mini,
)
from cardiolab.visualization.drift_plots import (
    plot_drift_curve,
    plot_drift_zones,
)
from cardiolab.visualization.hrr_plots import (
    plot_hrr_comparison,
    plot_hrr_curve,
    plot_hrr_gauge,
)
from cardiolab.visualization.nonlinear_plots import (
    plot_dfa_fluctuation,
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
from cardiolab.visualization.vo2max_plots import (
    plot_vo2max_comparison,
    plot_vo2max_evolution,
    plot_vo2max_gauge,
)

__all__ = [
    # training_load_plots
    "plot_atl_ctl_tsb",
    "plot_trimp_history",
    "plot_tsb_zones",
    # dashboard_plots
    "plot_session_dashboard",
    "plot_longitudinal_heatmap",
    "plot_readiness_evolution",
    "plot_score_evolution",
    "plot_resting_mini",
    "plot_hrr_mini",
    "plot_drift_mini",
    "plot_vo2max_mini",
    "plot_coherence_mini",
    # coherence_plots
    "plot_coherence_psd",
    "plot_coherence_score_evolution",
    "plot_coherence_tachogram",
    # drift_plots
    "plot_drift_curve",
    "plot_drift_zones",
    # hrr_plots
    "plot_hrr_comparison",
    "plot_hrr_curve",
    "plot_hrr_gauge",
    # nonlinear_plots
    "plot_dfa_fluctuation",
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
    # vo2max_plots
    "plot_vo2max_comparison",
    "plot_vo2max_evolution",
    "plot_vo2max_gauge",
]
