# Cardiac Data Measurement Guide

## Overview

This guide explains how to correctly record cardiac data to obtain reliable
HRV analyses in cardioanalysis. Data quality has a direct impact on the
accuracy of every downstream metric and score.

---

## Why data quality matters

HRV analysis is highly sensitive to noise and measurement artefacts.
A poor-quality recording can produce completely misleading results, regardless
of how sophisticated the analysis pipeline is.

---

## Types of cardiac data

### 1. RR intervals (recommended)

Time between two consecutive heartbeats, in milliseconds.

* Most accurate input for HRV analysis.
* Directly consumed by the cardiolab pipeline.

### 2. Heart rate (HR)

Beats per minute averaged over a short window.

* Easy to measure with most consumer devices.
* Less precise for HRV: the averaging process discards beat-to-beat timing.

### 3. ECG signal

Raw electrical signal of the heart.

* Highest precision — R-peaks can be detected at sample-level accuracy.
* Allows direct extraction of RR intervals.

---

## Measurement devices

### Chest straps (ECG-based) — recommended

Examples: Polar H10, Garmin HRM-Pro

* Very high accuracy.
* Ideal for HRV analysis.
* Recommended for this project.

### Smartwatches (PPG-based)

Examples: Apple Watch, Garmin, Fitbit

* Convenient and accessible.
* Less accurate, especially for HRV — optical pulse detection introduces noise.

### Clinical ECG devices

* Maximum precision.
* Not practical for daily tracking.

---

## Which data to use in cardioanalysis

Priority order:

1. **RR intervals** — ideal, direct pipeline input.
2. **ECG** → converted to RR via R-peak detection.
3. **HR** → converted to RR (least reliable — use only as a fallback).

Any conversion introduces a loss of precision.

---

## Best practices

* Measure at rest — never immediately after exercise.
* Stay still throughout the recording.
* Use the same device every session.
* Record at the same time each day (ideally upon waking).
* Avoid disturbances: noise, movement, bright light.

---

## Common mistakes to avoid

* Measuring after physical or emotional stress.
* Switching devices between sessions (breaks baseline continuity).
* Moving during measurement.
* Comparing your values directly with another person's values.

---

## Summary

* Data quality is critical — it cannot be compensated for in software.
* RR intervals are the best input data.
* Consistency across sessions matters more than absolute precision.
