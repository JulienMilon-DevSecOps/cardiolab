# DFA α1 Thresholds Protocol

## Physiological principle

DFA α1 measures how successive heartbeats are correlated over short scales (4–16
beats, see [`features/nonlinear.md`](../features/nonlinear.md)). During exercise it falls
as intensity rises, because the sympathetic drive takes over from the vagal control of
the heart:

| α1 | Beat pattern | Intensity |
|----|--------------|-----------|
| ≈ 1.0 | Correlated (fractal) | Easy, well below the first threshold |
| **0.75** | — | **First ventilatory threshold (VT1, aerobic threshold)** |
| **0.5** | Random | **Second ventilatory threshold (VT2, anaerobic threshold)** |
| < 0.5 | Anti-correlated | Severe intensity |

On an incremental test, the heart rate at which α1 crosses 0.75 (HRVT1) and 0.5
(HRVT2) estimates the two thresholds without a gas analyser or lactate (Rogers et al.
2021a, 2021b).

## How to perform the protocol

### Equipment

Set-ups in detail: [`sensors/indoor_cycling.md`](../sensors/indoor_cycling.md) (indoor
trainer) and [`sensors/garmin.md`](../sensors/garmin.md) (watch).

- A **chest strap** recording beat intervals (Polar H10 or similar). Optical sensors
  (watch, armband) do not give beat-accurate intervals during exercise: do not use them.
- Optional: a power meter (cycling) or a speed source (treadmill, GPS track) to get the
  power or speed at each threshold.
- On an indoor trainer driven by an app (MyWhoosh, Zwift…), the app does not record the
  beat intervals: record the test on the watch with the chest strap and the trainer as power
  sensor — set-up B of [`sensors/indoor_cycling.md`](../sensors/indoor_cycling.md).

### Procedure

1. **Warm-up** 10 minutes at a very easy pace (α1 must start above 1.0).
2. **Incremental part** up to exhaustion, without stopping between steps:
   - cycling: a ramp of about +20 to +25 W per minute, or 1–3 minute steps;
   - running: +0.5 km/h per minute on a treadmill, or 2–3 minute steps on a track.
   The incremental part should last at least 10–12 minutes: each α1 value uses 2 minutes
   of beats.
3. **Stop** at exhaustion; keep recording a few minutes of recovery if you wish — it is
   ignored by the analysis.
4. Same sport, same conditions for every test you want to compare.

This is a maximal test: see the safety note in [Limitations](#limitations-and-precautions).

### Recording

```python
from cardiolab import RRSeries, dfa_thresholds
from cardiolab.sensors_tools import parse_rr_file

data = parse_rr_file("2026-11-05 ramp.txt")
result = dfa_thresholds(RRSeries(data["rr_intervals"]))

result.vt1.status   # 'detected', 'not_reached' or 'unreliable'
result.vt1.hr       # heart rate at HRVT1 (bpm)
result.vt2.hr       # heart rate at HRVT2 (bpm), nan if not detected
```

With power (or speed) sampled over the test — time in seconds from the first beat:

```python
result = dfa_thresholds(rr, intensity=(time_sec, power_w), intensity_unit="W")
result.vt1.intensity   # power at HRVT1
```

## Method

1. Artefacts are corrected first (`auto_clean=True`): missed beats bias α1 (Rogers et al.
   2021c).
2. **Time-varying α1** — `dfa_alpha1_series()`: α1 over a 2-minute window centred on each
   time point, every 5 s (Rogers et al. 2021a), with the mean heart rate of each window.
3. Only the part of the test **up to the peak heart rate** is kept: α1 rises again
   during recovery.
4. For each threshold, a **linear regression of α1 against heart rate** over the decline
   gives the heart rate at the threshold value:
   - HRVT1: windows where α1 lies between 1.0 and 0.5 (as published);
   - HRVT2: windows where α1 lies between 0.75 and 0.25 (same ±0.25 band — cardiolab
     choice).
5. A regression of α1 against time gives the moment of the threshold; the intensity is
   read at that moment.

## Computed metrics

| Field | Description |
|-------|-------------|
| `vt1`, `vt2` | `ThresholdEstimate`: `status`, `hr` (bpm), `time_sec`, `intensity`, `r_squared`, `n_windows` |
| `times`, `alpha1`, `hr` | α1 and heart rate of every window — for charts |
| `intensity`, `intensity_unit` | Window mean intensity, when provided |
| `hr_peak` | Highest window heart rate — end of the analysed part |
| `quality` | Signal quality (share of corrected beats) |

### Threshold status

| `status` | Meaning |
|----------|---------|
| `detected` | Threshold found within the heart rates of the test |
| `not_reached` | α1 never fell below the value: the test did not go hard enough (common for HRVT2 if stopped early) |
| `unreliable` | Less than 60 s of windows around the value, α1 not decreasing with heart rate, or a crossing outside the observed heart rates — **never extrapolated** |

## Interpreting results

- **HRVT1** is the top of the easy intensity: endurance sessions stay below it.
- **HRVT2** is the top of the « threshold » intensity: above it, effort is sustainable
  only for a few minutes.
- The thresholds give the athlete's **training zones** — see below.
- To follow progress, repeat the test in the same conditions and compare the **power or
  speed** at each threshold: the threshold heart rate changes little with training.

## Training zones

`result.zones()` returns heart rate zones anchored on the two thresholds and on the
maximal heart rate — by default `hr_max_observed`, the highest heart rate held for 5 s
during the test (the test goes to exhaustion); pass `hr_max=` to use another value.

```python
for z in result.zones():            # five zones (default)
    print(z.zone, z.name, round(z.hr_low), round(z.hr_high))
result.zones(model=3)               # three zones
```

**Three zones** (Seiler 2010) — read directly from the thresholds: zone 1 below HRVT1,
zone 2 between the thresholds, zone 3 above HRVT2. Same boundaries as the RPE guide
(≤ 4 below VT1, 5–6 between, ≥ 7 above), see
[`training_load/atl_ctl_tsb.md`](../training_load/atl_ctl_tsb.md).

**Five zones** — the scale most athletes know, after Olympiatoppen's intensity scale
(I-scale 2024: ~55–72, 72–82, 82–87, 87–92, 92–100 % of HRmax). Instead of fixed
percentages, the boundaries are anchored on the measured thresholds:

| Zone | Name | From | To | RPE (0–10, I-scale) |
|------|------|------|----|---------------------|
| 1 | Recovery | HRVT1 × 55/82 | HRVT1 × 72/82 | 1–2 |
| 2 | Endurance | HRVT1 × 72/82 | **HRVT1** | 2–3 |
| 3 | Tempo | **HRVT1** | **HRVT2** | 4–5 |
| 4 | Threshold | **HRVT2** | HRVT2 + 5/13 × (HRmax − HRVT2) | 6–7 |
| 5 | VO2max | HRVT2 + 5/13 × (HRmax − HRVT2) | HRmax | 8–10 |

- Zones 1–2 make up zone 1 of the three-zone model, zone 3 lies between the thresholds,
  zones 4–5 are above the second threshold.
- The inner splits keep the I-scale proportions: with HRVT1 at 82 % and HRVT2 at 87 % of
  HRmax, the zones are exactly the I-scale percentages.
- Placing HRVT1 at the top of zone 2 and HRVT2 at the top of zone 3 is a **cardiolab
  correspondence** (lactate about 2 and 4 mmol/L; the I-scale zones 2 and 3 reach about
  2.0 and 3.5 mmol/L). Olympiatoppen itself recommends adapting the scale to each athlete
  from tests — which is what these zones do.
- Zones are sport-specific: a running test gives running zones (HRmax is about 5 % higher
  running than cycling, per Olympiatoppen).

`cardiolab.analytics.zones` also exposes `three_zones()`, `five_zones()` and `zone_of()`
for thresholds obtained elsewhere (laboratory test).

## Storage, charts and reports

- **Storage** (migration V007, table `hrv_dfa_thresholds`):
  `repo.save_dfa_thresholds(ThresholdRecord.from_result(result, date, sport="cycling"), user_id)`.
  Thresholds measured elsewhere (laboratory) are entered with
  `ThresholdRecord.manual(date, vt1_hr, vt2_hr, sport=...)` — same table, `source = 'manual'`;
  `record.zones(hr_max=...)` gives the zones either way. `repo.load_dfa_thresholds(user_id)`
  returns them by date: the last one of a sport sets its zones.
- **Charts** (`cardiolab.visualization`): `plot_dfa_alpha1` (α1 and heart rate over the test,
  both thresholds), `plot_alpha1_vs_hr`, `plot_training_zones`, `plot_threshold_evolution`.
- **Report and export**: `table_dfa_thresholds_history`, `dfa_thresholds_to_csv` / `_json`.

## Limitations and precautions

- **Individual accuracy**: on average HRVT1 matches VT1 well (bias −1.9 bpm), but the
  limits of agreement are −12 to +8 bpm (n = 15, Rogers et al. 2021a). HRVT2 vs VT2:
  171 vs 174 bpm on average, r = 0.78 (Rogers et al. 2021b). Use the thresholds as
  estimates, and confirm them with how the sessions feel.
- **Protocol type**: agreement is better with ramps and short steps; with 4-minute steps,
  HRVT1 showed insufficient reliability in a later study, HRVT2 held.
- **Signal**: above 5 % of corrected beats, a `PhysiologicalWarning` is raised — the
  thresholds are unreliable. A chest strap gave thresholds about 4 bpm lower than an ECG
  (Rogers et al. 2021c).
- **Ectopic beats**: frequent premature beats make α1 meaningless.
- **Safety**: this is a maximal effort. After 35–40 years of age, or with risk factors or
  symptoms, ask a doctor before a maximal test. cardiolab is not a medical device.

## References

- Olympiatoppen (2024). *Olympiatoppen's intensity scale*, version 2.
  https://olt-skala.nif.no/olt_2024_en.pdf
- Seiler, S. (2010). What is best practice for training intensity and duration
  distribution in endurance athletes? *International Journal of Sports Physiology and
  Performance*, 5(3), 276–291.

- Rogers, B., Giles, D., Draper, N., Hoos, O., & Gronwald, T. (2021a). A new detection
  method defining the aerobic threshold for endurance exercise and training prescription
  based on fractal correlation properties of heart rate variability. *Frontiers in
  Physiology*, 11, 596567. https://doi.org/10.3389/fphys.2020.596567
- Rogers, B., Giles, D., Draper, N., Mourot, L., & Gronwald, T. (2021b). Detection of the
  anaerobic threshold in endurance sports: validation of a new method using correlation
  properties of heart rate variability. *Journal of Functional Morphology and
  Kinesiology*, 6(2), 38. https://doi.org/10.3390/jfmk6020038
- Rogers, B., Giles, D., Draper, N., Mourot, L., & Gronwald, T. (2021c). Influence of
  artefact correction and recording device type on the practical application of a
  non-linear heart rate variability biomarker for aerobic threshold determination.
  *Sensors*, 21(3), 821. https://doi.org/10.3390/s21030821
