"""Represent a set of HRV metrics computed for a given session and resting protocol and result."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cardiolab.features.frequency_domain import frequency_domain
from cardiolab.features.time_domain import ln_rmssd, pnn50, rmssd, sdnn
from cardiolab.signals.rr import RRSeries


@dataclass
class HRVFeatures:
    """Represents a set of HRV metrics computed for a given session.
    
    FR :
    Représente un ensemble de métriques HRV calculées pour une session donnée.
    Ce modèle est conçu pour être stocké en base de données et utilisé pour
    reconstruire une baseline sans recalculer les signaux bruts.
    EN :
    Represents a set of HRV metrics computed for a given session.
    This model is designed to be stored in a database and used to
    reconstruct a baseline without recomputing raw signals.
    """

    date: str | None = None

    rmssd: float = 0.0
    ln_rmssd: float = 0.0
    sdnn: float = 0.0
    pnn50: float = 0.0
    mean_hr: float = 0.0

    vlf: float = 0.0
    lf: float = 0.0
    hf: float = 0.0

    lf_hf: float = 0.0
    hf_pct: float = 0.0
    lf_nu: float = 0.0
    hf_nu: float = 0.0

    duration:float = 0.0
    score : float = 0.0


# ======================
# PROTOCOLE PRINCIPAL
# ======================

def resting_hrv(
    rr: RRSeries,
    min_duration: float = 300.0,
    compute_score: bool = False,
) -> HRVFeatures:
    """Compute HRV metrics in a resting protocol.
    
    FR :
    Calcule les métriques HRV dans un protocole de repos.
    Ce protocole est utilisé pour évaluer la récupération, la fatigue
    et l’état du système nerveux autonome.
    Conditions recommandées :
    - durée ≥ 5 minutes
    - position stable (couché ou assis)
    - respiration naturelle
    EN :
    Computes HRV metrics in a resting protocol.
    This protocol is used to assess recovery, fatigue,
    and autonomic nervous system state.
    Recommended conditions:
    - duration ≥ 5 minutes
    - stable position (lying or seated)
    - natural breathing

    Args : 
        rr : RRSeries
            RR intarvall serie / Série d'intervalles RR
        min_duration : float
            Minimal duration recommanded in secondes (default: 300s) / Durée minimale recommandée en secondes (default: 300s)
        compute_score : bool
            If True, calculate a simple score / Si True, calcule un score simple

    Return :
        HRVFeatures
            Résultat du protocole
    """
    # ======================
    # VALIDATION
    # ======================

    duration = rr.duration

    if duration < min_duration:
        # on ne bloque pas, mais on avertit
        # (important en pratique)
        pass

    # ======================
    # FEATURES
    # ======================

    rmssd_value = rmssd(rr)
    ln_rmssd_value = ln_rmssd(rr)
    sdnn_value = sdnn(rr)
    pnn50_value = pnn50(rr)
    mean_hr_value = rr.mean_hr

    frequency_indicators = frequency_domain(rr)

    print(frequency_indicators)

    # ======================
    # SCORE (simple)
    # ======================

    score = None

    if compute_score:
        score = _compute_simple_score(rmssd_value, mean_hr_value)

    return HRVFeatures(
        rmssd=rmssd_value,
        ln_rmssd=ln_rmssd_value,
        sdnn=sdnn_value,
        pnn50=pnn50_value,
        mean_hr=mean_hr_value,
        vlf=frequency_indicators["VLF"] ,
        lf=frequency_indicators["LF"],
        hf=frequency_indicators["HF"] ,
        lf_hf=frequency_indicators["LF_HF"] ,
        hf_pct=frequency_indicators["HF_pct"] ,
        lf_nu=frequency_indicators["LF_nu"] ,
        hf_nu=frequency_indicators["HF_nu"] ,
        duration=duration,
        score=score,
    )


# ======================
# SCORE (VERSION SIMPLE)
# ======================

def _compute_simple_score(rmssd_value: float, mean_hr: float) -> float:
    """Compute a simple score based on RMSSD and heart rate.
    
    FR :
    Calcule un score simple basé sur RMSSD et la fréquence cardiaque.
    ⚠️ Ce score est volontairement simplifié et sera amélioré
    avec l’ajout d’une baseline utilisateur.
    EN :
    Computes a simple score based on RMSSD and heart rate.
    ⚠️ This is a simplified score that will be improved
    with user baseline integration.
    """
    # normalisation simple
    rmssd_norm = np.tanh(rmssd_value / 50.0)
    hr_penalty = np.tanh((mean_hr - 60.0) / 30.0)

    score = (rmssd_norm - hr_penalty + 1) / 2  # entre 0 et 1

    return float(score)