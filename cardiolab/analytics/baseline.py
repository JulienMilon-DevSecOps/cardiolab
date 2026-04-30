from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cardiolab.protocols.resting import HRVFeatures


@dataclass
class Baseline:
    """
    FR :
    Gère l’historique des métriques HRV (features) et fournit des statistiques
    (moyenne, médiane, rolling). Compatible avec des données venant :
    - du pipeline RR/ECG
    - d'une base de données

    EN :
    Manages HRV feature history and provides statistics (mean, median, rolling).
    Compatible with data coming from:
    - RR/ECG pipeline
    - database
    """

    history: list[HRVFeatures] = field(default_factory=list)
    window: int = 7

    # ======================
    # FACTORIES
    # ======================

    @classmethod
    def from_features(cls, features_list: list[HRVFeatures]) -> Baseline:
        """
        FR :
        Crée une baseline à partir de features déjà calculées.

        EN :
        Creates a baseline from precomputed features.
        """

        return cls(history = sorted(features_list, key=lambda x: x.date or ""))


    @classmethod
    def from_resting_results(cls, results) -> Baseline:
        """
        FR :
        Crée une baseline à partir des résultats du protocole resting.

        EN :
        Creates a baseline from resting protocol results.
        """

        features = []

        for r in results:
            features.append(
                HRVFeatures(
                    date=str(r.duration),  # à adapter selon ton modèle
                    rmssd=r.rmssd,
                    ln_rmssd=float(np.log(r.rmssd)) if r.rmssd > 0 else 0.0,
                    sdnn=r.sdnn,
                    pnn50=r.pnn50,
                    mean_hr=r.mean_hr,
                    vlf=r.vlf,
                    lf=r.lf,
                    hf=r.hf,
                    lf_hf=r.lf_hf,
                    hf_pct=r.hf_pct,
                    lf_nu=r.lf_nu,
                    hf_nu=r.hf_nu,
                )
            )

        return cls(history=features)

    def _get_recent(self) -> list[HRVFeatures]:
        """
        FR :
        Retourne les dernières mesures selon la fenêtre définie.

        EN :
        Returns recent measurements based on rolling window.
        """
        return self.history[-self.window :]

    # ======================
    # BASELINE CALCUL
    # ======================


    def mean_rmssd(self) -> float | None:
        """
        FR :
        Calcule le RMSSD moyen sur la fenêtre.

        EN :
        Computes mean RMSSD over the window.
        """
        data = self._get_recent()

        if not data:
            return None

        values = [r.rmssd for r in data]
        return float(np.mean(values))
    
    def median_rmssd(self) -> float | None:
        """
        FR :
        Calcule le RMSSD median sur la fenêtre.

        EN :
        Computes median RMSSD over the window.
        """
        data = self._get_recent()

        if not data:
            return None

        values = [r.rmssd for r in data]
        return float(np.median(values))

    def mean_hr(self) -> float | None:
        """
        FR :
        Calcule la fréquence cardiaque moyenne.

        EN :
        Computes mean heart rate.
        """
        data = self._get_recent()

        if not data:
            return None

        values = [r.mean_hr for r in data]
        return float(np.mean(values))
    
    # ======================
    # ROLLING 7 days
    # ======================

    def rolling_rmssd(self, window: int = 7) -> list[float]:
        """
        FR :
        Calcule la moyenne glissante du RMSSD sur une fenêtre donnée.

        EN :
        Computes rolling average of RMSSD over a given window.
        """

        values = [r.rmssd for r in self.history]

        if len(values) < window:
            return []

        return [
            float(np.mean(values[i - self.window + 1 : i + 1]))
            for i in range(self.window - 1, len(values))
        ]
    

    def rolling_rmssd_median(self, window: int = 7) -> list[float]:
        """
        FR :
        Moyenne glissante robuste (médiane).

        EN :
        Robust rolling average using median.
        """

        values = [r.rmssd for r in self.history]

        if len(values) < window:
            return []

        return [
            float(np.median(values[i - self.window + 1 : i + 1]))
            for i in range(self.window - 1, len(values))
        ]