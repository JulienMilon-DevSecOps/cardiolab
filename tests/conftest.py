"""Pytest configuration and shared fixtures for all tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

# ── Chargement .env ──────────────────────────────────────────────────────────
# Charge les variables d'environnement depuis le .env situé à la racine du
# projet (un niveau au-dessus de tests/).  Permet d'utiliser DB_HOST_TEST,
# DB_NAME_TEST, etc. directement dans les tests d'intégration sans avoir à les
# exporter manuellement dans le shell.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent.parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv facultatif — CI n'en a pas besoin

from cardiolab.analytics.baseline import Baseline
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.signals.ecg import ECGSignal
from cardiolab.signals.rr import RRSeries

# ======================
# RRSeries FIXTURES
# ======================


@pytest.fixture
def normal_rr_series():
    """Return a normal RRSeries of 300 intervals at ~70 bpm (resting state)."""
    # Simulating normal resting HR ~70 bpm = 857 ms interval
    intervals = np.random.normal(857, 20, 300).clip(min=300)
    return RRSeries(intervals=intervals)


@pytest.fixture
def short_rr_series():
    """Short RRSeries - < 1 minute (only 30 intervals)."""
    intervals = np.random.normal(857, 20, 30).clip(min=300)
    return RRSeries(intervals=intervals)


@pytest.fixture
def elevated_hr_rr_series():
    """RRSeries with elevated heart rate (high stress/exercise)."""
    # Higher HR = shorter intervals ~600ms (100 bpm)
    intervals = np.random.normal(600, 15, 300).clip(min=300)
    return RRSeries(intervals=intervals)


@pytest.fixture
def low_variability_rr_series():
    """RRSeries with low variability - potential illness/fatigue."""
    intervals = np.random.normal(857, 5, 300).clip(min=300)  # Very low std
    return RRSeries(intervals=intervals)


@pytest.fixture
def rr_series_with_outliers():
    """RRSeries with some outlier intervals (arrhythmias)."""
    intervals = np.random.normal(857, 20, 300).clip(min=300)
    # Add some outliers
    intervals[50] = 1500  # big gap
    intervals[150] = 200  # small gap
    return RRSeries(intervals=intervals)


@pytest.fixture
def rr_series_with_timestamps():
    """RRSeries with explicit timestamps."""
    intervals = np.random.normal(857, 20, 100).clip(min=300)
    timestamps = np.cumsum(intervals / 1000.0)
    return RRSeries(intervals=intervals, timestamps=timestamps)


# ======================
# ECGSignal FIXTURES
# ======================


@pytest.fixture
def normal_ecg_signal():
    """Return a normal 5-minute ECG signal at 256 Hz with ~70 bpm heart rate."""
    fs = 256
    duration = 300  # 5 min in seconds
    t = np.linspace(0, duration, fs * duration)
    # Simulate ECG with heart rate ~70 bpm
    signal = (
        np.sin(2 * np.pi * (70 / 60) * t)
        + 0.1 * np.sin(2 * np.pi * 5 * t)  # Some harmonic
        + 0.01 * np.random.randn(len(t))  # Small noise
    )
    return ECGSignal(signal, sampling_rate=fs)


@pytest.fixture
def clean_ecg_signal():
    """Clean ECG signal without noise."""
    fs = 256
    duration = 60  # 1 min
    t = np.linspace(0, duration, fs * duration)
    signal = np.sin(2 * np.pi * (70 / 60) * t)
    return ECGSignal(signal, sampling_rate=fs)


@pytest.fixture
def noisy_ecg_signal():
    """ECG signal with high noise level."""
    fs = 256
    duration = 60
    t = np.linspace(0, duration, fs * duration)
    signal = (
        np.sin(2 * np.pi * (70 / 60) * t) + 0.5 * np.random.randn(len(t))  # High noise
    )
    return ECGSignal(signal, sampling_rate=fs)


@pytest.fixture
def short_ecg_signal():
    """Short ECG signal - only 30 seconds."""
    fs = 256
    duration = 30
    t = np.linspace(0, duration, fs * duration)
    signal = np.sin(2 * np.pi * (70 / 60) * t)
    return ECGSignal(signal, sampling_rate=fs)


# ======================
# HRVFeatures FIXTURES
# ======================


@pytest.fixture
def normal_hrv_features():
    """Return normal HRV features representing a healthy resting session."""
    return HRVFeatures(
        date="2026-05-12T10:00:00",
        rmssd=60.0,
        ln_rmssd=4.09,
        sdnn=80.0,
        pnn50=25.0,
        mean_hr=70.0,
        vlf=500.0,
        lf=1500.0,
        hf=2000.0,
        lf_hf=0.75,
        hf_pct=0.4,
        lf_nu=0.4,
        hf_nu=0.6,
        hf_hr=2000.0 / 70.0,
        duration=300.0,
        score=75.0,
    )


@pytest.fixture
def poor_hrv_features():
    """Poor HRV features - fatigue/stress state."""
    return HRVFeatures(
        date="2026-05-12T11:00:00",
        rmssd=25.0,  # Low RMSSD
        ln_rmssd=3.22,
        sdnn=40.0,
        pnn50=5.0,
        mean_hr=85.0,  # Elevated HR
        vlf=200.0,
        lf=800.0,
        hf=400.0,  # Low HF
        lf_hf=2.0,  # High ratio
        hf_pct=0.2,
        lf_nu=0.67,
        hf_nu=0.33,
        hf_hr=400.0 / 85.0,
        duration=300.0,
        score=35.0,
    )


@pytest.fixture
def excellent_hrv_features():
    """Excellent HRV features - well recovered state."""
    return HRVFeatures(
        date="2026-05-12T09:00:00",
        rmssd=100.0,
        ln_rmssd=4.61,
        sdnn=120.0,
        pnn50=50.0,
        mean_hr=55.0,
        vlf=800.0,
        lf=2000.0,
        hf=3500.0,
        lf_hf=0.57,
        hf_pct=0.55,
        lf_nu=0.36,
        hf_nu=0.64,
        hf_hr=3500.0 / 55.0,
        duration=300.0,
        score=92.0,
    )


# ======================
# Baseline FIXTURES
# ======================


@pytest.fixture
def baseline_7days(normal_hrv_features, excellent_hrv_features, poor_hrv_features):
    """Baseline with 7 days of data (normal pattern)."""
    features = [normal_hrv_features]
    # Generate 6 more days of similar data
    for i in range(1, 7):
        feature = HRVFeatures(
            date=f"2026-05-{12 - i:02d}T10:00:00",
            rmssd=60.0 + np.random.normal(0, 5),
            ln_rmssd=4.09,
            sdnn=80.0 + np.random.normal(0, 5),
            pnn50=25.0 + np.random.normal(0, 3),
            mean_hr=70.0 + np.random.normal(0, 2),
            vlf=500.0,
            lf=1500.0,
            hf=2000.0,
            lf_hf=0.75,
            hf_pct=0.4,
            lf_nu=0.4,
            hf_nu=0.6,
            duration=300.0,
            score=75.0 + np.random.normal(0, 5),
        )
        features.append(feature)

    return Baseline(history=features, window=7)


@pytest.fixture
def baseline_30days():
    """Baseline with 30 days of data."""
    features = []
    for i in range(30):
        # Create 30 days with gradual variation
        date = f"2026-04-{13 + (i % 30):02d}T10:00:00"
        # Simulate gradual improvement (RMSSD increases)
        rmssd_value = 50.0 + i
        feature = HRVFeatures(
            date=date,
            rmssd=rmssd_value,
            ln_rmssd=np.log(rmssd_value),
            sdnn=70.0 + i * 0.5,
            pnn50=20.0 + i * 0.3,
            mean_hr=75.0 - i * 0.1,
            vlf=500.0,
            lf=1500.0,
            hf=2000.0,
            lf_hf=0.75,
            hf_pct=0.4,
            lf_nu=0.4,
            hf_nu=0.6,
            duration=300.0,
            score=70.0 + i * 0.5,
        )
        features.append(feature)

    return Baseline(history=features, window=7)


@pytest.fixture
def baseline_insufficient_data():
    """Baseline with only 2 data points (insufficient for some analyses)."""
    features = [
        HRVFeatures(
            date="2026-05-11",
            rmssd=60.0,
            ln_rmssd=4.09,
            sdnn=80.0,
            pnn50=25.0,
            mean_hr=70.0,
            vlf=500.0,
            lf=1500.0,
            hf=2000.0,
            lf_hf=0.75,
            hf_pct=0.4,
            lf_nu=0.4,
            hf_nu=0.6,
            duration=300.0,
            score=75.0,
        ),
        HRVFeatures(
            date="2026-05-12",
            rmssd=65.0,
            ln_rmssd=4.17,
            sdnn=85.0,
            pnn50=27.0,
            mean_hr=68.0,
            vlf=520.0,
            lf=1600.0,
            hf=2100.0,
            lf_hf=0.76,
            hf_pct=0.41,
            lf_nu=0.43,
            hf_nu=0.57,
            duration=300.0,
            score=78.0,
        ),
    ]
    return Baseline(history=features, window=7)


# ======================
# File FIXTURES
# ======================


@pytest.fixture
def temp_csv_polar_file(tmp_path):
    """Create a temporary Polar CSV file for testing."""
    csv_file = tmp_path / "polar_sample.csv"
    csv_content = """RR(ms),Time(s)
810,0.81
800,1.61
805,2.41
795,3.20
810,4.01
800,4.81
805,5.61
795,6.41
"""
    csv_file.write_text(csv_content)
    return csv_file


@pytest.fixture
def temp_txt_polar_file(tmp_path):
    """Create a temporary Polar TXT file for testing."""
    txt_file = tmp_path / "polar_sample.txt"
    txt_content = """810
800
805
795
810
800
805
795
"""
    txt_file.write_text(txt_content)
    return txt_file


@pytest.fixture
def temp_invalid_csv_file(tmp_path):
    """Create a temporary invalid CSV file."""
    csv_file = tmp_path / "invalid.csv"
    csv_content = """column1,column2
value1,value2
"""
    csv_file.write_text(csv_content)
    return csv_file


@pytest.fixture
def temp_empty_file(tmp_path):
    """Create an empty file."""
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("")
    return empty_file


# ======================
# Mock Data Generators
# ======================


@pytest.fixture
def hrv_features_generator():
    """Return a factory function for creating HRVFeatures with custom parameters."""

    def _create(
        rmssd: float = 60.0,
        sdnn: float = 80.0,
        mean_hr: float = 70.0,
        date: str | None = None,
        **kwargs,
    ) -> HRVFeatures:
        if date is None:
            date = datetime.now().isoformat()

        ln_rmssd_val = np.log(rmssd) if rmssd > 0 else 0.0
        return HRVFeatures(
            date=date,
            rmssd=rmssd,
            ln_rmssd=ln_rmssd_val,
            sdnn=sdnn,
            pnn50=kwargs.get("pnn50", 25.0),
            mean_hr=mean_hr,
            vlf=kwargs.get("vlf", 500.0),
            lf=kwargs.get("lf", 1500.0),
            hf=kwargs.get("hf", 2000.0),
            lf_hf=kwargs.get("lf_hf", 0.75),
            hf_pct=kwargs.get("hf_pct", 0.4),
            lf_nu=kwargs.get("lf_nu", 0.4),
            hf_nu=kwargs.get("hf_nu", 0.6),
            duration=kwargs.get("duration", 300.0),
            score=kwargs.get("score", 75.0),
        )

    return _create


@pytest.fixture
def rr_series_generator():
    """Return a factory function for creating RRSeries with custom HR and variability."""

    def _create(
        mean_rr: float = 857,
        std_rr: float = 20,
        length: int = 300,
        with_outliers: bool = False,
    ) -> RRSeries:
        intervals = np.random.normal(mean_rr, std_rr, length).clip(min=300)

        if with_outliers:
            # Add some outliers
            outlier_indices = np.random.choice(length, size=5, replace=False)
            for idx in outlier_indices:
                intervals[idx] = np.random.choice([1500, 200])

        return RRSeries(intervals=intervals)

    return _create
