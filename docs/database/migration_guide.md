# Database Migration Guide

cardiolab ships SQL migration files that evolve the PostgreSQL schema safely
across versions. Migrations are applied with a single call and are tracked in a
`schema_migrations` table so that they are never applied twice.

---

## Quick start

```python
from cardiolab.database import HRVRepository

with HRVRepository.from_env() as repo:
    applied = repo.run_migrations()
    if applied:
        print("Applied:", applied)
    else:
        print("Database is up to date.")
```

Or with a bare psycopg2 connection:

```python
import psycopg2
from cardiolab.database import run_migrations

conn = psycopg2.connect(host="...", dbname="...", user="...", password="...")
applied = run_migrations(conn)
conn.close()
```

---

## How it works

1. On first call, `run_migrations` creates the `schema_migrations` table:

   ```sql
   CREATE TABLE IF NOT EXISTS schema_migrations (
       version    TEXT      PRIMARY KEY,
       applied_at TIMESTAMP DEFAULT NOW()
   );
   ```

2. It reads all `V*.sql` files bundled inside `cardiolab/database/migrations/`
   and compares them against the recorded versions.

3. Each pending migration is executed in its own transaction. On success its
   version is inserted into `schema_migrations`. If a migration fails, the
   database is left at the last successfully applied version and the exception
   propagates.

4. Re-running is always safe — already-applied migrations are skipped.

---

## Bundled migrations

| File | Version | Content |
|---|---|---|
| `V001__initial_schema.sql` | v0.1.0 | Creates all 7 base tables |
| `V002__add_apen_sampen_ortho_metrics.sql` | v0.1.x→v0.2.0 | Adds `apen`/`sampen` + orthostatic enrichment columns |
| `V003__add_training_sessions.sql` | v0.2.0 | Adds `hrv_training_sessions` table |

---

## Custom table names

If you configured non-default table names when initialising `HRVRepository`,
the SQL migration files use the default names (`hrv_features`, `hrv_orthostatic`,
etc.). You will need to run the SQL manually against your custom table names, or
subclass `HRVRepository` and override `run_migrations`.

---

## Writing your own migration

Create a file `V004__<description>.sql` in `cardiolab/database/migrations/`
(or in a local copy of the migrations directory) and apply it via
`run_migrations`. Use `ADD COLUMN IF NOT EXISTS` to make alterations idempotent:

```sql
-- V004__add_user_preferences.sql
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id          TEXT PRIMARY KEY,
    primary_protocol TEXT NOT NULL DEFAULT 'resting',
    created_at       TIMESTAMP DEFAULT NOW(),
    updated_at       TIMESTAMP DEFAULT NOW()
);
```

> **Note:** only increment the version number — never modify an already-applied
> migration file. Changes to applied files are ignored by the runner.
