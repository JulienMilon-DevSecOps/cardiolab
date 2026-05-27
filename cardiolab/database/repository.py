"""PostgreSQL repository for HRV feature storage and retrieval.

Manages six protocol tables through a single class:

* **Resting** (``hrv_features``): one row per session, 19 HRV indicators.
* **Orthostatic** (``hrv_orthostatic``): one row per test, 19 HRV indicators
  for three phases (supine / transition / standing).
* **Cardiac coherence** (``hrv_coherence``): spectral coherence score from
  paced-breathing sessions.
* **Heart Rate Recovery** (``hrv_hrr``): HRR1 and HRR2 from post-exercise
  recordings.
* **Cardiac drift** (``hrv_drift``): progressive HR increase at constant load.
* **VO2max estimation** (``hrv_vo2max``): RMSSD-based and HR-ratio VO2max
  estimates.

Typical usage::

    with HRVRepository.from_env() as repo:
        repo.create_table()
        repo.save_features(features, user_id="alice")
        history = repo.load_features(user_id="alice")

        repo.create_orthostatic_table()
        repo.save_orthostatic(result, user_id="alice", date="2026-05-15")

        repo.create_coherence_table()
        repo.save_coherence(coherence_result, user_id="alice", date="2026-05-15")

        repo.create_hrr_table()
        repo.save_hrr(hrr_result, user_id="alice", date="2026-05-15")

        repo.create_drift_table()
        repo.save_drift(drift_result, user_id="alice", date="2026-05-15")

        repo.create_vo2max_table()
        repo.save_vo2max(vo2max_result, user_id="alice", date="2026-05-15")

Schema version note:
    The addition of ``apen`` and ``sampen`` columns (v0.2) is a **breaking
    schema change**. Existing tables must be dropped and recreated::

        DROP TABLE hrv_features;
        DROP TABLE hrv_orthostatic;
        -- then call repo.create_table() / repo.create_orthostatic_table()

"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from psycopg2 import connect, sql

from cardiolab.protocols.cardiac_coherence import CoherenceResult
from cardiolab.protocols.cardiac_drift import DriftResult
from cardiolab.protocols.hrr import HRRResult
from cardiolab.protocols.orthostatic import OrthostaticResult
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.protocols.vo2max import VO2maxResult

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
    "apen": "FLOAT",
    "sampen": "FLOAT",
    "duration": "FLOAT",
    "score": "FLOAT",
    "method": "TEXT",
}

_DATA_COLUMNS: list[str] = [c for c in _HRV_COLUMNS if c not in ("user_id", "date")]


# ======================
# ORTHOSTATIC — COLUMN REGISTRY
# ======================


def _hrv_fields(prefix: str) -> dict[str, str]:
    """Return the 19 HRV metric column definitions for a phase prefix.

    Covers the time-domain (RMSSD, ln_RMSSD, SDNN, pNN50, mean HR),
    frequency-domain (VLF, LF, HF, LF/HF, HF%, LF_nu, HF_nu, HF/FC) and
    non-linear (SD1, SD2, SD1/SD2, DFA α1, ApEn, SampEn) indicators from
    ``HRVFeatures``, without the ``duration`` field (stored separately per
    phase).

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
        f"{prefix}_apen": "FLOAT",
        f"{prefix}_sampen": "FLOAT",
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
    # ── Methodological metadata ───────────────────────────────────────────
    # Single column for all phases: all three calls to resting_hrv() use the
    # same spectral method, so storing it once avoids redundancy.
    "spectral_method": "TEXT",
}

_ORTHO_DATA_COLUMNS: list[str] = [
    c for c in _ORTHO_COLUMNS if c not in ("user_id", "date")
]


# ======================
# COHERENCE — COLUMN REGISTRY
# ======================

_COHERENCE_COLUMNS: dict[str, str] = {
    "user_id": "TEXT NOT NULL",
    "date": "DATE NOT NULL",
    "coherence_score": "FLOAT",
    "resonance_freq": "FLOAT",
    "peak_power": "FLOAT",
    "total_power_resonance": "FLOAT",
    "rmssd": "FLOAT",
    "sdnn": "FLOAT",
    "mean_hr": "FLOAT",
    "duration": "FLOAT",
}

_COHERENCE_DATA_COLUMNS: list[str] = [
    c for c in _COHERENCE_COLUMNS if c not in ("user_id", "date")
]


# ======================
# HRR — COLUMN REGISTRY
# ======================

_HRR_COLUMNS: dict[str, str] = {
    "user_id": "TEXT NOT NULL",
    "date": "DATE NOT NULL",
    "hr_peak": "FLOAT",
    "hr_at_60s": "FLOAT",
    "hr_at_120s": "FLOAT",
    "hrr_60": "FLOAT",
    "hrr_120": "FLOAT",
    "hrr_60_category": "TEXT",
    "hrr_120_category": "TEXT",
    "duration": "FLOAT",
}

_HRR_DATA_COLUMNS: list[str] = [c for c in _HRR_COLUMNS if c not in ("user_id", "date")]


# ======================
# DRIFT — COLUMN REGISTRY
# ======================

_DRIFT_COLUMNS: dict[str, str] = {
    "user_id": "TEXT NOT NULL",
    "date": "DATE NOT NULL",
    "drift_rate": "FLOAT",
    "drift_magnitude": "FLOAT",
    "r_squared": "FLOAT",
    "drift_detected": "BOOLEAN",
    "initial_hr": "FLOAT",
    "final_hr": "FLOAT",
    "n_windows": "INTEGER",
    "interpretation": "TEXT",
    "duration": "FLOAT",
}

_DRIFT_DATA_COLUMNS: list[str] = [
    c for c in _DRIFT_COLUMNS if c not in ("user_id", "date")
]


# ======================
# VO2MAX — COLUMN REGISTRY
# ======================

_VO2MAX_COLUMNS: dict[str, str] = {
    "user_id": "TEXT NOT NULL",
    "date": "DATE NOT NULL",
    "vo2max_uth": "FLOAT",
    "vo2max_esco_flatt": "FLOAT",
    "vo2max_ln_rmssd": "FLOAT",
    "hr_rest": "FLOAT",
    "hr_max": "FLOAT",
    "rmssd_used": "FLOAT",
    "ln_rmssd_used": "FLOAT",
    "fitness_category": "TEXT",
}

_VO2MAX_DATA_COLUMNS: list[str] = [
    c for c in _VO2MAX_COLUMNS if c not in ("user_id", "date")
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

    def to_flat_dict(self) -> dict:
        """Return a flat dict of all fields (one row per session).

        Mirrors the structure produced by ``OrthostaticResult.to_flat_dict()``
        so that export functions that iterate over result objects can handle
        ``OrthostaticRecord`` with the same code path.

        HRV fields are prefixed ``supine_``, ``transition_``, and
        ``standing_``.  Timing and response metrics are unprefixed.

        Returns:
            Dictionary with one key per metric, suitable for CSV export.

        """

        def _hrv_fields(prefix: str, features: HRVFeatures) -> dict:
            return {
                f"{prefix}_rmssd": features.rmssd,
                f"{prefix}_ln_rmssd": features.ln_rmssd,
                f"{prefix}_sdnn": features.sdnn,
                f"{prefix}_pnn50": features.pnn50,
                f"{prefix}_mean_hr": features.mean_hr,
                f"{prefix}_vlf": features.vlf,
                f"{prefix}_lf": features.lf,
                f"{prefix}_hf": features.hf,
                f"{prefix}_lf_hf": features.lf_hf,
                f"{prefix}_hf_pct": features.hf_pct,
                f"{prefix}_lf_nu": features.lf_nu,
                f"{prefix}_hf_nu": features.hf_nu,
                f"{prefix}_hf_hr": features.hf_hr,
                f"{prefix}_sd1": features.sd1,
                f"{prefix}_sd2": features.sd2,
                f"{prefix}_sd_ratio": features.sd_ratio,
                f"{prefix}_dfa_alpha1": features.dfa_alpha1,
                f"{prefix}_apen": features.apen,
                f"{prefix}_sampen": features.sampen,
            }

        return {
            "date": self.date,
            **_hrv_fields("supine", self.supine),
            **_hrv_fields("transition", self.transition_features),
            **_hrv_fields("standing", self.standing),
            "transition_start_sec": self.transition_start_sec,
            "transition_end_sec": self.transition_end_sec,
            "transition_duration_sec": self.transition_duration_sec,
            "transition_delta_hr": self.transition_delta_hr,
            "transition_peak_hr": self.transition_peak_hr,
            "hr_response": self.hr_response,
            "lf_hf_ratio_change": self.lf_hf_ratio_change,
            "hf_response_pct": self.hf_response_pct,
            "hf_hr_pct_change": self.hf_hr_pct_change,
            "interpretation": self.interpretation,
        }

    def to_reporting_row(self) -> dict:
        """Return a condensed dict for use in reporting tables.

        Produces the same keys as ``table_orthostatic_history`` expects so
        that ``OrthostaticRecord`` objects can be passed to reporting helpers
        without conversion.

        Returns:
            Dictionary with date, key supine/standing metrics, response
            indicators, and interpretation.

        """
        return {
            "date": self.date,
            "supine_rmssd": self.supine.rmssd,
            "standing_rmssd": self.standing.rmssd,
            "supine_hr": self.supine.mean_hr,
            "standing_hr": self.standing.mean_hr,
            "hr_response": self.hr_response,
            "lf_hf_change": self.lf_hf_ratio_change,
            "hf_response_pct": self.hf_response_pct,
            "hf_hr_pct_change": self.hf_hr_pct_change,
            "interpretation": self.interpretation,
        }


# ======================
# ROW HELPERS
# ======================


def _features_from_row(
    row: tuple,
    offset: int,
    date: str | None = None,
    duration: float = 0.0,
) -> HRVFeatures:
    """Reconstruct an ``HRVFeatures`` from 19 consecutive row values.

    Reads ``row[offset]`` through ``row[offset + 18]`` in the order produced
    by ``_hrv_fields()``: rmssd, ln_rmssd, sdnn, pnn50, mean_hr, vlf, lf, hf,
    lf_hf, hf_pct, lf_nu, hf_nu, hf_hr, sd1, sd2, sd_ratio, dfa_alpha1,
    apen, sampen.

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
        apen=row[offset + 17],
        sampen=row[offset + 18],
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

    Column layout (70 data values after user_id + date):

    * supine HRV (19) + supine_duration_sec (1)
    * transition timing (5)
    * transition HRV (19)
    * standing HRV (19) + standing_duration_sec (1)
    * derived metrics (5)

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
        # supine HRV (19)
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
        sf.apen,
        sf.sampen,
        # supine_duration_sec (1)
        p.supine.duration_sec,
        # transition timing (5)
        p.transition.start_sec,
        p.transition.end_sec,
        p.transition.duration_sec,
        p.transition.delta_hr,
        p.transition.peak_hr,
        # transition HRV (19)
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
        tf.apen,
        tf.sampen,
        # standing HRV (19)
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
        stf.apen,
        stf.sampen,
        # standing_duration_sec (1)
        p.standing.duration_sec,
        # derived (5)
        result.hr_response,
        result.lf_hf_ratio_change,
        result.hf_response_pct,
        result.hf_hr_pct_change,
        result.interpretation,
        # spectral_method (1) — same for all phases
        sf.method,
    )


# ======================
# NUMPY ADAPTER (psycopg2 + NumPy 2.x)
# ======================


def _register_numpy_adapters() -> None:
    """Register psycopg2 adapters for NumPy scalar types.

    NumPy 2.0 changed the ``repr()`` of scalars: ``repr(np.float64(1.5))``
    now returns ``"np.float64(1.5)"`` instead of ``"1.5"``.  Without an
    explicit adapter, psycopg2 falls back to ``str()``/``repr()`` and
    PostgreSQL interprets ``np.float64`` as a schema name, raising::

        ProgrammingError: schema "np" does not exist

    Calling ``register_adapter`` multiple times with the same type is safe —
    each call simply overwrites the previous registration.

    This function is a no-op when NumPy is not installed.
    """
    try:
        import numpy as np
        from psycopg2.extensions import AsIs, register_adapter

        register_adapter(np.float64, lambda v: AsIs(float(v)))
        register_adapter(np.float32, lambda v: AsIs(float(v)))
        register_adapter(np.int64,   lambda v: AsIs(int(v)))
        register_adapter(np.int32,   lambda v: AsIs(int(v)))
        register_adapter(np.bool_,   lambda v: AsIs(bool(v)))
    except ImportError:
        pass  # NumPy non installé — aucune action requise


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
        coherence_table_name: str = "hrv_coherence",
        hrr_table_name: str = "hrv_hrr",
        drift_table_name: str = "hrv_drift",
        vo2max_table_name: str = "hrv_vo2max",
        port: int = 5432,
    ) -> None:
        """Store connection parameters and validate table names."""
        for name in (
            table_name,
            ortho_table_name,
            coherence_table_name,
            hrr_table_name,
            drift_table_name,
            vo2max_table_name,
        ):
            _validate_identifier(name)
        self._dsn = {
            "host": host,
            "database": database,
            "user": user,
            "password": password,
            "port": port,
        }
        self.table_name = table_name
        self.ortho_table_name = ortho_table_name
        self.coherence_table_name = coherence_table_name
        self.hrr_table_name = hrr_table_name
        self.drift_table_name = drift_table_name
        self.vo2max_table_name = vo2max_table_name
        self._conn = None

    # ── Factory ──────────────────────────────────────────────────────────

    @classmethod
    def from_env(
        cls,
        table_name: str = "hrv_features",
        ortho_table_name: str = "hrv_orthostatic",
        coherence_table_name: str = "hrv_coherence",
        hrr_table_name: str = "hrv_hrr",
        drift_table_name: str = "hrv_drift",
        vo2max_table_name: str = "hrv_vo2max",
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
            coherence_table_name: Cardiac coherence table name. Defaults to
                ``"hrv_coherence"``.
            hrr_table_name: Heart Rate Recovery table name. Defaults to
                ``"hrv_hrr"``.
            drift_table_name: Cardiac drift table name. Defaults to
                ``"hrv_drift"``.
            vo2max_table_name: VO2max estimation table name. Defaults to
                ``"hrv_vo2max"``.

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
            coherence_table_name=coherence_table_name,
            hrr_table_name=hrr_table_name,
            drift_table_name=drift_table_name,
            vo2max_table_name=vo2max_table_name,
        )

    # ── Connection lifecycle ──────────────────────────────────────────────

    def __enter__(self) -> HRVRepository:
        """Open the database connection and register NumPy type adapters."""
        self._conn = connect(**self._dsn)
        _register_numpy_adapters()
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
                f.apen,
                f.sampen,
                f.duration,
                f.score,
                f.method,
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
            "       sd1, sd2, sd_ratio, dfa_alpha1, apen, sampen,\n"
            "       duration, score, method\n"
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
                apen=row[18],
                sampen=row[19],
                duration=row[20],
                score=row[21],
                method=row[22] or "welch",
            )
            for row in rows
        ]

    # ── Orthostatic — schema ──────────────────────────────────────────────

    def create_orthostatic_table(self) -> None:
        """Create the orthostatic HRV table if it does not already exist.

        The table stores all 19 HRV metrics for three phases (supine,
        transition, standing) as prefixed columns, plus transition timing
        and derived metrics. A ``UNIQUE(user_id, date)`` constraint supports
        safe upserts.

        Column layout (72 total data columns after user_id + date):

        * ``supine_*`` — 19 HRV metrics + ``supine_duration_sec``
        * ``transition_start_sec``, ``transition_end_sec``,
          ``transition_duration_sec``, ``transition_delta_hr``,
          ``transition_peak_hr``
        * ``transition_*`` — 19 HRV metrics (short window, ≈ 20–60 s)
        * ``standing_*`` — 19 HRV metrics + ``standing_duration_sec``
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

        Row index layout (date at [0], data columns from [1]):

        * ``[1..19]``  — supine HRV (19)    ``[20]`` supine_duration_sec
        * ``[21..25]`` — transition timing (5)
        * ``[26..44]`` — transition HRV (19)
        * ``[45..63]`` — standing HRV (19)  ``[64]`` standing_duration_sec
        * ``[65..69]`` — derived metrics (5)
        * ``[70]``     — spectral_method (TEXT)

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
            # [1..19]  supine HRV (19)    [20] supine_duration_sec
            # [21..25] transition timing   [26..44] transition HRV (19)
            # [45..63] standing HRV (19)  [64] standing_duration_sec
            # [65..69] derived metrics (5)  [70] spectral_method
            spectral_method: str = row[70] or "welch"
            supine = _features_from_row(row, offset=1, date=date, duration=row[20])
            supine.method = spectral_method
            transition = _features_from_row(row, offset=26, date=date)
            transition.method = spectral_method
            standing = _features_from_row(row, offset=45, date=date, duration=row[64])
            standing.method = spectral_method
            records.append(
                OrthostaticRecord(
                    date=date,
                    supine=supine,
                    transition_start_sec=row[21],
                    transition_end_sec=row[22],
                    transition_duration_sec=row[23],
                    transition_delta_hr=row[24],
                    transition_peak_hr=row[25],
                    transition_features=transition,
                    standing=standing,
                    hr_response=row[65],
                    lf_hf_ratio_change=row[66],
                    hf_response_pct=row[67],
                    hf_hr_pct_change=row[68],
                    interpretation=row[69],
                )
            )

        return records

    # ── Cardiac coherence — schema ────────────────────────────────────────

    def create_coherence_table(self) -> None:
        """Create the cardiac coherence session table if it does not exist.

        Stores results from paced-breathing coherence sessions (5-5 protocol).
        A ``UNIQUE(user_id, date)`` constraint supports safe upserts.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        columns_sql = ",\n    ".join(f"{k} {v}" for k, v in _COHERENCE_COLUMNS.items())
        query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table} (\n"
            "    id SERIAL PRIMARY KEY,\n"
            "    {columns},\n"
            "    UNIQUE(user_id, date)\n"
            ");"
        ).format(
            table=sql.Identifier(self.coherence_table_name),
            columns=sql.SQL(columns_sql),
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query)

    # ── Cardiac coherence — write ─────────────────────────────────────────

    def save_coherence(
        self,
        result: CoherenceResult,
        user_id: str,
        date: str,
    ) -> None:
        """Insert or update one cardiac coherence session record.

        Args:
            result: Protocol output from ``cardiac_coherence()``.
            user_id: User identifier.
            date: ISO date string for the session.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the insert fails.

        """
        all_cols = ["user_id", "date"] + _COHERENCE_DATA_COLUMNS
        col_identifiers = sql.SQL(", ").join(sql.Identifier(c) for c in all_cols)
        placeholders = sql.SQL(", ").join(
            sql.Placeholder() for _ in range(len(all_cols))
        )
        update_set = sql.SQL(", ").join(
            sql.SQL("{col} = EXCLUDED.{col}").format(col=sql.Identifier(c))
            for c in _COHERENCE_DATA_COLUMNS
        )
        query = sql.SQL(
            "INSERT INTO {table} ({cols}) VALUES ({vals})\n"
            "ON CONFLICT (user_id, date) DO UPDATE SET {update};"
        ).format(
            table=sql.Identifier(self.coherence_table_name),
            cols=col_identifiers,
            vals=placeholders,
            update=update_set,
        )
        row = (
            user_id,
            date,
            result.coherence_score,
            result.resonance_freq,
            result.peak_power,
            result.total_power_resonance,
            result.rmssd,
            result.sdnn,
            result.mean_hr,
            result.duration,
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, row)

    # ── Cardiac coherence — read ──────────────────────────────────────────

    def load_coherence(self, user_id: str) -> list[CoherenceResult]:
        """Load all cardiac coherence session records for a user.

        Args:
            user_id: Identifier of the user whose sessions are retrieved.

        Returns:
            List of ``CoherenceResult`` sorted by ascending date.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        select_cols = sql.SQL(", ").join(
            sql.Identifier(c) for c in ["date"] + _COHERENCE_DATA_COLUMNS
        )
        query = sql.SQL(
            "SELECT {cols}\nFROM {table}\nWHERE user_id = %s\nORDER BY date ASC;"
        ).format(cols=select_cols, table=sql.Identifier(self.coherence_table_name))
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()
        return [
            CoherenceResult(
                date=str(row[0]),
                coherence_score=row[1],
                resonance_freq=row[2],
                peak_power=row[3],
                total_power_resonance=row[4],
                rmssd=row[5],
                sdnn=row[6],
                mean_hr=row[7],
                duration=row[8],
            )
            for row in rows
        ]

    # ── Heart Rate Recovery — schema ──────────────────────────────────────

    def create_hrr_table(self) -> None:
        """Create the Heart Rate Recovery session table if it does not exist.

        Stores HRR1 and HRR2 values from post-exercise recordings.
        A ``UNIQUE(user_id, date)`` constraint supports safe upserts.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        columns_sql = ",\n    ".join(f"{k} {v}" for k, v in _HRR_COLUMNS.items())
        query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table} (\n"
            "    id SERIAL PRIMARY KEY,\n"
            "    {columns},\n"
            "    UNIQUE(user_id, date)\n"
            ");"
        ).format(
            table=sql.Identifier(self.hrr_table_name),
            columns=sql.SQL(columns_sql),
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query)

    # ── Heart Rate Recovery — write ───────────────────────────────────────

    def save_hrr(
        self,
        result: HRRResult,
        user_id: str,
        date: str,
    ) -> None:
        """Insert or update one Heart Rate Recovery session record.

        Args:
            result: Protocol output from ``heart_rate_recovery()``.
            user_id: User identifier.
            date: ISO date string for the session.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the insert fails.

        """
        all_cols = ["user_id", "date"] + _HRR_DATA_COLUMNS
        col_identifiers = sql.SQL(", ").join(sql.Identifier(c) for c in all_cols)
        placeholders = sql.SQL(", ").join(
            sql.Placeholder() for _ in range(len(all_cols))
        )
        update_set = sql.SQL(", ").join(
            sql.SQL("{col} = EXCLUDED.{col}").format(col=sql.Identifier(c))
            for c in _HRR_DATA_COLUMNS
        )
        query = sql.SQL(
            "INSERT INTO {table} ({cols}) VALUES ({vals})\n"
            "ON CONFLICT (user_id, date) DO UPDATE SET {update};"
        ).format(
            table=sql.Identifier(self.hrr_table_name),
            cols=col_identifiers,
            vals=placeholders,
            update=update_set,
        )
        row = (
            user_id,
            date,
            result.hr_peak,
            result.hr_at_60s,
            result.hr_at_120s,
            result.hrr_60,
            result.hrr_120,
            result.hrr_60_category,
            result.hrr_120_category,
            result.duration,
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, row)

    # ── Heart Rate Recovery — read ────────────────────────────────────────

    def load_hrr(self, user_id: str) -> list[HRRResult]:
        """Load all Heart Rate Recovery session records for a user.

        Args:
            user_id: Identifier of the user whose sessions are retrieved.

        Returns:
            List of ``HRRResult`` sorted by ascending date.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        select_cols = sql.SQL(", ").join(
            sql.Identifier(c) for c in ["date"] + _HRR_DATA_COLUMNS
        )
        query = sql.SQL(
            "SELECT {cols}\nFROM {table}\nWHERE user_id = %s\nORDER BY date ASC;"
        ).format(cols=select_cols, table=sql.Identifier(self.hrr_table_name))
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()
        return [
            HRRResult(
                date=str(row[0]),
                hr_peak=row[1],
                hr_at_60s=row[2],
                hr_at_120s=row[3] if row[3] is not None else float("nan"),
                hrr_60=row[4],
                hrr_120=row[5] if row[5] is not None else float("nan"),
                hrr_60_category=row[6] or "",
                hrr_120_category=row[7] or "",
                duration=row[8],
            )
            for row in rows
        ]

    # ── Cardiac drift — schema ────────────────────────────────────────────

    def create_drift_table(self) -> None:
        """Create the cardiac drift session table if it does not exist.

        Stores progressive HR drift analysis from constant-load exercise.
        A ``UNIQUE(user_id, date)`` constraint supports safe upserts.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        columns_sql = ",\n    ".join(f"{k} {v}" for k, v in _DRIFT_COLUMNS.items())
        query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table} (\n"
            "    id SERIAL PRIMARY KEY,\n"
            "    {columns},\n"
            "    UNIQUE(user_id, date)\n"
            ");"
        ).format(
            table=sql.Identifier(self.drift_table_name),
            columns=sql.SQL(columns_sql),
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query)

    # ── Cardiac drift — write ─────────────────────────────────────────────

    def save_drift(
        self,
        result: DriftResult,
        user_id: str,
        date: str,
    ) -> None:
        """Insert or update one cardiac drift session record.

        Args:
            result: Protocol output from ``cardiac_drift()``.
            user_id: User identifier.
            date: ISO date string for the session.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the insert fails.

        """
        all_cols = ["user_id", "date"] + _DRIFT_DATA_COLUMNS
        col_identifiers = sql.SQL(", ").join(sql.Identifier(c) for c in all_cols)
        placeholders = sql.SQL(", ").join(
            sql.Placeholder() for _ in range(len(all_cols))
        )
        update_set = sql.SQL(", ").join(
            sql.SQL("{col} = EXCLUDED.{col}").format(col=sql.Identifier(c))
            for c in _DRIFT_DATA_COLUMNS
        )
        query = sql.SQL(
            "INSERT INTO {table} ({cols}) VALUES ({vals})\n"
            "ON CONFLICT (user_id, date) DO UPDATE SET {update};"
        ).format(
            table=sql.Identifier(self.drift_table_name),
            cols=col_identifiers,
            vals=placeholders,
            update=update_set,
        )
        row = (
            user_id,
            date,
            result.drift_rate,
            result.drift_magnitude,
            result.r_squared,
            result.drift_detected,
            result.initial_hr,
            result.final_hr,
            result.n_windows,
            result.interpretation,
            result.duration,
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, row)

    # ── Cardiac drift — read ──────────────────────────────────────────────

    def load_drift(self, user_id: str) -> list[DriftResult]:
        """Load all cardiac drift session records for a user.

        Args:
            user_id: Identifier of the user whose sessions are retrieved.

        Returns:
            List of ``DriftResult`` sorted by ascending date.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        select_cols = sql.SQL(", ").join(
            sql.Identifier(c) for c in ["date"] + _DRIFT_DATA_COLUMNS
        )
        query = sql.SQL(
            "SELECT {cols}\nFROM {table}\nWHERE user_id = %s\nORDER BY date ASC;"
        ).format(cols=select_cols, table=sql.Identifier(self.drift_table_name))
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()
        return [
            DriftResult(
                date=str(row[0]),
                drift_rate=row[1],
                drift_magnitude=row[2],
                r_squared=row[3],
                drift_detected=bool(row[4]),
                initial_hr=row[5],
                final_hr=row[6],
                n_windows=int(row[7]),
                interpretation=row[8] or "no_drift",
                duration=row[9],
            )
            for row in rows
        ]

    # ── VO2max — schema ───────────────────────────────────────────────────

    def create_vo2max_table(self) -> None:
        """Create the VO2max estimation session table if it does not exist.

        Stores VO2max estimates from HRV-based models (Uth, Esco-Flatt,
        ln-RMSSD). A ``UNIQUE(user_id, date)`` constraint supports safe upserts.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        columns_sql = ",\n    ".join(f"{k} {v}" for k, v in _VO2MAX_COLUMNS.items())
        query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table} (\n"
            "    id SERIAL PRIMARY KEY,\n"
            "    {columns},\n"
            "    UNIQUE(user_id, date)\n"
            ");"
        ).format(
            table=sql.Identifier(self.vo2max_table_name),
            columns=sql.SQL(columns_sql),
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query)

    # ── VO2max — write ────────────────────────────────────────────────────

    def save_vo2max(
        self,
        result: VO2maxResult,
        user_id: str,
        date: str,
    ) -> None:
        """Insert or update one VO2max estimation session record.

        Args:
            result: Protocol output from ``vo2max_from_hrv()``.
            user_id: User identifier.
            date: ISO date string for the session.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the insert fails.

        """
        all_cols = ["user_id", "date"] + _VO2MAX_DATA_COLUMNS
        col_identifiers = sql.SQL(", ").join(sql.Identifier(c) for c in all_cols)
        placeholders = sql.SQL(", ").join(
            sql.Placeholder() for _ in range(len(all_cols))
        )
        update_set = sql.SQL(", ").join(
            sql.SQL("{col} = EXCLUDED.{col}").format(col=sql.Identifier(c))
            for c in _VO2MAX_DATA_COLUMNS
        )
        query = sql.SQL(
            "INSERT INTO {table} ({cols}) VALUES ({vals})\n"
            "ON CONFLICT (user_id, date) DO UPDATE SET {update};"
        ).format(
            table=sql.Identifier(self.vo2max_table_name),
            cols=col_identifiers,
            vals=placeholders,
            update=update_set,
        )
        row = (
            user_id,
            date,
            result.vo2max_uth,
            result.vo2max_esco_flatt,
            result.vo2max_ln_rmssd,
            result.hr_rest,
            result.hr_max,
            result.rmssd_used,
            result.ln_rmssd_used,
            result.fitness_category,
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, row)

    # ── VO2max — read ─────────────────────────────────────────────────────

    def load_vo2max(self, user_id: str) -> list[VO2maxResult]:
        """Load all VO2max estimation session records for a user.

        Args:
            user_id: Identifier of the user whose sessions are retrieved.

        Returns:
            List of ``VO2maxResult`` sorted by ascending date.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        select_cols = sql.SQL(", ").join(
            sql.Identifier(c) for c in ["date"] + _VO2MAX_DATA_COLUMNS
        )
        query = sql.SQL(
            "SELECT {cols}\nFROM {table}\nWHERE user_id = %s\nORDER BY date ASC;"
        ).format(cols=select_cols, table=sql.Identifier(self.vo2max_table_name))
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()
        return [
            VO2maxResult(
                date=str(row[0]),
                vo2max_uth=row[1] if row[1] is not None else float("nan"),
                vo2max_esco_flatt=row[2],
                vo2max_ln_rmssd=row[3],
                hr_rest=row[4],
                hr_max=row[5] if row[5] is not None else float("nan"),
                rmssd_used=row[6],
                ln_rmssd_used=row[7],
                fitness_category=row[8] or "poor",
            )
            for row in rows
        ]
