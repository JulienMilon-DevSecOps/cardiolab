"""Initialize the PostgreSQL database — run this script only once.

Creates the ``hrv_features`` table with its full schema and a
``UNIQUE(user_id, date)`` constraint. Re-running the script is safe:
``CREATE TABLE IF NOT EXISTS`` is idempotent.

Prerequisites
-------------
1. PostgreSQL server running and accessible.
2. A ``.env`` file at the project root (copy ``.env.example`` and fill it in).
3. Dependencies installed: ``pip install -r requirements.txt``

Usage
-----
Run from the project root::

    python example/01_setup_database.py

"""

from __future__ import annotations

import uuid

from dotenv import load_dotenv

from cardiolab.database.repository import HRVRepository

load_dotenv()


def setup_database() -> None:
    """Create the HRV features table and print a setup summary."""
    print("=== cardiolab — database setup ===\n")

    with HRVRepository.from_env() as repo:
        repo.create_table()
        print(f"Table '{repo.table_name}' is ready.")

    print("\nTable columns:")
    print("  id          SERIAL PRIMARY KEY")
    print("  user_id     TEXT NOT NULL   ← UUID stored as text")
    print("  date        DATE NOT NULL   ← one row per user per day")
    print("  rmssd       FLOAT")
    print("  ln_rmssd    FLOAT")
    print("  sdnn        FLOAT")
    print("  pnn50       FLOAT")
    print("  mean_hr     FLOAT")
    print("  vlf         FLOAT")
    print("  lf          FLOAT")
    print("  hf          FLOAT")
    print("  lf_hf       FLOAT")
    print("  hf_pct      FLOAT")
    print("  lf_nu       FLOAT")
    print("  hf_nu       FLOAT")
    print("  duration    FLOAT")
    print("  score       FLOAT")
    print("  UNIQUE(user_id, date)")

    print("\nTip — generate your USER_ID once and add it to .env:")
    print(f"  USER_ID={uuid.uuid4()}")


if __name__ == "__main__":
    setup_database()
