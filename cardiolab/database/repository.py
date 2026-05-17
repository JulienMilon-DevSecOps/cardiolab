"""PostgreSQL repository for HRV feature storage and retrieval.

Manages two protocol tables through a single class:

* **Resting protocol** (``hrv_features``): one row per daily session, 16 HRV
  indicators + metadata.
* **Orthostatic protocol** (``hrv_orthostatic``): one row per test, all 12
  HRV indicators stored three times (supine / transition / standing) with
  prefixed column names, plus transition timing and derived metrics.

Typical usage::

    with HRVRepository.from_env() as repo:
        # --- Resting ---
        repo.create_table()
        repo.save_features(features, user_id="alice")
        history = repo.load_features(user_id="alice")

        # --- Orthostatic ---
        repo.create_orthostatic_table()
        repo.save_orthostatic(result, user_id="alice", date="2026-05-15")
        records = repo.load_orthostatic(user_id="alice")

"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from psycopg2 import connect, sql

from cardiolab.protocols.orthostatic import OrthostaticResult
from cardiolab.protocols.resting import HRVFeatures

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
# RESTING — COLUMN REGISTRY
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
    "hf_hr": "FLOAT",
    "sd1": "FLOAT",
    "sd2": "FLOAT",
    "sd_ratio": "FLOAT",
    "dfa_alpha1": "FLOAT",
    "duration": "FLOAT",
    "score": "FLOAT",
}

_DATA_COLUMNS: list[str] = [c for c in _HRV_COLUMNS if c not in ("user_id", "date")]


# ======================
# ORTHOSTATIC — COLUMN REGISTRY
# ======================


def _hrv_fields(prefix: str) -> dict[str, str]:
    """Return the 12 HRV metric column definitions for a phase prefix.

    Covers the time-domain (RMSSD, SDNN, pNN50, mean HR), frequency-domain
    (VLF, LF, HF, LF/HF, HF%, LF_nu, HF_nu, HF/FC) and non-linear (SD1, SD2,
    SD1/SD2, DFA α1) indicators from ``HRVFeatures``, without the ``duration``
    field (stored separately per phase).

    Args:
        prefix: Column name prefix, e.g. ``"supine"``, ``"standing"`` or
            ``"transition"``.

    Returns:
        Ordered dict ``{column_name: sql_type}``.

    """
    return {
        f"{prefix}_rmssd": "FLOAT",
        f"{prefix}_ln_rmssd": "FLOAT",
        f"{prefix}_sdnn": "FLOAT",
        f"{prefix}_pnn50": "FLOAT",
        f"{prefix}_mean_hr": "FLOAT",
        f"{prefix}_vlf": "FLOAT",
        f"{prefix}_lf": "FLOAT",
        f"{prefix}_hf": "FLOAT",
        f"{prefix}_lf_hf": "FLOAT",
        f"{prefix}_hf_pct": "FLOAT",
        f"{prefix}_lf_nu": "FLOAT",
        f"{prefix}_hf_nu": "FLOAT",
        f"{prefix}_hf_hr": "FLOAT",
        f"{prefix}_sd1": "FLOAT",
        f"{prefix}_sd2": "FLOAT",
        f"{prefix}_sd_ratio": "FLOAT",
        f"{prefix}_dfa_alpha1": "FLOAT",
    }


_ORTHO_COLUMNS: dict[str, str] = {
    "user_id": "TEXT NOT NULL",
    "date": "DATE NOT NULL",
    # ── Supine phase ──────────────────────────────────────────────────────
    **_hrv_fields("supine"),
    "supine_duration_sec": "FLOAT",
    # ── Transition ────────────────────────────────────────────────────────
    "transition_start_sec": "FLOAT",
    "transition_end_sec": "FLOAT",
    "transition_duration_sec": "FLOAT",
    "transition_delta_hr": "FLOAT",
    "transition_peak_hr": "FLOAT",
    # Transition HRV — short window (≈ 20–60 s); frequency-domain metrics
    # may be unreliable but are stored for completeness.
    **_hrv_fields("transition"),
    # ── Standing phase ────────────────────────────────────────────────────
    **_hrv_fields("standing"),
    "standing_duration_sec": "FLOAT",
    # ── Derived metrics ───────────────────────────────────────────────────
    "hr_response": "FLOAT",
    "lf_hf_ratio_change": "FLOAT",
    "hf_response_pct": "FLOAT",
    "hf_hr_pct_change": "FLOAT",
    "interpretation": "TEXT",
}

_ORTHO_DATA_COLUMNS: list[str] = [
    c for c in _ORTHO_COLUMNS if c not in ("user_id", "date")
]


# ======================
# ORTHOSTATIC RECORD (load return type)
# ======================


@dataclass
class OrthostaticRecord:
    """Orthostatic session reconstructed from database storage.

    This is the read-side counterpart of ``OrthostaticResult``. It cannot
    carry the raw ``RRSeries`` (not stored in the DB), but it exposes all
    computed metrics as ``HRVFeatures`` objects so that ``record.supine.rmssd``
    etc. work the same way as with the live protocol output.

    Attributes:
        date: ISO date string of the recording session.
        supine: Full HRV features for the supine phase.
        standing: Full HRV features for the standing phase.
        transition_features: HRV features for the transition window.
            Computed on a short segment (≈ 20–60 s); frequency-domain
            metrics should be interpreted with care.
        transition_start_sec: Transition onset time in seconds from the
            start of the recording.
        transition_end_sec: Transition end time in seconds.
        transition_duration_sec: Duration of the transition window (s).
        transition_delta_hr: HR rise from supine baseline to peak (bpm).
        transition_peak_hr: Maximum HR reached during the transition (bpm).
        hr_response: HR increase from supine to standing mean (bpm).
        lf_hf_ratio_change: Standing LF/HF divided by supine LF/HF.
        hf_response_pct: Relative HF power change supine → standing (%).
        hf_hr_pct_change: Relative change in the HF/FC ratio supine → standing (%).
            Formula: (HF/FC_standing − HF/FC_supine) / HF/FC_supine × 100.
        interpretation: Clinical classification of the orthostatic response.

    """

    date: str
    supine: HRVFeatures
    standing: HRVFeatures
    transition_features: HRVFeatures
    transition_start_sec: float
    transition_end_sec: float
    transition_duration_sec: float
    transition_delta_hr: float
    transition_peak_hr: float
    hr_response: float
    lf_hf_ratio_change: float
    hf_response_pct: float
    hf_hr_pct_change: float
    interpretation: str


# ======================
# ROW HELPERS
# ======================


def _features_from_row(
    row: tuple,
    offset: int,
    date: str | None = None,
    duration: float = 0.0,
) -> HRVFeatures:
    """Reconstruct an ``HRVFeatures`` from 17 consecutive row values.

    Reads ``row[offset]`` through ``row[offset + 16]`` in the order produced
    by ``_hrv_fields()``: rmssd, ln_rmssd, sdnn, pnn50, mean_hr, vlf, lf, hf,
    lf_hf, hf_pct, lf_nu, hf_nu, hf_hr, sd1, sd2, sd_ratio, dfa_alpha1.

    Args:
        row: Full database row as a tuple.
        offset: Index of the first HRV column within ``row``.
        date: Optional date string to attach to the reconstructed features.
        duration: Phase duration in seconds.

    Returns:
        A populated ``HRVFeatures`` instance.

    """
    return HRVFeatures(
        date=date,
        rmssd=row[offset],
        ln_rmssd=row[offset + 1],
        sdnn=row[offset + 2],
        pnn50=row[offset + 3],
        mean_hr=row[offset + 4],
        vlf=row[offset + 5],
        lf=row[offset + 6],
        hf=row[offset + 7],
        lf_hf=row[offset + 8],
        hf_pct=row[offset + 9],
        lf_nu=row[offset + 10],
        hf_nu=row[offset + 11],
        hf_hr=row[offset + 12],
        sd1=row[offset + 13],
        sd2=row[offset + 14],
        sd_ratio=row[offset + 15],
        dfa_alpha1=row[offset + 16],
        duration=duration,
    )


def _build_ortho_row(
    result: OrthostaticResult,
    user_id: str,
    date: str,
) -> tuple:
    """Flatten an ``OrthostaticResult`` into a DB row tuple.

    The tuple order matches ``["user_id", "date"] + _ORTHO_DATA_COLUMNS``
    exactly and must stay in sync with ``_ORTHO_COLUMNS``.

    Args:
        result: Protocol output from ``orthostatic_hrv()``.
        user_id: User identifier.
        date: ISO date string for the session.

    Returns:
        A flat tuple ready for ``cursor.executemany()``.

    """
    p = result.phases
    sf = p.supine.features
    tf = p.transition.features
    stf = p.standing.features

    return (
        user_id,
        date,
        # supine HRV (17)
        sf.rmssd,
        sf.ln_rmssd,
        sf.sdnn,
        sf.pnn50,
        sf.mean_hr,
        sf.vlf,
        sf.lf,
        sf.hf,
        sf.lf_hf,
        sf.hf_pct,
        sf.lf_nu,
        sf.hf_nu,
        sf.hf_hr,
        sf.sd1,
        sf.sd2,
        sf.sd_ratio,
        sf.dfa_alpha1,
        # supine_duration_sec (1)
        p.supine.duration_sec,
        # transition timing (5)
        p.transition.start_sec,
        p.transition.end_sec,
        p.transition.duration_sec,
        p.transition.delta_hr,
        p.transition.peak_hr,
        # transition HRV (17)
        tf.rmssd,
        tf.ln_rmssd,
        tf.sdnn,
        tf.pnn50,
        tf.mean_hr,
        tf.vlf,
        tf.lf,
        tf.hf,
        tf.lf_hf,
        tf.hf_pct,
        tf.lf_nu,
        tf.hf_nu,
        tf.hf_hr,
        tf.sd1,
        tf.sd2,
        tf.sd_ratio,
        tf.dfa_alpha1,
        # standing HRV (17)
        stf.rmssd,
        stf.ln_rmssd,
        stf.sdnn,
        stf.pnn50,
        stf.mean_hr,
        stf.vlf,
        stf.lf,
        stf.hf,
        stf.lf_hf,
        stf.hf_pct,
        stf.lf_nu,
        stf.hf_nu,
        stf.hf_hr,
        stf.sd1,
        stf.sd2,
        stf.sd_ratio,
        stf.dfa_alpha1,
        # standing_duration_sec (1)
        p.standing.duration_sec,
        # derived (5)
        result.hr_response,
        result.lf_hf_ratio_change,
        result.hf_response_pct,
        result.hf_hr_pct_change,
        result.interpretation,
    )


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
        table_name: Name of the resting HRV table. Defaults to
            ``"hrv_features"``.
        ortho_table_name: Name of the orthostatic HRV table. Defaults to
            ``"hrv_orthostatic"``.
        port: PostgreSQL server port. Defaults to 5432.

    Raises:
        ValueError: If either table name is not a valid SQL identifier.

    Example::

        with HRVRepository.from_env() as repo:
            repo.create_table()
            repo.create_orthostatic_table()
            repo.save_features(features, user_id="alice")
            repo.save_orthostatic(result, user_id="alice", date="2026-05-15")

    """

    def __init__(
        self,
        host: str,
        database: str,
        user: str,
        password: str,
        table_name: str = "hrv_features",
        ortho_table_name: str = "hrv_orthostatic",
        port: int = 5432,
    ) -> None:
        """Store connection parameters and validate table names."""
        _validate_identifier(table_name)
        _validate_identifier(ortho_table_name)
        self._dsn = {
            "host": host,
            "database": database,
            "user": user,
            "password": password,
            "port": port,
        }
        self.table_name = table_name
        self.ortho_table_name = ortho_table_name
        self._conn = None

    # ── Factory ──────────────────────────────────────────────────────────

    @classmethod
    def from_env(
        cls,
        table_name: str = "hrv_features",
        ortho_table_name: str = "hrv_orthostatic",
    ) -> HRVRepository:
        """Build a repository from environment variables.

        Reads the following variables from the process environment (or a
        ``.env`` file loaded beforehand with ``python-dotenv``):

        * ``DB_HOST`` — server hostname
        * ``DB_NAME`` — database name
        * ``DB_USER`` — PostgreSQL username
        * ``DB_PASSWORD`` — PostgreSQL password
        * ``DB_PORT`` — server port (optional, defaults to 5432)

        Args:
            table_name: Resting HRV table name. Defaults to
                ``"hrv_features"``.
            ortho_table_name: Orthostatic HRV table name. Defaults to
                ``"hrv_orthostatic"``.

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
            ortho_table_name=ortho_table_name,
        )

    # ── Connection lifecycle ──────────────────────────────────────────────

    def __enter__(self) -> HRVRepository:
        """Open the database connection."""
        self._conn = connect(**self._dsn)
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb) -> None:
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
        """Return the active connection or raise if outside a ``with`` block."""
        if self._conn is None:
            raise RuntimeError(
                "HRVRepository must be used as a context manager: "
                "'with HRVRepository(...) as repo:'"
            )
        return self._conn

    # ── Resting — schema ─────────────────────────────────────────────────

    def create_table(
        self,
        include_fields: list[str] | None = None,
        exclude_fields: list[str] | None = None,
        extra_columns: dict[str, str] | None = None,
    ) -> None:
        """Create the resting HRV features table if it does not already exist.

        Adds a ``UNIQUE(user_id, date)`` constraint so that
        :meth:`save_features` can upsert without creating duplicates.
        ``user_id`` and ``date`` are always kept regardless of
        ``include_fields`` / ``exclude_fields``.

        Args:
            include_fields: If provided, only these fields from the default
                column set are included.
            exclude_fields: Field names to drop from the default column set.
            extra_columns: Additional columns as ``{column_name: sql_type}``.

        Raises:
            ValueError: If an extra column name is not a valid SQL identifier.
            psycopg2.Error: If the SQL statement is rejected.

        """
        fields = _HRV_COLUMNS.copy()

        if include_fields:
            mandatory = {"user_id", "date"}
            fields = {
                k: v for k, v in fields.items() if k in include_fields or k in mandatory
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

    # ── Resting — write ───────────────────────────────────────────────────

    def save_features(
        self,
        features: HRVFeatures | list[HRVFeatures],
        user_id: str,
    ) -> None:
        """Insert or update resting HRV session records for a user.

        Uses ``INSERT … ON CONFLICT (user_id, date) DO UPDATE`` (upsert): if
        a record already exists for the same ``user_id`` + ``date``, all
        metric columns are overwritten with the new values.

        Args:
            features: A single ``HRVFeatures`` or a list. All records are
                associated with ``user_id``.
            user_id: Identifier of the user who owns the sessions.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the insert fails.

        """
        if isinstance(features, HRVFeatures):
            features = [features]

        all_cols = ["user_id", "date"] + _DATA_COLUMNS
        col_identifiers = sql.SQL(", ").join(sql.Identifier(c) for c in all_cols)
        placeholders = sql.SQL(", ").join(
            sql.Placeholder() for _ in range(len(all_cols))
        )
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
                f.rmssd,
                f.ln_rmssd,
                f.sdnn,
                f.pnn50,
                f.mean_hr,
                f.vlf,
                f.lf,
                f.hf,
                f.lf_hf,
                f.hf_pct,
                f.lf_nu,
                f.hf_nu,
                f.hf_hr,
                f.sd1,
                f.sd2,
                f.sd_ratio,
                f.dfa_alpha1,
                f.duration,
                f.score,
            )
            for f in features
        ]

        with self._conn_or_raise().cursor() as cur:
            cur.executemany(query, rows)

    # ── Resting — read ────────────────────────────────────────────────────

    def load_features(self, user_id: str) -> list[HRVFeatures]:
        """Load all resting HRV session records for a user, sorted by date.

        The returned list can be passed directly to
        ``Baseline.from_features()`` to reconstruct the user's baseline.

        Args:
            user_id: Identifier of the user whose sessions are retrieved.

        Returns:
            List of ``HRVFeatures`` sorted by ascending date. Empty if no
            records exist for ``user_id``.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        query = sql.SQL(
            "SELECT date, rmssd, ln_rmssd, sdnn, pnn50, mean_hr,\n"
            "       vlf, lf, hf, lf_hf, hf_pct, lf_nu, hf_nu, hf_hr,\n"
            "       sd1, sd2, sd_ratio, dfa_alpha1,\n"
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
                hf_hr=row[13],
                sd1=row[14],
                sd2=row[15],
                sd_ratio=row[16],
                dfa_alpha1=row[17],
                duration=row[18],
                score=row[19],
            )
            for row in rows
        ]

    # ── Orthostatic — schema ──────────────────────────────────────────────

    def create_orthostatic_table(self) -> None:
        """Create the orthostatic HRV table if it does not already exist.

        The table stores all 12 HRV metrics for three phases (supine,
        transition, standing) as prefixed columns, plus transition timing
        and derived metrics. A ``UNIQUE(user_id, date)`` constraint supports
        safe upserts.

        Column layout (64 total):

        * ``user_id``, ``date``
        * ``supine_*`` — 17 HRV metrics + ``supine_duration_sec``
        * ``transition_start_sec``, ``transition_end_sec``,
          ``transition_duration_sec``, ``transition_delta_hr``,
          ``transition_peak_hr``
        * ``transition_*`` — 17 HRV metrics (short window, ≈ 20–60 s)
        * ``standing_*`` — 17 HRV metrics + ``standing_duration_sec``
        * ``hr_response``, ``lf_hf_ratio_change``, ``hf_response_pct``,
          ``hf_hr_pct_change``, ``interpretation``

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        columns_sql = ",\n    ".join(f"{k} {v}" for k, v in _ORTHO_COLUMNS.items())

        query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table} (\n"
            "    id SERIAL PRIMARY KEY,\n"
            "    {columns},\n"
            "    UNIQUE(user_id, date)\n"
            ");"
        ).format(
            table=sql.Identifier(self.ortho_table_name),
            columns=sql.SQL(columns_sql),
        )

        with self._conn_or_raise().cursor() as cur:
            cur.execute(query)

    # ── Orthostatic — write ───────────────────────────────────────────────

    def save_orthostatic(
        self,
        result: OrthostaticResult,
        user_id: str,
        date: str,
    ) -> None:
        """Insert or update one orthostatic session record.

        Uses the same upsert strategy as :meth:`save_features`: if a row
        already exists for ``(user_id, date)``, all metric columns are
        overwritten.

        Args:
            result: Protocol output from ``orthostatic_hrv()``.
            user_id: User identifier.
            date: ISO date string for the session (e.g. ``"2026-05-15"``).

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the insert fails.

        """
        all_cols = ["user_id", "date"] + _ORTHO_DATA_COLUMNS
        col_identifiers = sql.SQL(", ").join(sql.Identifier(c) for c in all_cols)
        placeholders = sql.SQL(", ").join(
            sql.Placeholder() for _ in range(len(all_cols))
        )
        update_set = sql.SQL(", ").join(
            sql.SQL("{col} = EXCLUDED.{col}").format(col=sql.Identifier(c))
            for c in _ORTHO_DATA_COLUMNS
        )

        query = sql.SQL(
            "INSERT INTO {table} ({cols}) VALUES ({vals})\n"
            "ON CONFLICT (user_id, date) DO UPDATE SET {update};"
        ).format(
            table=sql.Identifier(self.ortho_table_name),
            cols=col_identifiers,
            vals=placeholders,
            update=update_set,
        )

        row = _build_ortho_row(result, user_id, date)

        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, row)

    # ── Orthostatic — read ────────────────────────────────────────────────

    def load_orthostatic(self, user_id: str) -> list[OrthostaticRecord]:
        """Load all orthostatic session records for a user, sorted by date.

        Reconstructs ``HRVFeatures`` objects for each phase from the stored
        column values so that ``record.supine.rmssd`` etc. work identically
        to the live protocol output.

        Args:
            user_id: Identifier of the user whose sessions are retrieved.

        Returns:
            List of :class:`OrthostaticRecord` sorted by ascending date.
            Empty if no records exist for ``user_id``.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        select_cols = sql.SQL(", ").join(
            sql.Identifier(c) for c in ["date"] + _ORTHO_DATA_COLUMNS
        )

        query = sql.SQL(
            "SELECT {cols}\nFROM {table}\nWHERE user_id = %s\nORDER BY date ASC;"
        ).format(
            cols=select_cols,
            table=sql.Identifier(self.ortho_table_name),
        )

        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()

        records = []
        for row in rows:
            date = str(row[0])
            # Row layout mirrors _ORTHO_DATA_COLUMNS — offsets start at 1 (skip date).
            # [1..17]  supine HRV (17)    [18] supine_duration_sec
            # [19..23] transition timing   [24..40] transition HRV (17)
            # [41..57] standing HRV (17)  [58] standing_duration_sec
            # [59..63] derived metrics (5)
            records.append(
                OrthostaticRecord(
                    date=date,
                    supine=_features_from_row(
                        row, offset=1, date=date, duration=row[18]
                    ),
                    transition_start_sec=row[19],
                    transition_end_sec=row[20],
                    transition_duration_sec=row[21],
                    transition_delta_hr=row[22],
                    transition_peak_hr=row[23],
                    transition_features=_features_from_row(row, offset=24, date=date),
                    standing=_features_from_row(
                        row, offset=41, date=date, duration=row[58]
                    ),
                    hr_response=row[59],
                    lf_hf_ratio_change=row[60],
                    hf_response_pct=row[61],
                    hf_hr_pct_change=row[62],
                    interpretation=row[63],
                )
            )

        return records
