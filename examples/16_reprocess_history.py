"""Reprocess stored sessions from their raw RR intervals (cardiolab ≥ 0.4.0).

cardiolab 0.4.0 changes computed values (artefact correction, Lomb-Scargle,
signal quality). ``reprocess_sessions()`` recomputes every stored session from
``hrv_raw_sessions`` with the current pipeline:

1. Dry run (default) — before / after report, nothing written.
2. ``--apply`` — results replaced in one transaction; resting readiness
   scores recomputed in chronological order.
3. Running it again reports every session as unchanged.

Prerequisites
-------------
* Migrations applied (``01_setup_database.py`` — V005 adds the ``quality``
  column).
* Sessions saved with their raw RR (``02_feed_database.py``).
* ``.env`` file with ``DB_*`` and ``USER_ID``.

Usage
-----
Run from the project root::

    python examples/16_reprocess_history.py            # dry run
    python examples/16_reprocess_history.py --apply    # write

"""

from __future__ import annotations

import os
import sys
import uuid

from dotenv import load_dotenv

from cardiolab.database import HRVRepository, reprocess_sessions

load_dotenv()

_raw_user_id = os.environ.get("USER_ID")
if _raw_user_id is None:
    raise SystemExit("USER_ID not found in environment.")
USER_ID = str(uuid.UUID(_raw_user_id))
APPLY = "--apply" in sys.argv

with HRVRepository.from_env() as repo:
    report = reprocess_sessions(repo, USER_ID, dry_run=not APPLY)

print(report.summary())

# Largest score changes
for s in sorted(report.sessions, key=lambda s: s.date):
    if "score" in s.deltas():
        before, after = s.deltas()["score"]
        print(f"  {s.protocol:<12} {s.date}  score {before} → {after:.1f}")

if report.skipped:
    print(f"\n{len(report.skipped)} stored session(s) without raw RR — left untouched.")
if not APPLY:
    print("\nDry run — run with --apply to write.")
