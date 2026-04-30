from __future__ import annotations

import glob
import json

import matplotlib.pyplot as plt

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.scoring import readiness_score_oura
from cardiolab.protocols.resting import resting_hrv
from cardiolab.signals.rr import RRSeries


def plot_resting_evolution(path="cardiolab/datasets/resting/*.json"):
    """
    FR :
    Affiche l'évolution du RMSSD et du score dans le temps.

    EN :
    Plots RMSSD and readiness score evolution over time.
    """

    files = sorted(glob.glob(path))

    dates = []
    rmssd_values = []
    scores = []

    baseline = Baseline()

    for file in files:
        with open(file) as f:
            data = json.load(f)

        rr = RRSeries(data["rr_intervals"])
        result = resting_hrv(rr)

        baseline.add(result)

        score = readiness_score_oura(result, baseline)

        dates.append(data["date"])
        rmssd_values.append(result.rmssd)
        scores.append(score)

    # ======================
    # PLOT RMSSD
    # ======================

    plt.figure()
    plt.plot(dates, rmssd_values)
    plt.title("RMSSD over time")
    plt.xticks(rotation=45)
    plt.tight_layout()

    # ======================
    # PLOT SCORE
    # ======================

    plt.figure()
    plt.plot(dates, scores)
    plt.title("Readiness Score over time")
    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.show()



def plot_resting_evolution_rolling(path="cardiolab/datasets/resting/*.json"):
    """
    FR :
    Affiche l'évolution du RMSSD, du RMSSD lissé (rolling médian)
    et du score.

    EN :
    Plots RMSSD, rolling median RMSSD and readiness score over time.
    """

    files = sorted(glob.glob(path))

    dates = []
    rmssd_values = []
    rolling_values = []
    scores = []

    baseline = Baseline()

    for file in files:
        with open(file) as f:
            data = json.load(f)

        rr = RRSeries(data["rr_intervals"])
        result = resting_hrv(rr)

        baseline.add(result)

        score = readiness_score_oura(result, baseline)

        dates.append(data["date"])
        rmssd_values.append(result.rmssd)
        scores.append(score)

        rolling = baseline.rolling_rmssd_median()
        rolling_values.append(rolling[-1] if rolling else None)

    # RMSSD + rolling
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