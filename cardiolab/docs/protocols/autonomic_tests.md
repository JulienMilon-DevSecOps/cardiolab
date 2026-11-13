# Autonomic reflex tests — Ewing battery

Added in v0.8.0. Module: `cardiolab.protocols.autonomic_tests`.

## Physiological principle

The autonomic nervous system speeds the heart up (sympathetic) and slows it down (vagus
nerve). Three short tests make it change the heart rate on purpose and measure how much it
does (Ewing et al. 1985):

| Test | What you do | What answers | Result |
|---|---|---|---|
| **Deep breathing** | Breathe at 6 breaths per minute for 1 minute | The vagus nerve: the heart speeds up on each breath in and slows down on each breath out | Heart rate difference (bpm), E/I ratio |
| **Valsalva** | Blow at 40 mmHg for 15 s into a manometer mouthpiece | Both: the heart speeds up during the strain, then slows down sharply after it | Valsalva ratio |
| **30:15** | Stand up from lying (the [orthostatic test](orthostatic.md)) | The heart speeds up until about the 15th beat, then slows down around the 30th | 30:15 ratio |

Large changes are a good sign. They decrease naturally with age.

This is a **check-up**, not a daily measurement: once or twice a year, or when a fatigue
signal persists (see the [monitoring](../analytics/monitoring.md) and the daily score). The
two blood-pressure tests of the battery (handgrip, blood pressure on standing) are not
included: the current sensors do not measure blood pressure.

> **Not a medical device.** The interpretations are reference values from the
> literature, not a diagnosis. A low result is checked again another day, in the same
> conditions; if it repeats, discuss it with a doctor.

---

## Conditions for all three tests

- **In the morning**, rested, at rest for at least 5 minutes before starting.
- **Fasting**, or at least 2 hours after a meal; no coffee, tea, tobacco or alcohol before;
  no hard exercise the day before.
- **Chest strap** (beat-to-beat intervals). A wrist sensor is not precise enough.
- Not when ill (fever, cold), after a bad night, or under medication that acts on the heart
  rate (beta-blockers…) — or note it, the results are then not comparable.
- Same conditions from one check-up to the next.

---

## Deep breathing

### Procedure

1. Lie down or sit, rested, for 5 minutes, recording.
2. Breathe **slowly and deeply**: 5 s in, 5 s out (6 breaths per minute), for **1 minute**,
   ideally with a visual guide. Mark the start of the first breath.
3. Breathe normally again.

### Recording

```python
from cardiolab.protocols import deep_breathing_test

res = deep_breathing_test(rr, age=45)    # rr from the first paced breath
res.hr_difference      # 21.3 bpm — mean of (highest − lowest heart rate) per cycle
res.ei_ratio           # 1.33     — longest RR (breath out) / shortest RR (breath in)
res.n_cycles           # 6
res.breathing_rate     # 6.0 per minute
res.interpretation     # 'normal'
res.hr_difference_limit, res.ei_ratio_limit   # age-corrected lower limits
```

### How it is computed

- The heart rate is filtered around the breathing rhythm (0.05–0.2 Hz); each breathing
  cycle runs from one trough to the next.
- Per cycle: the shortest RR (breath in) and the longest RR (breath out). Heart rate
  difference = `60000/shortest − 60000/longest`; E/I ratio = `longest / shortest`.
- Result = mean over the complete cycles (Ewing: 6 cycles; May et al.: 3 consecutive ones).
- Fewer than **3 complete cycles** → `status = "unreliable"`. A breathing rate outside
  5–7 per minute gives a warning.

### Reference values

| | Normal | Borderline | Abnormal |
|---|---|---|---|
| Ewing et al. (1985), adults — without age | ≥ 15 bpm | 11–14 bpm | ≤ 10 bpm |
| With `age=` — May et al. (1999) | ≥ 15 bpm | between the age limit and 15 bpm | below the age limit |

Age limit (5th percentile of the general population, May et al. 1999):

| Age | 20 | 30 | 40 | 50 | 60 | 70 |
|---|---|---|---|---|---|---|
| Heart rate difference `(4.39 − 0.033 × age)²` | 13.9 bpm | 11.6 bpm | 9.4 bpm | 7.5 bpm | 5.8 bpm | 4.3 bpm |
| E/I ratio `1 + exp(−1.12 − 0.0198 × age)` | 1.22 | 1.18 | 1.15 | 1.12 | 1.10 | 1.08 |

The study covered 40–67 years: below or above, the limit is extrapolated (a warning says
so). Example: 8 bpm at 65 years is *abnormal* for Ewing's adult values but above the age
limit (5 bpm) → `borderline`.

---

## Valsalva manoeuvre

> **Before the test.** Do not do it with an eye disease (retina — diabetic retinopathy),
> poorly controlled blood pressure, a known heart problem, recent surgery (eyes, abdomen,
> chest), a hernia, or during pregnancy: ask a doctor first. Stop if you feel dizzy or
> unwell. Few people will do it: it needs a **manometer**.

### Equipment

A manometer (or blood-pressure cuff gauge) connected to a mouthpiece with a small air leak,
so that the pressure comes from the chest and not from the cheeks. Without it, the strain
is not standardised and the results cannot be compared.

### Procedure

1. Sit, rested, recording, for at least 1 minute.
2. Note the **start** of the strain. Blow into the mouthpiece to hold **40 mmHg for
   15 seconds**.
3. Release and breathe normally, still seated, for at least **1 minute**, recording.

### Recording

```python
from cardiolab.protocols import valsalva_ratio

res = valsalva_ratio(rr, strain_start_sec=62.0)    # end = start + 15 s by default
res.ratio            # 1.72
res.max_hr, res.min_hr   # 98 bpm during the strain, 57 bpm after it
res.interpretation   # 'normal'
```

- Ratio = **longest RR in the 30 s after the strain / shortest RR during the strain**
  (= highest heart rate during / lowest heart rate after).
- A heart rate that barely rises during the strain (< 5 bpm above the 30 s before) → warning:
  the blowing was probably too weak. A recording that stops less than 20 s after the strain →
  `unreliable`. A strain outside 10–20 s → warning.

### Reference values (Ewing et al. 1985)

| Normal | Borderline | Abnormal |
|---|---|---|
| ≥ 1.21 | 1.11–1.20 | ≤ 1.10 |

The ratio also decreases with age (Low et al. 1997; Gelber et al. 1997). cardiolab applies
the adult values at every age: an older person may be classed lower than an age-specific
table would.

---

## 30:15 ratio

Nothing more to do than the [orthostatic test](orthostatic.md): lie for 5 minutes, then
**stand up in one go** and stay still. Mark the moment you stand up if you can.

```python
from cardiolab.protocols import orthostatic_hrv, ratio_30_15

res = ratio_30_15(orthostatic_hrv(rr))        # or ratio_30_15(rr, stand_sec=300.0)
res.ratio              # 1.28
res.stand_estimated    # True — moment of standing estimated
res.interpretation     # 'normal'
```

- Beats are counted from the moment of standing: **longest RR among beats 20–40 / shortest
  RR among beats 5–25** (the windows allow for the peak not being exactly at beat 15).
- Moment of standing: `stand_sec` when known; otherwise estimated as the start of the heart
  rate rise (the transition found by `detect_phases` starts later, its 30-s mean lags).
  On synthetic recordings the estimate is within a few beats, with the same ratio.
- At least 40 beats after standing.

### Reference values (Ewing et al. 1985)

| Normal | Borderline | Abnormal |
|---|---|---|
| ≥ 1.04 | 1.01–1.03 | ≤ 1.00 |

Same remark as Valsalva: the ratio decreases with age; adult values at every age.

---

## Storage

`AutonomicTestsResult(date, deep_breathing=…, valsalva=…, ratio_30_15=…)` groups the tests of
one day (any may be missing). Table `hrv_autonomic_tests`, migration
`V008__autonomic_tests.sql`:

```python
from cardiolab.protocols import AutonomicTestsResult

with HRVRepository.from_env() as repo:
    repo.save_autonomic_tests(AutonomicTestsResult("2026-11-14", deep_breathing=res), user_id)
    history = repo.load_autonomic_tests(user_id)
```

Saving the same day again replaces the whole row: pass every test done that day. The
breathing cycles and the warnings are not stored.

---

## Limitations

- Reference values: Ewing's adult cut-offs come from diabetic autonomic neuropathy
  screening; age-corrected values only for deep breathing (May et al. 1999, 40–67 years).
- Very sensitive to the conditions: coffee, digestion, fatigue, irregular breathing,
  a weak or too long strain.
- In trained athletes, a strong vagal tone gives large responses: the tests detect a
  **loss** of response, they do not grade fitness.
- The 30:15 ratio is weak as a stand-alone test: read it with the other two.

## References

- Ewing, D. J., Martyn, C. N., Young, R. J., & Clarke, B. F. (1985). The value of
  cardiovascular autonomic function tests: 10 years experience in diabetes. *Diabetes Care*,
  8(5), 491–498.
- May, O., Arildsen, H., & Møller, M. (1999). Parasympathetic function during deep breathing
  in the general population: relation to coronary risk factors and normal range. *Journal of
  Internal Medicine*, 245(3), 287–294.
- Low, P. A., Denq, J. C., Opfer-Gehrking, T. L., et al. (1997). Effect of age and gender on
  sudomotor and cardiovagal function and blood pressure response to tilt in normal subjects.
  *Muscle & Nerve*, 20(12), 1561–1568.
- Gelber, D. A., Pfeifer, M., Dawson, B., & Schumer, M. (1997). Cardiovascular autonomic
  nervous system tests: determination of normative values and effect of confounding
  variables. *Journal of the Autonomic Nervous System*, 62(1–2), 40–44.
- Shields, R. W. (2009). Heart rate variability with deep breathing as a clinical test of
  cardiovagal function. *Cleveland Clinic Journal of Medicine*, 76(Suppl 2), S37–S40.
