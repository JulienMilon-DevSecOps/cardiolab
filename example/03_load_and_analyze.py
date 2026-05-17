"""Load persisted HRV sessions from the database and run the analytics pipeline.

Demonstrates the full read-side workflow:
1. Retrieve all sessions for a user from PostgreSQL.
2. Build a personal baseline (rolling 7-day window).
3. Score the most recent session (Oura-inspired + multi-factor).
4. Detect anomalies in today's RMSSD.
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
from cardiolab.analytics.scoring import readiness_score_multi, readiness_score_oura
from cardiolab.analytics.trends import trend_rmssd
from cardiolab.database.repository import HRVRepository

load_dotenv()

_raw_user_id = os.environ.get("USER_ID")
if _raw_user_id is None:
    raise SystemExit(
        "USER_ID not found in environment.\n"
        "Run 02_feed_database.py first to generate and register your UUID."
    )
USER_ID = str(uuid.UUID(_raw_user_id))


# ---------------------------------------------------------------------------
# DISPLAY HELPERS
# ---------------------------------------------------------------------------


def _separator(title: str = "") -> None:
    if title:
        print(f"\n{'─' * 10} {title} {'─' * (44 - len(title))}")
    else:
        print("─" * 55)


def _display_session(label: str, f) -> None:
    print(f"\n  {label}")
    print(f"    Date      : {f.date}")
    print(f"    RMSSD     : {f.rmssd:.2f} ms")
    print(f"    ln_RMSSD  : {f.ln_rmssd:.3f}")
    print(f"    SDNN      : {f.sdnn:.2f} ms")
    print(f"    pNN50     : {f.pnn50:.1f} %")
    print(f"    HR moyen  : {f.mean_hr:.1f} bpm")
    print(f"    VLF       : {f.vlf:.5f}")
    print(f"    LF        : {f.lf:.5f}")
    print(f"    HF        : {f.hf:.5f}")
    print(f"    LF/HF     : {f.lf_hf:.2f}")
    print(f"    HF%       : {f.hf_pct:.2f}")
    print(f"    LF_nu     : {f.lf_nu:.2f}")
    print(f"    HF_nu     : {f.hf_nu:.2f}")
    print(f"    Durée     : {f.duration:.0f} s")


# ---------------------------------------------------------------------------
# ANALYTICS PIPELINE
# ---------------------------------------------------------------------------


def analyze() -> None:
    """Load features from DB and run the full analytics pipeline."""
    print("=== cardiolab — load & analyze ===\n")
    print(f"User ID : {USER_ID}")

    # ------------------------------------------------------------------
    # 1. LOAD FROM DATABASE
    # ------------------------------------------------------------------
    with HRVRepository.from_env() as repo:
        features = repo.load_features(user_id=USER_ID)

    if not features:
        raise SystemExit(
            f"No sessions found for USER_ID={USER_ID}.\nRun 02_feed_database.py first."
        )

    _separator("SESSIONS CHARGÉES")
    print(f"\n  {len(features)} session(s) trouvée(s) pour cet utilisateur.\n")
    print(f"  {'Date':<25} {'RMSSD':>7} {'HR':>6} {'Score':>7}")
    print(f"  {'-' * 50}")
    for f in features:
        print(f"  {str(f.date):<25} {f.rmssd:>7.1f} {f.mean_hr:>6.1f} {f.score:>7.1f}")

    # ------------------------------------------------------------------
    # 2. BASELINE (rolling 7 sessions)
    # ------------------------------------------------------------------
    baseline = Baseline.from_features(features)

    _separator("BASELINE (7 sessions)")
    print(f"\n  RMSSD moyen   : {baseline.mean_rmssd():.2f} ms")
    print(f"  RMSSD médiane : {baseline.median_rmssd():.2f} ms")
    print(f"  HR moyen      : {baseline.mean_hr():.1f} bpm")

    # ------------------------------------------------------------------
    # 3. SCORE DE LA DERNIÈRE SESSION
    # ------------------------------------------------------------------
    latest = features[-1]

    score_oura = readiness_score_oura(latest, baseline)
    score_multi = readiness_score_multi(latest, baseline)

    _separator("SCORE — SESSION LA PLUS RÉCENTE")
    _display_session("Métriques HRV", latest)

    print(f"\n    Score Oura        : {score_oura:.1f} / 100")
    print(f"    Score multi-factor: {score_multi:.1f} / 100")

    interpretation = (
        "Très bien récupéré"
        if score_multi >= 80
        else "Récupération normale"
        if score_multi >= 60
        else "Fatigue modérée"
        if score_multi >= 40
        else "Fatigué"
        if score_multi >= 20
        else "Surcharge — repos conseillé"
    )
    print(f"    Interprétation    : {interpretation}")

    # ------------------------------------------------------------------
    # 4. DÉTECTION D'ANOMALIE
    # ------------------------------------------------------------------
    if len(features) >= 3:
        _separator("ANOMALIE RMSSD")

        for method in ("simple", "zscore", "rolling"):
            result = detect_rmssd_anomaly(latest, baseline, method=method)
            status = result.get("status", "n/a")
            print(f"\n  Méthode {method:<8} : {status}")
            if "delta_pct" in result:
                print(f"    Δ vs baseline   : {result['delta_pct']:+.1f} %")
            if "z_score" in result:
                print(f"    z-score         : {result['z_score']:+.2f}")
    else:
        print("\n  [Anomalie] Pas assez de sessions (minimum 3).")

    # ------------------------------------------------------------------
    # 5. TENDANCE RMSSD
    # ------------------------------------------------------------------
    if len(features) >= 5:
        _separator("TENDANCE RMSSD")
        trend = trend_rmssd(baseline)
        print(f"\n  Direction : {trend['trend']}")
        print(f"  Pente     : {trend['slope']:+.2f} ms / session")
    else:
        print("\n  [Tendance] Pas assez de sessions (minimum 5).")

    _separator()
    print()


if __name__ == "__main__":
    analyze()
