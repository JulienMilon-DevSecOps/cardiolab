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

    with pytest.raises(
        ValueError, match=r"Inconsistency between timestamps and sampling_rate .*"
    ):
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


# ======================
# Construction — error branches
# ======================


def test_ecg_creation_without_sampling_rate_or_timestamps():
    """ECGSignal raises ValueError when neither sampling_rate nor timestamps is given."""
    data, _ = generate_fake_ecg()
    with pytest.raises(ValueError, match="Provide either sampling_rate or timestamps"):
        ECGSignal(data)


def test_ecg_creation_timestamps_wrong_length():
    """ECGSignal raises ValueError when timestamps length differs from data length."""
    data, fs = generate_fake_ecg()
    bad_timestamps = np.arange(len(data) - 10) / fs
    with pytest.raises(ValueError, match="timestamps and data must have the same length"):
        ECGSignal(data, timestamps=bad_timestamps)


def test_ecg_infer_sampling_rate_invalid_timestamps():
    """_infer_sampling_rate raises ValueError for non-monotone timestamps."""
    data, fs = generate_fake_ecg()
    # Decreasing timestamps → mean_dt < 0
    bad_timestamps = np.linspace(10.0, 0.0, len(data))
    with pytest.raises(ValueError, match="Invalid timestamps"):
        ECGSignal(data, timestamps=bad_timestamps)


def test_ecg_generate_timestamps_invalid_sampling_rate():
    """ECGSignal raises ValueError when sampling_rate is zero or negative."""
    data, _ = generate_fake_ecg()
    with pytest.raises(ValueError, match="sampling_rate must be > 0"):
        ECGSignal(data, sampling_rate=0.0)


# ======================
# Properties
# ======================


def test_ecg_duration():
    """duration returns the difference between last and first timestamp."""
    data, fs = generate_fake_ecg(fs=250, duration=10)
    ecg = ECGSignal(data, sampling_rate=fs)
    assert ecg.duration == pytest.approx(ecg.timestamps[-1] - ecg.timestamps[0])


# ======================
# to_rr variants
# ======================


def test_ecg_to_rr_no_clean():
    """to_rr(clean=False) returns a series without calling remove_outliers."""
    data, fs = generate_fake_ecg()
    ecg = ECGSignal(data, sampling_rate=fs)
    rr = ecg.to_rr(clean=False)
    assert len(rr) > 0


def test_ecg_to_rr_not_enough_peaks():
    """to_rr raises ValueError when fewer than 2 R-peaks are detected."""
    # A constant signal produces no peaks at all.
    data = np.zeros(500)
    ecg = ECGSignal(data, sampling_rate=250.0)
    with pytest.raises(ValueError, match="Not enough R-peaks detected"):
        ecg.to_rr()


# ======================
# __repr__
# ======================


def test_ecg_repr():
    """__repr__ returns a string containing ECGSignal metadata."""
    data, fs = generate_fake_ecg()
    ecg = ECGSignal(data, sampling_rate=fs)
    r = repr(ecg)
    assert "ECGSignal" in r
    assert "Hz" in r
