from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from signals.rr import RRSeries
from features.time_domain import rmssd, sdnn, pnn50


@dataclass
class RestingResult:
    """
    FR :
    Résultat du protocole HRV au repos.

    EN :
    Result of the resting HRV protocol.
    """

    rmssd: float
    sdnn: float
    pnn50: float
    mean_hr: float
    duration: float
    score: Optional[float] = None

    def to_dict(self) -> dict:
        """
        FR :
        Convertit le résultat en dictionnaire.

        EN :
        Converts result to dictionary.
        """
        return {
            "rmssd": self.rmssd,
            "sdnn": self.sdnn,
            "pnn50": self.pnn50,
            "mean_hr": self.mean_hr,
            "duration": self.duration,
            "score": self.score,
        }


# ======================
# PROTOCOLE PRINCIPAL
# ======================

def resting_hrv(
    rr: RRSeries,
    min_duration: float = 300.0,
    compute_score: bool = False,
) -> RestingResult:
    """
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

    Parameters
    ----------
    rr : RRSeries
        Série d'intervalles RR
    min_duration : float
        Durée minimale recommandée en secondes (default: 300s)
    compute_score : bool
        Si True, calcule un score simple

    Returns
    -------
    RestingResult
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
    sdnn_value = sdnn(rr)
    pnn50_value = pnn50(rr)
    mean_hr_value = rr.mean_hr

    # ======================
    # SCORE (simple)
    # ======================

    score = None

    if compute_score:
        score = _compute_simple_score(rmssd_value, mean_hr_value)

    return RestingResult(
        rmssd=rmssd_value,
        sdnn=sdnn_value,
        pnn50=pnn50_value,
        mean_hr=mean_hr_value,
        duration=duration,
        score=score,
    )


# ======================
# SCORE (VERSION SIMPLE)
# ======================

def _compute_simple_score(rmssd_value: float, mean_hr: float) -> float:
    """
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