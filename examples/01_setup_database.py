"""Initialize the PostgreSQL database — run this script only once.

Applies all pending SQL migrations to create the full cardiolab schema:
``hrv_features``, ``hrv_orthostatic``, ``hrv_coherence``, ``hrv_hrr``,
``hrv_drift``, ``hrv_vo2max``, ``hrv_raw_sessions``, ``hrv_training_sessions``,
``user_profiles``.

Re-running the script is safe: migrations are idempotent and already-applied
versions are skipped.

Prerequisites
-------------
1. PostgreSQL server running and accessible.
2. A ``.env`` file at the project root (copy ``.env.example`` and fill it in).
3. Dependencies installed: ``pip install "cardiolab[database,dev]"``

Usage
-----
Run from the project root::

    python example/01_setup_database.py

"""

from __future__ import annotations

import uuid

from dotenv import load_dotenv

from cardiolab.database import HRVRepository, run_migrations

load_dotenv()


def setup_database() -> None:
    """Apply all pending migrations and print a setup summary."""
    print("=== cardiolab — database setup ===\n")

    with HRVRepository.from_env() as repo:
        applied = run_migrations(repo.conn)

    if applied:
        print(f"Applied {len(applied)} migration(s):")
        for v in applied:
            print(f"  ✓  {v}")
    else:
        print("All migrations already applied — schema is up to date.")

    print("\nTip — generate your USER_ID once and add it to .env:")
    print(f"  USER_ID={uuid.uuid4()}")


if __name__ == "__main__":
    setup_database()
