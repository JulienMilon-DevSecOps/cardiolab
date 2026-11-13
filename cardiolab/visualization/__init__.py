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
dfa_threshold_plots
    DFA α1 thresholds: α1 and heart rate over the test, α1 against heart rate,
    training zones scale, thresholds over time.
hrr_plots
    Heart Rate Recovery: recovery curve with HRR1/HRR2 markers, multi-session
    comparison of HR-drop curves, and semi-circular HRR1 gauge.
hr_max_plots
    HRmax field test (heart rate, held 5 s, peak retained, final effort) and
    HRmax over time per sport (tests, observed values, profile).
lsct_plots
    Lamberts submaximal cycle test: one test (heart rate, power, stages,
    recovery) and power / HRR60 over time.
orthostatic_plots
    Orthostatic test: four-panel multi-session plot showing RMSSD/HR per phase
    (supine / transition / standing) and autonomic response metrics (ΔHR, ΔRMSSD,
    HF/HR%, LF/HR%) over time.
monitoring_plots
    Training adaptation monitoring (Plews): 7-day lnRMSSD mean against the SWC
    band, coloured by state, with the 7-day CV on a second axis.
statistical_plots
    Multivariate anomalies over time (Mahalanobis distance, threshold, deviation
    of each metric) and trend lines with their 95 % confidence band.
vo2max_plots
    VO2max estimation from HRV: grouped model comparison bars with ACSM zone
    backgrounds, multi-session best-estimate evolution with ±10 % uncertainty
    band, and semi-circular fitness gauge (poor → excellent).
dashboard_plots
    Synthetic dashboards: multi-protocol session dashboard (2×3 grid), longitudinal
    heatmap (sessions × metrics), readiness score evolution, and per-protocol
    mini-dashboards (resting, HRR, drift, VO2max, coherence).
"""

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
from cardiolab.visualization.dfa_threshold_plots import (
    plot_alpha1_vs_hr,
    plot_dfa_alpha1,
    plot_threshold_evolution,
    plot_training_zones,
)
from cardiolab.visualization.drift_plots import (
    plot_drift_curve,
    plot_drift_zones,
)
from cardiolab.visualization.hr_max_plots import (
    plot_hr_max_history,
    plot_hr_max_test,
)
from cardiolab.visualization.hrr_plots import (
    plot_hrr_comparison,
    plot_hrr_curve,
    plot_hrr_gauge,
)
from cardiolab.visualization.lsct_plots import plot_lsct_evolution, plot_lsct_session
from cardiolab.visualization.monitoring_plots import plot_ln_rmssd_monitoring
from cardiolab.visualization.nonlinear_plots import (
    plot_dfa_fluctuation,
    plot_poincare,
    plot_poincare_comparison,
    plot_sd1_sd2_evolution,
)
from cardiolab.visualization.orthostatic_plots import (
    plot_orthostatic_dual_score_evolution,
    plot_orthostatic_phases_evolution,
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
from cardiolab.visualization.statistical_plots import (
    plot_anomaly_timeline,
    plot_trend_overlay,
)
from cardiolab.visualization.training_load_plots import (
    plot_atl_ctl_tsb,
    plot_trimp_history,
    plot_tsb_zones,
)
from cardiolab.visualization.vo2max_plots import (
    plot_vo2max_comparison,
    plot_vo2max_evolution,
    plot_vo2max_gauge,
)

__all__ = [
    # dfa_threshold_plots
    "plot_dfa_alpha1",
    "plot_alpha1_vs_hr",
    "plot_training_zones",
    "plot_threshold_evolution",
    # hr_max_plots
    "plot_hr_max_test",
    "plot_hr_max_history",
    # lsct_plots
    "plot_lsct_session",
    "plot_lsct_evolution",
    # monitoring_plots
    "plot_ln_rmssd_monitoring",
    # statistical_plots
    "plot_anomaly_timeline",
    "plot_trend_overlay",
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
    # orthostatic_plots
    "plot_orthostatic_dual_score_evolution",
    "plot_orthostatic_phases_evolution",
    # vo2max_plots
    "plot_vo2max_comparison",
    "plot_vo2max_evolution",
    "plot_vo2max_gauge",
]
