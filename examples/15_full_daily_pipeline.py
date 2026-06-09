"""Example 15 — Full daily HRV pipeline (synthetic, no database required).

Simulates a complete morning routine from raw RR data to actionable readiness
and training load decision:

  1. Morning RR measurement → resting HRV protocol.
  2. Personal baseline from 30 days of history.
  3. Readiness scoring (multi-factor + composite).
  4. RMSSD anomaly detection (z-score method).
  5. TRIMP calculation for the planned training session.
  6. ATL/CTL/TSB update with today's session.
  7. Summary output.

All data is generated synthetically — runs without PostgreSQL or real files.
To persist the session, uncomment the database block at the bottom.

Usage::

    python example/15_full_daily_pipeline.py

"""

from __future__ import annotations

import warnings
from datetime import date as _date
from datetime import timedelta

import numpy as np

from cardiolab import (
    Baseline,
    RRSeries,
    detect_rmssd_anomaly,
    readiness_score_composite,
    readiness_score_multi,
    resting_hrv,
    trend_rmssd,
)
from cardiolab.analytics.training_load import (
    TrainingLoad,
    trimp_banister,
    trimp_hrv_based,
)
from cardiolab.signals.rr import PhysiologicalWarning

rng = np.random.default_rng(42)

TODAY = str(_date(2026, 6, 9))

print("=" * 60)
print(f"  cardiolab — Daily HRV Pipeline  ({TODAY})")
print("=" * 60)


# ── Step 1: Morning RR measurement ────────────────────────────────────────────
print("\n── Step 1 · Morning RR measurement ─────────────────────────")

rr_morning = rng.normal(920, 45, 310).clip(600, 1400)
with warnings.catch_warnings():
    warnings.simplefilter("ignore", PhysiologicalWarning)
    rr = RRSeries(rr_morning)
    today_features = resting_hrv(rr, min_duration=0.0)

print(f"  RMSSD    : {today_features.rmssd:.1f} ms")
print(f"  Mean HR  : {today_features.mean_hr:.1f} bpm")
print(f"  SDNN     : {today_features.sdnn:.1f} ms")
print(f"  LF/HF    : {today_features.lf_hf:.2f}")


# ── Step 2: Personal baseline (30-day history) ────────────────────────────────
print("\n── Step 2 · Personal baseline (30 days) ─────────────────────")

history = []
base_start = _date(2026, 5, 10)
for i in range(30):
    d = base_start + timedelta(days=i)
    hist_rr = rng.normal(870, 40, 300).clip(600, 1400)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PhysiologicalWarning)
        f = resting_hrv(RRSeries(hist_rr), min_duration=0.0)
    history.append(f)

baseline = Baseline.from_features(history)
print(f"  Baseline RMSSD  : {baseline.mean_rmssd():.1f} ms  (median: {baseline.median_rmssd():.1f})")
print(f"  Baseline HR     : {baseline.mean_hr():.1f} bpm")

trend = trend_rmssd(baseline)
print(f"  RMSSD trend     : {trend['trend']}  (slope {trend['slope']:+.2f} ms/session)")


# ── Step 3: Readiness scoring ─────────────────────────────────────────────────
print("\n── Step 3 · Readiness scoring ───────────────────────────────")

score_multi = readiness_score_multi(today_features, baseline)
score_comp = readiness_score_composite(today_features, baseline)

print(f"  Multi-factor    : {score_multi:.1f} / 100")
print(f"  Composite       : {score_comp:.1f} / 100")

if score_multi >= 80:
    readiness_label = "Very well recovered — train hard"
elif score_multi >= 60:
    readiness_label = "Normal recovery — moderate session OK"
elif score_multi >= 40:
    readiness_label = "Mild fatigue — reduce intensity"
else:
    readiness_label = "High fatigue — rest or light activity"
print(f"  Interpretation  : {readiness_label}")


# ── Step 4: RMSSD anomaly detection ───────────────────────────────────────────
print("\n── Step 4 · Anomaly detection (z-score) ─────────────────────")

anomaly = detect_rmssd_anomaly(today_features, baseline, method="zscore")
print(f"  Status : {anomaly['status']}")
if "z" in anomaly:
    print(f"  Z-score: {anomaly['z']:+.2f}")


# ── Step 5: TRIMP for today's planned training ────────────────────────────────
print("\n── Step 5 · TRIMP — planned 60-min run ──────────────────────")

# HRV-based: readiness drives the training impulse.
trimp_hrv = trimp_hrv_based(duration_min=60.0, readiness_score=score_multi)

# Banister: use if you have a heart rate monitor.
trimp_ban = trimp_banister(
    duration_min=60.0,
    hr_mean=148.0,
    hr_max=185.0,
    hr_rest=52.0,
    sex="male",
)
print(f"  HRV-based TRIMP : {trimp_hrv:.1f}")
print(f"  Banister TRIMP  : {trimp_ban:.1f}")


# ── Step 6: ATL / CTL / TSB update ────────────────────────────────────────────
print("\n── Step 6 · ATL / CTL / TSB ─────────────────────────────────")

# Build session list from the 30-day history + today.
past_sessions = [
    {"date": str(base_start + timedelta(days=i)), "trimp": trimp_hrv_based(60, 65)}
    for i in range(30)
    if rng.random() < 0.6
]
past_sessions.append({"date": TODAY, "trimp": trimp_hrv})

tl = TrainingLoad.from_sessions(past_sessions)
print(f"  ATL (fatigue)  : {tl.atl[-1]:.1f}")
print(f"  CTL (fitness)  : {tl.ctl[-1]:.1f}")
print(f"  TSB (form)     : {tl.tsb[-1]:+.1f}  ({'fresh' if tl.tsb[-1] >= 0 else 'fatigued'})")


# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  DAILY SUMMARY")
print("=" * 60)
print(f"  Date            : {TODAY}")
print(f"  RMSSD           : {today_features.rmssd:.1f} ms  (baseline: {baseline.mean_rmssd():.1f})")
print(f"  Readiness       : {score_multi:.1f} / 100  → {readiness_label}")
print(f"  Anomaly         : {anomaly['status']}")
print(f"  TRIMP (planned) : {trimp_hrv:.1f}")
print(f"  TSB             : {tl.tsb[-1]:+.1f}")
print()


# ── Optional: persist to database ─────────────────────────────────────────────
# Uncomment the block below once PostgreSQL is configured.
#
# import dataclasses
# import os, uuid
# from dotenv import load_dotenv
# from cardiolab.database import HRVRepository
#
# load_dotenv()
# USER_ID = str(uuid.UUID(os.environ["USER_ID"]))
#
# with HRVRepository.from_env() as repo:
#     session = dataclasses.replace(today_features, date=TODAY)
#     repo.save_features([session], user_id=USER_ID)
#     repo.save_training_session(
#         user_id=USER_ID,
#         date=TODAY,
#         duration_min=60,
#         sport_type="running",
#         trimp=trimp_hrv,
#     )
# print("Session persisted to database.")
