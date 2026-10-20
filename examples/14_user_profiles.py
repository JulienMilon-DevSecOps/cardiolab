"""Example 14 — User profiles: create, read, update, list, and delete.

Demonstrates the complete ``user_profiles`` table CRUD workflow:
1. Apply migrations to ensure the table exists.
2. Create a user profile — main protocol and load method (cardiolab ≥ 0.5.0).
3. Load and inspect it.
4. Update fields.
5. List all profiles.
6. Delete the demo profile (cleanup).

The demo always uses a **temporary user id**: it never touches the profile of
the ``USER_ID`` of your ``.env``.

Prerequisites
-------------
* ``.env`` file with ``DB_*`` variables.

Usage::

    python examples/14_user_profiles.py

"""

from __future__ import annotations

import uuid

from dotenv import load_dotenv

from cardiolab.analytics.training_load import LOAD_METHOD_REQUIREMENTS
from cardiolab.database import HRVRepository

load_dotenv()

DEMO_USER_ID = f"demo-{uuid.uuid4()}"

print("=== cardiolab — user profiles ===\n")
print(f"Demo user_id : {DEMO_USER_ID}\n")

with HRVRepository.from_env() as repo:
    # ── 0. Ensure migrations are applied ─────────────────────────────────────
    repo.run_migrations()

    # ── 1. Create (upsert) ────────────────────────────────────────────────────
    print("── 1. Create profile ───────────────────────────────────────")
    repo.save_user_profile(
        user_id=DEMO_USER_ID,
        primary_protocol="resting",  # or "orthostatic" (supine phase)
        sex="female",
        birth_year=1990,
        height_cm=168.0,
        hr_max=188,
        hr_rest=52,
        weight_kg=62.5,
        load_method="rpe",  # "hrv", "banister" or "rpe" — one method per athlete
    )
    print("  Data each load method needs:")
    for method, needs in LOAD_METHOD_REQUIREMENTS.items():
        print(f"    {method:<9} session: {needs['session']} · other: {needs['other']}")
    print()

    # ── 2. Load ───────────────────────────────────────────────────────────────
    print("── 2. Load profile ─────────────────────────────────────────")
    profile = repo.load_user_profile(DEMO_USER_ID)
    print(f"  Main protocol : {profile['primary_protocol']}")
    print(f"  Load method   : {profile['load_method']}")
    print(f"  HR max / rest : {profile['hr_max']} / {profile['hr_rest']} bpm")
    print(f"  created_at    : {profile['created_at']}")
    print()

    # ── 3. Update fields ──────────────────────────────────────────────────────
    print("── 3. Update weight and load method ────────────────────────")
    repo.update_user_profile(DEMO_USER_ID, weight_kg=63.2, load_method="banister")
    updated = repo.load_user_profile(DEMO_USER_ID)
    print(f"  Weight      : {profile['weight_kg']} → {updated['weight_kg']} kg")
    print(f"  Load method : {profile['load_method']} → {updated['load_method']}")
    print("  (changing the method changes the load scale: reprocess the history)")
    print()

    # ── 4. List all profiles ──────────────────────────────────────────────────
    print("── 4. List all profiles ────────────────────────────────────")
    profiles = repo.list_user_profiles()
    print(f"  Total : {len(profiles)}")
    for p in profiles:
        print(
            f"    • {p['user_id'][:13]}…  {p['primary_protocol']}  {p['load_method']}"
        )
    print()

    # ── 5. Delete (cleanup) ───────────────────────────────────────────────────
    print("── 5. Delete the demo profile ──────────────────────────────")
    print(f"  Deleted : {repo.delete_user_profile(DEMO_USER_ID)}")
    print()

print("Done.")
