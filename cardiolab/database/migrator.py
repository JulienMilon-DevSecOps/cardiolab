"""Database migration runner for cardiolab.

Applies pending SQL migrations from the bundled ``migrations/`` directory to
the connected PostgreSQL database.  Migration state is tracked in a
``schema_migrations`` table that is created automatically on first run.

Typical usage::

    from cardiolab.database import HRVRepository

    with HRVRepository.from_env() as repo:
        applied = repo.run_migrations()
        if applied:
            print(f"Applied: {applied}")
        else:
            print("Database is up to date.")

Each migration file is named ``V<nnn>__<description>.sql`` and is applied in
ascending alphabetical order.  Once applied, a version string (the file stem,
e.g. ``"V001__initial_schema"``) is recorded in ``schema_migrations`` so that
the same migration is never applied twice.

Migration files are bundled inside the ``cardiolab`` package and are
accessible without the original source tree.
"""

from __future__ import annotations

from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT      PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT NOW()
);
"""


def run_migrations(conn) -> list[str]:
    """Apply all pending SQL migrations to the database.

    Creates the ``schema_migrations`` tracking table if it does not exist,
    then applies every ``V*.sql`` file in the bundled ``migrations/`` directory
    whose version string is not yet recorded.

    Each migration is applied in a separate transaction: if one fails, the
    database is left at the last successfully applied version and the exception
    propagates to the caller.

    Args:
        conn: An open ``psycopg2`` connection.  The caller is responsible for
            the connection lifecycle (open, close, rollback on error).

    Returns:
        List of version strings (file stems) that were applied during this
        call, in application order.  Returns an empty list when the database
        is already up to date.

    Example::

        import psycopg2
        from cardiolab.database.migrator import run_migrations

        conn = psycopg2.connect(dsn="...")
        applied = run_migrations(conn)
        conn.close()

    """
    with conn.cursor() as cur:
        cur.execute(_CREATE_TRACKING_TABLE)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations ORDER BY version")
        already_applied: set[str] = {row[0] for row in cur.fetchall()}

    pending = sorted(
        f for f in MIGRATIONS_DIR.glob("V*.sql") if f.stem not in already_applied
    )

    applied: list[str] = []
    for filepath in pending:
        sql_text = filepath.read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql_text)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (filepath.stem,),
            )
        conn.commit()
        applied.append(filepath.stem)

    return applied
