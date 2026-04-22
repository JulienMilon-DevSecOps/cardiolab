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
    # STATISTIQUES SIMPLES
    # ======================

    def std(self) -> float:
        """
        SDNN
        
        FR :
        SDNN est l’écart-type des intervalles RR (ou NN) sur une période donnée.

        Interprétation physiologique :
            * mesure la variabilité globale du rythme cardiaque
            * reflète :
                activité sympathique + parasympathique

        Lecture (valeurs variable suivant la durée d'analyse)
            * SDNN élevé → bonne variabilité → système adaptable
            * SDNN faible → fatigue / stress / faible adaptabilité

        Valeurs typiques (cour terme ~5 min)
        | SDNN (ms) | Interprétation |
        | --------- | -------------- |
        | < 20      | très faible    |
        | 20 – 50   | faible         |
        | 50 – 80   | normal         |
        | > 80      | élevé          |

        EN :
        SDNN is the standard deviation of the RR (or NN) intervals over a given period.

        Physiological interpretation:
            * measures the overall variability of heart rate
            * reflects:
                sympathetic + parasympathetic activity

        Reading (values vary depending on the duration of analysis)

            * High SDNN → good variability → adaptable system
            * Low SDNN → fatigue / stress / poor adaptability

        Typical values (short term ~5 min)
        | SDNN (ms) | Interpretation |
        | --------- | -------------- |
        | < 20      | very low       |
        | 20 – 50   | low            |
        | 50 – 80   | normal         |
        | > 80      | high           |

        """
        return float(np.std(self.intervals, ddof=1))

    def rmssd(self) -> float:
        """
        RMSSD
        
        FR :
        RMSSD mesure la variabilité à court terme entre battements consécutifs.
        RMSSD = sqrt(mean((RR[i+1] - RR[i])²))
        
        Interprétation physiologique
            reflète principalement l'activité parasympathique (vagale)
        
        Lecture 
            * RMSSD élevé → bonne récupération / relaxation
            * RMSSD faible → stress / fatigue / charge élevée
        
        C’est LA métrique la plus utilisée en sport

        Valeurs typiques (adulte)
        | RMSSD (ms) | Interprétation |
        | ---------- | -------------- |
        | < 20       | très faible    |
        | 20 – 40    | faible         |
        | 40 – 70    | normal         |
        | 70 – 100   | bon            |
        | > 100      | très élevé     |

        * < 30 → fatigue, stress, surcharge
        * > 70 → bonne récupération
        * > 100 → très bon état parasympathique (souvent athlètes)

        Dépendant de la personne, âge, niveau sportif, ...

        EN :
        RMSSD measures short-term variability between consecutive heartbeats.
        RMSSD = sqrt(mean((RR[i+1] - RR[i])²))

        Physiological Interpretation
            Primarily reflects parasympathetic (vagal) activity.

        Reading
            * High RMSSD → good recovery/relaxation
            * Low RMSSD → stress/fatigue/high workload

        This is THE most widely used metric in sports.
        
        Typical Values (Adult)
        | RMSSD (ms) | Interprétation |
        | ---------- | -------------- |
        | < 20       | very low       |
        | 20 – 40    | low            |
        | 40 – 70    | normal         |
        | 70 – 100   | high           |
        | > 100      | very high      |

        * < 30 → fatigue, stress, overload
        * > 70 → good recovery
        * > 100 → very good parasympathetic function (often found in athletes)

        Depends on the individual, age, fitness level, etc.
        """
        diff = np.diff(self.intervals)
        return float(np.sqrt(np.mean(diff ** 2)))

    def pnn50(self) -> float:
        """
        pNN50 (%)
        
        FR : 
        pNN50 est le pourcentage de paires d’intervalles RR successifs qui diffèrent de plus de 50 ms.
        pNN50 = (nombre de |RR[i+1] - RR[i]| > 50 ms) / total x 100

        Interprétation physiologique
            reflète principalement l'activité parasympathique
        
            Lecture
                * pNN50 élevé → forte variabilité (relaxation)
                * pNN50 faible → stress / fatigue
            
            Valeurs typique
            | pNN50 (%) | Interprétation |
            | --------- | -------------- |
            | < 5%      | très faible    |
            | 5 – 15%   | faible         |
            | 15 – 30%  | normal         |
            | > 30%     | élevé          |

            Indicateur tout de même peux fiable, sensible au bruit.

            EN :
            pNN50 is the percentage of successive RR interval pairs that differ by more than 50 ms.
            pNN50 = (number of |RR[i+1] - RR[i]| > 50 ms) / total x 100

            Physiological interpretation
                primarily reflects parasympathetic activity

            Reading
                * High pNN50 → high variability (relaxation)
                * Low pNN50 → stress / fatigue

            Typical values
            | pNN50 (%) | Interprétation |
            | --------- | -------------- |
            | < 5%      | very low       |
            | 5 – 15%   | low            |
            | 15 – 30%  | normal         |
            | > 30%     | high           |

            However, this indicator is not very reliable and is sensitive to noise.

        """
        diff = np.abs(np.diff(self.intervals))
        return float(np.sum(diff > 50) / len(diff) * 100)

    # ======================
    # VISUALISATION DEBUG
    # ======================

    def summary(self) -> dict:
        return {
            "n": len(self.intervals),
            "duration_s": self.duration,
            "mean_rr": self.mean_rr,
            "mean_hr": self.mean_hr,
            "sdnn": self.std(),
            "rmssd": self.rmssd(),
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
            f"rmssd={self.rmssd():.1f})"
        )