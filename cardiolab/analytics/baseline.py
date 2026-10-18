"""HRV feature history management and baseline statistics."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from cardiolab.protocols.resting import HRVFeatures


@dataclass
class Baseline:
    """Rolling history of HRV sessions used as a personal reference.

    A baseline aggregates ``HRVFeatures`` records over time and exposes
    statistical summaries (mean, median, rolling windows) that contextualise
    each new measurement. It is compatible with both live pipeline data and
    records loaded from a database.

    Sessions whose signal quality is ``poor`` (more than 5 % of corrected
    beats, or uncorrected artefacts — see
    :func:`~cardiolab.signals.quality.signal_quality`) are left out of every
    statistic by default: a faulty recording must not shift the personal
    reference. Sessions without a quality index (stored before v0.4.0) are
    kept.

    Attributes:
        history: Chronologically ordered list of ``HRVFeatures`` sessions.
        window: Number of most-recent sessions considered for rolling
            statistics. Defaults to 7 (one week of daily measurements).
        include_poor: If ``True``, ``poor`` sessions are used like the others.
            Defaults to ``False`` (added in v0.4.0).

    """

    history: list[HRVFeatures] = field(default_factory=list)
    window: int = 7
    include_poor: bool = False

    # ======================
    # FACTORIES
    # ======================

    @classmethod
    def from_features(
        cls,
        features_list: list[HRVFeatures],
        include_poor: bool = False,
    ) -> Baseline:
        """Build a Baseline from an existing list of HRVFeatures.

        The list is sorted chronologically by ``date`` before being stored.
        Sessions without a date are sorted to the front.

        Args:
            features_list: List of ``HRVFeatures`` instances, in any order.
            include_poor: Use ``poor``-quality sessions in the statistics.
                Defaults to ``False``.

        Returns:
            A new ``Baseline`` with history sorted by ascending date.

        """
        return cls(
            history=sorted(features_list, key=lambda x: x.date or ""),
            include_poor=include_poor,
        )

    @classmethod
    def from_resting_results(cls, results, include_poor: bool = False) -> Baseline:
        """Build a Baseline from a collection of resting protocol results.

        Convenience factory that delegates to ``from_features`` when the
        input is already a sequence of ``HRVFeatures`` objects.

        Args:
            results: Iterable of ``HRVFeatures`` instances produced by the
                resting protocol or loaded from storage.
            include_poor: Use ``poor``-quality sessions in the statistics.
                Defaults to ``False``.

        Returns:
            A new ``Baseline`` with history sorted by ascending date.

        """
        return cls.from_features(list(results), include_poor=include_poor)

    # ======================
    # SESSIONS USED
    # ======================

    @property
    def sessions(self) -> list[HRVFeatures]:
        """Sessions used by the statistics — ``history`` without ``poor`` ones.

        Returns:
            ``history`` minus the sessions graded ``poor``, unless
            ``include_poor`` is ``True``. Sessions with no quality index are
            kept.

        """
        if self.include_poor:
            return self.history
        return [s for s in self.history if not (s.quality and s.quality.is_poor)]

    @property
    def excluded(self) -> list[HRVFeatures]:
        """Sessions left out of the statistics because their quality is ``poor``."""
        if self.include_poor:
            return []
        return [s for s in self.history if s.quality and s.quality.is_poor]

    # ======================
    # INTERNAL
    # ======================

    def _get_recent(self) -> list[HRVFeatures]:
        """Return the most recent usable sessions within the rolling window.

        Returns:
            The last ``window`` sessions of :attr:`sessions`, or all of them
            if there are fewer than ``window``.

        """
        return self.sessions[-self.window :]

    # ======================
    # EXPORT
    # ======================

    def to_dataframe(self):
        """Return a pandas DataFrame of the full session history.

        Each row corresponds to one ``HRVFeatures`` session in chronological
        order (oldest first). Returns an empty ``DataFrame`` when the history
        is empty.

        Returns:
            A ``pandas.DataFrame`` with one row per session and one column
            per HRV feature field.

        Raises:
            ImportError: If ``pandas`` is not installed. Install with
                ``pip install cardiolab[analysis]``.

        """
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "pandas is required for to_dataframe(). "
                "Install it with: pip install cardiolab[analysis]"
            ) from exc

        if not self.history:
            return pd.DataFrame()

        return pd.DataFrame([s.to_dict() for s in self.history])

    # ======================
    # BASELINE STATISTICS
    # ======================

    def mean_rmssd(self) -> float | None:
        """Compute the mean RMSSD over the rolling window.

        Returns:
            Mean RMSSD in milliseconds across the most recent ``window``
            sessions, or ``None`` if the history is empty.

        """
        data = self._get_recent()

        if not data:
            return None

        values = [r.rmssd for r in data]
        return float(np.mean(values))

    def median_rmssd(self) -> float | None:
        """Compute the median RMSSD over the rolling window.

        The median is more robust than the mean to occasional outlier sessions
        (illness, travel, equipment issues).

        Returns:
            Median RMSSD in milliseconds across the most recent ``window``
            sessions, or ``None`` if the history is empty.

        """
        data = self._get_recent()

        if not data:
            return None

        values = [r.rmssd for r in data]
        return float(np.median(values))

    def mean_hr(self) -> float | None:
        """Compute the mean heart rate over the rolling window.

        Returns:
            Mean heart rate in bpm across the most recent ``window``
            sessions, or ``None`` if the history is empty.

        """
        data = self._get_recent()

        if not data:
            return None

        values = [r.mean_hr for r in data]
        return float(np.mean(values))

    def median_sd1(self) -> float | None:
        """Compute the median SD1 (Poincaré short-term variability) over the window.

        SD1 is mathematically equivalent to RMSSD / √2. Sessions where SD1
        was not computed (stored as ``0.0``) are excluded from the median to
        avoid biasing the baseline downward.

        Returns:
            Median SD1 in milliseconds across the most recent ``window``
            sessions that have a non-zero SD1, or ``None`` if the history
            is empty or all values are zero.

        """
        data = self._get_recent()

        if not data:
            return None

        values = [r.sd1 for r in data if r.sd1 > 0.0]

        if not values:
            return None

        return float(np.median(values))

    def median_dfa_alpha1(self) -> float | None:
        """Compute the median DFA α1 exponent over the rolling window.

        Sessions where DFA α1 was not computed (stored as ``0.0`` or
        ``nan``) are excluded from the median.

        Returns:
            Median DFA α1 across the most recent ``window`` sessions that
            have a valid (non-zero, non-nan) value, or ``None`` if no valid
            values exist.

        """
        data = self._get_recent()

        if not data:
            return None

        values = [
            r.dfa_alpha1
            for r in data
            if r.dfa_alpha1 > 0.0 and not np.isnan(r.dfa_alpha1)
        ]

        if not values:
            return None

        return float(np.median(values))

    # ======================
    # ROLLING STATISTICS
    # ======================

    def rolling_rmssd(self) -> list[float]:
        """Compute the rolling mean of RMSSD over the full history.

        Applies a sliding window of size ``self.window`` across all sessions
        in chronological order. The first value corresponds to the mean of
        the first ``window`` sessions.

        Returns:
            List of rolling mean values, one per session starting from
            position ``window - 1``. Returns an empty list when the history
            contains fewer sessions than ``window``.

        """
        values = [r.rmssd for r in self.sessions]

        if len(values) < self.window:
            return []

        return [
            float(np.mean(values[i - self.window + 1 : i + 1]))
            for i in range(self.window - 1, len(values))
        ]

    def rolling_rmssd_median(self) -> list[float]:
        """Compute the rolling median of RMSSD over the full history.

        Applies a sliding median window of size ``self.window`` across all
        sessions. More robust than ``rolling_rmssd`` when the history contains
        occasional outlier sessions.

        Returns:
            List of rolling median values, one per session starting from
            position ``window - 1``. Returns an empty list when the history
            contains fewer sessions than ``window``.

        """
        values = [r.rmssd for r in self.sessions]

        if len(values) < self.window:
            return []

        return [
            float(np.median(values[i - self.window + 1 : i + 1]))
            for i in range(self.window - 1, len(values))
        ]
