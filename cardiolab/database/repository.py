"""PostgreSQL repository for HRV feature storage and retrieval.

Replaces the former ``shema.py`` (table management) and the previous
``repository.py`` (read-only queries) with a single class that owns the full
lifecycle: connection, schema creation, upsert, and load.

Typical usage::

    with HRVRepository.from_env() as repo:
        repo.create_table()
        repo.save_features(features, user_id="alice")
        history = repo.load_features(user_id="alice")
        baseline = Baseline.from_features(history)

"""

from __future__ import annotations

import os
import re

from psycopg2 import connect, sql

from cardiolab.protocols.resting import HRVFeatures


# ======================
# COLUMN REGISTRY
# ======================

_HRV_COLUMNS: dict[str, str] = {
    "user_id": "TEXT NOT NULL",
    "date": "DATE NOT NULL",
    "rmssd": "FLOAT",
    "ln_rmssd": "FLOAT",
    "sdnn": "FLOAT",
    "pnn50": "FLOAT",
    "mean_hr": "FLOAT",
    "vlf": "FLOAT",
    "lf": "FLOAT",
    "hf": "FLOAT",
    "lf_hf": "FLOAT",
    "hf_pct": "FLOAT",
    "lf_nu": "FLOAT",
    "hf_nu": "FLOAT",
    "duration": "FLOAT",
    "score": "FLOAT",
}

# Columns that are data (not the primary key or conflict target).
_DATA_COLUMNS: list[str] = [c for c in _HRV_COLUMNS if c not in ("user_id", "date")]


# ======================
# VALIDATION
# ======================


def _validate_identifier(name: str) -> None:
    """Raise if ``name`` is not a safe SQL identifier.

    Accepts only names composed of ASCII letters, digits, and underscores,
    starting with a letter or underscore. This prevents SQL injection when
    an identifier must be interpolated into a query.

    Args:
        name: The SQL identifier to validate.

    Raises:
        ValueError: If ``name`` contains characters outside ``[a-zA-Z0-9_]``
            or starts with a digit.

    """
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")


# ======================
# REPOSITORY
# ======================


class HRVRepository:
    """PostgreSQL repository for storing and loading HRV session records.

    Groups schema management, upsert, and query under a single object that
    holds one open connection per context-manager block. All writes are
    committed atomically when the ``with`` block exits without error; any
    exception triggers a rollback before the connection is closed.

    Args:
        host: Database server hostname or IP address.
        database: Name of the target PostgreSQL database.
        user: PostgreSQL username.
        password: PostgreSQL password.
        table_name: Name of the HRV table. Must be a valid SQL identifier.
            Defaults to ``"hrv_features"``.
        port: PostgreSQL server port. Defaults to 5432.

    Raises:
        ValueError: If ``table_name`` is not a valid SQL identifier.

    Example::

        with HRVRepository("localhost", "hrv_db", "user", "pass") as repo:
            repo.create_table()
            repo.save_features(today_features, user_id="alice")
            history = repo.load_features(user_id="alice")

    """

    def __init__(
        self,
        host: str,
        database: str,
        user: str,
        password: str,
        table_name: str = "hrv_features",
        port: int = 5432,
    ) -> None:
        _validate_identifier(table_name)
        self._dsn = {
            "host": host,
            "database": database,
            "user": user,
            "password": password,
            "port": port,
        }
        self.table_name = table_name
        self._conn = None

    # ======================
    # FACTORY
    # ======================

    @classmethod
    def from_env(cls, table_name: str = "hrv_features") -> HRVRepository:
        """Build a repository from environment variables.

        Reads the following variables from the process environment (or a
        ``.env`` file loaded beforehand with ``python-dotenv``):

        * ``DB_HOST`` — server hostname
        * ``DB_NAME`` — database name
        * ``DB_USER`` — PostgreSQL username
        * ``DB_PASSWORD`` — PostgreSQL password
        * ``DB_PORT`` — server port (optional, defaults to 5432)

        Args:
            table_name: HRV table name. Defaults to ``"hrv_features"``.

        Returns:
            A configured ``HRVRepository`` instance (not yet connected).

        Raises:
            KeyError: If a required environment variable is missing.

        """
        return cls(
            host=os.environ["DB_HOST"],
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            port=int(os.environ.get("DB_PORT", 5432)),
            table_name=table_name,
        )

    # ======================
    # CONNECTION LIFECYCLE
    # ======================

    def __enter__(self) -> HRVRepository:
        """Open the database connection."""
        self._conn = connect(**self._dsn)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Commit on success, rollback on exception, then close."""
        if self._conn is None:
            return
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
        self._conn = None

    def _conn_or_raise(self):
        """Return the active connection or raise if called outside a ``with`` block."""
        if self._conn is None:
            raise RuntimeError(
                "HRVRepository must be used as a context manager: "
                "'with HRVRepository(...) as repo:'"
            )
        return self._conn

    # ======================
    # SCHEMA
    # ======================

    def create_table(
        self,
        include_fields: list[str] | None = None,
        exclude_fields: list[str] | None = None,
        extra_columns: dict[str, str] | None = None,
    ) -> None:
        """Create the HRV features table if it does not already exist.

        Adds a ``UNIQUE(user_id, date)`` constraint so that
        :meth:`save_features` can use ``ON CONFLICT … DO UPDATE`` to safely
        re-run the pipeline without creating duplicate rows.

        ``user_id`` and ``date`` are always included; they are required for
        the unique constraint and the ``WHERE`` clause in :meth:`load_features`.

        Args:
            include_fields: If provided, only these fields from the default
                column set are included (``user_id`` and ``date`` are always
                kept regardless).
            exclude_fields: Field names to drop from the default column set.
                ``user_id`` and ``date`` cannot be excluded.
            extra_columns: Additional columns as ``{column_name: sql_type}``.
                Column names are validated; types are used verbatim.

        Raises:
            ValueError: If an extra column name is not a valid SQL identifier.
            psycopg2.Error: If the SQL statement is rejected by the server.

        """
        fields = _HRV_COLUMNS.copy()

        if include_fields:
            mandatory = {"user_id", "date"}
            fields = {
                k: v
                for k, v in fields.items()
                if k in include_fields or k in mandatory
            }

        if exclude_fields:
            for f in exclude_fields:
                if f not in ("user_id", "date"):
                    fields.pop(f, None)

        if extra_columns:
            for k in extra_columns:
                _validate_identifier(k)
            fields.update(extra_columns)

        columns_sql = ",\n    ".join(f"{k} {v}" for k, v in fields.items())

        query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table} (\n"
            "    id SERIAL PRIMARY KEY,\n"
            "    {columns},\n"
            "    UNIQUE(user_id, date)\n"
            ");"
        ).format(
            table=sql.Identifier(self.table_name),
            columns=sql.SQL(columns_sql),
        )

        with self._conn_or_raise().cursor() as cur:
            cur.execute(query)

    # ======================
    # WRITE
    # ======================

    def save_features(
        self,
        features: HRVFeatures | list[HRVFeatures],
        user_id: str,
    ) -> None:
        """Insert or update HRV session records for a user.

        Uses ``INSERT … ON CONFLICT (user_id, date) DO UPDATE`` (upsert): if
        a record already exists for the same ``user_id`` + ``date``, all metric
        columns are overwritten with the new values. This makes it safe to
        re-run the pipeline after recalculating features.

        Args:
            features: A single :class:`~cardiolab.protocols.resting.HRVFeatures`
                or a list. All records are associated with ``user_id``.
            user_id: Identifier of the user who owns the sessions.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the insert fails (e.g. table does not exist).

        """
        if isinstance(features, HRVFeatures):
            features = [features]

        all_cols = ["user_id", "date"] + _DATA_COLUMNS

        col_identifiers = sql.SQL(", ").join(sql.Identifier(c) for c in all_cols)
        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in range(len(all_cols)))
        update_set = sql.SQL(", ").join(
            sql.SQL("{col} = EXCLUDED.{col}").format(col=sql.Identifier(c))
            for c in _DATA_COLUMNS
        )

        query = sql.SQL(
            "INSERT INTO {table} ({cols}) VALUES ({vals})\n"
            "ON CONFLICT (user_id, date) DO UPDATE SET {update};"
        ).format(
            table=sql.Identifier(self.table_name),
            cols=col_identifiers,
            vals=placeholders,
            update=update_set,
        )

        rows = [
            (
                user_id,
                f.date,
                f.rmssd, f.ln_rmssd, f.sdnn, f.pnn50, f.mean_hr,
                f.vlf, f.lf, f.hf, f.lf_hf, f.hf_pct, f.lf_nu, f.hf_nu,
                f.duration, f.score,
            )
            for f in features
        ]

        with self._conn_or_raise().cursor() as cur:
            cur.executemany(query, rows)

    # ======================
    # READ
    # ======================

    def load_features(self, user_id: str) -> list[HRVFeatures]:
        """Load all HRV session records for a user, ordered by ascending date.

        The returned list can be passed directly to
        :meth:`~cardiolab.analytics.baseline.Baseline.from_features` to
        reconstruct the user's personal baseline without reprocessing raw
        signals.

        Args:
            user_id: Identifier of the user whose sessions are retrieved.

        Returns:
            List of :class:`~cardiolab.protocols.resting.HRVFeatures` sorted
            by ascending date. Empty if no records are found for ``user_id``.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        query = sql.SQL(
            "SELECT date, rmssd, ln_rmssd, sdnn, pnn50, mean_hr,\n"
            "       vlf, lf, hf, lf_hf, hf_pct, lf_nu, hf_nu,\n"
            "       duration, score\n"
            "FROM {table}\n"
            "WHERE user_id = %s\n"
            "ORDER BY date ASC;"
        ).format(table=sql.Identifier(self.table_name))

        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()

        return [
            HRVFeatures(
                date=str(row[0]),
                rmssd=row[1],
                ln_rmssd=row[2],
                sdnn=row[3],
                pnn50=row[4],
                mean_hr=row[5],
                vlf=row[6],
                lf=row[7],
                hf=row[8],
                lf_hf=row[9],
                hf_pct=row[10],
                lf_nu=row[11],
                hf_nu=row[12],
                duration=row[13],
                score=row[14],
            )
            for row in rows
        ]
