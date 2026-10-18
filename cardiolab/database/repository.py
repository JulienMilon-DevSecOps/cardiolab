"""PostgreSQL repository for HRV feature storage and retrieval.

Manages the cardiolab tables through a single class:

* **Raw sessions** (``hrv_raw_sessions``): raw RR intervals in ms for every
  recorded session. Source of truth that allows reprocessing with different
  parameters. Linked to protocol tables via ``(user_id, session_date, protocol)``.
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

Implementation:
    The six protocol tables keyed by ``UNIQUE(user_id, date)`` are described by
    ``_ProtocolTable`` specifications (column registry + row → result function)
    and handled by the generic ``_create`` / ``_upsert`` / ``_select`` methods;
    the public ``create_* / save_* / load_*`` methods are thin wrappers. See
    ``docs/database/migration_guide.md`` to add a protocol table.

Schema migrations:
    Use :func:`HRVRepository.run_migrations` (or the standalone
    :func:`cardiolab.database.migrator.run_migrations`) to apply pending SQL
    migrations safely.  The migration runner tracks applied versions in a
    ``schema_migrations`` table and never re-applies a completed migration.

"""

from __future__ import annotations

import math
import os
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from psycopg2 import connect, sql
from psycopg2.extras import Json

from cardiolab.protocols.cardiac_coherence import CoherenceResult
from cardiolab.protocols.cardiac_drift import DriftResult
from cardiolab.protocols.hrr import HRRResult
from cardiolab.protocols.orthostatic import OrthostaticResult
from cardiolab.protocols.resting import HRVFeatures
from cardiolab.protocols.vo2max import VO2maxResult
from cardiolab.signals.quality import SignalQuality, quality_columns
from cardiolab.signals.rr import RRSeries
from cardiolab.sports import validate_sport

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
# COLUMN REGISTRIES
# ======================
#
# Each protocol table is described by an ordered ``{column_name: sql_type}``
# registry starting with the ``user_id`` / ``date`` key. Metric column names
# are the attribute names of the protocol result dataclass, so rows can be
# written and read by name (see ``_ProtocolTable`` below).


def _data_columns(columns: dict[str, str]) -> list[str]:
    """Return the metric columns of a registry (everything but ``user_id`` / ``date``)."""
    return [c for c in columns if c not in ("user_id", "date")]


# The 19 HRV indicators stored for a resting session and for each orthostatic
# phase, in storage order: time domain, frequency domain, non-linear.
_HRV_METRICS: tuple[str, ...] = (
    "rmssd",
    "ln_rmssd",
    "sdnn",
    "pnn50",
    "mean_hr",
    "vlf",
    "lf",
    "hf",
    "lf_hf",
    "hf_pct",
    "lf_nu",
    "hf_nu",
    "hf_hr",
    "sd1",
    "sd2",
    "sd_ratio",
    "dfa_alpha1",
    "apen",
    "sampen",
)

# ── Resting ──────────────────────────────────────────────────────────────────

_HRV_COLUMNS: dict[str, str] = {
    "user_id": "TEXT NOT NULL",
    "date": "DATE NOT NULL",
    **dict.fromkeys(_HRV_METRICS, "FLOAT"),
    "duration": "FLOAT",
    "score": "FLOAT",
    "method": "TEXT",
    "quality": "JSONB",
}

_DATA_COLUMNS: list[str] = _data_columns(_HRV_COLUMNS)


# ── Orthostatic ──────────────────────────────────────────────────────────────


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
    return {f"{prefix}_{metric}": "FLOAT" for metric in _HRV_METRICS}


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
    "lf_hr_pct_change": "FLOAT",
    "delta_rmssd": "FLOAT",
    "interpretation": "TEXT",
    # ── Methodological metadata ───────────────────────────────────────────
    # Single column for all phases: all three calls to resting_hrv() use the
    # same spectral method, so storing it once avoids redundancy.
    "spectral_method": "TEXT",
    # ── Autonomic score ───────────────────────────────────────────────────
    "score": "FLOAT DEFAULT 0.0",
    # ── Signal quality (v0.4.0) ───────────────────────────────────────────
    # {"overall": …, "supine": …, "transition": …, "standing": …}
    "quality": "JSONB",
}

_ORTHO_DATA_COLUMNS: list[str] = _data_columns(_ORTHO_COLUMNS)

# ── Cardiac coherence ────────────────────────────────────────────────────────

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
    "score": "FLOAT DEFAULT 0.0",
    "quality": "JSONB",
}

# ── Heart Rate Recovery ──────────────────────────────────────────────────────

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
    "score": "FLOAT DEFAULT 0.0",
}

# ── Cardiac drift ────────────────────────────────────────────────────────────

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
    "score": "FLOAT DEFAULT 0.0",
}

# ── VO2max ───────────────────────────────────────────────────────────────────

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
    "score": "FLOAT DEFAULT 0.0",
    "quality": "JSONB",
}


# ======================
# TRAINING SESSIONS — COLUMN REGISTRY
# ======================

_TRAINING_SESSIONS_COLUMNS: dict[str, str] = {
    "user_id": "TEXT NOT NULL",
    "date": "DATE NOT NULL",
    "duration_min": "FLOAT",
    "sport_type": "TEXT",
    "trimp": "FLOAT",
    "notes": "TEXT",
}

# Columns writable by save_training_session() (excludes activity_id, user_id, date)
_TRAINING_SESSIONS_DATA_COLUMNS: list[str] = [
    c for c in _TRAINING_SESSIONS_COLUMNS if c not in ("user_id", "date")
]

# All columns returned by load/find (activity_id first, then data columns)
_TRAINING_SESSIONS_SELECT_COLUMNS: list[str] = [
    "activity_id",
    "date",
    "duration_min",
    "sport_type",
    "trimp",
    "notes",
]


# ======================
# USER PROFILES — COLUMN REGISTRY
# ======================

_USER_PROFILES_COLUMNS: dict[str, str] = {
    "primary_protocol": "TEXT NOT NULL DEFAULT 'resting'",
    "sex": "TEXT",
    "birth_year": "INT",
    "height_cm": "FLOAT",
    "hr_max": "INT",
    "hr_rest": "INT",
    "weight_kg": "FLOAT",
}

# Fields that can be updated via update_user_profile() — excludes user_id and timestamps
_USER_PROFILES_UPDATABLE: frozenset[str] = frozenset(_USER_PROFILES_COLUMNS.keys())

# All columns returned by load / list queries
_USER_PROFILES_SELECT_COLUMNS: list[str] = [
    "user_id",
    *_USER_PROFILES_COLUMNS.keys(),
    "created_at",
    "updated_at",
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
        score: Composite autonomic score [0–100] computed by
            :func:`cardiolab.analytics.scoring.orthostatic_score`. Defaults to
            0.0 for rows imported before the score column was added.
        quality: Signal quality of the whole recording; each phase carries its
            own index in ``supine.quality`` etc. ``None`` for rows stored
            before v0.4.0.

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
    lf_hr_pct_change: float
    delta_rmssd: float
    interpretation: str
    score: float = 0.0
    quality: SignalQuality | None = None

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
            "lf_hr_pct_change": self.lf_hr_pct_change,
            "delta_rmssd": self.delta_rmssd,
            "interpretation": self.interpretation,
            "score": self.score,
            **quality_columns(self.quality),
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
            "lf_hr_pct_change": self.lf_hr_pct_change,
            "delta_rmssd": self.delta_rmssd,
            "interpretation": self.interpretation,
            "score": self.score,
            "quality_grade": self.quality.grade if self.quality else None,
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

    Reads ``row[offset]`` through ``row[offset + 18]`` in the order of
    ``_HRV_METRICS``: rmssd, ln_rmssd, sdnn, pnn50, mean_hr, vlf, lf, hf,
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
    values = row[offset : offset + len(_HRV_METRICS)]
    return HRVFeatures(
        date=date,
        duration=duration,
        **dict(zip(_HRV_METRICS, values, strict=True)),
    )


def _phase_features(
    r: dict,
    prefix: str,
    date: str,
    duration: float = 0.0,
) -> HRVFeatures:
    """Rebuild the ``HRVFeatures`` of one orthostatic phase from a named row.

    Args:
        r: Row as ``{column_name: value}``.
        prefix: Phase prefix — ``"supine"``, ``"transition"`` or ``"standing"``.
        date: Session date attached to the features.
        duration: Phase duration in seconds.

    Returns:
        The phase features, with the session-wide spectral method.

    """
    values = tuple(r[f"{prefix}_{metric}"] for metric in _HRV_METRICS)
    features = _features_from_row(values, offset=0, date=date, duration=duration)
    features.method = r["spectral_method"] or "welch"
    features.quality = SignalQuality.from_dict((r.get("quality") or {}).get(prefix))
    return features


def _build_ortho_row(
    result: OrthostaticResult,
    user_id: str,
    date: str,
) -> tuple:
    """Flatten an ``OrthostaticResult`` into a DB row tuple.

    Values are gathered by column name and returned in the order of
    ``_ORTHO_COLUMNS`` (``user_id``, ``date``, then ``_ORTHO_DATA_COLUMNS``),
    so the row can never drift out of sync with the schema: a column without
    a value raises ``KeyError``.

    Args:
        result: Protocol output from ``orthostatic_hrv()``.
        user_id: User identifier.
        date: ISO date string for the session.

    Returns:
        A flat tuple ready for ``cursor.execute()``.

    """
    p = result.phases
    values: dict = {"user_id": user_id, "date": date}
    for prefix, phase in (
        ("supine", p.supine),
        ("transition", p.transition),
        ("standing", p.standing),
    ):
        values.update(
            {f"{prefix}_{m}": getattr(phase.features, m) for m in _HRV_METRICS}
        )
    values.update(
        supine_duration_sec=p.supine.duration_sec,
        transition_start_sec=p.transition.start_sec,
        transition_end_sec=p.transition.end_sec,
        transition_duration_sec=p.transition.duration_sec,
        transition_delta_hr=p.transition.delta_hr,
        transition_peak_hr=p.transition.peak_hr,
        standing_duration_sec=p.standing.duration_sec,
        hr_response=result.hr_response,
        lf_hf_ratio_change=result.lf_hf_ratio_change,
        hf_response_pct=result.hf_response_pct,
        hf_hr_pct_change=result.hf_hr_pct_change,
        lf_hr_pct_change=result.lf_hr_pct_change,
        delta_rmssd=result.delta_rmssd,
        interpretation=result.interpretation,
        # Same spectral method for all phases — stored once
        spectral_method=p.supine.features.method,
        score=result.score,
        quality=_ortho_quality(result),
    )
    return tuple(values[c] for c in _ORTHO_COLUMNS)


def _ortho_quality(result: OrthostaticResult) -> Json | None:
    """Quality JSON of an orthostatic session: whole recording + each phase."""
    p = result.phases
    data = {
        "overall": result.quality,
        "supine": p.supine.features.quality,
        "transition": p.transition.features.quality,
        "standing": p.standing.features.quality,
    }
    data = {k: q.to_dict() for k, q in data.items() if isinstance(q, SignalQuality)}
    return Json(data) if data else None


# ── Row → result object (one per protocol table) ─────────────────────────────
# Each receives {"date": …, <data column>: …} and restores the defaults of
# nullable columns exactly as stored results are expected downstream.


def _or(value, default):
    """Return ``default`` when a nullable column is NULL."""
    return default if value is None else value


def _resting_from_row(r: dict) -> HRVFeatures:
    """Rebuild a resting session (quality ``None`` for rows stored before v0.4.0)."""
    return HRVFeatures(
        **r
        | {
            "date": str(r["date"]),
            "method": r["method"] or "welch",
            "quality": SignalQuality.from_dict(r["quality"]),
        }
    )


def _ortho_record_from_row(r: dict) -> OrthostaticRecord:
    """Rebuild an orthostatic session (three phases + derived metrics)."""
    date = str(r["date"])
    return OrthostaticRecord(
        date=date,
        supine=_phase_features(r, "supine", date, r["supine_duration_sec"]),
        transition_start_sec=r["transition_start_sec"],
        transition_end_sec=r["transition_end_sec"],
        transition_duration_sec=r["transition_duration_sec"],
        transition_delta_hr=r["transition_delta_hr"],
        transition_peak_hr=r["transition_peak_hr"],
        transition_features=_phase_features(r, "transition", date),
        standing=_phase_features(r, "standing", date, r["standing_duration_sec"]),
        hr_response=r["hr_response"],
        lf_hf_ratio_change=r["lf_hf_ratio_change"],
        hf_response_pct=r["hf_response_pct"],
        hf_hr_pct_change=r["hf_hr_pct_change"],
        lf_hr_pct_change=r["lf_hr_pct_change"],
        delta_rmssd=r["delta_rmssd"],
        interpretation=r["interpretation"],
        score=r["score"] or 0.0,
        quality=SignalQuality.from_dict((r["quality"] or {}).get("overall")),
    )


def _coherence_from_row(r: dict) -> CoherenceResult:
    """Rebuild a cardiac coherence session."""
    return CoherenceResult(
        **r
        | {
            "date": str(r["date"]),
            "score": _or(r["score"], 0.0),
            "quality": SignalQuality.from_dict(r["quality"]),
        }
    )


def _hrr_from_row(r: dict) -> HRRResult:
    """Rebuild a Heart Rate Recovery session (HRR2 is NULL for < 120 s)."""
    return HRRResult(
        **r
        | {
            "date": str(r["date"]),
            "hr_at_120s": _or(r["hr_at_120s"], math.nan),
            "hrr_120": _or(r["hrr_120"], math.nan),
            "hrr_60_category": r["hrr_60_category"] or "",
            "hrr_120_category": r["hrr_120_category"] or "",
            "score": _or(r["score"], 0.0),
        }
    )


def _drift_from_row(r: dict) -> DriftResult:
    """Rebuild a cardiac drift session."""
    return DriftResult(
        **r
        | {
            "date": str(r["date"]),
            "drift_detected": bool(r["drift_detected"]),
            "n_windows": int(r["n_windows"]),
            "interpretation": r["interpretation"] or "no_drift",
            "score": _or(r["score"], 0.0),
        }
    )


def _vo2max_from_row(r: dict) -> VO2maxResult:
    """Rebuild a VO2max estimation (Uth model is NULL without hr_max)."""
    return VO2maxResult(
        **r
        | {
            "date": str(r["date"]),
            "vo2max_uth": _or(r["vo2max_uth"], math.nan),
            "hr_max": _or(r["hr_max"], math.nan),
            "fitness_category": r["fitness_category"] or "poor",
            "score": _or(r["score"], 0.0),
            "quality": SignalQuality.from_dict(r["quality"]),
        }
    )


# ======================
# PROTOCOL TABLE SPECIFICATIONS
# ======================


@dataclass(frozen=True)
class _ProtocolTable:
    """Storage specification of a protocol table keyed by ``UNIQUE(user_id, date)``.

    Drives the generic ``HRVRepository._create`` / ``_upsert`` / ``_select``
    methods, so adding a protocol table only takes a column registry and a
    ``from_row`` function.

    Attributes:
        table_attr: Name of the ``HRVRepository`` attribute holding the table
            name (table names are configurable per repository instance).
        columns: Column registry ``{name: sql_type}``, ``user_id`` and ``date``
            first; metric columns are named after the result attributes.
        from_row: Builds the result object from ``{"date": …, <metric>: …}``.

    """

    table_attr: str
    columns: dict[str, str]
    from_row: Callable[[dict], Any]

    @property
    def data_columns(self) -> list[str]:
        """Metric columns, in storage order."""
        return _data_columns(self.columns)

    def values(self, result: Any) -> tuple:
        """Read the metric column values from the same-named result attributes."""
        return tuple(getattr(result, c) for c in self.data_columns)


_RESTING = _ProtocolTable("table_name", _HRV_COLUMNS, _resting_from_row)
_ORTHOSTATIC = _ProtocolTable(
    "ortho_table_name", _ORTHO_COLUMNS, _ortho_record_from_row
)
_COHERENCE = _ProtocolTable(
    "coherence_table_name", _COHERENCE_COLUMNS, _coherence_from_row
)
_HRR = _ProtocolTable("hrr_table_name", _HRR_COLUMNS, _hrr_from_row)
_DRIFT = _ProtocolTable("drift_table_name", _DRIFT_COLUMNS, _drift_from_row)
_VO2MAX = _ProtocolTable("vo2max_table_name", _VO2MAX_COLUMNS, _vo2max_from_row)


# ======================
# QUERY BUILDERS
# ======================
# Table and column names always go through ``sql.Identifier``; column types
# come from the constant registries above (or validated ``extra_columns``).


def _create_table_query(table: str, columns: dict[str, str]) -> sql.Composed:
    """``CREATE TABLE IF NOT EXISTS`` with a serial id and ``UNIQUE(user_id, date)``."""
    columns_sql = ",\n    ".join(
        f"{name} {sql_type}" for name, sql_type in columns.items()
    )
    return sql.SQL(
        "CREATE TABLE IF NOT EXISTS {table} (\n"
        "    id SERIAL PRIMARY KEY,\n"
        "    {columns},\n"
        "    UNIQUE(user_id, date)\n"
        ");"
    ).format(table=sql.Identifier(table), columns=sql.SQL(columns_sql))


def _upsert_query(table: str, data_columns: list[str]) -> sql.Composed:
    """``INSERT … ON CONFLICT (user_id, date) DO UPDATE`` on every metric column."""
    all_cols = ["user_id", "date", *data_columns]
    return sql.SQL(
        "INSERT INTO {table} ({cols}) VALUES ({vals})\n"
        "ON CONFLICT (user_id, date) DO UPDATE SET {update};"
    ).format(
        table=sql.Identifier(table),
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in all_cols),
        vals=sql.SQL(", ").join(sql.Placeholder() for _ in all_cols),
        update=sql.SQL(", ").join(
            sql.SQL("{col} = EXCLUDED.{col}").format(col=sql.Identifier(c))
            for c in data_columns
        ),
    )


def _select_query(
    table: str,
    data_columns: list[str],
    *,
    single_date: bool,
) -> sql.Composed:
    """Select ``date`` + metric columns for a user — whole history or one date."""
    if single_date:
        template = sql.SQL(
            "SELECT {cols}\nFROM {table}\nWHERE user_id = %s AND date::date = %s;"
        )
    else:
        template = sql.SQL(
            "SELECT {cols}\nFROM {table}\nWHERE user_id = %s\nORDER BY date ASC;"
        )
    return template.format(
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in ["date", *data_columns]),
        table=sql.Identifier(table),
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
        register_adapter(np.int64, lambda v: AsIs(int(v)))
        register_adapter(np.int32, lambda v: AsIs(int(v)))
        register_adapter(np.bool_, lambda v: AsIs(bool(v)))
    except ImportError:
        pass  # NumPy non installé — aucune action requise


def _register_quality_adapter() -> None:
    """Store :class:`SignalQuality` values as JSONB (``quality`` columns)."""
    from psycopg2.extensions import register_adapter

    register_adapter(SignalQuality, lambda q: Json(q.to_dict()))


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
        raw_sessions_table_name: str = "hrv_raw_sessions",
        training_sessions_table_name: str = "hrv_training_sessions",
        user_profiles_table_name: str = "user_profiles",
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
            raw_sessions_table_name,
            training_sessions_table_name,
            user_profiles_table_name,
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
        self.raw_sessions_table_name = raw_sessions_table_name
        self.training_sessions_table_name = training_sessions_table_name
        self.user_profiles_table_name = user_profiles_table_name
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
        raw_sessions_table_name: str = "hrv_raw_sessions",
        training_sessions_table_name: str = "hrv_training_sessions",
        user_profiles_table_name: str = "user_profiles",
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
            raw_sessions_table_name: Raw RR intervals table name. Defaults to
                ``"hrv_raw_sessions"``.
            training_sessions_table_name: Training sessions table name.
                Defaults to ``"hrv_training_sessions"``.
            user_profiles_table_name: User profiles table name. Defaults to
                ``"user_profiles"``.

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
            raw_sessions_table_name=raw_sessions_table_name,
            training_sessions_table_name=training_sessions_table_name,
            user_profiles_table_name=user_profiles_table_name,
        )

    # ── Connection lifecycle ──────────────────────────────────────────────

    def __enter__(self) -> HRVRepository:
        """Open the database connection and register NumPy type adapters."""
        self._conn = connect(**self._dsn)
        _register_numpy_adapters()
        _register_quality_adapter()
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

    # ── Migrations ───────────────────────────────────────────────────────

    def run_migrations(self) -> list[str]:
        """Apply all pending SQL migrations to the database.

        Convenience wrapper around
        :func:`cardiolab.database.migrator.run_migrations` that uses the
        repository's open connection.

        Returns:
            List of migration version strings applied during this call
            (e.g. ``["V001__initial_schema", "V002__add_apen_sampen_ortho_metrics"]``).
            Empty list if the database is already up to date.

        Raises:
            RuntimeError: If called outside a ``with`` block.

        Example::

            with HRVRepository.from_env() as repo:
                applied = repo.run_migrations()

        """
        from cardiolab.database.migrator import run_migrations as _run

        return _run(self._conn_or_raise())

    # ── Generic protocol-table operations ────────────────────────────────

    def _create(
        self, spec: _ProtocolTable, columns: dict[str, str] | None = None
    ) -> None:
        """Create a protocol table (``CREATE TABLE IF NOT EXISTS``).

        Args:
            spec: Table specification.
            columns: Column registry overriding ``spec.columns`` (custom
                resting schemas).

        """
        query = _create_table_query(
            getattr(self, spec.table_attr), columns or spec.columns
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query)

    def _upsert(self, spec: _ProtocolTable, row: tuple) -> None:
        """Insert or update one ``(user_id, date, *metrics)`` row."""
        query = _upsert_query(getattr(self, spec.table_attr), spec.data_columns)
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, row)

    def _select(
        self,
        spec: _ProtocolTable,
        user_id: str,
        date: str | None = None,
    ) -> list:
        """Load a user's sessions — all of them by ascending date, or those of ``date``.

        Args:
            spec: Table specification.
            user_id: Identifier of the user whose sessions are retrieved.
            date: ISO date string; only the date part (``[:10]``) is matched.
                ``None`` loads the whole history.

        Returns:
            Result objects built by ``spec.from_row``.

        """
        query = _select_query(
            getattr(self, spec.table_attr),
            spec.data_columns,
            single_date=date is not None,
        )
        params = (user_id,) if date is None else (user_id, date[:10])
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        columns = ["date", *spec.data_columns]
        return [spec.from_row(dict(zip(columns, row, strict=True))) for row in rows]

    def _select_one(self, spec: _ProtocolTable, user_id: str, date: str):
        """Return the session of ``date`` (unique per user and date), or ``None``."""
        rows = self._select(spec, user_id, date)
        return rows[0] if rows else None

    # ── Resting ───────────────────────────────────────────────────────────

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

        self._create(_RESTING, fields)

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

        query = _upsert_query(self.table_name, _RESTING.data_columns)
        rows = [(user_id, f.date, *_RESTING.values(f)) for f in features]

        with self._conn_or_raise().cursor() as cur:
            cur.executemany(query, rows)

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
        return self._select(_RESTING, user_id)

    def load_features_for_date(self, user_id: str, date: str) -> HRVFeatures | None:
        """Load the resting HRV session recorded on a specific date, or None.

        Issues a targeted ``WHERE date::date = %s`` query instead of loading
        the full history, making it O(1) rather than O(N).

        Args:
            user_id: Athlete identifier.
            date: ISO date string (``"YYYY-MM-DD"`` or ``"YYYY-MM-DDTHH:MM:SS"``);
                only the date part is used.

        Returns:
            The matching :class:`~cardiolab.protocols.resting.HRVFeatures`, or
            ``None`` when no record exists for that date.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        return self._select_one(_RESTING, user_id, date)

    # ── Orthostatic ───────────────────────────────────────────────────────

    def create_orthostatic_table(self) -> None:
        """Create the orthostatic HRV table if it does not already exist.

        The table stores all 19 HRV metrics for three phases (supine,
        transition, standing) as prefixed columns, plus transition timing
        and derived metrics. A ``UNIQUE(user_id, date)`` constraint supports
        safe upserts.

        Column layout (73 data columns after user_id + date):

        * ``supine_*`` — 19 HRV metrics + ``supine_duration_sec``
        * ``transition_start_sec``, ``transition_end_sec``,
          ``transition_duration_sec``, ``transition_delta_hr``,
          ``transition_peak_hr``
        * ``transition_*`` — 19 HRV metrics (short window, ≈ 20–60 s)
        * ``standing_*`` — 19 HRV metrics + ``standing_duration_sec``
        * ``hr_response``, ``lf_hf_ratio_change``, ``hf_response_pct``,
          ``hf_hr_pct_change``, ``lf_hr_pct_change``, ``delta_rmssd``,
          ``interpretation``
        * ``spectral_method``, ``score``

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        self._create(_ORTHOSTATIC)

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
        self._upsert(_ORTHOSTATIC, _build_ortho_row(result, user_id, date))

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
        return self._select(_ORTHOSTATIC, user_id)

    def load_orthostatic_for_date(
        self, user_id: str, date: str
    ) -> OrthostaticRecord | None:
        """Load the orthostatic session recorded on a specific date, or None.

        Issues a targeted ``WHERE date::date = %s`` query instead of loading
        the full history, making it O(1) rather than O(N).

        Args:
            user_id: Athlete identifier.
            date: ISO date string (``"YYYY-MM-DD"`` or ``"YYYY-MM-DDTHH:MM:SS"``);
                only the date part is used.

        Returns:
            The matching :class:`~cardiolab.database.repository.OrthostaticRecord`,
            or ``None`` when no record exists for that date.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        return self._select_one(_ORTHOSTATIC, user_id, date)

    # ── Cardiac coherence ─────────────────────────────────────────────────

    def create_coherence_table(self) -> None:
        """Create the cardiac coherence session table if it does not exist.

        Stores results from paced-breathing coherence sessions (5-5 protocol).
        A ``UNIQUE(user_id, date)`` constraint supports safe upserts.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        self._create(_COHERENCE)

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
        self._upsert(_COHERENCE, (user_id, date, *_COHERENCE.values(result)))

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
        return self._select(_COHERENCE, user_id)

    # ── Heart Rate Recovery ───────────────────────────────────────────────

    def create_hrr_table(self) -> None:
        """Create the Heart Rate Recovery session table if it does not exist.

        Stores HRR1 and HRR2 values from post-exercise recordings.
        A ``UNIQUE(user_id, date)`` constraint supports safe upserts.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        self._create(_HRR)

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
        self._upsert(_HRR, (user_id, date, *_HRR.values(result)))

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
        return self._select(_HRR, user_id)

    # ── Cardiac drift ─────────────────────────────────────────────────────

    def create_drift_table(self) -> None:
        """Create the cardiac drift session table if it does not exist.

        Stores progressive HR drift analysis from constant-load exercise.
        A ``UNIQUE(user_id, date)`` constraint supports safe upserts.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        self._create(_DRIFT)

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
        self._upsert(_DRIFT, (user_id, date, *_DRIFT.values(result)))

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
        return self._select(_DRIFT, user_id)

    # ── VO2max ────────────────────────────────────────────────────────────

    def create_vo2max_table(self) -> None:
        """Create the VO2max estimation session table if it does not exist.

        Stores VO2max estimates from HRV-based models (Uth, Esco-Flatt,
        ln-RMSSD). A ``UNIQUE(user_id, date)`` constraint supports safe upserts.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        self._create(_VO2MAX)

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
        self._upsert(_VO2MAX, (user_id, date, *_VO2MAX.values(result)))

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
        return self._select(_VO2MAX, user_id)

    # ── Raw sessions — schema ────────────────────────────────────────────

    def create_raw_sessions_table(self) -> None:
        """Create the raw RR sessions table if it does not already exist.

        The table stores the raw RR interval array (in milliseconds) for every
        recorded session together with provenance metadata.  It is the
        **source of truth** for all protocol analyses: having the raw signal
        allows reprocessing with different parameters (spectral method, clean
        thresholds, …) without re-importing original files.

        Schema::

            hrv_raw_sessions (
                id           SERIAL PRIMARY KEY,
                user_id      TEXT      NOT NULL,
                session_date DATE      NOT NULL,
                protocol     TEXT      NOT NULL,
                rr_intervals FLOAT[]   NOT NULL,   -- ms, one value per beat
                source_file  TEXT,                  -- original filename
                device       TEXT DEFAULT 'hrv_elite',
                duration_sec FLOAT,                 -- total recording duration
                beat_count   INT,                   -- len(rr_intervals)
                created_at   TIMESTAMP DEFAULT NOW(),
                metadata     JSONB     DEFAULT '{}',
                UNIQUE(user_id, session_date, protocol)
            )

        The ``UNIQUE(user_id, session_date, protocol)`` constraint mirrors the
        key used by all protocol tables, enabling natural joins and safe
        upserts.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table} (\n"
            "    id           SERIAL PRIMARY KEY,\n"
            "    user_id      TEXT      NOT NULL,\n"
            "    session_date DATE      NOT NULL,\n"
            "    protocol     TEXT      NOT NULL,\n"
            "    rr_intervals FLOAT[]   NOT NULL,\n"
            "    source_file  TEXT,\n"
            "    device       TEXT      DEFAULT 'hrv_elite',\n"
            "    duration_sec FLOAT,\n"
            "    beat_count   INT,\n"
            "    created_at   TIMESTAMP DEFAULT NOW(),\n"
            "    metadata     JSONB     DEFAULT '{{}}',\n"
            "    UNIQUE(user_id, session_date, protocol)\n"
            ");"
        ).format(table=sql.Identifier(self.raw_sessions_table_name))

        with self._conn_or_raise().cursor() as cur:
            cur.execute(query)

    # ── Raw sessions — write ─────────────────────────────────────────────

    def save_raw_session(
        self,
        rr: RRSeries,
        user_id: str,
        date: str,
        protocol: str,
        source_file: str | None = None,
        device: str = "hrv_elite",
        metadata: dict | None = None,
    ) -> None:
        """Save raw RR intervals for a session (upsert).

        Stores the full RR interval array in milliseconds alongside provenance
        metadata.  An existing row for the same ``(user_id, date, protocol)``
        is overwritten so repeated imports are safe.

        Args:
            rr: RR interval series to persist.  ``rr.intervals`` is converted
                to a plain Python list before insertion so that NumPy arrays
                are handled transparently.
            user_id: User identifier (UUID or string).
            date: ISO-format date string (``"YYYY-MM-DD"``).
            protocol: Protocol name (``"resting"``, ``"orthostatic"``, etc.).
            source_file: Original filename for traceability. Optional.
            device: Acquisition device name. Defaults to ``"hrv_elite"``.
            metadata: Arbitrary key-value pairs serialised as JSONB — e.g.
                ``{"method": "ar", "hr_max": 185.0}``. Defaults to ``{}``.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        rr_list = [float(v) for v in rr.intervals]
        meta = Json(metadata or {})

        query = sql.SQL(
            "INSERT INTO {table} "
            "(user_id, session_date, protocol, rr_intervals, source_file, "
            " device, duration_sec, beat_count, metadata)\n"
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)\n"
            "ON CONFLICT (user_id, session_date, protocol) DO UPDATE SET\n"
            "    rr_intervals = EXCLUDED.rr_intervals,\n"
            "    source_file  = EXCLUDED.source_file,\n"
            "    device       = EXCLUDED.device,\n"
            "    duration_sec = EXCLUDED.duration_sec,\n"
            "    beat_count   = EXCLUDED.beat_count,\n"
            "    metadata     = EXCLUDED.metadata,\n"
            "    created_at   = NOW();"
        ).format(table=sql.Identifier(self.raw_sessions_table_name))

        with self._conn_or_raise().cursor() as cur:
            cur.execute(
                query,
                (
                    user_id,
                    date,
                    protocol,
                    rr_list,
                    source_file,
                    device,
                    rr.duration,
                    len(rr_list),
                    meta,
                ),
            )

    # ── Raw sessions — read ──────────────────────────────────────────────

    def load_raw_session(
        self,
        user_id: str,
        date: str,
        protocol: str,
    ) -> RRSeries | None:
        """Load raw RR intervals for a specific session.

        Args:
            user_id: User identifier.
            date: ISO date string (``"YYYY-MM-DD"``).
            protocol: Protocol name.

        Returns:
            A :class:`~cardiolab.signals.rr.RRSeries` reconstructed from the
            stored intervals, or ``None`` if no record exists for the given
            ``(user_id, date, protocol)`` triplet.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        query = sql.SQL(
            "SELECT rr_intervals, metadata\n"
            "FROM {table}\n"
            "WHERE user_id = %s AND session_date = %s AND protocol = %s;"
        ).format(table=sql.Identifier(self.raw_sessions_table_name))

        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, (user_id, date, protocol))
            row = cur.fetchone()

        if row is None:
            return None

        rr_intervals, metadata = row
        return RRSeries(
            intervals=rr_intervals,
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    def list_raw_sessions(
        self,
        user_id: str,
        protocol: str | None = None,
    ) -> list[dict]:
        """List stored raw sessions for a user.

        Args:
            user_id: User identifier.
            protocol: If provided, filter to sessions of that protocol only.

        Returns:
            List of dicts, one per session, sorted by ascending date.
            Each dict has keys: ``date``, ``protocol``, ``source_file``,
            ``device``, ``duration_sec``, ``beat_count``, ``created_at``,
            ``metadata``.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        if protocol is not None:
            query = sql.SQL(
                "SELECT session_date, protocol, source_file, device,\n"
                "       duration_sec, beat_count, created_at, metadata\n"
                "FROM {table}\n"
                "WHERE user_id = %s AND protocol = %s\n"
                "ORDER BY session_date ASC;"
            ).format(table=sql.Identifier(self.raw_sessions_table_name))
            params = (user_id, protocol)
        else:
            query = sql.SQL(
                "SELECT session_date, protocol, source_file, device,\n"
                "       duration_sec, beat_count, created_at, metadata\n"
                "FROM {table}\n"
                "WHERE user_id = %s\n"
                "ORDER BY session_date ASC, protocol ASC;"
            ).format(table=sql.Identifier(self.raw_sessions_table_name))
            params = (user_id,)

        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return [
            {
                "date": str(row[0]),
                "protocol": row[1],
                "source_file": row[2],
                "device": row[3],
                "duration_sec": row[4],
                "beat_count": row[5],
                "created_at": str(row[6]) if row[6] else None,
                "metadata": row[7] if isinstance(row[7], dict) else {},
            }
            for row in rows
        ]

    # ── Training sessions — schema ────────────────────────────────────────

    def create_training_sessions_table(self) -> None:
        """Create the training sessions table if it does not already exist.

        Schema::

            activity_id  TEXT PRIMARY KEY   -- UUID generated in Python (uuid4)
            user_id      TEXT NOT NULL
            date         DATE NOT NULL
            duration_min FLOAT              -- duration in minutes
            sport_type   TEXT               -- e.g. "running", "cycling"
            trimp        FLOAT              -- nullable: computed later if readiness absent
            notes        TEXT               -- free-text notes

        Design rationale: one row per **activity**, not per day.  Multiple
        activities on the same day are each stored as independent rows, each
        with their own ``activity_id``.  ATL/CTL/TSB aggregation (TRIMP sum
        per day) is handled by :meth:`TrainingLoad.from_sessions
        <cardiolab.analytics.training_load.TrainingLoad.from_sessions>`.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        columns_sql = ",\n    ".join(
            f"{k} {v}" for k, v in _TRAINING_SESSIONS_COLUMNS.items()
        )
        query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table} (\n"
            "    activity_id TEXT PRIMARY KEY,\n"
            "    {columns}\n"
            ");"
        ).format(
            table=sql.Identifier(self.training_sessions_table_name),
            columns=sql.SQL(columns_sql),
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query)

    # ── Training sessions — write ─────────────────────────────────────────

    def save_training_session(
        self,
        user_id: str,
        date: str,
        duration_min: float | None = None,
        sport_type: str | None = None,
        trimp: float | None = None,
        notes: str | None = None,
    ) -> str:
        """Insert a new training activity and return its ``activity_id``.

        Each call always inserts a **new row** — there is no upsert.  Multiple
        activities on the same day are each stored independently and identified
        by their ``activity_id``.  The caller is responsible for not inserting
        duplicates when that matters (e.g. an interface should confirm before
        logging a second activity of the same sport on the same day).

        Args:
            user_id: User identifier.
            date: ISO date string (e.g. ``"2026-05-29"``).
            duration_min: Duration of the training session in minutes.
            sport_type: Sport — a code of :data:`cardiolab.sports.SPORTS`
                (``"running"``, ``"cycling"``…) or any name
                :func:`cardiolab.sports.validate_sport` recognises
                (« Course à pied », ``"vélo"``…). Always stored as the code.
                ``None`` means no sport.
            trimp: Pre-computed TRIMP value. May be ``None`` when the
                readiness score for the day is not available yet.
            notes: Free-text notes about the session.

        Returns:
            The ``activity_id`` (UUID string) of the newly created row.

        Raises:
            ValueError: If ``sport_type`` is not a known sport (the message
                suggests the closest one) — nothing is written.
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the insert fails.

        """
        sport_type = validate_sport(sport_type)
        activity_id = str(uuid.uuid4())
        all_cols = ["activity_id", "user_id", "date"] + _TRAINING_SESSIONS_DATA_COLUMNS
        col_identifiers = sql.SQL(", ").join(sql.Identifier(c) for c in all_cols)
        placeholders = sql.SQL(", ").join(
            sql.Placeholder() for _ in range(len(all_cols))
        )
        query = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({vals});").format(
            table=sql.Identifier(self.training_sessions_table_name),
            cols=col_identifiers,
            vals=placeholders,
        )
        row = (activity_id, user_id, date, duration_min, sport_type, trimp, notes)
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, row)
        return activity_id

    def delete_training_session(self, activity_id: str) -> bool:
        """Delete a training activity by its unique ``activity_id``.

        Args:
            activity_id: UUID string identifying the activity to delete.

        Returns:
            ``True`` if a row was deleted, ``False`` if no matching row existed.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the delete fails.

        """
        query = sql.SQL("DELETE FROM {table} WHERE activity_id = %s;").format(
            table=sql.Identifier(self.training_sessions_table_name)
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, (activity_id,))
            return cur.rowcount == 1

    # ── Training sessions — read ──────────────────────────────────────────

    def load_training_sessions(self, user_id: str) -> list[dict]:
        """Load all training activities for a user, sorted by date then activity_id.

        Args:
            user_id: User identifier.

        Returns:
            List of dicts, one per activity, sorted ascending by date.
            Each dict has keys: ``activity_id``, ``date``, ``duration_min``,
            ``sport_type``, ``trimp``, ``notes``.
            Multiple activities on the same day appear as distinct rows.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        sel = sql.SQL(", ").join(
            sql.Identifier(c) for c in _TRAINING_SESSIONS_SELECT_COLUMNS
        )
        query = sql.SQL(
            "SELECT {sel}\n"
            "FROM {table}\n"
            "WHERE user_id = %s\n"
            "ORDER BY date ASC, activity_id ASC;"
        ).format(
            sel=sel,
            table=sql.Identifier(self.training_sessions_table_name),
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, (user_id,))
            rows = cur.fetchall()
        return [
            dict(zip(_TRAINING_SESSIONS_SELECT_COLUMNS, row, strict=False))
            | {"date": str(row[1])}
            for row in rows
        ]

    def find_training_sessions(
        self,
        user_id: str,
        date: str,
        sport_type: str | None = None,
    ) -> list[dict]:
        """Find activities for a user on a given date, optionally filtered by sport.

        Intended for the delete workflow: look up which activities exist before
        asking the user to confirm or choose by ``activity_id``.

        Args:
            user_id: User identifier.
            date: ISO date string (``"YYYY-MM-DD"``).
            sport_type: Optional sport filter (code or any name
                :func:`cardiolab.sports.validate_sport` recognises). When
                ``None``, all activities on the date are returned regardless
                of sport type.

        Returns:
            List of matching activity dicts (same keys as
            :meth:`load_training_sessions`), ordered by sport_type then
            activity_id.  Empty list when nothing matches.

        Raises:
            ValueError: If ``sport_type`` is not a known sport.
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the query fails.

        """
        sel = sql.SQL(", ").join(
            sql.Identifier(c) for c in _TRAINING_SESSIONS_SELECT_COLUMNS
        )
        sport_type = validate_sport(sport_type)
        if sport_type is not None:
            query = sql.SQL(
                "SELECT {sel} FROM {table}\n"
                "WHERE user_id = %s AND date = %s AND sport_type = %s\n"
                "ORDER BY sport_type ASC, activity_id ASC;"
            ).format(sel=sel, table=sql.Identifier(self.training_sessions_table_name))
            params: tuple = (user_id, date, sport_type)
        else:
            query = sql.SQL(
                "SELECT {sel} FROM {table}\n"
                "WHERE user_id = %s AND date = %s\n"
                "ORDER BY sport_type ASC, activity_id ASC;"
            ).format(sel=sel, table=sql.Identifier(self.training_sessions_table_name))
            params = (user_id, date)
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [
            dict(zip(_TRAINING_SESSIONS_SELECT_COLUMNS, row, strict=False))
            | {"date": str(row[1])}
            for row in rows
        ]

    # ── User profiles — schema ────────────────────────────────────────────

    def create_user_profiles_table(self) -> None:
        """Create the user profiles table if it does not already exist.

        Schema::

            user_profiles (
                user_id          TEXT      PRIMARY KEY,
                primary_protocol TEXT      NOT NULL DEFAULT 'resting',
                sex              TEXT,
                birth_year       INT,
                height_cm        FLOAT,
                hr_max           INT,
                hr_rest          INT,
                weight_kg        FLOAT,
                created_at       TIMESTAMP DEFAULT NOW(),
                updated_at       TIMESTAMP DEFAULT NOW()
            )

        ``primary_protocol`` drives the readiness source for TRIMP computation
        (``"resting"`` or ``"orthostatic"``). Physical fields are used by
        specific formulas: ``sex`` for Banister TRIMP, ``hr_max``/``hr_rest``
        for Banister and Uth VO2max, ``birth_year`` for ACSM age-based norms.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SQL statement is rejected.

        """
        columns_sql = ",\n    ".join(
            f"{k} {v}" for k, v in _USER_PROFILES_COLUMNS.items()
        )
        query = sql.SQL(
            "CREATE TABLE IF NOT EXISTS {table} (\n"
            "    user_id   TEXT PRIMARY KEY,\n"
            "    {columns},\n"
            "    created_at TIMESTAMP DEFAULT NOW(),\n"
            "    updated_at TIMESTAMP DEFAULT NOW()\n"
            ");"
        ).format(
            table=sql.Identifier(self.user_profiles_table_name),
            columns=sql.SQL(columns_sql),
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query)

    # ── User profiles — write ─────────────────────────────────────────────

    def save_user_profile(
        self,
        user_id: str,
        primary_protocol: str = "resting",
        sex: str | None = None,
        birth_year: int | None = None,
        height_cm: float | None = None,
        hr_max: int | None = None,
        hr_rest: int | None = None,
        weight_kg: float | None = None,
    ) -> None:
        """Insert or update a user profile (upsert on ``user_id``).

        On conflict, all provided fields are overwritten and ``updated_at``
        is refreshed.  ``created_at`` is never modified by an update.

        Args:
            user_id: Unique user identifier (UUID string).
            primary_protocol: ``"resting"`` or ``"orthostatic"``. Determines
                which HRV table feeds the readiness score used for TRIMP.
            sex: ``"male"``, ``"female"``, or ``None``. Selects the Banister
                TRIMP weighting coefficient (``b``).
            birth_year: Year of birth. Used for ACSM VO2max age norms.
            height_cm: Height in centimetres.
            hr_max: Maximal heart rate (bpm). Required for Banister TRIMP
                and Uth VO2max estimation.
            hr_rest: Resting heart rate (bpm). Required for Banister TRIMP.
            weight_kg: Body weight in kilograms.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the upsert fails.

        """
        cols = ["user_id", *_USER_PROFILES_COLUMNS.keys()]
        values = (
            user_id,
            primary_protocol,
            sex,
            birth_year,
            height_cm,
            hr_max,
            hr_rest,
            weight_kg,
        )
        placeholders = sql.SQL(", ").join(sql.Placeholder() * len(cols))
        col_ids = sql.SQL(", ").join(sql.Identifier(c) for c in cols)
        update_set = sql.SQL(", ").join(
            sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c))
            for c in _USER_PROFILES_COLUMNS
        )
        query = sql.SQL(
            "INSERT INTO {table} ({cols}, created_at, updated_at)\n"
            "VALUES ({vals}, NOW(), NOW())\n"
            "ON CONFLICT (user_id) DO UPDATE SET\n"
            "    {update_set},\n"
            "    updated_at = NOW();"
        ).format(
            table=sql.Identifier(self.user_profiles_table_name),
            cols=col_ids,
            vals=placeholders,
            update_set=update_set,
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, values)

    def update_user_profile(self, user_id: str, **fields) -> bool:
        """Update specific fields of an existing user profile.

        Only fields whose names are in :data:`_USER_PROFILES_UPDATABLE` are
        accepted; any other key raises ``ValueError`` before touching the DB.

        Args:
            user_id: Unique user identifier.
            **fields: Field names and their new values. Accepted keys:
                ``primary_protocol``, ``sex``, ``birth_year``,
                ``height_cm``, ``hr_max``, ``hr_rest``, ``weight_kg``.

        Returns:
            ``True`` if a profile with ``user_id`` existed and was updated,
            ``False`` if no such profile was found.

        Raises:
            ValueError: If any key in ``fields`` is not a known updatable
                field, or if ``fields`` is empty.
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the UPDATE fails.

        """
        if not fields:
            raise ValueError("At least one field must be provided.")
        unknown = set(fields) - _USER_PROFILES_UPDATABLE
        if unknown:
            raise ValueError(
                f"Unknown field(s): {sorted(unknown)}. "
                f"Accepted: {sorted(_USER_PROFILES_UPDATABLE)}"
            )
        set_clause = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(k)) for k in fields
        )
        query = sql.SQL(
            "UPDATE {table} SET {set_clause}, updated_at = NOW() WHERE user_id = %s;"
        ).format(
            table=sql.Identifier(self.user_profiles_table_name),
            set_clause=set_clause,
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, (*fields.values(), user_id))
            return cur.rowcount > 0

    def delete_user_profile(self, user_id: str) -> bool:
        """Delete the profile for ``user_id``.

        Args:
            user_id: Unique user identifier.

        Returns:
            ``True`` if a profile was deleted, ``False`` if not found.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the DELETE fails.

        """
        query = sql.SQL("DELETE FROM {table} WHERE user_id = %s;").format(
            table=sql.Identifier(self.user_profiles_table_name)
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, (user_id,))
            return cur.rowcount > 0

    # ── User profiles — read ──────────────────────────────────────────────

    def load_user_profile(self, user_id: str) -> dict | None:
        """Return the profile for ``user_id``, or ``None`` if not found.

        Args:
            user_id: Unique user identifier.

        Returns:
            Dictionary with keys matching :data:`_USER_PROFILES_SELECT_COLUMNS`,
            or ``None`` if no profile exists for ``user_id``.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SELECT fails.

        """
        sel = sql.SQL(", ").join(
            sql.Identifier(c) for c in _USER_PROFILES_SELECT_COLUMNS
        )
        query = sql.SQL("SELECT {sel} FROM {table} WHERE user_id = %s;").format(
            sel=sel, table=sql.Identifier(self.user_profiles_table_name)
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query, (user_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return dict(zip(_USER_PROFILES_SELECT_COLUMNS, row, strict=False))

    def list_user_profiles(self) -> list[dict]:
        """Return all user profiles sorted by ``user_id``.

        Returns:
            List of dicts, each with keys matching
            :data:`_USER_PROFILES_SELECT_COLUMNS`.  Empty list when no
            profiles exist.

        Raises:
            RuntimeError: If called outside a ``with`` block.
            psycopg2.Error: If the SELECT fails.

        """
        sel = sql.SQL(", ").join(
            sql.Identifier(c) for c in _USER_PROFILES_SELECT_COLUMNS
        )
        query = sql.SQL("SELECT {sel} FROM {table} ORDER BY user_id ASC;").format(
            sel=sel, table=sql.Identifier(self.user_profiles_table_name)
        )
        with self._conn_or_raise().cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
        return [
            dict(zip(_USER_PROFILES_SELECT_COLUMNS, row, strict=False)) for row in rows
        ]
