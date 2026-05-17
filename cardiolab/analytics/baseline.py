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

    Attributes:
        history: Chronologically ordered list of ``HRVFeatures`` sessions.
        window: Number of most-recent sessions considered for rolling
            statistics. Defaults to 7 (one week of daily measurements).

    """

    history: list[HRVFeatures] = field(default_factory=list)
    window: int = 7

    # ======================
    # FACTORIES
    # ======================

    @classmethod
    def from_features(cls, features_list: list[HRVFeatures]) -> Baseline:
        """Build a Baseline from an existing list of HRVFeatures.

        The list is sorted chronologically by ``date`` before being stored.
        Sessions without a date are sorted to the front.

        Args:
            features_list: List of ``HRVFeatures`` instances, in any order.

        Returns:
            A new ``Baseline`` with history sorted by ascending date.

        """
        return cls(history=sorted(features_list, key=lambda x: x.date or ""))

    @classmethod
    def from_resting_results(cls, results) -> Baseline:
        """Build a Baseline from a collection of resting protocol results.

        Convenience factory that delegates to ``from_features`` when the
        input is already a sequence of ``HRVFeatures`` objects.

        Args:
            results: Iterable of ``HRVFeatures`` instances produced by the
                resting protocol or loaded from storage.

        Returns:
            A new ``Baseline`` with history sorted by ascending date.

        """
        return cls.from_features(list(results))

    # ======================
    # INTERNAL
    # ======================

    def _get_recent(self) -> list[HRVFeatures]:
        """Return the most recent sessions within the rolling window.

        Returns:
            Slice of ``history`` containing the last ``window`` sessions.
            Returns the full history if its length is less than ``window``.

        """
        return self.history[-self.window :]

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
        values = [r.rmssd for r in self.history]

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
        values = [r.rmssd for r in self.history]

        if len(values) < self.window:
            return []

        return [
            float(np.median(values[i - self.window + 1 : i + 1]))
            for i in range(self.window - 1, len(values))
        ]
