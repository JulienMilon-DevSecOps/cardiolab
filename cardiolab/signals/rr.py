from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np


@dataclass
class RRSeries:
    """
    FR :
    Représentation d'une série d'intervalles RR (en millisecondes).

    Attributes
    ----------
    intervals : np.ndarray
        Intervalles RR en millisecondes.
    timestamps : Optional[np.ndarray]
        Temps associés à chaque intervalle (en secondes).
    metadata : dict
        Informations additionnelles (source, capteur, utilisateur, etc.)

    EN :
    Representation of a series of RR intervals (in milliseconds).

    Attributes
    ----------
    intervals: np.ndarray
        RR intervals in milliseconds.
    timestamps: Optional[np.ndarray]
        Time associated with each interval (in seconds).
    metadata: dict
        Additional information (source, sensor, user, etc.)
    """

    intervals: np.ndarray
    timestamps: Optional[np.ndarray] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.intervals = np.asarray(self.intervals, dtype=float)

        if self.timestamps is not None:
            self.timestamps = np.asarray(self.timestamps, dtype=float)
            if len(self.timestamps) != len(self.intervals):
                raise ValueError("timestamps and intervals must have same size")

        self._validate()

    # ======================
    # VALIDATION
    # ======================

    def _validate(self):
        if len(self.intervals) < 2:
            raise ValueError("RRSeries must contain at least 2 intervals")

        if np.any(self.intervals <= 0):
            raise ValueError("RR intervals RR must be positive")

    # ======================
    # PROPRIÉTÉS DE BASE
    # ======================

    @property
    def duration(self) -> float:
        """
        FR :
        Durée totale en secondes
        
        EN:
        Duration in seconds
        """
        return np.sum(self.intervals) / 1000.0

    @property
    def mean_rr(self) -> float:
        """
        FR : 
        RR moyen (ms)
        
        EN :
        RR mean (ms)
        """
        return float(np.mean(self.intervals))

    @property
    def mean_hr(self) -> float:
        """
        FR :
        Fréquence cardiaque moyenne (bpm)
        
        EN :
        Mean Heart Rate (bpm)
        """
        return float(60000.0 / self.mean_rr)

    @property
    def min_hr(self) -> float:
        """
        FR :
        Fréquence cardiaque minimale (bpm)
        
        EN :
        Minimum Heart Rate (bpm)
        """
        return float(60000.0 / np.max(self.intervals))

    @property
    def max_hr(self) -> float:
        """
        FR :
        Fréquence cardiaque maximale (bpm)
        
        EN :
        Maximum Heart Rate (bpm)
        """
        return float(60000.0 / np.min(self.intervals))

    # ======================
    # CONVERSIONS
    # ======================

    def to_hr(self) -> np.ndarray:
        """
        FR :
        Convertit RR → HR (bpm)
        
        EN :
        Convert RR → HR (bpm)
        """
        return 60000.0 / self.intervals


    @classmethod
    def from_hr(cls, hr_values: np.ndarray) -> "RRSeries":
        """
        FR :
        Crée RRSeries à partir d'une série HR (bpm)
        
        EN : 
        Create RR Series from HR serie (bpm)
        """
        hr_values = np.asarray(hr_values, dtype=float)

        if np.any(hr_values <= 0):
            raise ValueError("HR must be > 0")

        rr = 60000.0 / hr_values
        return cls(rr)

    # ======================
    # NETTOYAGE
    # ======================

    def remove_outliers(
        self,
        low: float = 300,
        high: float = 2000,
        method: str = "threshold"
    ) -> "RRSeries":
        """
        FR :
        Supprime les intervalles aberrants.

        Parameters
        ----------
        low : float
            seuil bas (ms)
        high : float
            seuil haut (ms)
        method : str
            "threshold" ou "zscore"

        EN :
        Removes outliers.

        Parameters
        ----------
        low: float
            low threshold (ms)
        high: float
            high threshold (ms)
        method: str
            "threshold" or "zscore"
        """

        rr = self.intervals.copy()

        if method == "threshold":
            mask = (rr >= low) & (rr <= high)

        elif method == "zscore":
            z = (rr - np.mean(rr)) / np.std(rr)
            mask = np.abs(z) < 3

        else:
            raise ValueError("Method unknown")

        cleaned_rr = rr[mask]

        timestamps = self.timestamps[mask] if self.timestamps is not None else None

        return RRSeries(cleaned_rr, timestamps, self.metadata)

    # ======================
    # INTERPOLATION
    # ======================

    def interpolate(self, fs: float = 4.0) -> Tuple[np.ndarray, np.ndarray]:
        """
        FR:
        Interpolation pour analyse fréquentielle.

        Parameters
        ----------
        fs : float
            fréquence d'échantillonnage cible (Hz)

        Returns
        -------
        t_interp : np.ndarray
        rr_interp : np.ndarray

        EN :
        Interpolation for frequency analysis.

        Parameters

        -----------
        fs: float
            Target sampling frequency (Hz)

        Returns
        ------
        t_interp: np.ndarray
        rr_interp: np.ndarray
        """

        if self.timestamps is None:
            t = np.cumsum(self.intervals) / 1000.0
        else:
            t = self.timestamps

        t_interp = np.arange(t[0], t[-1], 1.0 / fs)
        rr_interp = np.interp(t_interp, t, self.intervals)

        return t_interp, rr_interp

    # ======================
    # SEGMENTATION
    # ======================

    def segment(self, window_sec: float) -> list[RRSeries]:
        """
        FR :
        Découpe la série en segments de durée fixe.

        EN :
        Divide the series into segments of fixed duration.
        """

        segments = []
        current = []
        total_time = 0

        for rr in self.intervals:
            current.append(rr)
            total_time += rr / 1000.0

            if total_time >= window_sec:
                segments.append(RRSeries(np.array(current)))
                current = []
                total_time = 0

        return segments


    # ======================
    # VISUALISATION DEBUG
    # ======================

    def summary(self) -> dict:
        return {
            "n": len(self.intervals),
            "duration_s": self.duration,
            "mean_rr": self.mean_rr,
            "mean_hr": self.mean_hr,
        }

    # ======================
    # MAGIC METHODS
    # ======================

    def __len__(self):
        return len(self.intervals)

    def __repr__(self):
        return (
            f"RRSeries(n={len(self)}, "
            f"mean_hr={self.mean_hr:.1f}, "
        )