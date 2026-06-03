"""Unit tests for cardiolab.database.migrator."""

from __future__ import annotations

from unittest.mock import MagicMock

from cardiolab.database.migrator import MIGRATIONS_DIR, run_migrations

# ======================
# HELPERS
# ======================


def _mock_conn(applied_versions: list[str] | None = None) -> MagicMock:
    """Return a psycopg2 connection mock with a controllable schema_migrations state."""
    conn = MagicMock()
    cursor_ctx = MagicMock()
    cursor = MagicMock()
    cursor_ctx.__enter__ = MagicMock(return_value=cursor)
    cursor_ctx.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cursor_ctx
    rows = [(v,) for v in (applied_versions or [])]
    cursor.fetchall.return_value = rows
    return conn


# ======================
# MIGRATIONS DIRECTORY
# ======================


class TestMigrationsDir:
    """Validate the bundled migrations directory and files."""

    def test_migrations_dir_exists(self):
        """MIGRATIONS_DIR points to an existing directory."""
        assert MIGRATIONS_DIR.exists()
        assert MIGRATIONS_DIR.is_dir()

    def test_at_least_three_migration_files(self):
        """At least V001, V002, V003 are present."""
        files = sorted(MIGRATIONS_DIR.glob("V*.sql"))
        assert len(files) >= 3

    def test_files_named_with_version_prefix(self):
        """Every SQL file starts with the 'V' version prefix."""
        for f in MIGRATIONS_DIR.glob("V*.sql"):
            assert f.stem.startswith("V"), f"{f.name} does not start with 'V'"

    def test_files_sorted_correctly(self):
        """Migration files are in ascending alphabetical (version) order."""
        files = sorted(MIGRATIONS_DIR.glob("V*.sql"))
        stems = [f.stem for f in files]
        assert stems == sorted(stems)

    def test_v001_exists(self):
        """V001__initial_schema.sql is present."""
        assert (MIGRATIONS_DIR / "V001__initial_schema.sql").exists()

    def test_v002_exists(self):
        """V002__add_apen_sampen_ortho_metrics.sql is present."""
        assert (MIGRATIONS_DIR / "V002__add_apen_sampen_ortho_metrics.sql").exists()

    def test_v003_exists(self):
        """V003__add_training_sessions.sql is present."""
        assert (MIGRATIONS_DIR / "V003__add_training_sessions.sql").exists()

    def test_sql_files_are_non_empty(self):
        """Every SQL migration file contains at least one byte."""
        for f in MIGRATIONS_DIR.glob("V*.sql"):
            assert f.stat().st_size > 0, f"{f.name} is empty"


# ======================
# run_migrations — unit (mocked connection)
# ======================


class TestRunMigrationsUnit:
    """Unit tests with a mocked psycopg2 connection."""

    def test_creates_tracking_table(self):
        """run_migrations creates the schema_migrations tracking table."""
        conn = _mock_conn()
        run_migrations(conn)
        cursor = conn.cursor.return_value.__enter__.return_value
        executed_sqls = [c.args[0] for c in cursor.execute.call_args_list]
        assert any("schema_migrations" in sql for sql in executed_sqls)

    def test_returns_list_of_applied_versions(self):
        """Returns a non-empty list of version strings on a fresh database."""
        conn = _mock_conn(applied_versions=[])
        result = run_migrations(conn)
        assert isinstance(result, list)
        assert len(result) >= 3

    def test_returns_empty_list_when_all_applied(self):
        """Returns [] when every migration is already recorded."""
        all_stems = [f.stem for f in sorted(MIGRATIONS_DIR.glob("V*.sql"))]
        conn = _mock_conn(applied_versions=all_stems)
        result = run_migrations(conn)
        assert result == []

    def test_skips_already_applied(self):
        """Already-applied versions are excluded from the returned list."""
        files = sorted(MIGRATIONS_DIR.glob("V*.sql"))
        first_stem = files[0].stem
        conn = _mock_conn(applied_versions=[first_stem])
        result = run_migrations(conn)
        assert first_stem not in result
        assert len(result) == len(files) - 1

    def test_commits_after_each_migration(self):
        """One commit per migration plus one for the tracking table creation."""
        conn = _mock_conn()
        n_files = len(list(MIGRATIONS_DIR.glob("V*.sql")))
        run_migrations(conn)
        assert conn.commit.call_count == n_files + 1

    def test_version_inserted_into_tracking_table(self):
        """Each applied migration is recorded in schema_migrations."""
        conn = _mock_conn()
        run_migrations(conn)
        cursor = conn.cursor.return_value.__enter__.return_value
        insert_calls = [
            c
            for c in cursor.execute.call_args_list
            if "INSERT INTO schema_migrations" in str(c)
        ]
        assert len(insert_calls) >= 3

    def test_applied_versions_match_file_stems(self):
        """Returned version list matches the sorted SQL file stems."""
        conn = _mock_conn()
        result = run_migrations(conn)
        expected = [f.stem for f in sorted(MIGRATIONS_DIR.glob("V*.sql"))]
        assert result == expected
