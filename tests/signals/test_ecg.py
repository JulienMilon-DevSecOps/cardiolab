"""Unit tests for the ECGSignal class.

FR :
Tests unitaires pour la classe ECGSignal.
Ces tests valident la création, la cohérence des données et la conversion en RR.
EN :
Unit tests for the ECGSignal class.
These tests validate creation, data consistency, and conversion to RR.
"""

import numpy as np
import pytest

from cardiolab.signals.ecg import ECGSignal


def generate_fake_ecg(fs=250, duration=10):
    """Generate a simple synthetic ECG signal for testing.
    
    FR :
    Génère un signal ECG synthétique simple pour les tests.
    EN :
    Generates a simple synthetic ECG signal for testing.
    """
    t = np.linspace(0, duration, fs * duration)
    signal = np.sin(2 * np.pi * 1.2 * t)
    return signal, fs


def test_ecg_creation_with_sampling_rate():
    """Ensure ECG can be created with a sampling rate.
    
    FR :
    Vérifie la création d’un ECG avec sampling_rate.
    EN :
    Ensures ECG can be created with a sampling rate.
    """
    data, fs = generate_fake_ecg()
    ecg = ECGSignal(data, sampling_rate=fs)

    assert ecg.sampling_rate == fs
    assert ecg.timestamps is not None


def test_ecg_creation_with_timestamps():
    """Ensure ECG can be created with timestamps.
    
    FR :
    Vérifie la création d’un ECG avec timestamps.
    EN :
    Ensures ECG can be created with timestamps.
    """
    data, fs = generate_fake_ecg()
    timestamps = np.arange(len(data)) / fs

    ecg = ECGSignal(data, timestamps=timestamps)

    assert ecg.sampling_rate > 0


def test_ecg_consistency_check():
    """Ensure inconsistency between timestamps and sampling rate raises an error.
    
    FR :
    Vérifie qu'une incohérence timestamps / sampling_rate lève une erreur.
    EN :
    Ensures inconsistency between timestamps and sampling rate raises an error.
    """
    data, fs = generate_fake_ecg()
    timestamps = np.arange(len(data)) / (fs * 2)  # incohérent

    with pytest.raises(ValueError, match=r"Inconsistency between timestamps and sampling_rate .*"):
        ECGSignal(data, sampling_rate=fs, timestamps=timestamps)


def test_r_peak_detection():
    """Ensure R-peaks are detected.
    
    FR :
    Vérifie que des R-peaks sont détectés.
    EN :
    Ensures R-peaks are detected.
    """
    data, fs = generate_fake_ecg()
    ecg = ECGSignal(data, sampling_rate=fs)

    peaks = ecg.detect_r_peaks()
    assert len(peaks) > 0


def test_ecg_to_rr():
    """Ensure ECG → RRSeries conversion works.
    
    FR :
    Vérifie la conversion ECG → RRSeries.
    EN :
    Ensures ECG → RRSeries conversion works.
    """
    data, fs = generate_fake_ecg()
    ecg = ECGSignal(data, sampling_rate=fs)

    rr = ecg.to_rr()
    assert len(rr) > 0