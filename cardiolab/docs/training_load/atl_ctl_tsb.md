# ATL / CTL / TSB — Training Load Model

## Purpose

The ATL/CTL/TSB model quantifies three interdependent physiological states:

| Metric | Full name | Represents | Tau |
|--------|-----------|------------|-----|
| **ATL** | Acute Training Load | Short-term fatigue | 7 days |
| **CTL** | Chronic Training Load | Long-term fitness | 42 days |
| **TSB** | Training Stress Balance | Current form = CTL − ATL | — |

The model was introduced by Banister et al. (1975, 1991) and refined by
Morton et al. (1990) under the name "impulse-response model".  
It is widely used in endurance sports (cycling, running, triathlon) to plan
training blocks and predict performance readiness.

---

## The TRIMP — Training Impulse

TRIMP is the daily load unit. It translates a training session into a single
dimensionless number that feeds ATL and CTL. cardiolab offers three methods —
**use one method consistently for a given athlete**: their scales differ, and
ATL / CTL built from a mix of them are meaningless (see
[Which method?](#which-method)).

### HRV-based TRIMP (primary method in cardiolab)

```
TRIMP = duration_min × (1 − readiness / 100)
```

| Variable | Source | Meaning |
|----------|--------|---------|
| `duration_min` | `training_sessions.duration_min` | Workout duration in minutes |
| `readiness` | HRV protocol score (0–100) | Athlete's recovery state that day |

**Interpretation of the formula:**

- If `readiness = 100` (fully recovered) → `TRIMP = 0`: same effort, minimal
  physiological cost.
- If `readiness = 0` (severely stressed) → `TRIMP = duration_min`: maximum cost.
- A 60-minute run with readiness 70 → `TRIMP = 60 × 0.30 = 18`.
- The same 60-minute run with readiness 30 → `TRIMP = 60 × 0.70 = 42`.

This approach captures the insight that the same external load has a very
different physiological impact depending on the athlete's recovery state.
It is **cardiolab's heuristic**, not a published method: it weighs the session
by the morning state, not by the intensity of the effort itself. Published
individualised loads (e.g. the iTRIMP of Manzi et al. 2009) weigh the effort
heart rate instead — see Banister below.

### Banister TRIMP (fallback for HR-sensor data)

When an HR sensor provides effort heart rate but no HRV readiness is available:

```
TRIMP = duration_min × HRR_ratio × e^(b × HRR_ratio)
```

Where:
- `HRR_ratio = (HR_mean − HR_rest) / (HR_max − HR_rest)` — heart rate reserve fraction
- `b = 1.92` for men, `1.67` for women (sex-specific weighting from Banister 1991)

> Reference: Banister EW. (1991). *Modeling elite athletic performance.*  
> In: Green HJ, McDougal JD, Wenger HA (Eds.), Physiological Testing of the
> High-Performance Athlete. Champaign: Human Kinetics, pp. 403–424.

### Session RPE (all sports, no heart rate) — added in v0.5.0

```
load = duration_min × RPE
```

The athlete rates the **whole session** about 30 minutes after it ends, on the
CR-10 scale (Foster et al. 2001):

| RPE | Effort |
|-----|--------|
| 0 | Rest |
| 1 | Very, very easy |
| 2 | Easy |
| 3 | Moderate |
| 4 | Somewhat hard |
| 5–6 | Hard |
| 7–9 | Very hard |
| 10 | Maximal |

A 60-minute session rated 5 gives 300 arbitrary units (AU). `trimp_session_rpe()`
validates the RPE (whole number 0–10); `save_training_session(..., rpe=)` stores
it (column `rpe`, migration V006).

> Reference: Foster C, Florhaug JA, Franklin J, et al. (2001). A new approach to
> monitoring exercise training. *J Strength Cond Res*, 15(1), 109–115.

### Which method?

| | HRV-based | Banister | Session RPE |
|---|---|---|---|
| Formula | duration × (1 − readiness / 100) | duration × HRR × e^(b × HRR) | duration × RPE (0–10) |
| Needs | Morning HRV measurement | Effort heart rate, HR max, HR rest | The athlete's rating after the session |
| Sports | All | Endurance (steady efforts) | **All** — strength, intervals, team sports |
| Weighs | The athlete's state that morning | The intensity of the effort | The perceived intensity of the effort |
| 60 min session | 0 – 60 | ≈ 50 – 200 | 0 – 600 AU |
| Limits | Ignores the intensity of the session; cardiolab heuristic | Underestimates strength work and short intervals (HR lags behind) | Subjective; needs a rating every session |
| Evidence | — | Banister 1991 | Foster et al. 2001 — widely validated across sports |

Choose the method from the data the athlete will provide **every session**, and
keep it: changing method changes the scale of ATL / CTL / TSB.

---

## Protocol consistency rule

**The readiness score feeding TRIMP must come from a single, stable protocol.**

| Rule | Reason |
|------|--------|
| Choose `"resting"` **or** `"orthostatic"` at setup | Each protocol builds a personal baseline (rolling mean ± SD of RMSSD). Mixing two baselines pollutes the distribution and produces wrong readiness scores. |
| Never cross-use the two protocols | A resting RMSSD of 52 ms is not comparable to an orthostatic supine RMSSD of 52 ms without re-normalisation. |
| Switching protocol resets the readiness series | Historical TRIMP values remain valid; new values start a fresh baseline. |

When `"orthostatic"` is the primary protocol, the **supine phase**
(not the ΔHR orthostatic score) is used as the readiness input; its score de
forme is stored with the session (`readiness_score`, migration V006 — v0.5.0)
and read back by `load_readiness_for_date(..., baseline=None, ...)`. The supine
phase is physiologically equivalent to a resting measurement and preserves
day-to-day variability. The orthostatic score (ΔHR) is stable in healthy
athletes and is a poor fatigue indicator.

---

## ATL — Acute Training Load (7-day EMA)

```
ATL(t) = TRIMP(t) × k_a  +  ATL(t-1) × (1 − k_a)
```

```
k_a = 1 − e^(−1/τ_a)    with  τ_a = 7
```

`k_a ≈ 0.1331` — each day contributes ~13 % of the new value;
the previous ATL carries ~87 %.

ATL rises quickly after intense training blocks and decays fast during rest.
It represents short-term fatigue accumulated over the past ~7 days.

**Initial condition:** `ATL(0) = 0` (or the last known value when resuming
from a saved state).

---

## CTL — Chronic Training Load (42-day EMA)

```
CTL(t) = TRIMP(t) × k_c  +  CTL(t-1) × (1 − k_c)
```

```
k_c = 1 − e^(−1/τ_c)    with  τ_c = 42
```

`k_c ≈ 0.0235` — the 42-day filter responds slowly to day-to-day changes.

CTL rises over training blocks lasting weeks or months and decays slowly during
detraining. It represents the accumulated fitness (aerobic capacity, structural
adaptations) built by consistent training.

**Important:** CTL does not become meaningful until ~6 weeks of data (one time
constant). Interpret CTL values from a short history with caution.

---

## TSB — Training Stress Balance

```
TSB(t) = CTL(t) − ATL(t)
```

TSB is the difference between fitness and fatigue on any given day.

### TSB zones

| TSB | Zone | Athlete state |
|-----|------|--------------|
| > +25 | Fresh / detraining | High form but fitness may be declining; risk of detraining if prolonged |
| +5 to +25 | Optimal | Peak performance window; ideal for competition or key sessions |
| −10 to +5 | Neutral | Normal training state; manageable fatigue |
| −30 to −10 | Accumulated fatigue | Functional overreaching; adaptation stimulus present |
| < −30 | Overload | Non-functional overreaching; injury and illness risk elevated |

> Reference: Coggan A. (2003). *Training and racing using a power meter.*  
> Originally applied to cycling power but validated for HRV-based load in
> Plews DJ et al. (2013).

---

## Rest days

On days with no training session, `TRIMP = 0`.

The EMA formulas still apply:

```
ATL(t) = 0 × k_a + ATL(t-1) × (1 − k_a)  =  ATL(t-1) × (1 − k_a)
CTL(t) = CTL(t-1) × (1 − k_c)
```

Because `τ_a < τ_c`, ATL decays **faster** than CTL during rest. TSB therefore
rises automatically on recovery days — which is the intended physiological
interpretation (fatigue clears faster than fitness is lost).

The TRIMP time series must be **dense** (one value per day, even if zero) for
the EMA to be correct. Gaps in the series must be filled with zeros before
computing ATL and CTL.

---

## Full computation flow

```
1. Load training sessions from DB → list[dict] (sorted by date ASC)
2. Build a daily TRIMP series:
   - Fill gaps between first and last session with TRIMP = 0
   - Replace NULL trimp with 0 (session logged but readiness not yet available)
3. Compute ATL:   ATL[0] = 0; ATL[i] = TRIMP[i] * k_a + ATL[i-1] * (1 - k_a)
4. Compute CTL:   CTL[0] = 0; CTL[i] = TRIMP[i] * k_c + CTL[i-1] * (1 - k_c)
5. Compute TSB:   TSB[i] = CTL[i] - ATL[i]
6. Return DataFrame: date | trimp | atl | ctl | tsb
```

The `TrainingLoad` class (v0.2.0 — Phase 3) encapsulates steps 2–6.

---

## Numerical example

Starting from zero, training daily with TRIMP = 40 for 14 days:

| Day | TRIMP | ATL | CTL | TSB |
|-----|-------|-----|-----|-----|
| 1 | 40 | 5.3 | 0.9 | −4.4 |
| 7 | 40 | 24.9 | 6.1 | −18.8 |
| 14 | 40 | 33.4 | 11.7 | −21.7 |

Then 7 rest days (TRIMP = 0):

| Day | TRIMP | ATL | CTL | TSB |
|-----|-------|-----|-----|-----|
| 15 | 0 | 29.0 | 11.5 | −17.5 |
| 18 | 0 | 19.0 | 11.0 | −8.0 |
| 21 | 0 | 12.4 | 10.6 | −1.8 |

After 7 rest days, ATL drops by ~63 % while CTL drops by only ~15 % —
TSB moves from −21.7 to −1.8, approaching the optimal zone.

---

## Data requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| History to interpret ATL | 2 weeks | 4 weeks |
| History to interpret CTL | 6 weeks | 3 months |
| History for TSB planning | 2 months | 6 months |
| Session frequency | ≥ 3 sessions/week | Daily logging |

---

## References

- Banister EW et al. (1975). A systems model of training for athletic performance.  
  *Aust J Sports Med*, 7, 57–61.
- Banister EW. (1991). Modeling elite athletic performance. In: *Physiological
  Testing of the High-Performance Athlete*. Human Kinetics, pp. 403–424.
- Morton RH et al. (1990). Modeling human performance in running.  
  *J Appl Physiol*, 69(3), 1171–1177.
- Manzi V et al. (2009). Dose–response relationship of autonomic nervous system
  responses to individualized training impulse in marathon runners.
  *J Strength Cond Res*, 23(9), 2722–2729.
- Plews DJ et al. (2012). Heart rate variability in elite triathletes, is variation
  in variability the key to effective training? A case comparison.
  *Eur J Appl Physiol*, 112(11), 3729–3741.
- Foster C et al. (2001). A new approach to monitoring exercise training.
  *J Strength Cond Res*, 15(1), 109–115.
- Coggan A. (2003). *Training and racing using a power meter* (internal
  TrainingPeaks document — widely cited in endurance sport literature).
