"""Signal quality index of an RR recording.

Every session gets a :class:`SignalQuality`: share of beats flagged as
artefacts, whether they were corrected before analysis, number of beats,
effective duration and a grade — ``good``, ``acceptable`` or ``poor``.

A score only means something if the signal behind it is sound: a session with
8 % of corrected beats must not weigh like a clean one in the baseline
(:class:`~cardiolab.analytics.baseline.Baseline` leaves ``poor`` sessions out
by default).

Grading:

* artefacts **corrected** (``auto_clean=True`` or
  :meth:`RRSeries.correct_artifacts`): ``good`` below 2 %, ``acceptable``
  below 5 %, ``poor`` from 5 % (Lipponen & Tarvainen 2019 — above 5 %, the
  recording should be measured again);
* artefacts detected but **not corrected**: ``poor`` as soon as one is found —
  a single missed beat left in a 5-minute recording can double RMSSD
  (sample 2026-04-24: 78.5 ms raw, 41.1 ms corrected).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from cardiolab.signals.artifacts import WARNING_THRESHOLD_PCT, detect_artifacts

GOOD_MAX_PCT = 2.0
"""Share of artefacts (%) below which a corrected recording is ``good``."""

ACCEPTABLE_MAX_PCT = WARNING_THRESHOLD_PCT
"""Share of artefacts (%) below which a corrected recording is ``acceptable``."""

GRADES: tuple[str, ...] = ("good", "acceptable", "poor")
"""Quality grades, best first."""


def grade_quality(
    artifact_pct: float,
    corrected: bool,
    *,
    good_max: float = GOOD_MAX_PCT,
    acceptable_max: float = ACCEPTABLE_MAX_PCT,
) -> str:
    """Grade a recording from its share of artefacts.

    Args:
        artifact_pct: Share of beats flagged as artefacts, in %.
        corrected: ``True`` if the artefacts were corrected before analysis.
        good_max: Threshold (%) below which a corrected recording is ``good``.
        acceptable_max: Threshold (%) below which it is ``acceptable``.

    Returns:
        ``"good"``, ``"acceptable"`` or ``"poor"``. Uncorrected artefacts
        always give ``"poor"``.

    """
    if not corrected and artifact_pct > 0:
        return "poor"
    if artifact_pct < good_max:
        return "good"
    if artifact_pct < acceptable_max:
        return "acceptable"
    return "poor"


@dataclass(frozen=True)
class SignalQuality:
    """Quality index of the RR signal behind a session.

    Attributes:
        grade: ``"good"``, ``"acceptable"`` or ``"poor"`` (see
            :func:`grade_quality`).
        artifact_pct: Share of beats flagged as artefacts, in %.
        corrected: ``True`` if the artefacts were corrected before analysis.
        n_beats: Number of RR intervals analysed.
        effective_duration: Duration of the analysed signal, in seconds.

    """

    grade: str
    artifact_pct: float
    corrected: bool
    n_beats: int
    effective_duration: float

    @property
    def is_poor(self) -> bool:
        """``True`` for a ``poor`` recording."""
        return self.grade == "poor"

    @classmethod
    def from_counts(
        cls,
        n_beats: int,
        n_artifacts: int,
        corrected: bool,
        effective_duration: float,
        *,
        good_max: float = GOOD_MAX_PCT,
        acceptable_max: float = ACCEPTABLE_MAX_PCT,
    ) -> SignalQuality:
        """Build the quality index from artefact counts.

        Args:
            n_beats: Number of RR intervals analysed.
            n_artifacts: Number of beats flagged as artefacts.
            corrected: ``True`` if the artefacts were corrected.
            effective_duration: Duration of the analysed signal (s).
            good_max: See :func:`grade_quality`.
            acceptable_max: See :func:`grade_quality`.

        Returns:
            The quality index.

        """
        pct = 100.0 * n_artifacts / n_beats if n_beats else 0.0
        return cls(
            grade=grade_quality(
                pct, corrected, good_max=good_max, acceptable_max=acceptable_max
            ),
            artifact_pct=round(pct, 2),
            corrected=corrected,
            n_beats=int(n_beats),
            effective_duration=round(float(effective_duration), 1),
        )

    @classmethod
    def from_dict(cls, data: dict | None) -> SignalQuality | None:
        """Rebuild a quality index stored with :meth:`to_dict` (``None`` stays ``None``)."""
        if not data:
            return None
        return cls(
            grade=data["grade"],
            artifact_pct=float(data["artifact_pct"]),
            corrected=bool(data["corrected"]),
            n_beats=int(data["n_beats"]),
            effective_duration=float(data["effective_duration"]),
        )

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict (stored in the ``quality`` JSONB column)."""
        return asdict(self)


def quality_columns(quality: SignalQuality | None, prefix: str = "quality_") -> dict:
    """Flatten a quality index into scalar columns for tables and CSV exports.

    Args:
        quality: Quality index, or ``None`` when unknown (sessions stored
            before v0.4.0).
        prefix: Column name prefix.

    Returns:
        ``{prefix + field: value}`` for every :class:`SignalQuality` field;
        values are ``None`` when ``quality`` is ``None``.

    """
    fields = ("grade", "artifact_pct", "corrected", "n_beats", "effective_duration")
    data = quality.to_dict() if quality is not None else dict.fromkeys(fields)
    return {f"{prefix}{name}": data[name] for name in fields}


def artifact_indices(intervals) -> list[int]:
    """Return the indices of the beats flagged by :func:`~cardiolab.signals.artifacts.detect_artifacts`."""
    found = detect_artifacts(np.asarray(intervals, dtype=float))
    return sorted({i for idx in found.values() for i in idx})


def signal_quality(
    rr,
    *,
    good_max: float = GOOD_MAX_PCT,
    acceptable_max: float = ACCEPTABLE_MAX_PCT,
) -> SignalQuality:
    """Assess the quality of an RR series.

    If the series was corrected (:meth:`RRSeries.correct_artifacts` stores its
    report in ``metadata["artifact_correction"]``), the share of corrected
    beats is used. Otherwise artefacts are detected (Lipponen & Tarvainen
    2019, without correcting them) and any artefact found makes the recording
    ``poor``.

    Args:
        rr: An ``RRSeries``.
        good_max: See :func:`grade_quality`.
        acceptable_max: See :func:`grade_quality`.

    Returns:
        The quality index of the series.

    """
    report = rr.metadata.get("artifact_correction") if rr.metadata else None
    if report:
        # Share of the input beats; the corrected series may be one beat
        # longer / shorter per missed / extra beat
        pct = (
            100.0 * report["n_corrected"] / report["n_input"]
            if report["n_input"]
            else 0.0
        )
        corrected = True
    else:
        n = len(rr.intervals)
        pct = 100.0 * len(artifact_indices(rr.intervals)) / n if n else 0.0
        corrected = False
    return SignalQuality(
        grade=grade_quality(
            pct, corrected, good_max=good_max, acceptable_max=acceptable_max
        ),
        artifact_pct=round(pct, 2),
        corrected=corrected,
        n_beats=len(rr.intervals),
        effective_duration=round(float(rr.duration), 1),
    )
