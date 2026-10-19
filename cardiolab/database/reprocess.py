"""Reprocess stored sessions from their raw RR intervals.

v0.4.0 changes computed values (artefact correction, spectral analysis,
signal quality). Without reprocessing, the history would mix two pipelines and
distort baselines, scores and trends. The raw RR intervals of every session are
kept in ``hrv_raw_sessions``: this module recomputes the results of past
sessions from them, with the current pipeline.

Typical usage::

    from cardiolab.database import HRVRepository, reprocess_sessions

    with HRVRepository.from_env() as repo:
        report = reprocess_sessions(repo, user_id)            # dry run
        print(report.summary())

    with HRVRepository.from_env() as repo:
        reprocess_sessions(repo, user_id, dry_run=False)      # write

All writes happen inside the caller's ``with HRVRepository`` block — one
transaction: committed together when the block exits, rolled back on any
database error.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.scoring import (
    SCORED_PROTOCOLS,
    orthostatic_readiness_score,
    session_score,
)
from cardiolab.protocols.cardiac_coherence import cardiac_coherence
from cardiolab.protocols.cardiac_drift import cardiac_drift
from cardiolab.protocols.hrr import heart_rate_recovery
from cardiolab.protocols.orthostatic import orthostatic_hrv
from cardiolab.protocols.resting import resting_hrv
from cardiolab.protocols.vo2max import vo2max_from_hrv
from cardiolab.signals.rr import RRSeries

PROTOCOLS: tuple[str, ...] = SCORED_PROTOCOLS
"""Protocols that can be reprocessed."""

KEY_METRICS: dict[str, tuple[str, ...]] = {
    "resting": ("rmssd", "mean_hr", "hf", "lf_hf", "dfa_alpha1", "sampen", "score"),
    "orthostatic": (
        "supine_rmssd",
        "standing_rmssd",
        "hr_response",
        "hf_hr_pct_change",
        "score",
        "readiness_score",
    ),
    "coherence": ("coherence_score", "rmssd", "score"),
    "hrr": ("hrr_60", "hrr_120", "score"),
    "drift": ("drift_rate", "score"),
    "vo2max": ("vo2max_uth", "vo2max_ln_rmssd", "fitness_category", "score"),
}
"""Metrics compared before / after, per protocol (plus ``quality_grade``)."""

_HRV_CORRECTED = ("coherence", "vo2max")
"""Protocols without ``auto_clean`` whose RR series is corrected beforehand."""


# ======================
# ANALYSIS PIPELINE
# ======================


def analyse_session(
    protocol: str,
    rr: RRSeries,
    *,
    method: str = "lomb",
    auto_clean: bool = True,
    hr_max: float | None = None,
) -> Any:
    """Analyse one raw recording with the current pipeline (score not set).

    The single definition of "how a session is computed", shared by
    reprocessing and imports:

    * ``resting`` / ``orthostatic`` — ``auto_clean`` and spectral ``method``
      passed to the protocol;
    * ``coherence`` / ``vo2max`` — RR series corrected first when
      ``auto_clean`` (:meth:`RRSeries.correct_artifacts`), so that their
      quality index is graded as corrected;
    * ``hrr`` / ``drift`` — heart-rate based, analysed as recorded.

    Args:
        protocol: One of :data:`PROTOCOLS`.
        rr: Raw RR intervals of the session.
        method: Spectral method (resting, orthostatic). Defaults to ``"lomb"``.
        auto_clean: Correct artefacts before analysis. Defaults to ``True``.
        hr_max: Maximal heart rate, for the Uth VO2max model.

    Returns:
        The protocol result.

    Raises:
        ValueError: If ``protocol`` is unknown, or raised by the protocol
            (e.g. no orthostatic transition found).

    """
    if protocol == "resting":
        return resting_hrv(rr, auto_clean=auto_clean, method=method)
    if protocol == "orthostatic":
        return orthostatic_hrv(rr, auto_clean=auto_clean, method=method)
    if protocol in _HRV_CORRECTED and auto_clean:
        rr, _ = rr.correct_artifacts()
    if protocol == "coherence":
        return cardiac_coherence(rr)
    if protocol == "vo2max":
        return vo2max_from_hrv(rr, hr_max=hr_max)
    if protocol == "hrr":
        return heart_rate_recovery(rr)
    if protocol == "drift":
        return cardiac_drift(rr)
    raise ValueError(
        f"Unknown protocol {protocol!r}. Choose from {', '.join(PROTOCOLS)}."
    )


# ======================
# REPORT
# ======================


@dataclass
class SessionChange:
    """Before / after values of one reprocessed session.

    Attributes:
        protocol: Protocol name.
        date: Session date (ISO).
        status: ``"changed"``, ``"unchanged"``, ``"new"`` (raw RR but no
            stored result) or ``"failed"`` (analysis error — stored row kept).
        before: Key metrics stored before reprocessing (empty for ``new``).
        after: Key metrics recomputed (empty for ``failed``).
        error: Error message for ``failed`` sessions.
        warnings: Physiological warnings raised during the analysis.
        changed_fields: Every stored field whose value changed — the status
            is ``changed`` as soon as one does, even outside ``before`` /
            ``after`` (key metrics only).

    """

    protocol: str
    date: str
    status: str
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    changed_fields: list[str] = field(default_factory=list)

    def deltas(self) -> dict[str, tuple[Any, Any]]:
        """Return the metrics whose value changed: ``{metric: (before, after)}``."""
        return {
            key: (self.before.get(key), self.after.get(key))
            for key in self.after
            if not _same(self.before.get(key), self.after.get(key))
        }


@dataclass
class ReprocessReport:
    """Outcome of :func:`reprocess_sessions`.

    Attributes:
        user_id: User whose sessions were reprocessed.
        dry_run: ``True`` if nothing was written.
        method: Spectral method used.
        sessions: One :class:`SessionChange` per raw session.
        skipped: Stored sessions without raw RR intervals (Apple Health
            imports, SDNN only…), left untouched: ``(protocol, date)``.

    """

    user_id: str
    dry_run: bool
    method: str
    sessions: list[SessionChange] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def count(self, status: str) -> int:
        """Return the number of sessions with ``status``."""
        return sum(1 for s in self.sessions if s.status == status)

    @property
    def written(self) -> int:
        """Number of sessions written (0 in dry run)."""
        if self.dry_run:
            return 0
        return self.count("changed") + self.count("new")

    def summary(self) -> str:
        """Human-readable summary, one line per protocol."""
        mode = (
            "dry run — nothing written" if self.dry_run else f"{self.written} written"
        )
        lines = [f"Reprocessing ({mode}, spectral method: {self.method})"]
        for protocol in PROTOCOLS:
            items = [s for s in self.sessions if s.protocol == protocol]
            skipped = sum(1 for p, _ in self.skipped if p == protocol)
            if not items and not skipped:
                continue
            counts = {
                st: sum(1 for s in items if s.status == st)
                for st in ("changed", "unchanged", "new", "failed")
            }
            lines.append(
                f"  {protocol:<12} {len(items):>3} sessions — "
                f"{counts['changed']} changed, {counts['unchanged']} unchanged, "
                f"{counts['new']} new, {counts['failed']} failed, "
                f"{skipped} without raw RR"
            )
        for s in self.sessions:
            if s.status == "failed":
                lines.append(f"  ✗ {s.protocol} {s.date}: {s.error}")
        return "\n".join(lines)

    def to_rows(self) -> list[dict]:
        """Flat rows (one per session and metric) for CSV or DataFrame export."""
        rows = []
        for s in self.sessions:
            keys = list(dict.fromkeys([*s.before, *s.after])) or [""]
            for key in keys:
                before, after = s.before.get(key), s.after.get(key)
                rows.append(
                    {
                        "protocol": s.protocol,
                        "date": s.date,
                        "status": s.status,
                        "metric": key,
                        "before": before,
                        "after": after,
                        "change_pct": _change_pct(before, after),
                        "changed_fields": ";".join(s.changed_fields),
                        "error": s.error or "",
                    }
                )
        return rows


def _same(a, b) -> bool:
    """Equality with NaN == NaN and a relative tolerance for floats."""
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) or math.isnan(b):
            return math.isnan(a) and math.isnan(b)
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12)
    return a == b


def _change_pct(before, after) -> float | None:
    """Relative change in % (``None`` when not numeric or before is 0)."""
    numeric = all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in (before, after)
    )
    if not numeric or not before or math.isnan(before) or math.isnan(after):
        return None
    return round(100.0 * (after - before) / abs(before), 2)


def _key_values(protocol: str, result) -> dict:
    """Key metrics of a result or stored record, plus its quality grade."""
    flat = (
        result.to_flat_dict() if hasattr(result, "to_flat_dict") else result.to_dict()
    )
    values = {key: _native(flat.get(key)) for key in KEY_METRICS[protocol]}
    quality = getattr(result, "quality", None)
    values["quality_grade"] = quality.grade if quality is not None else None
    return values


def _stored_fields(protocol: str, result) -> dict:
    """Every stored value of a result or record, flattened — used to detect changes.

    Orthostatic sessions add the quality of each phase (stored in the JSONB
    column, not in the flat dict).
    """
    flat = (
        result.to_flat_dict() if hasattr(result, "to_flat_dict") else result.to_dict()
    )
    # Dates identify the session, they are not stored values (phase dates too)
    fields = {k: _native(v) for k, v in flat.items() if not k.endswith("date")}
    if protocol == "orthostatic":
        for prefix, features in _phase_features(result):
            quality = getattr(features, "quality", None)
            fields[f"{prefix}_quality"] = quality.to_dict() if quality else None
    return fields


def _phase_features(result) -> list[tuple[str, Any]]:
    """Phase features of an ``OrthostaticResult`` or ``OrthostaticRecord``."""
    if hasattr(result, "phases"):
        p = result.phases
        return [
            ("supine", p.supine.features),
            ("transition", p.transition.features),
            ("standing", p.standing.features),
        ]
    if hasattr(result, "supine"):
        return [
            ("supine", result.supine),
            ("transition", result.transition_features),
            ("standing", result.standing),
        ]
    return []


def _changed_fields(before: dict, after: dict) -> list[str]:
    """Fields stored on both sides whose value differs."""
    return sorted(
        k for k in before.keys() & after.keys() if not _same(before[k], after[k])
    )


def _native(value):
    """NumPy scalars → Python scalars, for clean comparisons and exports."""
    return value.item() if hasattr(value, "item") else value


# ======================
# REPROCESSING
# ======================


def _storage(repo, user_id: str) -> dict[str, tuple[Callable, Callable]]:
    """``{protocol: (load_all, save)}`` bound to ``repo`` and ``user_id``."""

    def save_resting(result, date: str) -> None:
        result.date = date
        repo.save_features(result, user_id=user_id)

    def saver(method_name: str) -> Callable:
        def save(result, date: str) -> None:
            getattr(repo, method_name)(result, user_id=user_id, date=date)

        return save

    return {
        "resting": (lambda: repo.load_features(user_id), save_resting),
        "orthostatic": (
            lambda: repo.load_orthostatic(user_id),
            saver("save_orthostatic"),
        ),
        "coherence": (lambda: repo.load_coherence(user_id), saver("save_coherence")),
        "hrr": (lambda: repo.load_hrr(user_id), saver("save_hrr")),
        "drift": (lambda: repo.load_drift(user_id), saver("save_drift")),
        "vo2max": (lambda: repo.load_vo2max(user_id), saver("save_vo2max")),
    }


def _hr_max(stored, raw_meta: dict, default: float | None) -> float | None:
    """hr_max for VO2max: stored estimation → raw metadata → ``default``."""
    value = getattr(stored, "hr_max", None)
    if value is not None and math.isfinite(value) and value > 0:
        return float(value)
    value = raw_meta.get("hr_max")
    return float(value) if value else default


def reprocess_sessions(
    repo,
    user_id: str,
    protocol: str | None = None,
    since: str | None = None,
    dry_run: bool = True,
    *,
    method: str = "lomb",
    auto_clean: bool = True,
    hr_max: float | None = None,
) -> ReprocessReport:
    """Recompute stored sessions from their raw RR intervals.

    For each session of ``hrv_raw_sessions`` (in chronological order), the
    raw RR series is analysed with :func:`analyse_session`, the score is
    recomputed with :func:`~cardiolab.analytics.scoring.session_score` — the
    resting readiness score against a baseline made of the **previous**
    sessions, already reprocessed — and the result replaces the stored one.

    Running it twice gives the same values (the second run reports every
    session as ``unchanged``).

    Args:
        repo: An open :class:`~cardiolab.database.repository.HRVRepository`
            (inside a ``with`` block — it holds the transaction).
        user_id: User whose sessions are reprocessed.
        protocol: A single protocol, or ``None`` for all of them.
        since: Only reprocess sessions on or after this ISO date; earlier
            stored sessions still feed the resting baseline.
        dry_run: If ``True`` (default), compute and report without writing.
        method: Spectral method for resting and orthostatic sessions.
            Defaults to ``"lomb"`` (the v0.4.0 default).
        auto_clean: Correct artefacts before analysis. Defaults to ``True``.
        hr_max: Maximal heart rate for VO2max sessions whose stored
            estimation has none.

    Returns:
        A :class:`ReprocessReport` with before / after values per session.

    Raises:
        ValueError: If ``protocol`` is unknown.

    """
    protocols = PROTOCOLS if protocol is None else (protocol,)
    unknown = set(protocols) - set(PROTOCOLS)
    if unknown:
        raise ValueError(
            f"Unknown protocol {sorted(unknown)[0]!r}. Choose from {', '.join(PROTOCOLS)}."
        )

    report = ReprocessReport(user_id=user_id, dry_run=dry_run, method=method)
    storage = _storage(repo, user_id)

    for proto in protocols:
        raw = {s["date"]: s for s in repo.list_raw_sessions(user_id, proto)}
        if not raw:
            continue  # nothing to reprocess — the table is not even queried
        load_all, save = storage[proto]
        stored = {str(r.date): r for r in load_all()}

        report.skipped.extend(
            (proto, d)
            for d in sorted(set(stored) - set(raw))
            if since is None or d >= since
        )

        # Score de forme baseline: previous sessions (resting) or previous
        # supine phases (orthostatic), with their final values
        history: list = []
        for date in sorted(set(stored) | set(raw)):
            todo = date in raw and (since is None or date >= since)
            if not todo:
                if date in stored and (kept := _baseline_entry(proto, stored[date])):
                    history.append(kept)
                continue

            change = _reprocess_one(
                proto,
                date,
                repo.load_raw_session(user_id, date, proto),
                stored.get(date),
                raw[date].get("metadata") or {},
                history,
                method=method,
                auto_clean=auto_clean,
                hr_max=hr_max,
            )
            report.sessions.append(change.session)
            source = change.result if change.result is not None else stored.get(date)
            if source is not None and (kept := _baseline_entry(proto, source)):
                history.append(kept)
            if not dry_run and change.session.status in ("changed", "new"):
                save(change.result, date)

    return report


def _baseline_entry(protocol: str, item):
    """Features that feed the score de forme baseline (``None`` if none).

    Resting: the session itself. Orthostatic: its supine phase — from an
    ``OrthostaticResult`` (``phases.supine.features``) or a stored
    ``OrthostaticRecord`` (``supine``).
    """
    if protocol == "resting":
        return item
    if protocol == "orthostatic":
        if hasattr(item, "phases"):
            return item.phases.supine.features
        return getattr(item, "supine", None)
    return None


@dataclass
class _Outcome:
    session: SessionChange
    result: Any = None


def _reprocess_one(
    protocol: str,
    date: str,
    rr: RRSeries,
    stored,
    raw_meta: dict,
    history: list,
    *,
    method: str,
    auto_clean: bool,
    hr_max: float | None,
) -> _Outcome:
    """Analyse and score one session; compare with the stored result."""
    before = _key_values(protocol, stored) if stored is not None else {}
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = analyse_session(
                protocol,
                rr,
                method=method,
                auto_clean=auto_clean,
                hr_max=_hr_max(stored, raw_meta, hr_max)
                if protocol == "vo2max"
                else None,
            )
    except Exception as exc:  # noqa: BLE001 — reported, stored row kept
        return _Outcome(
            SessionChange(protocol, date, "failed", before=before, error=str(exc))
        )

    if hasattr(result, "date"):
        result.date = date
    baseline = Baseline.from_features(history) if protocol == "resting" else None
    result.score = session_score(protocol, result, baseline)
    if protocol == "orthostatic":
        # Score de forme of the supine phase vs the previous supine phases
        supine = result.phases.supine.features
        supine.date = date
        result.readiness_score = orthostatic_readiness_score(
            supine, Baseline.from_features(history)
        )

    after = _key_values(protocol, result)
    # Status from EVERY stored field (e.g. SampEn of each orthostatic phase),
    # not only the key metrics shown in the report
    changed = (
        _changed_fields(
            _stored_fields(protocol, stored), _stored_fields(protocol, result)
        )
        if stored is not None
        else []
    )
    if stored is None:
        status = "new"
    elif changed:
        status = "changed"
    else:
        status = "unchanged"
    return _Outcome(
        SessionChange(
            protocol,
            date,
            status,
            before=before,
            after=after,
            warnings=sorted({str(w.message) for w in caught}),
            changed_fields=changed,
        ),
        result,
    )
