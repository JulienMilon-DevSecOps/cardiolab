# Time-Domain HRV Features

Time-domain metrics are computed directly on the sequence of RR intervals
without any spectral transformation. They are robust, fast to compute, and
reliable from recordings as short as 2–3 minutes.

---

## RMSSD — Root Mean Square of Successive Differences

**Field**: `rmssd` | **Unit**: ms

### Definition

$$\text{RMSSD} = \sqrt{\frac{1}{N-1} \sum_{i=1}^{N-1} (RR_{i+1} - RR_i)^2}$$

### Physiological background

RMSSD measures **beat-to-beat variability** — the variation in the length of
consecutive heartbeat intervals. High beat-to-beat variability reflects strong
**parasympathetic (vagal) tone**: the vagus nerve continuously modulates heart
rate in response to respiration (respiratory sinus arrhythmia). When the vagus
nerve is active and heart rate is well-regulated, consecutive beats differ more.
When the sympathetic nervous system dominates (stress, fatigue, illness), beats
become more uniform and RMSSD drops.

RMSSD is the **primary HRV marker** for sports science and daily wellness
monitoring. It is robust to respiratory rate and recording length variations
compared to frequency-domain metrics.

### Reference values (5-minute resting supine)

| RMSSD (ms) | Interpretation |
|------------|----------------|
| < 20 | Very low — possible high fatigue, illness, or overtraining |
| 20 – 40 | Low — below-average vagal tone |
| 40 – 70 | Normal — healthy resting state |
| 70 – 100 | High — good autonomic health or high aerobic fitness |
| > 100 | Very high — typical of well-trained endurance athletes |

> **Individual baseline matters more than absolute value.** A value of 30 ms
> may be normal for one person and low for another. Track relative changes
> against your personal 7-day or 30-day baseline.

### Clinical interpretation

- **Acute drop (> 2 SD below baseline)**: stress response, acute illness, or
  high training load. Consider reducing training intensity.
- **Chronic low RMSSD**: possible overtraining syndrome, poor sleep, or
  persistent fatigue. Medical review recommended if sustained.
- **Elevated RMSSD**: recovery state, taper phase, or high aerobic fitness.
- **Very high RMSSD in athletes**: physiological, not pathological. Well-trained
  athletes commonly exceed 100 ms.

### Notes

- Minimum reliable recording: **2 minutes** (but 5 minutes recommended).
- Sensitive to outlier beats — always clean with `remove_outliers()`.
- Not directly comparable across different recording conditions (supine vs.
  standing, morning vs. evening).

---

## ln_RMSSD — Natural Logarithm of RMSSD

**Field**: `ln_rmssd` | **Unit**: dimensionless

### Definition

$$\ln\text{RMSSD} = \ln(\text{RMSSD})$$

### Physiological background

Raw RMSSD values are **right-skewed**: small deviations from the mean are
common, but occasional large values pull the distribution rightward. This
non-normality makes statistical operations (mean, standard deviation, regression)
less reliable on raw RMSSD.

The log transformation produces a **more normally distributed** metric. This
makes it better suited for:
- Day-to-day change tracking relative to a baseline.
- Statistical tests comparing groups.
- Building readiness score formulas.

### Reference values

Derived from RMSSD: `ln(40) ≈ 3.7`, `ln(70) ≈ 4.25`, `ln(100) ≈ 4.6`.

### Notes

- Used internally in baseline-relative scoring.
- Returns `0.0` if RMSSD is zero or negative (degenerate edge case).

---

## SDNN — Standard Deviation of NN intervals

**Field**: `sdnn` | **Unit**: ms

### Definition

$$\text{SDNN} = \sqrt{\frac{1}{N-1} \sum_{i=1}^{N} (RR_i - \overline{RR})^2}$$

(computed with ddof=1, unbiased estimator)

### Physiological background

SDNN measures **total heart rate variability** over the recording window. Unlike
RMSSD (which captures only fast, beat-to-beat changes), SDNN is influenced by
both:
- **Fast parasympathetic oscillations** (reflected in HF band, < 5 s cycles).
- **Slow sympathetic and mixed oscillations** (LF band, 5–25 s cycles, blood
  pressure control, baroreflex).

SDNN is therefore a marker of **overall autonomic regulation**. In long-term
recordings (24 h Holter), SDNN is the primary predictor of cardiovascular risk.
In short 5-minute recordings, it is less clinically standardised than RMSSD.

### Reference values (5-minute resting supine)

| SDNN (ms) | Interpretation |
|-----------|----------------|
| < 20 | Very low — possible autonomic dysfunction |
| 20 – 50 | Low |
| 50 – 80 | Normal |
| > 80 | High — good overall autonomic regulation |

### Notes

- **Strongly dependent on recording duration**: SDNN from a 5-minute recording
  cannot be compared to SDNN from a 24-hour recording.
- Less robust to artefacts than RMSSD — a single very long or very short
  interval inflates SDNN significantly.

---

## pNN50 — Percentage of pairs with ΔRR > 50 ms

**Field**: `pnn50` | **Unit**: %

### Definition

$$\text{pNN50} = \frac{\text{count}(|RR_{i+1} - RR_i| > 50 \text{ ms})}{N - 1} \times 100$$

### Physiological background

pNN50 counts what fraction of consecutive interval differences exceed 50 ms.
Like RMSSD, it primarily reflects **parasympathetic activity** and beat-to-beat
variability. The two metrics are highly correlated but not redundant: pNN50 is
more sensitive to the distribution tail (large beats differences).

### Reference values (5-minute resting supine)

| pNN50 (%) | Interpretation |
|-----------|----------------|
| < 5 | Very low |
| 5 – 15 | Low |
| 15 – 30 | Normal |
| > 30 | High |

### Notes

- **More sensitive to noise** than RMSSD: a single artefact pair with ΔRR > 50
  ms adds 1 to the count regardless of magnitude.
- Preferred for research comparisons where RMSSD distributions are non-normal;
  RMSSD is generally preferred for daily sports monitoring.

---

## mean_HR — Mean Heart Rate

**Field**: `mean_hr` | **Unit**: bpm

### Definition

$$\text{mean\_HR} = \frac{60{,}000}{\overline{RR}} \; \text{(bpm)}$$

where $\overline{RR}$ is the mean RR interval in milliseconds.

### Physiological background

Resting heart rate is one of the most accessible cardiovascular fitness markers.
Low resting HR is typically associated with high aerobic fitness and strong
parasympathetic regulation. High resting HR may indicate sympathetic activation
(stress, illness) or deconditioning.

### Reference values (resting supine)

| HR (bpm) | Interpretation |
|----------|----------------|
| < 40 | Very low — common in trained endurance athletes |
| 40 – 60 | Low-normal |
| 60 – 80 | Normal |
| 80 – 100 | Elevated — may indicate stress or deconditioning |
| > 100 | Tachycardia — medical evaluation recommended |

### Notes

- Resting HR is **strongly trainable**: years of endurance training can lower it
  by 10–20 bpm.
- An elevated HR on a normally low-HR day is an early signal of illness or
  recovery deficit — often visible before RMSSD changes.
