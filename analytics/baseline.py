from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from protocols.resting import RestingResult


@dataclass
class Baseline:
    """
    FR :
    Représente une baseline utilisateur basée sur un historique de mesures HRV.

    Permet de :
    - calculer une moyenne (baseline)
    - suivre l’évolution
    - comparer une nouvelle mesure

    EN :
    Represents a user baseline based on HRV measurement history.

    Allows to:
    - compute baseline values
    - track evolution
    - compare new measurements
    """

    history: List[RestingResult] = field(default_factory=list)
    window: int = 7  # rolling window (jours)

    # ======================
    # DATA
    # ======================

    def add(self, result: RestingResult):
        """
        FR :
        Ajoute une nouvelle mesure à l’historique.

        EN :
        Adds a new measurement to the history.
        """
        self.history.append(result)

    def _get_recent(self) -> List[RestingResult]:
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


    def mean_rmssd(self) -> Optional[float]:
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
    
    def median_rmssd(self) -> Optional[float]:
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

    def mean_hr(self) -> Optional[float]:
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