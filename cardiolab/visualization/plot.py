"""Visualisation helpers for resting HRV session histories."""

from __future__ import annotations

import glob
import json

import matplotlib.pyplot as plt

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.scoring import readiness_score_oura
from cardiolab.protocols.resting import resting_hrv
from cardiolab.signals.rr import RRSeries


def plot_resting_evolution(path: str = "cardiolab/datasets/resting/*.json") -> None:
    """Plot RMSSD and readiness score over time from stored session files.

    Loads all JSON session records matching ``path``, runs the resting HRV
    protocol on each, computes the readiness score relative to all previous
    sessions, and displays two separate figures:

    1. RMSSD over time.
    2. Readiness score over time.

    Args:
        path: Glob pattern pointing to the JSON session files.
            Defaults to ``"cardiolab/datasets/resting/*.json"``.

    """
    files = sorted(glob.glob(path))

    dates = []
    rmssd_values = []
    scores = []
    past_features = []

    for file in files:
        with open(file) as f:
            data = json.load(f)

        rr = RRSeries(data["rr_intervals"])
        result = resting_hrv(rr)
        result.date = data["date"]

        baseline = Baseline.from_features(past_features) if past_features else Baseline()
        score = readiness_score_oura(result, baseline)

        past_features.append(result)
        dates.append(data["date"])
        rmssd_values.append(result.rmssd)
        scores.append(score)

    # ======================
    # RMSSD plot
    # ======================

    plt.figure()
    plt.plot(dates, rmssd_values)
    plt.title("RMSSD over time")
    plt.xticks(rotation=45)
    plt.tight_layout()

    # ======================
    # Score plot
    # ======================

    plt.figure()
    plt.plot(dates, scores)
    plt.title("Readiness Score over time")
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.show()


def plot_resting_evolution_rolling(
    path: str = "cardiolab/datasets/resting/*.json",
) -> None:
    """Plot RMSSD, its rolling median, and readiness score from session files.

    Identical to ``plot_resting_evolution`` but adds a second line on the
    RMSSD figure showing the rolling median, which smooths day-to-day
    fluctuations and highlights longer-term trends.

    Args:
        path: Glob pattern pointing to the JSON session files.
            Defaults to ``"cardiolab/datasets/resting/*.json"``.

    """
    files = sorted(glob.glob(path))

    dates = []
    rmssd_values = []
    rolling_values = []
    scores = []
    past_features = []

    for file in files:
        with open(file) as f:
            data = json.load(f)

        rr = RRSeries(data["rr_intervals"])
        result = resting_hrv(rr)
        result.date = data["date"]

        baseline = Baseline.from_features(past_features) if past_features else Baseline()
        score = readiness_score_oura(result, baseline)

        past_features.append(result)
        dates.append(data["date"])
        rmssd_values.append(result.rmssd)
        scores.append(score)

        rolling = baseline.rolling_rmssd_median()
        rolling_values.append(rolling[-1] if rolling else None)

    # RMSSD + rolling median
    plt.figure()
    plt.plot(dates, rmssd_values, label="RMSSD")
    plt.plot(dates, rolling_values, label="RMSSD (rolling median)")
    plt.legend()
    plt.title("RMSSD evolution")
    plt.xticks(rotation=45)
    plt.tight_layout()

    # Score
    plt.figure()
    plt.plot(dates, scores)
    plt.title("Readiness Score")
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.show()
