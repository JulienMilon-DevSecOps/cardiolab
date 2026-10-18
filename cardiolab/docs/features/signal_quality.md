# Signal quality — `SignalQuality`

Added in v0.4.0. Module: `cardiolab.signals.quality`.

A score only means something if the signal behind it is sound. Every session
analysed by `resting_hrv()`, `orthostatic_hrv()`, `cardiac_coherence()` and
`vo2max_from_hrv()` now carries a quality index:

```python
features = resting_hrv(rr, auto_clean=True)
features.quality
# SignalQuality(grade='good', artifact_pct=0.31, corrected=True,
#               n_beats=321, effective_duration=331.6)
```

| Field | Meaning |
|-------|---------|
| `grade` | `good`, `acceptable` or `poor` |
| `artifact_pct` | Share of beats flagged as artefacts (%) |
| `corrected` | `True` if the artefacts were corrected before analysis (`auto_clean=True`) |
| `n_beats` | RR intervals analysed |
| `effective_duration` | Duration of the analysed signal (s) |

---

## Grading

| Situation | `good` | `acceptable` | `poor` |
|-----------|--------|--------------|--------|
| Artefacts **corrected** | < 2 % | 2 – 5 % | ≥ 5 % |
| Artefacts detected, **not corrected** | none found | — | at least one |

- **Corrected**: above 5 % of corrected beats the recording should be measured
  again (Lipponen & Tarvainen 2019) — the same threshold as the
  `PhysiologicalWarning` of `correct_artifacts()`.
- **Not corrected**: a single artefact left in the signal can distort every
  metric based on successive differences. On the sample of 2026-04-24, one
  missed beat in 320 (0.3 %) gives RMSSD 78.5 ms instead of 41.1 ms once
  corrected. Without `auto_clean`, any artefact found therefore makes the
  session `poor`.

Thresholds are configurable:

```python
from cardiolab.signals.quality import signal_quality

signal_quality(rr, good_max=1.0, acceptable_max=3.0)
```

`signal_quality(rr)` reads the correction report that `correct_artifacts()`
stores in `rr.metadata["artifact_correction"]`; on an uncorrected series it
runs the artefact detection (Lipponen & Tarvainen 2019, without correcting).

---

## Orthostatic test — one index per phase

Movement artefacts are frequent when standing up. Each phase is graded on the
artefacts that fall within its own time window:

```python
result = orthostatic_hrv(rr, auto_clean=True)
result.phases.supine.features.quality    # used by the readiness score
result.phases.standing.features.quality
result.quality                           # whole recording
```

An artefact while standing therefore does not exclude the supine phase — the
one used as the main daily measurement — from the baseline.

---

## Baseline — `poor` sessions left out

`Baseline` ignores `poor` sessions in every statistic (median RMSSD, mean HR,
rolling medians, DFA α1…), so that a faulty recording does not shift the
personal reference. `trend_rmssd()` and `detect_rmssd_anomaly()` follow the
same rule.

```python
baseline = Baseline.from_features(history)
baseline.sessions    # sessions used
baseline.excluded    # poor sessions left out
Baseline.from_features(history, include_poor=True)  # previous behaviour
```

Sessions stored before v0.4.0 have no quality index (`quality=None`): their
quality is **unknown**, and they are kept.

The readiness score of a `poor` session is still computed — but it should be
read with caution, and the session will not count in the following days'
baseline.

---

## Storage — migration V005

A `quality JSONB` column is added to `hrv_features`, `hrv_orthostatic`,
`hrv_coherence` and `hrv_vo2max`:

```json
{"grade": "good", "artifact_pct": 0.31, "corrected": true,
 "n_beats": 321, "effective_duration": 331.6}
```

`hrv_orthostatic` stores one object per phase:
`{"overall": …, "supine": …, "transition": …, "standing": …}`.

Apply it with `repo.run_migrations()` (or `python local/main_init_db.py`).
Existing rows keep `NULL`. Heart rate recovery and cardiac drift are based on
heart rate averages, robust to isolated artefacts, and are not graded.

---

## Reports and charts

- History tables (resting, orthostatic, coherence, VO2max) show a
  **Signal quality** column (green / orange / red, `n/a` when unknown), translated
  with `LABELS_FR`.
- Evolution charts (`plot_resting_evolution`, `plot_resting_evolution_rolling`,
  `plot_readiness_evolution`, `plot_score_evolution`,
  `plot_coherence_score_evolution`, `plot_vo2max_evolution`,
  `plot_orthostatic_dual_score_evolution`) put a **red cross** on `poor`
  sessions.
- `to_dict()` exports flatten the index into `quality_grade`,
  `quality_artifact_pct`, `quality_corrected`, `quality_n_beats`,
  `quality_effective_duration`.

---

## Reference

Lipponen, J. A., & Tarvainen, M. P. (2019). A robust algorithm for heart rate
variability time series artefact correction using novel beat classification.
*Journal of Medical Engineering & Technology*, 43(3), 173–181.
