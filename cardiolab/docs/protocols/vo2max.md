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

### Model 2 — ln-RMSSD (indicative)

```
VO2max ≈ 24.89 + 5.97 × ln(RMSSD)
```

Used for the fitness category **only when HRmax is unknown**. **No published
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
- Estimate: **220 − age** (precision ±10–15 bpm — unreliable at the individual level).
- Improved estimate: **208 − 0.7 × age** (Tanaka et al. 2001 — healthy adults).

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

# Without HRmax — indicative ln-RMSSD estimate only
result = vo2max_from_hrv(rr)
print(f"VO2max (ln-RMSSD)   : {result.vo2max_ln_rmssd:.1f} mL/kg/min")
```

## Computed metrics

| Metric | Description | Unit |
|---|---|---|
| `vo2max_uth` | VO2max (Uth et al. 2004): 15.3 × HRmax/HRrest | mL/kg/min |
| `vo2max_ln_rmssd` | Indicative VO2max: 24.89 + 5.97 × ln(RMSSD) | mL/kg/min |
| `vo2max_esco_flatt` | Deprecated — always `nan` since v0.4.0 | — |
| `hr_rest` | Resting HR derived from the RR series | bpm |
| `hr_max` | Maximum HR provided by the user | bpm |
| `rmssd_used` | RMSSD computed from the RR series | ms |
| `ln_rmssd_used` | ln(RMSSD) | dimensionless |
| `fitness_category` | ACSM aerobic fitness category | text |

## Interpreting results

### Aerobic fitness categories (ACSM 2022 — mixed adults)

| VO2max (mL/kg/min) | Category | Interpretation |
|---|---|---|
| ≥ 58 | **Excellent** | Elite athletic level |
| 48 – 57 | **Very good** | Trained amateur athlete |
| 38 – 47 | **Good** | Active adult |
| 28 – 37 | **Fair** | Active but untrained |
| < 28 | **Poor** | Sedentary — increased cardiometabolic risk |

### Reference values by age and sex (men, ACSM)

| Age | Poor | Fair | Good | Very good | Excellent |
|---|---|---|---|---|---|
| 20–29 | < 38 | 38–43 | 44–50 | 51–56 | > 56 |
| 30–39 | < 34 | 34–38 | 39–45 | 46–51 | > 51 |
| 40–49 | < 30 | 30–34 | 35–41 | 42–46 | > 46 |
| 50–59 | < 25 | 25–30 | 31–37 | 38–42 | > 42 |
| 60–69 | < 21 | 21–25 | 26–32 | 33–37 | > 37 |

### Model comparison

| Model | Required data | Precision | Recommendation |
|---|---|---|---|
| Uth (HRmax/HRrest) | HRmax + resting recording | ±10–15 % | Reference — give HRmax (test, or 208 − 0.7 × age) |
| ln-RMSSD | Resting recording only | not established | Indication only, when HRmax is unknown |

**Fitness category priority**: Uth when HRmax is available, otherwise the indicative
ln-RMSSD estimate (changed in v0.4.0 — was Esco-Flatt).

### Longitudinal tracking

Repeating the measurement under identical conditions (same time, same duration, same
position) allows tracking of estimated VO2max without an exercise test. With the Uth
model, a lower resting HR at the same HRmax raises the estimate.

## Limitations and precautions

- These estimates are **population-level predictions** with an individual imprecision
  of ±10–15 %. Do not use them for medical decisions without confirmation by direct
  testing.
- The Uth model is sensitive to **HRmax quality**: an estimated value (220 − age)
  introduces an additional error of ±10 bpm.
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

American College of Sports Medicine. (2022). *ACSM's Guidelines for Exercise Testing
and Prescription* (11th ed.). Lippincott Williams & Wilkins.
