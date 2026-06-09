"""Example 14 — User profiles: create, read, update, list, and delete.

Demonstrates the complete ``user_profiles`` table CRUD workflow:
1. Apply migrations to ensure the table exists.
2. Create a user profile.
3. Load and inspect it.
4. Update a field.
5. List all profiles.
6. Delete the profile (cleanup).

Prerequisites
-------------
* ``01_setup_database.py`` has been run (or run it from within this script).
* ``.env`` file with ``DB_*`` variables.

Usage::

    python example/14_user_profiles.py

"""

from __future__ import annotations

import os
import uuid

from dotenv import load_dotenv

from cardiolab.database import HRVRepository, run_migrations

load_dotenv()

# Use USER_ID from .env, or generate a temporary one for this demo.
_raw = os.environ.get("USER_ID")
DEMO_USER_ID = str(uuid.UUID(_raw)) if _raw else str(uuid.uuid4())

print("=== cardiolab — user profiles ===\n")
print(f"Demo user_id : {DEMO_USER_ID}\n")

with HRVRepository.from_env() as repo:

    # ── 0. Ensure migrations are applied ─────────────────────────────────────
    run_migrations(repo.conn)

    # ── 1. Create (upsert) ────────────────────────────────────────────────────
    print("── 1. Create profile ───────────────────────────────────────")
    profile = repo.save_user_profile(
        user_id=DEMO_USER_ID,
        first_name="Alice",
        last_name="Dupont",
        email="alice@example.com",
        birth_date="1990-03-15",
        sex="female",
        height_cm=168.0,
        weight_kg=62.5,
    )
    print(f"  Created : {profile.first_name} {profile.last_name}")
    print(f"  Email   : {profile.email}")
    print(f"  DOB     : {profile.birth_date}  |  Sex : {profile.sex}")
    print(f"  Height  : {profile.height_cm} cm  |  Weight : {profile.weight_kg} kg")
    print()

    # ── 2. Load ───────────────────────────────────────────────────────────────
    print("── 2. Load profile ─────────────────────────────────────────")
    loaded = repo.load_user_profile(DEMO_USER_ID)
    print(f"  Loaded  : {loaded.first_name} {loaded.last_name}")
    print(f"  created_at : {loaded.created_at}")
    print()

    # ── 3. Update a field ─────────────────────────────────────────────────────
    print("── 3. Update weight ────────────────────────────────────────")
    repo.update_user_profile(DEMO_USER_ID, {"weight_kg": 63.2})
    updated = repo.load_user_profile(DEMO_USER_ID)
    print(f"  Weight before : {profile.weight_kg} kg")
    print(f"  Weight after  : {updated.weight_kg} kg")
    print()

    # ── 4. List all profiles ──────────────────────────────────────────────────
    print("── 4. List all profiles ────────────────────────────────────")
    profiles = repo.list_user_profiles()
    print(f"  Total : {len(profiles)}")
    for p in profiles:
        name = f"{p.first_name or ''} {p.last_name or ''}".strip() or "(no name)"
        print(f"    • {name}  ({p.user_id[:8]}…)")
    print()

    # ── 5. Delete (cleanup) ───────────────────────────────────────────────────
    print("── 5. Delete profile (demo cleanup) ────────────────────────")
    deleted = repo.delete_user_profile(DEMO_USER_ID)
    print(f"  Deleted : {deleted}")
    print()

print("Done.")
