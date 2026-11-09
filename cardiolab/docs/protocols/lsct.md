# Lamberts Submaximal Cycle Test (LSCT)

## Physiological principle

A short cycling test without an all-out effort, to follow fitness and fatigue week after
week. The **heart rate is imposed** and the **power is measured**: at the same heart rate, a
fitter athlete produces more power; a tired athlete produces less, or feels it harder, or can
no longer bring the heart rate up (Lamberts et al. 2011).

| Stage | Duration | Target |
|-------|----------|--------|
| 1 | 6 min | 60 % of HRmax |
| 2 | 6 min | 80 % of HRmax |
| 3 | 3 min | 90 % of HRmax |
| Recovery | 90 s | stop pedalling, sit upright |

The power of stages 2 and 3 is the most reliable variable (ICC 0.85–1.00, typical error
1.3–4.4 %) and the best predictor of performance (r = 0.80–0.94 with the 40-km time trial);
the heart rate recovery is less informative (r = 0.55–0.68).

## How to perform the protocol

### Equipment

- A **power** source: indoor trainer with power, or power meter.
- A **heart rate** source: chest strap or watch — the beat intervals are not needed.
- Indoors, set-up A of [`sensors/indoor_cycling.md`](../sensors/indoor_cycling.md) (the app
  alone) is enough, provided the exported file contains the heart rate. With the heart rate
  on the watch and the power in the app (set-up C), merge the two files first:
  `lsct_from_records(merge_fit_records(watch, app), hr_max=...)`.
- **HRmax**: from the profile, a maximal test or the age — **always the same one** from test
  to test, otherwise the stages change and the tests cannot be compared.

### Procedure

1. Warm-up as you like (it is not analysed): note when stage 1 starts.
2. Ride each stage at its **target heart rate** (±1–2 bpm), not at a power: adjust the power
   to hold the heart rate. **No gradients**: in the app, use ERG mode (you set the watts,
   in steps of 5–10 W) or an entirely flat route (gears and cadence). On a hilly route the
   trainer imposes the resistance — a climb pushes the heart rate above the target, a
   descent leaves no power to push — and the stages are no longer held at their target
   (seen on the author's first test, 2026-11-09).
   The heart rate lags the power by 1–2 min: at the start of a stage, go straight to a
   reasonable power instead of a burst, then adjust in small steps; lower the power when the
   heart rate drifts up within a stage.
3. Note your **perceived exertion** at the end of each stage (same scale every time — the
   0–10 scale of cardioanalysis).
4. At the end of stage 3, **stop pedalling and sit upright for 90 s**, recording. Check that
   the app does not pause the recording when the wheel stops (otherwise HRR60 is missing);
   if it does, record on the watch too, auto-pause off.
5. Same bike, trainer, app mode (ERG or flat route), time of day and conditions each week.

### Recording

```python
from cardiolab.protocols import compare_lsct, lsct_from_records
from cardiolab.sensors_tools import parse_fit_records

records = parse_fit_records("2026-11-13_lsct.fit")
result = lsct_from_records(records, hr_max=185, start_sec=300, rpe=(3, 5, 7))

result.stage(2).mean_power, result.stage(3).mean_power   # W
result.stage(3).target_reached                           # HR brought up to 90 %?
result.hrr_60                                            # bpm

compare_lsct(result, previous_tests).interpretation      # 'improving', 'stable', ...
```

`start_sec` is the start of stage 1 in the file. With series from another source,
`lsct(time_sec, heart_rate, power, hr_max, ...)`.

## Computed metrics

| Field | Description |
|-------|-------------|
| `stages[i].mean_power` | Mean power of the stage (W) |
| `stages[i].mean_hr` | Mean heart rate of the stage (bpm) |
| `stages[i].hr_end` | Mean heart rate over the stage's last minute (bpm) |
| `stages[i].target_reached` | `hr_end` ≥ target − 2 bpm |
| `stages[i].rpe` | Perceived exertion entered |
| `hrr_60` | Heart rate at the end of stage 3 minus 60 s later (5-s medians) |
| `warnings` | `recovery_missing`, `stage3_target_not_reached`, `stage<n>_off_target` |

A stage held more than 5 bpm away from its target (above it, or below it for stages 1–2) is
flagged `stage<n>_off_target`: the test was not ridden as prescribed (wrong `start_sec`,
wrong HRmax, power fixed instead of heart rate) and is not comparable with the others.

## Interpreting results

Compare a test with **your own previous tests** — `compare_lsct(current, previous)`, with
one test or the mean of the last 3–4:

| Change | Reading | Basis |
|--------|---------|-------|
| Power of stages 2–3 up ≥ 5 %, same perceived exertion | **Improving** | Power at fixed heart rate reflects fitness |
| Power down ≥ 5 % | **Fatigue possible** | Power and perceived exertion responded to a fatiguing training period, and recovered after it |
| Power up **with** perceived exertion up ≥ 1 point, or stage 3 target not reached | **Possible overreaching** | Decroix et al. 2017 (6 professional cyclists, training camp) |
| Otherwise | **Stable** | — |

The 5 % threshold is a cardiolab choice, above the largest typical error (4.4 %). The
readings are **cardiolab heuristics** built on small studies: confirm with the morning
readiness score and how the training feels. The heart rate recovery is reported, but not
used for the reading (inconsistent results as a fatigue marker).

## Limitations and precautions

- Validated on **trained cyclists**, on the bike only — no validated running version is
  used by cardiolab.
- The targets depend on HRmax: an HRmax changed between two tests makes them not
  comparable (keep the old one, or start a new series).
- Heat, hydration, caffeine and time of day change the heart rate: keep the conditions.
- cardiolab is not a medical device.

## References

- Lamberts, R. P., Swart, J., Noakes, T. D., & Lambert, M. I. (2011). A novel submaximal
  cycle test to monitor fatigue and predict cycling performance. *British Journal of
  Sports Medicine*, 45(10), 797–804.
- Decroix, L., Lamberts, R. P., & Meeusen, R. (2017). Can the Lamberts and Lambert
  Submaximal Cycle Test reflect overreaching in professional cyclists? *International
  Journal of Sports Physiology and Performance*. PubMed 28422523.
