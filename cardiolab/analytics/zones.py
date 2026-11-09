"""Heart rate training zones anchored on the athlete's own thresholds.

Two models, both built from the two thresholds (HRVT1, HRVT2 — see
:mod:`cardiolab.protocols.dfa_thresholds`) and the maximal heart rate:

**Three zones** (Seiler) — the physiological model, read directly from the
thresholds:

| Zone | Heart rate      | Intensity                     |
| ---- | --------------- | ----------------------------- |
| 1    | < HRVT1         | Easy — below the first threshold |
| 2    | HRVT1 – HRVT2   | Between the thresholds        |
| 3    | > HRVT2         | Above the second threshold    |

**Five zones** — the scale most athletes know (watches, training plans),
after Olympiatoppen's intensity scale (I-scale 2024, zones I-1 to I-5:
~55–72, 72–82, 82–87, 87–92, 92–100 % of HRmax). Zones 1–2 of the five-zone
model make up zone 1 of the three-zone model, zone 3 lies between the
thresholds, zones 4–5 are above the second threshold. The boundaries are
therefore **anchored on the measured thresholds** rather than on fixed
percentages of HRmax:

| Zone | From                         | To                           |
| ---- | ---------------------------- | ---------------------------- |
| 1    | HRVT1 × 55/82                | HRVT1 × 72/82                |
| 2    | HRVT1 × 72/82                | HRVT1                        |
| 3    | HRVT1                        | HRVT2                        |
| 4    | HRVT2                        | HRVT2 + 5/13 × (HRmax − HRVT2) |
| 5    | HRVT2 + 5/13 × (HRmax − HRVT2) | HRmax                      |

The two inner splits keep the I-scale proportions: zone 2 is 72–82 % and
zone 1 starts at 55 % when HRVT1 sits at 82 % of HRmax; zone 4 covers the
first 5/13 of the span between HRVT2 (87 %) and HRmax (87–92 % of 87–100 %).
Placing HRVT1 at the top of zone 2 and HRVT2 at the top of zone 3 is a
cardiolab correspondence (lactate ~2 and ~4 mmol/L, I-scale zones 2 and 3
reaching ~2.0 and ~3.5 mmol/L) — the I-scale itself is meant to be adapted
to each athlete from tests.

**Without thresholds** (no test yet), :func:`five_zones_from_hr_max` and
:func:`three_zones_from_hr_max` fall back on the fixed I-scale percentages of
HRmax (55 / 72 / 82 / 87 / 92 / 100 %); the three-zone version groups them
like the anchored model (< 82 %, 82–87 %, > 87 %). These zones are generic:
the athlete's thresholds can sit well away from 82 and 87 %.

References:
    Seiler, S. (2010). What is best practice for training intensity and
    duration distribution in endurance athletes? International Journal of
    Sports Physiology and Performance, 5(3), 276–291.

    Olympiatoppen (2024). Olympiatoppen's intensity scale, version 2.

"""

from __future__ import annotations

from dataclasses import dataclass

I_SCALE_ZONE1_LOW = 55.0 / 82.0
"""Bottom of zone 1 as a fraction of HRVT1 (55 % vs 82 % of HRmax)."""

I_SCALE_ZONE2_LOW = 72.0 / 82.0
"""Bottom of zone 2 as a fraction of HRVT1 (72 % vs 82 % of HRmax)."""

I_SCALE_ZONE4_SHARE = 5.0 / 13.0
"""Share of the HRVT2 – HRmax span covered by zone 4 (87–92 % of 87–100 %)."""

I_SCALE_PCT_HR_MAX = (55.0, 72.0, 82.0, 87.0, 92.0, 100.0)
"""Bounds of the five I-scale zones in % of HRmax (Olympiatoppen 2024)."""


@dataclass(frozen=True)
class HeartRateZone:
    """One training zone: number, name and heart rate bounds (bpm)."""

    zone: int
    name: str
    hr_low: float
    hr_high: float

    def contains(self, hr: float) -> bool:
        """Return ``True`` when ``hr`` lies in the zone (lower bound included)."""
        return self.hr_low <= hr < self.hr_high


def three_zones(hr_vt1: float, hr_vt2: float, hr_max: float) -> list[HeartRateZone]:
    """Return the three-zone model (Seiler) from the two thresholds.

    Args:
        hr_vt1: Heart rate at the first threshold (bpm).
        hr_vt2: Heart rate at the second threshold (bpm).
        hr_max: Maximal heart rate (bpm) — top of zone 3.

    Returns:
        Three zones; zone 1 starts at 0 bpm.

    Raises:
        ValueError: Unless ``0 < hr_vt1 < hr_vt2 < hr_max``.

    """
    _check(hr_vt1, hr_vt2, hr_max)
    return [
        HeartRateZone(1, "below_vt1", 0.0, hr_vt1),
        HeartRateZone(2, "between_thresholds", hr_vt1, hr_vt2),
        HeartRateZone(3, "above_vt2", hr_vt2, hr_max),
    ]


def five_zones(hr_vt1: float, hr_vt2: float, hr_max: float) -> list[HeartRateZone]:
    """Return the five-zone model anchored on the thresholds (see module docstring).

    Args:
        hr_vt1: Heart rate at the first threshold (bpm) — top of zone 2.
        hr_vt2: Heart rate at the second threshold (bpm) — top of zone 3.
        hr_max: Maximal heart rate (bpm) — top of zone 5.

    Returns:
        Five contiguous zones, from zone 1 (recovery) to zone 5 (maximal).

    Raises:
        ValueError: Unless ``0 < hr_vt1 < hr_vt2 < hr_max``.

    """
    _check(hr_vt1, hr_vt2, hr_max)
    z1_low = hr_vt1 * I_SCALE_ZONE1_LOW
    z2_low = hr_vt1 * I_SCALE_ZONE2_LOW
    z5_low = hr_vt2 + I_SCALE_ZONE4_SHARE * (hr_max - hr_vt2)
    return [
        HeartRateZone(1, "recovery", z1_low, z2_low),
        HeartRateZone(2, "endurance", z2_low, hr_vt1),
        HeartRateZone(3, "tempo", hr_vt1, hr_vt2),
        HeartRateZone(4, "threshold", hr_vt2, z5_low),
        HeartRateZone(5, "vo2max", z5_low, hr_max),
    ]


def five_zones_from_hr_max(hr_max: float) -> list[HeartRateZone]:
    """Return the five zones as fixed % of HRmax, for an athlete without thresholds.

    Args:
        hr_max: Maximal heart rate (bpm) — measured, observed or estimated.

    Returns:
        Five zones at 55–72, 72–82, 82–87, 87–92 and 92–100 % of ``hr_max``.

    Raises:
        ValueError: If ``hr_max`` is not positive.

    """
    _check_hr_max(hr_max)
    b = [hr_max * pct / 100.0 for pct in I_SCALE_PCT_HR_MAX]
    names = ("recovery", "endurance", "tempo", "threshold", "vo2max")
    return [HeartRateZone(i + 1, names[i], b[i], b[i + 1]) for i in range(5)]


def three_zones_from_hr_max(hr_max: float) -> list[HeartRateZone]:
    """Return the three zones as fixed % of HRmax (< 82, 82–87, > 87 %).

    Args:
        hr_max: Maximal heart rate (bpm).

    Returns:
        Three zones; zone 1 starts at 0 bpm.

    Raises:
        ValueError: If ``hr_max`` is not positive.

    """
    _check_hr_max(hr_max)
    return three_zones(
        hr_max * I_SCALE_PCT_HR_MAX[2] / 100.0,
        hr_max * I_SCALE_PCT_HR_MAX[3] / 100.0,
        hr_max,
    )


def zone_of(hr: float, zones: list[HeartRateZone]) -> int | None:
    """Return the zone number of ``hr``, or ``None`` outside the zones.

    A heart rate equal to the top of the last zone (HRmax) belongs to it.
    """
    for z in zones:
        if z.contains(hr):
            return z.zone
    if zones and hr == zones[-1].hr_high:
        return zones[-1].zone
    return None


def time_in_zones(
    heart_rate, zones: list[HeartRateZone], sample_sec: float = 1.0
) -> dict[int, float]:
    """Return the time spent in each zone (s) from a regularly sampled heart rate.

    Samples below the first zone count in zone 1, above the last one in the
    last zone (sprints above HRmax, easy minutes below zone 1); missing samples
    (``nan``) are ignored.

    Args:
        heart_rate: Heart rate samples (bpm), e.g. ``FitRecords.heart_rate``.
        zones: Output of :func:`five_zones` or :func:`three_zones`.
        sample_sec: Interval between two samples (s). Defaults to 1 s (FIT
            records).

    Returns:
        ``{zone number: seconds}`` for every zone, 0 when never reached.

    Raises:
        ValueError: If ``zones`` is empty or ``sample_sec`` is not positive.

    """
    import numpy as np

    if not zones:
        raise ValueError("zones must not be empty")
    if sample_sec <= 0:
        raise ValueError("sample_sec must be positive")
    hr = np.asarray(heart_rate, dtype=float)
    hr = hr[np.isfinite(hr)]
    # Upper bounds of zones 1 … n−1: a sample goes to the first zone whose top it is below
    bounds = np.array([z.hr_high for z in zones[:-1]])
    index = np.searchsorted(bounds, hr, side="right")
    counts = np.bincount(index, minlength=len(zones))
    return {z.zone: float(counts[i] * sample_sec) for i, z in enumerate(zones)}


def _check_hr_max(hr_max: float) -> None:
    """Raise ``ValueError`` unless ``hr_max`` is positive."""
    if not hr_max > 0:
        raise ValueError(f"HRmax must be positive, got {hr_max}")


def _check(hr_vt1: float, hr_vt2: float, hr_max: float) -> None:
    """Raise ``ValueError`` unless the three heart rates are ordered and positive."""
    if not 0 < hr_vt1 < hr_vt2 < hr_max:
        raise ValueError(
            "Expected 0 < HRVT1 < HRVT2 < HRmax, got "
            f"{hr_vt1:.0f} / {hr_vt2:.0f} / {hr_max:.0f} bpm"
        )
