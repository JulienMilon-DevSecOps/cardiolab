# VO2max Estimation from HRV

## Physiological principle

Maximal oxygen uptake (VO2max) is the gold standard of cardiorespiratory capacity.
Direct measurement requires a laboratory (gas analyser, maximal exercise test).
cardiolab gives one reference estimate (Uth, heart rate ratio) and one indicative
estimate from resting HRV.

### Model 1 — HR Ratio (Uth et al. 2004)

The Heart Rate Ratio (HRR) method relies on the relationship between maximal HR,
resting HR, and VO2max:

```
VO2max ≈ 15.3 × (HRmax / HRrest)
```

**Rationale**: HRmax is determined by maximal stroke volume and maximal O₂ uptake;
HRrest reflects vagal tone and cardiac reserve. The HRmax/HRrest ratio correlates
linearly with VO2max (r = 0.87 in the original study).

**Precision**: ±10–15 % (standard error ≈ 3.5 mL/kg/min).

**Which HRmax** (changed in v0.5.0) — in this order:

1. the `hr_max` you give (maximal test, or a value you know) — `hr_max_source = "provided"`;
2. otherwise, with the age (`birth_year` of the profile), **208 − 0.7 × age**
   (Tanaka et al. 2001) — `hr_max_source = "tanaka"`. A population prediction
   (SD ≈ ±10 bpm between individuals): the estimate is less precise than with a
   measured HRmax, but it keeps the sourced Uth model;
3. neither → no Uth estimate (`hr_max_source = None`).

### Model 2 — ln-RMSSD (indicative)

```
VO2max ≈ 24.89 + 5.97 × ln(RMSSD)
```

Used for the fitness category **only when neither HRmax nor the age is known**
(since v0.5.0 the age gives a Tanaka HRmax and the Uth model). **No published
source could be verified for this equation**: read it as an indication, not a
measurement. Endurance training raises both VO2max and resting RMSSD, but resting
HRV adds little to heart rate for predicting VO2max — in 145 young adults, heart rate
explained about 17 % of VO2max variance and the HF power of HRV only 3 % more
(Grant et al. 2013). Give HRmax whenever possible.

### Removed in v0.4.0 — "Esco & Flatt (2014)" RMSSD model

`VO2max ≈ 18.37 + 0.054 × RMSSD` returned 20–24 mL/kg/min over the whole normal
RMSSD range (20–100 ms): every user without HRmax was classed "poor" or "fair". The
cited paper (Esco & Flatt 2014, *J Sports Sci Med* 13:535) studies ultra-short HRV
recordings and contains no VO2max equation. The model is no longer computed;
`vo2max_esco_flatt` is kept for storage compatibility and is always `nan`
(rows stored before v0.4.0 keep their old value until reprocessed).

## How to perform the protocol

### Measurement conditions

- **Resting** recording, fasted or ≥ 2 h after a light meal.
- **Supine** or **seated** position for at least 5 minutes before recording.
- Recommended duration: **5 minutes** (minimum 30 RR intervals).
- Same time each day (morning upon waking is ideal for resting HR).

### Obtaining HRmax (for the Uth model)

- Direct measurement during a maximal exercise test (ergometer, Cooper test, etc.).
- Without a measured value, cardiolab uses **208 − 0.7 × age** (Tanaka et al. 2001 —
  meta-analysis of 351 studies and a laboratory study of healthy adults) when the
  age is known. The older **220 − age** formula underestimates HRmax after 40.

### Recording

```python
from cardiolab.signals.rr import RRSeries
from cardiolab.protocols.vo2max import vo2max_from_hrv

rr = RRSeries.from_csv("morning_rest.csv")

# With known HRmax
result = vo2max_from_hrv(rr, hr_max=185.0)
print(f"VO2max (Uth)        : {result.vo2max_uth:.1f} mL/kg/min")
print(f"VO2max (ln-RMSSD)   : {result.vo2max_ln_rmssd:.1f} mL/kg/min")
print(f"Fitness category    : {result.fitness_category}")  # from Uth

# Without HRmax, with age and sex — Tanaka HRmax, norms of the same sex and age
result = vo2max_from_hrv(rr, age=36, sex="male")
print(result.hr_max, result.hr_max_source)          # 182.8 tanaka
print(f"{result.percentile:.0f}th percentile, {result.fitness_category}")

# Neither HRmax nor age — indicative ln-RMSSD estimate only
result = vo2max_from_hrv(rr)
print(f"VO2max (ln-RMSSD)   : {result.vo2max_ln_rmssd:.1f} mL/kg/min")
```

`reprocess_sessions()` and the import script read the age (`birth_year`), sex and
HRmax of the user profile.

## Computed metrics

| Metric | Description | Unit |
|---|---|---|
| `vo2max_uth` | VO2max (Uth et al. 2004): 15.3 × HRmax/HRrest | mL/kg/min |
| `vo2max_ln_rmssd` | Indicative VO2max: 24.89 + 5.97 × ln(RMSSD) | mL/kg/min |
| `vo2max_esco_flatt` | Deprecated — always `nan` since v0.4.0 | — |
| `hr_rest` | Resting HR derived from the RR series | bpm |
| `hr_max` | HRmax used by the Uth model — provided or Tanaka | bpm |
| `hr_max_source` | `provided`, `tanaka` or `None` (column added by V006) | text |
| `rmssd_used` | RMSSD computed from the RR series | ms |
| `ln_rmssd_used` | ln(RMSSD) | dimensionless |
| `fitness_category` | Fitness category — by age and sex when known | text |
| `percentile` (property, not stored) | Percentile among people of the same sex and age | 0–100 |

## Interpreting results

### Fitness categories by age and sex (v0.5.0)

With the age and sex of the profile, the estimate is placed among people of the
same sex and decade, using the **FRIEND registry** reference standards (Kaminsky et
al. 2015 — 7 783 maximal treadmill tests of healthy US adults, the standards
adopted by ACSM 2022). VO2max at each percentile (mL/kg/min):

| Age | Men p10 | p25 | p50 | p75 | p90 | Women p10 | p25 | p50 | p75 | p90 |
|---|---|---|---|---|---|---|---|---|---|---|
| 20–29 | 32.1 | 40.1 | 48.0 | 55.2 | 61.8 | 23.9 | 30.5 | 37.6 | 44.7 | 51.3 |
| 30–39 | 30.2 | 35.9 | 42.4 | 49.2 | 56.5 | 20.9 | 25.3 | 30.2 | 36.1 | 41.4 |
| 40–49 | 26.8 | 31.9 | 37.8 | 45.0 | 52.1 | 18.8 | 22.1 | 26.7 | 32.4 | 38.4 |
| 50–59 | 22.8 | 27.1 | 32.6 | 39.7 | 45.6 | 17.3 | 19.9 | 23.4 | 27.6 | 32.0 |
| 60–69 | 19.8 | 23.7 | 28.2 | 34.5 | 40.3 | 14.6 | 17.2 | 20.0 | 23.8 | 27.0 |
| 70–79 | 17.1 | 20.4 | 24.4 | 30.4 | 36.6 | 13.6 | 15.6 | 18.3 | 20.8 | 23.1 |

Under 20 the 20–29 norms are used, from 80 the 70–79 norms.

| Percentile (same sex and age) | Category |
|---|---|
| ≥ 90th | **Excellent** |
| 75th – 90th | **Very good** |
| 25th – 75th | **Good** |
| 10th – 25th | **Fair** |
| < 10th | **Poor** |

The grouping is cardiolab's. The **score** (`vo2max_score()`) is the percentile
itself: 50 = median of your sex and age, 90 = better than 90 % of them. Between
table values the percentile is interpolated; beyond the 10th / 90th, a normal tail
fitted on that side of the distribution is used.

Example — 42 mL/kg/min is "good" (≈ 48th percentile) for a man of 35 and
"excellent" (> 99th percentile) for a woman of 55.

### Without age or sex — fixed adult scale

| VO2max (mL/kg/min) | Category |
|---|---|
| ≥ 58 | **Excellent** |
| 48 – 57 | **Very good** |
| 38 – 47 | **Good** |
| 28 – 37 | **Fair** |
| < 28 | **Poor** |

Score: sigmoid centred at 43 mL/kg/min. Fill in `birth_year` and `sex` in the
profile, then reprocess, to get categories by age and sex.

### Model comparison

| Model | Required data | Precision | Recommendation |
|---|---|---|---|
| Uth (HRmax/HRrest) | HRmax (or age → Tanaka) + resting recording | ±10–15 %, more with Tanaka | Reference |
| ln-RMSSD | Resting recording only | not established | Indication only, without HRmax and age |

**Fitness category priority**: Uth (provided HRmax, otherwise Tanaka), otherwise the
indicative ln-RMSSD estimate.

### Longitudinal tracking

Repeating the measurement under identical conditions (same time, same duration, same
position) allows tracking of estimated VO2max without an exercise test. With the Uth
model, a lower resting HR at the same HRmax raises the estimate.

## Limitations and precautions

- These estimates are **population-level predictions** with an individual imprecision
  of ±10–15 %. Do not use them for medical decisions without confirmation by direct
  testing.
- The Uth model is sensitive to **HRmax quality**: the Tanaka prediction has an
  individual SD of about ±10 bpm, i.e. about ±5–6 % on the VO2max estimate.
- The FRIEND norms come from healthy US adults tested on a treadmill: an estimate
  from resting HR is compared with measured values — read the percentile as an
  order of magnitude.
- The ln-RMSSD estimate has **no verified validation**; it follows RMSSD, which
  also varies day to day with fatigue — do not read its changes as fitness changes.
- RMSSD measured in ultra-short recordings (< 1 min) gives less precise results;
  prefer **≥ 5 min** of recording.

## References

Uth, N., Sørensen, H., Overgaard, K., & Pedersen, P. K. (2004). Estimation of VO2max
from the ratio between HRmax and HRrest — the Heart Rate Ratio Method.
*European Journal of Applied Physiology*, 91(1), 111–115.
https://doi.org/10.1007/s00421-003-0988-y

Grant, C. C., Murray, C., Janse van Rensburg, D. C., & Fletcher, L. (2013). A
comparison between heart rate and heart rate variability as indicators of cardiac
health and fitness. *Frontiers in Physiology*, 4, 337.
https://doi.org/10.3389/fphys.2013.00337

Tanaka, H., Monahan, K. D., & Seals, D. R. (2001). Age-predicted maximal heart rate
revisited. *Journal of the American College of Cardiology*, 37(1), 153–156.
https://doi.org/10.1016/S0735-1097(00)01054-8

Kaminsky, L. A., Arena, R., & Myers, J. (2015). Reference standards for
cardiorespiratory fitness measured with cardiopulmonary exercise testing: data from
the Fitness Registry and the Importance of Exercise National Database. *Mayo Clinic
Proceedings*, 90(11), 1515–1523. https://doi.org/10.1016/j.mayocp.2015.07.026

American College of Sports Medicine. (2022). *ACSM's Guidelines for Exercise Testing
and Prescription* (11th ed.). Lippincott Williams & Wilkins.
