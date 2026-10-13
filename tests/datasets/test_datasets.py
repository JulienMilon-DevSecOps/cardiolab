"""Tests for the sample datasets shipped with cardiolab (cardiolab.datasets)."""

from __future__ import annotations

from importlib.resources import files

import pytest

from cardiolab.datasets import list_samples, load_sample
from cardiolab.protocols.orthostatic import OrthostaticResult, orthostatic_hrv
from cardiolab.protocols.resting import resting_hrv
from cardiolab.signals.rr import RRSeries


@pytest.mark.unit
class TestListSamples:
    """list_samples() exposes the manifest."""

    def test_all_protocols(self):
        """6 resting + 1 orthostatic recordings."""
        samples = list_samples()
        assert len(samples) == 7
        assert {s["protocol"] for s in samples} == {"resting", "orthostatic"}

    def test_filter_by_protocol_sorted_by_date(self):
        """Filtering keeps one protocol, in chronological order."""
        resting = list_samples("resting")
        assert len(resting) == 6
        dates = [s["date"] for s in resting]
        assert dates == sorted(dates)

    def test_unknown_protocol_raises(self):
        """Unknown protocol → ValueError listing the available ones."""
        with pytest.raises(ValueError, match="Available: orthostatic, resting"):
            list_samples("hrr")

    def test_returns_copies(self):
        """Mutating a returned entry does not alter the manifest."""
        list_samples("resting")[0]["date"] = "mutated"
        assert list_samples("resting")[0]["date"] != "mutated"

    def test_every_manifest_file_is_packaged(self):
        """Each manifest entry points to a file shipped with the package."""
        root = files("cardiolab.datasets")
        for sample in list_samples():
            assert root.joinpath(sample["file"]).is_file(), sample["file"]


@pytest.mark.unit
class TestLoadSample:
    """load_sample() returns raw RRSeries matching the manifest."""

    @pytest.mark.parametrize(
        ("protocol", "index"),
        [("resting", i) for i in range(6)] + [("orthostatic", 0)],
    )
    def test_matches_manifest(self, protocol, index):
        """Beat count and duration agree with the manifest entry."""
        rr = load_sample(protocol, index)
        entry = list_samples(protocol)[index]
        assert isinstance(rr, RRSeries)
        assert len(rr) == entry["beats"]
        assert rr.intervals.sum() / 1000 == pytest.approx(
            entry["duration_sec"], abs=0.1
        )

    def test_metadata(self):
        """Metadata carries the manifest entry, source and licence."""
        rr = load_sample("resting", 0)
        assert rr.metadata["id"] == "resting-2026-04-24"
        assert rr.metadata["date"] == "2026-04-24"
        assert rr.metadata["source"] == "cardiolab sample dataset"
        assert rr.metadata["license"] == "CC-BY-4.0"

    def test_negative_index(self):
        """index=-1 → most recent recording."""
        assert load_sample("resting", -1).metadata["date"] == "2026-04-30"

    def test_index_out_of_range(self):
        """Out-of-range index → explicit IndexError."""
        with pytest.raises(IndexError, match="out of range"):
            load_sample("orthostatic", 1)

    def test_raw_data_keeps_artefacts(self):
        """Samples are raw: the 1 718 ms artefact of 2026-04-24 is still there."""
        assert load_sample("resting", 0).intervals.max() == 1718.0


@pytest.mark.unit
class TestSamplesRunThroughProtocols:
    """The samples are usable as-is by the protocols."""

    def test_resting_protocol(self):
        """resting_hrv on a sample gives a physiological RMSSD."""
        features = resting_hrv(load_sample("resting", 0), auto_clean=True)
        assert 10.0 < features.rmssd < 200.0

    def test_orthostatic_protocol(self):
        """orthostatic_hrv detects the phases of the orthostatic sample."""
        result = orthostatic_hrv(load_sample("orthostatic"), auto_clean=True)
        assert isinstance(result, OrthostaticResult)
