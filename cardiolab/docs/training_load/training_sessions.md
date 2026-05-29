# Training Sessions

## Purpose

A training session record is the atomic unit of the training load model.
It links a workout to its physiological cost (TRIMP) so that the ATL/CTL/TSB
time series can be computed.

Without sessions there is no TRIMP. Without TRIMP there is no ATL/CTL/TSB.

---

## What is a training session?

A session captures the minimum information needed to compute training load:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | `TEXT` | yes | UUID identifying the athlete |
| `date` | `DATE` | yes | Date of the session (one per day maximum) |
| `duration_min` | `FLOAT` | recommended | Session duration in **minutes** |
| `sport_type` | `TEXT` | optional | Label: `"running"`, `"cycling"`, `"strength"`, … |
| `trimp` | `FLOAT` | nullable | Training Impulse — computed separately, stored here |
| `notes` | `TEXT` | optional | Free text (perceived exertion, conditions, …) |

The pair `(user_id, date)` is unique — one session per user per day.
An upsert strategy is used: saving a session for an existing `(user_id, date)`
overwrites the previous values.

> **Why `trimp` is nullable at save time**  
> TRIMP requires the readiness score of the same day, which comes from the HRV
> protocol. In practice the workflow is:  
> 1. Log the session immediately after the workout (TRIMP not yet known).  
> 2. Run the morning HRV protocol the next day.  
> 3. Recompute and update TRIMP for yesterday's session.  
> The column stays `NULL` until the readiness is available.

---

## Database schema

```sql
CREATE TABLE hrv_training_sessions (
    user_id      TEXT    NOT NULL,
    date         DATE    NOT NULL,
    duration_min FLOAT,
    sport_type   TEXT,
    trimp        FLOAT,
    notes        TEXT,
    UNIQUE (user_id, date)
);
```

The table name defaults to `hrv_training_sessions` and is configurable via the
`training_sessions_table_name` parameter of `HRVRepository`.

---

## Repository API

All database interactions go through `HRVRepository`.

### Create the table

```python
with HRVRepository.from_env() as repo:
    repo.create_training_sessions_table()
```

Idempotent — safe to call on every startup (`CREATE TABLE IF NOT EXISTS`).

### Save a session

```python
with HRVRepository.from_env() as repo:
    repo.save_training_session(
        user_id="550e8400-e29b-41d4-a716-446655440000",
        date="2026-05-29",
        duration_min=52.0,
        sport_type="running",
        trimp=41.6,        # pass None if readiness not yet available
        notes="Easy endurance run, legs felt heavy",
    )
```

Calling `save_training_session` again with the same `(user_id, date)` updates
all fields — no duplicate rows.

### Load all sessions

```python
with HRVRepository.from_env() as repo:
    sessions = repo.load_training_sessions(
        user_id="550e8400-e29b-41d4-a716-446655440000"
    )
```

Returns a `list[dict]` sorted ascending by date. Each dict contains:
`date`, `duration_min`, `sport_type`, `trimp`, `notes`.

Missing `trimp` values are returned as `None` and must be handled before
computing ATL/CTL/TSB (fill with `0` for rest-day equivalence, or recompute
once the readiness becomes available).

---

## Custom table name

Useful for testing or multi-environment setups:

```python
repo = HRVRepository.from_env(training_sessions_table_name="hrv_training_sessions_dev")
```

The environment variable `TRAINING_SESSIONS_TABLE_NAME` (if defined) is picked
up automatically by `from_env()`.

---

## Typical daily workflow

```
Morning
  └── HRV protocol (resting or orthostatic)
          → readiness_score computed and stored in protocol table

After workout
  └── save_training_session(date=today, duration_min=..., sport_type=..., trimp=None)

Evening / next morning
  └── load_readiness_for_date(date=yesterday, protocol="resting")
  └── trimp = trimp_hrv_based(duration_min, readiness_score)
  └── save_training_session(date=yesterday, trimp=trimp)   # upsert updates the value
```

See [atl_ctl_tsb.md](atl_ctl_tsb.md) for the full TRIMP computation.
