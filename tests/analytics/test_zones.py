"""Unit tests for heart rate training zones anchored on the thresholds."""

from __future__ import annotations

import numpy as np
import pytest

from cardiolab.analytics.zones import five_zones, three_zones, time_in_zones, zone_of


@pytest.mark.unit
class TestThreeZones:
    """``three_zones`` — Seiler's model, read from the thresholds."""

    def test_bounds(self):
        """Zone 1 below HRVT1, zone 2 between, zone 3 above HRVT2."""
        zones = three_zones(150, 170, 190)
        assert [(z.zone, z.hr_low, z.hr_high) for z in zones] == [
            (1, 0.0, 150),
            (2, 150, 170),
            (3, 170, 190),
        ]

    def test_order_checked(self):
        """Thresholds must be ordered below HRmax."""
        with pytest.raises(ValueError, match="HRVT1 < HRVT2 < HRmax"):
            three_zones(170, 150, 190)
        with pytest.raises(ValueError):
            three_zones(150, 170, 165)


@pytest.mark.unit
class TestFiveZones:
    """``five_zones`` — I-scale proportions anchored on the thresholds."""

    def test_reproduces_i_scale_at_reference_thresholds(self):
        """HRVT1 at 82 % and HRVT2 at 87 % of HRmax give the I-scale percentages."""
        hr_max = 200.0
        zones = five_zones(0.82 * hr_max, 0.87 * hr_max, hr_max)
        bounds = [(z.hr_low / hr_max, z.hr_high / hr_max) for z in zones]
        expected = [(0.55, 0.72), (0.72, 0.82), (0.82, 0.87), (0.87, 0.92), (0.92, 1.0)]
        for got, exp in zip(bounds, expected, strict=True):
            assert got == pytest.approx(exp)

    def test_thresholds_are_zone_boundaries(self):
        """HRVT1 tops zone 2, HRVT2 tops zone 3, HRmax tops zone 5."""
        zones = five_zones(145, 168, 188)
        assert zones[1].hr_high == 145
        assert zones[2].hr_low == 145
        assert zones[2].hr_high == 168
        assert zones[3].hr_low == 168
        assert zones[4].hr_high == 188

    def test_contiguous_and_named(self):
        """Each zone starts where the previous one ends."""
        zones = five_zones(145, 168, 188)
        for a, b in zip(zones, zones[1:], strict=False):
            assert a.hr_high == b.hr_low
        assert [z.name for z in zones] == [
            "recovery",
            "endurance",
            "tempo",
            "threshold",
            "vo2max",
        ]

    def test_order_checked(self):
        """HRmax below HRVT2 is refused."""
        with pytest.raises(ValueError):
            five_zones(145, 168, 160)


@pytest.mark.unit
class TestZoneOf:
    """``zone_of`` — zone of a heart rate."""

    def test_zone_lookup(self):
        """Lower bound included, upper bound excluded."""
        zones = five_zones(145, 168, 188)
        assert zone_of(150, zones) == 3
        assert zone_of(145, zones) == 3
        assert zone_of(144.9, zones) == 2
        assert zone_of(170, zones) == 4

    def test_hr_max_in_last_zone(self):
        """HRmax itself belongs to zone 5."""
        assert zone_of(188, five_zones(145, 168, 188)) == 5

    def test_outside(self):
        """Below zone 1 or above HRmax: no zone."""
        zones = five_zones(145, 168, 188)
        assert zone_of(60, zones) is None
        assert zone_of(200, zones) is None


@pytest.mark.unit
class TestTimeInZones:
    """``time_in_zones`` — seconds per zone from a 1-Hz heart rate."""

    def test_counts_per_zone(self):
        """Each sample counted once, in its zone."""
        zones = five_zones(145, 168, 188)
        hr = [100] * 10 + [140] * 20 + [150] * 5 + [170] * 3 + [180] * 2
        assert time_in_zones(hr, zones) == {1: 10.0, 2: 20.0, 3: 5.0, 4: 3.0, 5: 2.0}

    def test_outside_and_missing(self):
        """Below zone 1 → zone 1, above HRmax → zone 5, nan ignored."""
        zones = five_zones(145, 168, 188)
        out = time_in_zones([60, 200, np.nan, 145], zones, sample_sec=2.0)
        assert out == {1: 2.0, 2: 0.0, 3: 2.0, 4: 0.0, 5: 2.0}

    def test_three_zones(self):
        """Works with the three-zone model."""
        out = time_in_zones([120, 150, 175], three_zones(145, 168, 188))
        assert out == {1: 1.0, 2: 1.0, 3: 1.0}

    def test_errors(self):
        """Empty zones or non-positive sample interval."""
        with pytest.raises(ValueError):
            time_in_zones([120], [])
        with pytest.raises(ValueError):
            time_in_zones([120], three_zones(145, 168, 188), sample_sec=0)
