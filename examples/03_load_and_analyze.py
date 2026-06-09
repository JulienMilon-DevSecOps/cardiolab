"""Load persisted HRV sessions from the database and run the analytics pipeline.

Demonstrates the full read-side workflow:
1. Retrieve all resting sessions for a user from PostgreSQL.
2. Build a personal baseline (rolling 7-session window).
3. Score the most recent session with multi-factor and composite readiness.
4. Detect RMSSD anomalies using three methods.
5. Compute the long-term RMSSD trend.

Prerequisites
-------------
* ``01_setup_database.py`` has been run once.
* ``02_feed_database.py`` has been run to populate the table.
* ``.env`` file with ``DB_*`` and ``USER_ID``.

Usage
-----
Run from the project root::

    python example/03_load_and_analyze.py

"""

from __future__ import annotations

import os
import uuid

from dotenv import load_dotenv

from cardiolab.analytics.anomaly import detect_rmssd_anomaly
from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.scoring import readiness_score_composite, readiness_score_multi
from cardiolab.analytics.trends import trend_rmssd
from cardiolab.database.repository import HRVRepository

load_dotenv()

_raw_user_id = os.environ.get("USER_ID")
if _raw_user_id is None:
    raise SystemExit(
        "USER_ID not found in environment.\n"
        "Run 02_feed_database.py first to populate the database."
    )
USER_ID = str(uuid.UUID(_raw_user_id))


def _sep(title: str = "") -> None:
    if title:
        print(f"\n{'─' * 10} {title} {'─' * (44 - len(title))}")
    else:
        print("─" * 55)


def analyze() -> None:
    """Load HRV sessions from the DB and run the full analytics pipeline."""
    print("=== cardiolab — load & analyze ===\n")
    print(f"User ID : {USER_ID}")

    with HRVRepository.from_env() as repo:
        features = repo.load_features(user_id=USER_ID)

    if not features:
        raise SystemExit(
            f"No sessions found for USER_ID={USER_ID}.\nRun 02_feed_database.py first."
        )

    # ── 1. Sessions overview ──────────────────────────────────────────────────
    _sep("SESSIONS")
    print(f"\n  {len(features)} session(s) found.\n")
    print(f"  {'Date':<25} {'RMSSD':>7} {'HR':>6} {'Score':>7}")
    print(f"  {'-' * 50}")
    for f in features:
        score_str = f"{f.score:>7.1f}" if f.score is not None else "    n/a"
        print(f"  {str(f.date):<25} {f.rmssd:>7.1f} {f.mean_hr:>6.1f} {score_str}")

    # ── 2. Baseline ───────────────────────────────────────────────────────────
    baseline = Baseline.from_features(features)

    _sep("BASELINE (7-session window)")
    print(f"\n  RMSSD mean   : {baseline.mean_rmssd():.2f} ms")
    print(f"  RMSSD median : {baseline.median_rmssd():.2f} ms")
    print(f"  HR mean      : {baseline.mean_hr():.1f} bpm")

    # ── 3. Readiness scoring ──────────────────────────────────────────────────
    latest = features[-1]
    score_multi = readiness_score_multi(latest, baseline)
    score_composite = readiness_score_composite(latest, baseline)

    _sep("READINESS — latest session")
    print(f"\n  Date              : {latest.date}")
    print(f"  RMSSD             : {latest.rmssd:.2f} ms")
    print(f"  Score multi       : {score_multi:.1f} / 100")
    print(f"  Score composite   : {score_composite:.1f} / 100")

    label = (
        "Very well recovered"
        if score_multi >= 80
        else "Normal recovery"
        if score_multi >= 60
        else "Mild fatigue"
        if score_multi >= 40
        else "Fatigued"
        if score_multi >= 20
        else "Overload — rest advised"
    )
    print(f"  Interpretation    : {label}")

    # ── 4. Anomaly detection ──────────────────────────────────────────────────
    if len(features) >= 3:
        _sep("RMSSD ANOMALY")
        for method in ("simple", "zscore", "rolling"):
            result = detect_rmssd_anomaly(latest, baseline, method=method)
            status = result.get("status", "n/a")
            print(f"\n  Method {method:<8} : {status}")
            if "delta_pct" in result:
                print(f"    Δ vs baseline  : {result['delta_pct']:+.1f} %")
            if "z" in result:
                print(f"    z-score        : {result['z']:+.2f}")
    else:
        print("\n  [Anomaly] Not enough sessions (minimum 3).")

    # ── 5. RMSSD trend ────────────────────────────────────────────────────────
    if len(features) >= 5:
        _sep("RMSSD TREND")
        trend = trend_rmssd(baseline)
        print(f"\n  Direction : {trend['trend']}")
        print(f"  Slope     : {trend['slope']:+.2f} ms / session")
    else:
        print("\n  [Trend] Not enough sessions (minimum 5).")

    _sep()
    print()


if __name__ == "__main__":
    analyze()
