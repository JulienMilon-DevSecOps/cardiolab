# Orthostatic HRV Protocol

## Overview

The orthostatic protocol evaluates the cardiovascular and autonomic response to
a postural change — lying down to standing up. It reveals how the nervous system
dynamically regulates heart rate and vagal tone, providing insight into autonomic
flexibility, cardiovascular conditioning, and recovery state.

Unlike the resting protocol, it is not a daily measure. It is used periodically
to assess autonomic adaptability and detect conditions such as orthostatic
intolerance, sympathetic over-activation, or deconditioning.

---

## Principle

Changing posture from lying to standing triggers an immediate physiological
chain reaction:

1. Blood pools in the lower limbs, reducing venous return to the heart.
2. Cardiac output drops transiently, causing a brief fall in blood pressure.
3. The sympathetic nervous system activates to restore blood pressure: heart
   rate increases, vagal tone decreases.
4. Heart rate stabilises at a new, elevated standing level within 30–60 seconds.

Analysing the **amplitude**, **speed**, and **quality** of this response
characterises the state of the autonomic nervous system.

---

## Protocol structure

The recording spans three successive phases detected automatically by cardiolab:

```
Phase 1 — SUPINE          Phase 2 — TRANSITION       Phase 3 — STANDING
─────────────────────── │ ──────────────────────── │ ──────────────────
5 min lying (baseline)  │  Stand up → HR rises     │  5 min standing
                        │  until stabilisation     │  (new steady state)
```

| Phase | Duration | What is captured |
|-------|----------|-----------------|
| Supine | ≥ 4 min (5 recommended) | HRV baseline, sympatho-vagal balance |
| Transition | automatic (typically 20–60 s) | HR peak, delta HR, transition timing |
| Standing | ≥ 4 min (5 recommended) | New autonomic steady state |

---

## Recommended measurement frequency

| Frequency | Use case |
|-----------|----------|
| 1× / month | periodic autonomic health check |
| 1× / week | during an intensive training block |
| Before / after a training block | adaptation tracking |
| On suspicion of overtraining | targeted diagnostic |

This protocol is **not intended for daily use**. The resting protocol covers
daily monitoring; the orthostatic protocol answers the question: *how well does
my autonomic system respond to a cardiovascular challenge?*

---

## When to measure

* Morning, before any physical activity.
* At least **3 hours after the last training session** or intense effort.
* In a quiet, calm environment.
* Not during illness, fever, or severe fatigue — the test is then unreliable
  and should be postponed.

---

## Measurement procedure

### Step 1 — Supine phase (5 minutes)

1. Lie flat on your back, arms along your body.
2. Start the recording.
3. Breathe naturally. Remain still.
4. Do not speak, move, or check your phone.

### Step 2 — Stand up (transition)

5. At the 5-minute mark, **stand up smoothly** in one controlled movement (do
   not sit up first if possible — go directly from lying to standing).
6. Stand still. Keep the sensor on and do not pause the recording.

> Avoid sudden jerky movements: the transition detection algorithm looks for a
> sustained HR rise. A clean, single postural change gives the most reliable
> transition timestamp.

### Step 3 — Standing phase (5 minutes)

7. Stand still, feet shoulder-width apart.
8. Keep arms relaxed at your sides.
9. Breathe naturally.
10. Do not walk, shift weight, or lean against a wall.
11. Stop the recording after 5 minutes of standing.

---

## Position and movement

* **Supine**: strictly lying flat. Sitting up is not equivalent — it produces a
  weaker orthostatic stimulus and invalidates the clinical reference values.
* **Standing**: feet firmly on the floor, body upright. Avoid leaning or
  shifting weight from one foot to the other.
* Keep the sensor in contact at all times during the transition.

---

## Breathing

* Breathe naturally throughout both phases.
* Do not hold your breath when standing up — the Valsalva manœuvre this creates
  would distort the HR peak and alter the transition metrics.

---

## What to avoid

* Any movement during the supine or standing phases (shifts the HRV baseline).
* Pausing or stopping the recording during the transition.
* Sitting up before standing (reduces the orthostatic stimulus).
* Leaning against a wall or holding onto furniture during the standing phase.
* Measuring within 2 hours of a meal or caffeine intake.
* Measuring during psychological stress or acute illness.

---

## Computed metrics

### Phase metrics

Each of the three phases produces the full set of 15 HRV indicators (identical
to the resting protocol: RMSSD, SDNN, pNN50, mean HR, VLF, LF, HF, LF/HF,
HF%, LF_nu, HF_nu, HF/FC, duration, score).

### Transition metrics

| Metric | Description |
|--------|-------------|
| `delta_hr` | HR rise from supine baseline to transition peak (bpm) |
| `peak_hr` | Maximum instantaneous HR reached during the transition (bpm) |
| `transition_start_sec` | Timestamp of transition onset (s from recording start) |
| `transition_end_sec` | Timestamp of HR stabilisation (s from recording start) |
| `transition_duration_sec` | Duration of the transition window (s) |

### Derived orthostatic metrics

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| `hr_response` | HR standing − HR supine (bpm) | Magnitude of sympathetic activation |
| `lf_hf_ratio_change` | LF/HF standing ÷ LF/HF supine | Ratio > 1 → sympathetic shift on standing |
| `hf_response_pct` | (HF standing − HF supine) / HF supine × 100 | Relative vagal withdrawal (%) |
| `hf_hr_pct_change` | (HF/FC standing − HF/FC supine) / HF/FC supine × 100 | HR-normalised vagal withdrawal (%) |

---

## Interpreting results

### HR response (`hr_response`)

The heart rate increase from lying to standing is the primary autonomic reflex
indicator.

| HR rise | Clinical significance |
|---------|-----------------------|
| < 5 bpm | Impaired response — possible autonomic dysfunction or very high fitness |
| 5–30 bpm | Normal orthostatic response |
| > 30 bpm | Elevated response — possible POTS or deconditioning |

> **Note for athletes**: well-trained endurance athletes sometimes show HR rises
> at the upper end of the normal range (20–30 bpm) due to their low resting HR.
> This is physiological, not pathological.

### HF response (`hf_response_pct`)

HF power reflects parasympathetic (vagal) activity. It decreases on standing as
the sympathetic system takes over.

| HF change | Interpretation |
|-----------|----------------|
| −30 % to −50 % | Normal vagal withdrawal on standing |
| > −30 % (small drop) | Possible parasympathetic dominance or incomplete orthostatic response |
| < −60 % | Excessive vagal withdrawal — strong sympathetic activation |

### HF/FC change (`hf_hr_pct_change`)

HF/FC normalises vagal activity for heart rate, making it less sensitive to
baseline HR differences between individuals or between sessions.

| HF/FC change | Interpretation |
|--------------|----------------|
| −30 % to −80 % | Normal range |
| > −80 % | Strong sympathetic activation — monitor recovery state |
| Positive or near zero | Weak orthostatic response |

### LF/HF ratio change (`lf_hf_ratio_change`)

| Ratio | Interpretation |
|-------|----------------|
| ≈ 1 | No shift in autonomic balance on standing |
| > 1 | Sympathetic activation (normal on standing) |
| < 1 | Paradoxical parasympathetic dominance on standing (rare) |

### Clinical classifications

| `interpretation` | Criterion | Action |
|-----------------|-----------|--------|
| `normal` | HR rise 5–30 bpm | Normal response |
| `elevated_response` | HR rise > 30 bpm | Possible POTS — monitor, consider medical review |
| `impaired_response` | HR rise < 5 bpm | Possible autonomic dysfunction — consider medical review |
| `excessive_vagal_withdrawal` | HF drop > 60 % | Strong sympathetic dominance — check recovery and training load |

---

## Validity conditions

A measurement is considered reliable when:

* The supine phase lasted at least 4 minutes (5 recommended).
* The standing phase lasted at least 4 minutes (5 recommended).
* No movement artefacts disrupted either phase.
* The postural transition was performed in a single, clean movement.
* The sensor maintained stable contact throughout.
* The subject was not ill, under acute psychological stress, or recently
  medicated with beta-blockers or anti-arrhythmics.

---

## Tracking over time

A single orthostatic test is informative, but its value increases when compared
to a personal history:

* **After a recovery week**: HR response and HF/FC return towards baseline
  values → autonomic system has recharged.
* **During overreaching**: HR response decreases, HF/FC change weakens → the
  sympathetic system is blunted by accumulated fatigue.
* **After a training block**: progressive improvement in HR response and
  normalisation of HF/FC change → cardiovascular adaptation.

---

## Summary

The orthostatic protocol is a targeted autonomic stress test. Its primary
strength is revealing how quickly and effectively the nervous system shifts from
parasympathetic dominance (lying) to sympathetic activation (standing).

For athletes, it complements daily resting HRV by adding a dynamic dimension:
not just *how recovered are you?*, but *how reactive is your autonomic system
to a cardiovascular challenge?*
