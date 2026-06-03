"""Human-readable label dictionaries for all cardiolab protocols.

Two ready-to-use dictionaries are provided:

* :data:`LABELS_EN` — English labels (default in the package).
* :data:`LABELS_FR` — French labels, intended for the ``local/`` scripts.

Pass either dict as the ``labels`` keyword argument to any reporting table
function or visualization plot function::

    from cardiolab.labels import LABELS_FR
    table_resting_history(results, labels=LABELS_FR)
    plot_resting_evolution(results, labels=LABELS_FR)

Keys follow the internal metric names used in DataFrames and dataclass
attributes (e.g. ``"rmssd"``, ``"mean_hr"``).  Missing keys fall back to
the raw attribute name, so partial overrides are safe.

Phase group keys for the orthostatic MultiIndex table use the prefix
``"_phase_"`` followed by the English group name
(e.g. ``"_phase_Supine"``).
"""

from __future__ import annotations

# ── English ───────────────────────────────────────────────────────────────────

LABELS_EN: dict[str, str] = {
    # ── HRV — time domain ────────────────────────────────────────────────
    "rmssd": "RMSSD (ms)",
    "ln_rmssd": "ln(RMSSD)",
    "sdnn": "SDNN (ms)",
    "pnn50": "pNN50 (%)",
    "mean_hr": "HR (bpm)",
    # ── HRV — frequency domain ───────────────────────────────────────────
    "vlf": "VLF (ms²)",
    "lf": "LF (ms²)",
    "hf": "HF (ms²)",
    "lf_hf": "LF/HF",
    "hf_pct": "HF (%)",
    "lf_nu": "LF nu",
    "hf_nu": "HF nu",
    "hf_hr": "HF/HR",
    # ── HRV — non-linear ─────────────────────────────────────────────────
    "sd1": "SD1 (ms)",
    "sd2": "SD2 (ms)",
    "sd_ratio": "SD1/SD2",
    "dfa_alpha1": "DFA α1",
    "apen": "ApEn",
    "sampen": "SampEn",
    # ── Score / readiness ────────────────────────────────────────────────
    "score": "Readiness",
    "date": "Date",
    # ── Orthostatic — response metrics ───────────────────────────────────
    "hr_response": "ΔHR (bpm)",
    "hf_response_pct": "HF Δ (%)",
    "hf_hr_pct_change": "HF/HR Δ (%)",
    "lf_hr_pct_change": "LF/HR Δ (%)",
    "delta_rmssd": "ΔRMSSD (ms)",
    "lf_hf_change": "LF/HF Δ",
    "lf_hf_ratio_change": "LF/HF Δ",
    "interpretation": "Assessment",
    # ── Orthostatic — condensed history columns ──────────────────────────
    "supine_rmssd": "Supine RMSSD (ms)",
    "standing_rmssd": "Standing RMSSD (ms)",
    "supine_hr": "Supine HR (bpm)",
    "standing_hr": "Standing HR (bpm)",
    # ── Orthostatic — transition ─────────────────────────────────────────
    "transition_delta_hr": "Transition ΔHR (bpm)",
    "transition_peak_hr": "Peak HR (bpm)",
    # ── Orthostatic — MultiIndex phase groups ────────────────────────────
    "_phase_Supine": "Supine",
    "_phase_Transition": "Transition",
    "_phase_Standing": "Standing",
    "_phase_Autonomic response": "Autonomic response",
    # ── Coherence ────────────────────────────────────────────────────────
    "coherence_score": "Coherence (%)",
    "coherence_ratio": "Ratio",
    # ── HRR ──────────────────────────────────────────────────────────────
    "hrr_60": "HRR60 (bpm)",
    "hrr_120": "HRR120 (bpm)",
    "hrr_180": "HRR180 (bpm)",
    # ── Cardiac drift ────────────────────────────────────────────────────
    "drift_rate": "Drift (%/min)",
    # ── VO2max ────────────────────────────────────────────────────────────
    "vo2max_uth": "VO2max Uth (mL/kg/min)",
    "vo2max_ln_rmssd": "VO2max ln-RMSSD (mL/kg/min)",
    # ── Training load ─────────────────────────────────────────────────────
    "atl": "ATL (fatigue)",
    "ctl": "CTL (fitness)",
    "tsb": "TSB (form)",
    "trimp": "TRIMP",
    "duration_min": "Duration (min)",
    "sport_type": "Sport",
    "notes": "Notes",
    # ── Readiness / score zones ───────────────────────────────────────────────────────
    "zone_score_very_good": "Very good (80–100)",
    "zone_score_normal": "Normal (60–80)",
    "zone_score_moderate_fatigue": "Moderate fatigue (40–60)",
    "zone_score_fatigued": "Fatigued (0–40)",
    "zone_score_low": "Low",
    "zone_score_moderate": "Moderate",
    "zone_score_good": "Good",
    # ── Coherence zones ─────────────────────────────────────────────────────────
    "zone_coh_low": "Low coherence (< 40 %)",
    "zone_coh_moderate": "Moderate coherence (40–60 %)",
    "zone_coh_good": "Good coherence (≥ 60 %)",
    # ── HRR zones ───────────────────────────────────────────────────────────────
    "zone_hrr_impaired": "Impaired (< 12)",
    "zone_hrr_normal": "Normal (12–19)",
    "zone_hrr_good": "Good (20–24)",
    "zone_hrr_excellent": "Excellent (≥ 25)",
    # ── Drift zones ──────────────────────────────────────────────────────────────
    "zone_drift_no_drift": "No drift (< 0.5)",
    "zone_drift_mild": "Mild (0.5–1.5)",
    "zone_drift_moderate": "Moderate (1.5–3.0)",
    "zone_drift_strong": "Strong (> 3.0)",
    # ── VO2max zones ───────────────────────────────────────────────────────────
    "zone_vo2_poor": "Poor (< 28)",
    "zone_vo2_fair": "Fair (28–37)",
    "zone_vo2_good": "Good (38–47)",
    "zone_vo2_very_good": "Very good (48–57)",
    "zone_vo2_excellent": "Excellent (≥ 58)",
    # ── TSB zones ────────────────────────────────────────────────────────────────
    "zone_tsb_fresh": "Fresh / detraining",
    "zone_tsb_optimal": "Optimal",
    "zone_tsb_neutral": "Neutral",
    "zone_tsb_fatigue": "Accumulated fatigue",
    "zone_tsb_overload": "Overload",
    # ── Protocol names ────────────────────────────────────────────────────
    "protocol_resting": "Resting HRV",
    "protocol_orthostatic": "Orthostatic test",
    "protocol_coherence": "Cardiac coherence",
    "protocol_hrr": "Heart Rate Recovery",
    "protocol_drift": "Cardiac drift",
    "protocol_vo2max": "VO2max estimation",
}

# ── French ────────────────────────────────────────────────────────────────────

LABELS_FR: dict[str, str] = {
    # ── HRV — domaine temporel ───────────────────────────────────────────
    "rmssd": "RMSSD (ms)",
    "ln_rmssd": "ln(RMSSD)",
    "sdnn": "SDNN (ms)",
    "pnn50": "pNN50 (%)",
    "mean_hr": "FC (bpm)",
    # ── HRV — domaine fréquentiel ────────────────────────────────────────
    "vlf": "VLF (ms²)",
    "lf": "LF (ms²)",
    "hf": "HF (ms²)",
    "lf_hf": "LF/HF",
    "hf_pct": "HF (%)",
    "lf_nu": "LF nu",
    "hf_nu": "HF nu",
    "hf_hr": "HF/FC",
    # ── HRV — non-linéaire ───────────────────────────────────────────────
    "sd1": "SD1 (ms)",
    "sd2": "SD2 (ms)",
    "sd_ratio": "SD1/SD2",
    "dfa_alpha1": "DFA α1",
    "apen": "ApEn",
    "sampen": "SampEn",
    # ── Score / forme ────────────────────────────────────────────────────
    "score": "Score de forme",
    "date": "Date",
    # ── Orthostatique — métriques de réponse ─────────────────────────────
    "hr_response": "ΔFC (bpm)",
    "hf_response_pct": "Δ HF (%)",
    "hf_hr_pct_change": "Δ HF/FC (%)",
    "lf_hr_pct_change": "Δ LF/FC (%)",
    "delta_rmssd": "ΔRMSSD (ms)",
    "lf_hf_change": "Δ LF/HF",
    "lf_hf_ratio_change": "Δ LF/HF",
    "interpretation": "Évaluation",
    # ── Orthostatique — historique condensé ──────────────────────────────
    "supine_rmssd": "Allongé RMSSD (ms)",
    "standing_rmssd": "Debout RMSSD (ms)",
    "supine_hr": "Allongé FC (bpm)",
    "standing_hr": "Debout FC (bpm)",
    # ── Orthostatique — transition ───────────────────────────────────────
    "transition_delta_hr": "Transition ΔFC (bpm)",
    "transition_peak_hr": "FC max (bpm)",
    # ── Orthostatique — groupes de phases (MultiIndex) ───────────────────
    "_phase_Supine": "Allongé",
    "_phase_Transition": "Transition",
    "_phase_Standing": "Debout",
    "_phase_Autonomic response": "Réponse autonome",
    # ── Cohérence cardiaque ──────────────────────────────────────────────
    "coherence_score": "Cohérence (%)",
    "coherence_ratio": "Rapport",
    # ── Récupération cardiaque (HRR) ─────────────────────────────────────
    "hrr_60": "RRC60 (bpm)",
    "hrr_120": "RRC120 (bpm)",
    "hrr_180": "RRC180 (bpm)",
    # ── Dérive cardiaque ──────────────────────────────────────────────────
    "drift_rate": "Dérive (%/min)",
    # ── VO2max ────────────────────────────────────────────────────────────
    "vo2max_uth": "VO2max Uth (mL/kg/min)",
    "vo2max_ln_rmssd": "VO2max ln-RMSSD (mL/kg/min)",
    # ── Charge d'entraînement ─────────────────────────────────────────────
    "atl": "ATL (fatigue)",
    "ctl": "CTL (forme)",
    "tsb": "TSB (forme compétition)",
    "trimp": "TRIMP",
    "duration_min": "Durée (min)",
    "sport_type": "Sport",
    "notes": "Notes",
    # ── Zones repos / score ──────────────────────────────────────────────────────
    "zone_score_very_good": "Très bien (80–100)",
    "zone_score_normal": "Normal (60–80)",
    "zone_score_moderate_fatigue": "Fatigue modérée (40–60)",
    "zone_score_fatigued": "Fatigué(e) (0–40)",
    "zone_score_low": "Faible",
    "zone_score_moderate": "Modéré",
    "zone_score_good": "Bon",
    # ── Zones cohérence ──────────────────────────────────────────────────────────────
    "zone_coh_low": "Faible cohérence (< 40 %)",
    "zone_coh_moderate": "Cohérence modérée (40–60 %)",
    "zone_coh_good": "Bonne cohérence (≥ 60 %)",
    # ── Zones HRR ────────────────────────────────────────────────────────────────
    "zone_hrr_impaired": "Insuffisant (< 12)",
    "zone_hrr_normal": "Normal (12–19)",
    "zone_hrr_good": "Bon (20–24)",
    "zone_hrr_excellent": "Excellent (≥ 25)",
    # ── Zones dérive ──────────────────────────────────────────────────────────────
    "zone_drift_no_drift": "Pas de dérive (< 0.5)",
    "zone_drift_mild": "Légère (0.5–1.5)",
    "zone_drift_moderate": "Modérée (1.5–3.0)",
    "zone_drift_strong": "Forte (> 3.0)",
    # ── Zones VO2max ─────────────────────────────────────────────────────────────
    "zone_vo2_poor": "Faible (< 28)",
    "zone_vo2_fair": "Passable (28–37)",
    "zone_vo2_good": "Bon (38–47)",
    "zone_vo2_very_good": "Très bon (48–57)",
    "zone_vo2_excellent": "Excellent (≥ 58)",
    # ── Zones TSB ────────────────────────────────────────────────────────────────
    "zone_tsb_fresh": "Frais / désentraînement",
    "zone_tsb_optimal": "Optimal",
    "zone_tsb_neutral": "Neutre",
    "zone_tsb_fatigue": "Fatigue accumulée",
    "zone_tsb_overload": "Surcharge",
    # ── Noms de protocoles ────────────────────────────────────────────────
    "protocol_resting": "HRV au repos",
    "protocol_orthostatic": "Test orthostatique",
    "protocol_coherence": "Cohérence cardiaque",
    "protocol_hrr": "Récupération cardiaque (HRR)",
    "protocol_drift": "Dérive cardiaque",
    "protocol_vo2max": "Estimation VO2max",
}


# ── Public helper ─────────────────────────────────────────────────────────────


def lbl(labels: dict[str, str] | None, key: str, default: str | None = None) -> str:
    """Return the display string for *key* from *labels*, with a fallback.

    Args:
        labels: A labels dict such as :data:`LABELS_EN` or :data:`LABELS_FR`.
            Pass ``None`` to always return the fallback.
        key: The metric key to look up (e.g. ``"rmssd"``, ``"mean_hr"``).
        default: Fallback string when the key is absent. Defaults to *key*
            itself so callers never get ``None``.

    Returns:
        The display string.

    Examples:
        >>> lbl(LABELS_FR, "mean_hr")
        'FC (bpm)'
        >>> lbl(None, "rmssd", "RMSSD (ms)")
        'RMSSD (ms)'

    """
    if labels is None:
        return default if default is not None else key
    return labels.get(key, default if default is not None else key)
