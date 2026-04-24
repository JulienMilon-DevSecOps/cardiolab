from __future__ import annotations

import json
import glob

import numpy as np
import matplotlib.pyplot as plt

from signals.rr import RRSeries
from protocols.resting import resting_hrv
from analytics.baseline import Baseline
from analytics.scoring import readiness_score_oura


def plot_resting_evolution(path="datasets/resting/*.json"):
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