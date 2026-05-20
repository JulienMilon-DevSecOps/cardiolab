# Heart Rate Recovery (HRR) Protocol

## Physiological principle

Heart Rate Recovery (HRR) measures the speed at which HR decreases after maximal or
submaximal exercise. This decrease is primarily mediated by **parasympathetic
reactivation** (vagus nerve) in the first seconds to minutes post-effort.

HRR at 1 minute (HRR1 = HR_peak − HR_60s) is an **independent predictor of
cardiovascular mortality**: a drop < 12 bpm doubles all-cause mortality risk
(Cole et al. 1999). The underlying mechanism is vagal reactivation, which slows the
sinoatrial node as soon as effort stops.

Two indicators are computed:

- **HRR1**: HR drop at 60 seconds post-peak (vagal marker, strong prognostic value).
- **HRR2**: HR drop at 120 seconds post-peak (also integrates catecholamine clearance).

## How to perform the protocol

### Measurement conditions

- Continuous RR interval recording during exercise AND recovery.
- The RR series must **start at the effort peak** (last beat of maximal effort).
- **Passive** recovery phase: the subject sits or stands still without walking.
- Minimum post-peak recording duration: **2 minutes** (for both HRR1 and HRR2).

### Recommended effort protocol

- Maximal effort test (VO2max, Ruffier, Cooper test) or
- Submaximal effort at controlled intensity (85–95 % HRmax).
- The effort must be intense enough to raise HR to ≥ 150 bpm.

### Procedure

1. Start RR recording at least 2 min before the effort peak.
2. Continue recording for **at least 2 min** after the peak.
3. Identify the effort peak (maximum HR) and trim the series from that point.
4. Export the RR intervals from the recovery phase.

### Recording

```python
from cardiolab.signals.rr import RRSeries
from cardiolab.protocols.hrr import heart_rate_recovery

# The series must start at the effort peak
rr_recovery = RRSeries.from_csv("recovery.csv")
result = heart_rate_recovery(rr_recovery)

print(f"Peak HR: {result.hr_peak:.0f} bpm")
print(f"HRR1: {result.hrr_60:.0f} bpm → {result.hrr_60_category}")
print(f"HRR2: {result.hrr_120:.0f} bpm → {result.hrr_120_category}")
```

## Computed metrics

| Metric | Description | Unit |
|---|---|---|
| `hr_peak` | HR at the effort peak (first beat of the series) | bpm |
| `hr_at_60s` | HR at exactly 60 s post-peak | bpm |
| `hr_at_120s` | HR at exactly 120 s post-peak | bpm |
| `hrr_60` | HR drop at 60 s (HR_peak − HR_60s) | bpm |
| `hrr_120` | HR drop at 120 s (HR_peak − HR_120s) | bpm |
| `hrr_60_category` | Clinical category for HRR1 | text |
| `hrr_120_category` | Clinical category for HRR2 | text |
| `duration` | Total duration of the recovery recording | s |

## Interpreting results

### HRR1 — Drop at 60 seconds (Cole et al. 1999)

| HRR1 (bpm) | Category | Cardiovascular risk |
|---|---|---|
| ≥ 25 | **Excellent** | Very low — excellent vagal reactivation |
| 20 – 24 | **Good** | Low |
| 12 – 19 | **Normal** | Average risk |
| < 12 | **Impaired** | Elevated risk — independent prognostic marker |

> **Clinical threshold**: HRR1 < 12 bpm is an independent predictor of all-cause
> mortality (RR = 2.0; 95 % CI: 1.5–2.7; Cole et al. 1999).

### HRR2 — Drop at 120 seconds

| HRR2 (bpm) | Category |
|---|---|
| ≥ 55 | Excellent |
| 45 – 54 | Good |
| 35 – 44 | Normal |
| < 35 | Impaired |

### Typical values by population

| Population | Mean HRR1 | Mean HRR2 |
|---|---|---|
| Trained athletes | 35–50 bpm | 60–80 bpm |
| Active adults | 20–30 bpm | 40–55 bpm |
| Sedentary adults | 12–20 bpm | 30–45 bpm |
| Cardiac patients | < 12 bpm | < 30 bpm |

### Factors influencing HRR

- **Endurance training**: significantly increases HRR (vagal hypertrophy).
- **Age**: HRR decreases with age (≈ −0.5 bpm/year).
- **Medications**: beta-blockers reduce HRR; anticholinergics artificially increase it.
- **Pathologies**: heart failure, autonomic diabetes, vagal neuropathy → impaired HRR.

## Limitations and precautions

- Recovery must be **passive**: any activity (recovery walk) artificially accelerates
  the HR drop and overestimates HRR.
- HRR depends on **effort intensity**: submaximal exercise produces a less informative
  HRR.
- Avoid measuring HRR after effort in the context of an intercurrent illness (fever,
  severe dehydration).
- Minimum recommended: **30 RR intervals** for a reliable calculation (≈ 30 recovery
  beats).

## References

Cole, C. R., Blackstone, E. H., Pashkow, F. J., Snader, C. E., & Lauer, M. S.
(1999). Heart-rate recovery immediately after exercise as a predictor of mortality.
*New England Journal of Medicine*, 341(18), 1351–1357.
https://doi.org/10.1056/NEJM199910283411804

Imai, K., Sato, H., Hori, M., Kusuoka, H., Ozaki, H., Yokoyama, H., ... & Kamada,
T. (1994). Vagally mediated heart rate recovery after exercise is accelerated in
athletes but blunted in patients with chronic heart failure.
*Journal of the American College of Cardiology*, 24(6), 1529–1535.
https://doi.org/10.1016/0735-1097(94)90150-3

Morshedi-Meibodi, A., Larson, M. G., Levy, D., O'Donnell, C. J., & Vasan, R. S.
(2002). Heart rate recovery after treadmill exercise testing and risk of cardiovascular
disease events (The Framingham Heart Study).
*American Journal of Cardiology*, 90(8), 848–852.
https://doi.org/10.1016/S0002-9149(02)02801-1

Jouven, X., Empana, J. P., Schwartz, P. J., Desnos, M., Courbon, D., &
Ducimetière, P. (2005). Heart-rate profile during exercise as a predictor of sudden
death. *New England Journal of Medicine*, 352(19), 1951–1958.
https://doi.org/10.1056/NEJMoa043012
