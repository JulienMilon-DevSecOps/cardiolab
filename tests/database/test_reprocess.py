"""Tests for history reprocessing (issue v0.4.0-04) — cardiolab.database.reprocess."""

from __future__ import annotations

import copy
import math
import os
import warnings
from types import SimpleNamespace

import numpy as np
import pytest

from cardiolab.analytics.baseline import Baseline
from cardiolab.analytics.scoring import readiness_score_multi, session_score
from cardiolab.database.reprocess import (
    ReprocessReport,
    SessionChange,
    analyse_session,
    reprocess_sessions,
)
from cardiolab.datasets import load_sample
from cardiolab.protocols.resting import HRVFeatures, resting_hrv
from cardiolab.signals.rr import RRSeries

# ======================
# In-memory repository
# ======================


class FakeRepo:
    """Minimal in-memory stand-in for HRVRepository (raw sessions + results)."""

    def __init__(self):
        """Start empty."""
        self.raw: dict[tuple[str, str], tuple[RRSeries, dict]] = {}
        self.results: dict[str, dict[str, object]] = {}
        self.writes: list[tuple[str, str]] = []

    # raw sessions
    def add_raw(self, protocol, date, rr, metadata=None):
        """Store a raw recording."""
        self.raw[(protocol, date)] = (rr, metadata or {})

    def list_raw_sessions(self, user_id, protocol=None):
        """List raw sessions by ascending date."""
        return [
            {"date": d, "protocol": p, "metadata": m}
            for (p, d), (_, m) in sorted(self.raw.items(), key=lambda kv: kv[0][1])
            if protocol in (None, p)
        ]

    def load_raw_session(self, user_id, date, protocol):
        """Return a copy of a raw recording."""
        return RRSeries(self.raw[(protocol, date)][0].intervals.copy())

    # results
    def _store(self, protocol, date, result):
        self.writes.append((protocol, date))
        self.results.setdefault(protocol, {})[date] = copy.deepcopy(result)

    def _load(self, protocol):
        return [
            copy.deepcopy(r) for _, r in sorted(self.results.get(protocol, {}).items())
        ]

    def save_features(self, f, user_id):
        """Upsert a resting session."""
        self._store("resting", f.date, f)

    def load_features(self, user_id):
        """Return the resting sessions."""
        return self._load("resting")

    def save_orthostatic(self, r, user_id, date):
        """Upsert an orthostatic session."""
        r.date = date
        self._store("orthostatic", date, r)

    def load_orthostatic(self, user_id):
        """Return the orthostatic sessions."""
        return self._load("orthostatic")

    def save_vo2max(self, r, user_id, date):
        """Upsert a VO2max estimation."""
        self._store("vo2max", date, r)

    def load_vo2max(self, user_id):
        """Return the VO2max estimations."""
        return self._load("vo2max")


def _old_resting(rr: RRSeries, date: str) -> HRVFeatures:
    """Build a session as stored before v0.4.0: Welch, no correction, no quality."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f = resting_hrv(rr, method="welch")
    f.date, f.quality, f.score = date, None, 50.0
    return f


def _repo_with_resting(n: int = 4) -> FakeRepo:
    repo = FakeRepo()
    for i in range(n):
        date = f"2099-11-0{i + 1}"
        rr = load_sample("resting", i)
        repo.add_raw("resting", date, rr)
        repo.save_features(_old_resting(rr, date), "u")
    repo.writes.clear()
    return repo


# ======================
# analyse_session
# ======================


@pytest.mark.unit
class TestAnalyseSession:
    """The single analysis pipeline."""

    def test_resting_corrected_lomb(self):
        """Resting: artefacts corrected, Lomb-Scargle by default."""
        f = analyse_session("resting", load_sample("resting", 0))
        assert f.method == "lomb"
        assert f.quality.corrected

    def test_coherence_and_vo2max_corrected(self):
        """Coherence and VO2max get a corrected RR series when auto_clean."""
        rr = load_sample("resting", 0)  # contains a missed beat
        assert analyse_session("coherence", rr).quality.corrected
        assert analyse_session("vo2max", rr).quality.grade == "good"
        assert analyse_session("vo2max", rr, auto_clean=False).quality.grade == "poor"

    def test_vo2max_hr_max(self):
        """hr_max enables the Uth model."""
        r = analyse_session("vo2max", load_sample("resting", 1), hr_max=185.0)
        assert math.isfinite(r.vo2max_uth)

    def test_unknown_protocol(self):
        """Unknown protocol → ValueError."""
        with pytest.raises(ValueError, match="Unknown protocol"):
            analyse_session("yoga", load_sample("resting", 0))


# ======================
# reprocess_sessions
# ======================


@pytest.mark.unit
class TestReprocess:
    """Dry run, writes, idempotency, chronological scores."""

    def test_dry_run_writes_nothing(self):
        """Dry run (default): report computed, nothing written."""
        repo = _repo_with_resting()
        report = reprocess_sessions(repo, "u")
        assert report.dry_run
        assert report.count("changed") == 4
        assert repo.writes == []
        assert repo.results["resting"]["2099-11-01"].method == "welch"

    def test_apply_writes_new_pipeline(self):
        """dry_run=False replaces stored results with the new pipeline."""
        repo = _repo_with_resting()
        report = reprocess_sessions(repo, "u", dry_run=False)
        assert report.written == 4
        stored = repo.results["resting"]["2099-11-01"]
        assert stored.method == "lomb"
        assert stored.quality.corrected

    def test_idempotent(self):
        """A second run finds every session unchanged and writes nothing."""
        repo = _repo_with_resting()
        reprocess_sessions(repo, "u", dry_run=False)
        repo.writes.clear()
        second = reprocess_sessions(repo, "u", dry_run=False)
        assert second.count("unchanged") == 4
        assert repo.writes == []

    def test_scores_chronological(self):
        """Each resting score uses the previous sessions, already reprocessed."""
        repo = _repo_with_resting()
        reprocess_sessions(repo, "u", dry_run=False)
        final = [repo.results["resting"][f"2099-11-0{i}"] for i in range(1, 5)]
        assert final[0].score == 50.0  # no previous session
        expected = readiness_score_multi(final[3], Baseline.from_features(final[:3]))
        assert final[3].score == pytest.approx(expected)

    def test_since(self):
        """since: earlier sessions are not reprocessed but feed the baseline."""
        repo = _repo_with_resting()
        report = reprocess_sessions(repo, "u", since="2099-11-03", dry_run=False)
        assert [s.date for s in report.sessions] == ["2099-11-03", "2099-11-04"]
        assert repo.results["resting"]["2099-11-01"].method == "welch"
        assert repo.results["resting"]["2099-11-03"].score != 50.0

    def test_stored_without_raw_skipped(self):
        """A stored session without raw RR is listed as skipped, untouched."""
        repo = _repo_with_resting(2)
        repo.save_features(
            HRVFeatures(date="2099-10-31", rmssd=45.0, mean_hr=58.0), "u"
        )
        report = reprocess_sessions(repo, "u")
        assert report.skipped == [("resting", "2099-10-31")]

    def test_new_session(self):
        """Raw RR without a stored result → new, written."""
        repo = FakeRepo()
        repo.add_raw("resting", "2099-11-01", load_sample("resting", 1))
        report = reprocess_sessions(repo, "u", dry_run=False)
        assert report.sessions[0].status == "new"
        assert "2099-11-01" in repo.results["resting"]

    def test_failed_session_kept(self):
        """Analysis error → failed; the stored row is not overwritten."""
        repo = FakeRepo()
        flat = RRSeries(np.full(700, 900.0))  # no orthostatic transition
        repo.add_raw("orthostatic", "2099-11-01", flat)
        old_row = SimpleNamespace(date="2099-11-01", quality=None, to_flat_dict=dict)
        repo.results["orthostatic"] = {"2099-11-01": old_row}
        report = reprocess_sessions(repo, "u", protocol="orthostatic", dry_run=False)
        assert report.sessions[0].status == "failed"
        assert repo.writes == []
        assert "failed" in report.summary() or "✗" in report.summary()

    def test_vo2max_keeps_stored_hr_max(self):
        """VO2max: the hr_max of the stored estimation is reused."""
        repo = FakeRepo()
        rr = load_sample("resting", 1)
        repo.add_raw("vo2max", "2099-11-01", rr)
        old = analyse_session("vo2max", rr, hr_max=190.0)
        old.date, old.quality = "2099-11-01", None
        repo.results["vo2max"] = {"2099-11-01": old}
        reprocess_sessions(repo, "u", protocol="vo2max", dry_run=False)
        assert repo.results["vo2max"]["2099-11-01"].hr_max == 190.0

    def test_only_protocols_with_raw_are_queried(self):
        """Protocols without raw sessions are not loaded at all."""
        repo = _repo_with_resting(1)
        reprocess_sessions(repo, "u")  # FakeRepo has no load_coherence: would fail

    def test_unknown_protocol(self):
        """Unknown protocol → ValueError."""
        with pytest.raises(ValueError, match="Unknown protocol"):
            reprocess_sessions(FakeRepo(), "u", protocol="yoga")


# ======================
# Report
# ======================


@pytest.mark.unit
class TestReport:
    """SessionChange / ReprocessReport helpers."""

    def test_deltas_and_rows(self):
        """deltas() lists changed metrics; to_rows() gives the % change."""
        s = SessionChange(
            "resting",
            "2099-11-01",
            "changed",
            before={"rmssd": 78.5, "dfa_alpha1": float("nan")},
            after={"rmssd": 41.1, "dfa_alpha1": float("nan")},
        )
        assert s.deltas() == {"rmssd": (78.5, 41.1)}
        report = ReprocessReport("u", dry_run=True, method="lomb", sessions=[s])
        rmssd = next(r for r in report.to_rows() if r["metric"] == "rmssd")
        assert rmssd["change_pct"] == pytest.approx(-47.64)

    def test_summary(self):
        """summary() has one line per protocol."""
        report = reprocess_sessions(_repo_with_resting(2), "u")
        text = report.summary()
        assert "dry run" in text
        assert "resting" in text and "2 changed" in text


@pytest.mark.unit
def test_session_score_resting_neutral_without_baseline():
    """session_score: 50 for a first resting session."""
    assert session_score("resting", HRVFeatures(rmssd=50.0, mean_hr=60.0)) == 50.0


# ======================
# PostgreSQL
# ======================


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("DB_HOST_TEST"), reason="Requires DB_HOST_TEST")
class TestReprocessIntegration:
    """Full run against the PostgreSQL test database."""

    _USER = "test-integration-reprocess"
    _TABLES = {
        "table_name": "_cardiolab_test_rp_hrv",
        "ortho_table_name": "_cardiolab_test_rp_ortho",
        "raw_sessions_table_name": "_cardiolab_test_rp_raw",
    }

    @pytest.fixture(autouse=True)
    def _setup_teardown(self):
        from tests.database.test_repository import _repo_from_test_env, _test_table_drop

        self._repo = lambda: _repo_from_test_env(**self._TABLES)
        for table in self._TABLES.values():
            _test_table_drop(table)
        with self._repo() as repo:
            repo.create_table()
            repo.create_orthostatic_table()
            repo.create_raw_sessions_table()
            for i in range(3):
                date = f"2099-11-0{i + 1}"
                rr = load_sample("resting", i)
                repo.save_raw_session(rr, self._USER, date, "resting")
                repo.save_features(_old_resting(rr, date), user_id=self._USER)
            repo.save_raw_session(
                load_sample("orthostatic", 0), self._USER, "2099-11-01", "orthostatic"
            )
        yield
        for table in self._TABLES.values():
            _test_table_drop(table)

    def test_dry_run_apply_idempotent(self):
        """Dry run writes nothing; apply writes; a second apply changes nothing."""
        with self._repo() as repo:
            dry = reprocess_sessions(repo, self._USER)
        with self._repo() as repo:
            assert repo.load_features(self._USER)[0].method == "welch"
            assert dry.count("changed") == 3 and dry.count("new") == 1

        with self._repo() as repo:
            applied = reprocess_sessions(repo, self._USER, dry_run=False)
        assert applied.written == 4
        with self._repo() as repo:
            stored = repo.load_features(self._USER)
            ortho = repo.load_orthostatic(self._USER)
        assert {f.method for f in stored} == {"lomb"}
        assert all(f.quality is not None for f in stored)
        assert ortho[0].supine.quality is not None

        with self._repo() as repo:
            again = reprocess_sessions(repo, self._USER, dry_run=False)
        assert again.count("unchanged") == 4
        assert again.written == 0
