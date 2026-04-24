from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from signals.rr import RRSeries


@dataclass
class ECGSignal:
    """
    FR :
    Représentation d'un signal ECG.

    Parameters
    ----------
    data : np.ndarray
        Signal ECG brut
    sampling_rate : Optional[float]
        Fréquence d'échantillonnage (Hz)
    timestamps : Optional[np.ndarray]
        Temps associés (secondes)

    Notes
    -----
    - Fournir au moins sampling_rate OU timestamps
    - Si les deux sont fournis → validation de cohérence
    
    EN :
    ECG signal representation.

    Parameters
    ----------
    data: np.ndarray
        Raw ECG signal
    sampling_rate: Optional[float]
        Sampling rate (Hz)
    timestamps: Optional[np.ndarray]
    A   ssociated times (seconds)

    Notes
    ----
    - Provide at least sampling_rate OR timestamps
    - If both are provided → consistency check
    """

    data: np.ndarray
    sampling_rate: Optional[float] = None
    timestamps: Optional[np.ndarray] = None

    def __post_init__(self):
        self.data = np.asarray(self.data, dtype=float)

        if self.timestamps is not None:
            self.timestamps = np.asarray(self.timestamps, dtype=float)
            if len(self.timestamps) != len(self.data):
                raise ValueError("timestamps et data doivent avoir la même longueur")

        if self.sampling_rate is None and self.timestamps is None:
            raise ValueError("Fournir sampling_rate OU timestamps")

        # ======================
        # CAS 1 : timestamps → déduire sampling_rate
        # ======================
        if self.sampling_rate is None:
            self.sampling_rate = self._infer_sampling_rate()

        # ======================
        # CAS 2 : sampling_rate → créer timestamps
        # ======================
        elif self.timestamps is None:
            self.timestamps = self._generate_timestamps()

        # ======================
        # CAS 3 : les deux → vérifier cohérence
        # ======================
        else:
            self._validate_consistency()

    # ======================
    # INFÉRENCE
    # ======================

    def _infer_sampling_rate(self) -> float:
        """
        FR : 
        Déduit la fréquence d'échantillonnage à partir des timestamps.
        
        EN :
        Deduce the sampling frequency from the timestamps.
        """

        dt = np.diff(self.timestamps)

        # moyenne (robuste au bruit léger)
        mean_dt = np.mean(dt)

        if mean_dt <= 0:
            raise ValueError("timestamps invalid")

        fs = 1.0 / mean_dt
        return float(fs)

    def _generate_timestamps(self) -> np.ndarray:
        """
        FR :
        Génère timestamps à partir du sampling_rate.
        
        EN:
        Generate timestamps from sampling_rate.
        """

        if self.sampling_rate <= 0:
            raise ValueError("sampling_rate must be > 0")

        n = len(self.data)
        return np.arange(n) / self.sampling_rate

    # ======================
    # VALIDATION
    # ======================

    def _validate_consistency(self):
        """
        FR : 
        Vérifie que sampling_rate et timestamps sont cohérents.
        
        EN :
        Check that sampling_rate and timestamps are consistent.
        """

        dt = np.diff(self.timestamps)
        mean_dt = np.mean(dt)

        expected_dt = 1.0 / self.sampling_rate

        # tolérance (important en pratique)
        if not np.isclose(mean_dt, expected_dt, rtol=1e-2):
            raise ValueError(
                f"Inconsistence between timestamps / sampling_rate "
                f"(dt={mean_dt:.6f} vs expected={expected_dt:.6f})"
            )

    # ======================
    # PROPRIÉTÉS
    # ======================

    @property
    def duration(self) -> float:
        return self.timestamps[-1] - self.timestamps[0]

    # ======================
    # PRÉPROCESSING
    # ======================

    def bandpass_filter(self, low: float = 5.0, high: float = 15.0) -> np.ndarray:
        from scipy.signal import butter, filtfilt

        nyquist = 0.5 * self.sampling_rate
        low /= nyquist
        high /= nyquist

        b, a = butter(2, [low, high], btype="band")
        return filtfilt(b, a, self.data)

    # ======================
    # R-PEAK DETECTION
    # ======================

    def detect_r_peaks(self) -> np.ndarray:
        '''
        FR :
        Fonction permettant de detecter les pics, les pics R après avoir passer un filtre passe bande.
        
        EN :
        Function allowing the detection of peaks, R peaks after passing through a bandpass filter.
        '''
        from scipy.signal import find_peaks

        filtered = self.bandpass_filter()
        squared = filtered ** 2

        window_size = int(0.150 * self.sampling_rate)
        integrated = np.convolve(
            squared,
            np.ones(window_size) / window_size,
            mode="same"
        )

        distance = int(0.3 * self.sampling_rate)
        peaks, _ = find_peaks(integrated, distance=distance)

        return peaks

    # ======================
    # ECG → RR
    # ======================

    def to_rr(self, clean: bool = True) -> RRSeries:
        '''
        FR :
        Construction de la RRSeries à partir des données de l'ECG Brute.
        RRSeries étant les intervalles de temps (en ms) entre les pics R consécutifs.

        EN :
        Construction of the RRSeries from the raw ECG data.
RRSeries are the time intervals (in ms) between consecutive R peaks.
        '''
        
        r_peaks = self.detect_r_peaks()

        if len(r_peaks) < 2:
            raise ValueError("Not enough R-peaks")

        rr_intervals = np.diff(self.timestamps[r_peaks]) * 1000.0

        rr_timestamps = (
            (self.timestamps[r_peaks[:-1]] + self.timestamps[r_peaks[1:]]) / 2
        )

        rr = RRSeries(rr_intervals, rr_timestamps)

        if clean:
            rr = rr.remove_outliers()

        return rr

    def __repr__(self):
        return (
            f"ECGSignal(len={len(self.data)}, "
            f"fs={self.sampling_rate:.2f}Hz, "
            f"duration={self.duration:.2f}s)"
        )