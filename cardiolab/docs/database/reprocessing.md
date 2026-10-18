# Reprocessing the history — `reprocess_sessions()`

Added in v0.4.0. Module: `cardiolab.database.reprocess`.

v0.4.0 changes computed values: artefacts are corrected instead of deleted,
Lomb-Scargle is the default spectral method, every session gets a signal
quality index. Without reprocessing, the history would mix two pipelines and
distort baselines, scores and trends.

The raw RR intervals of every session are kept in `hrv_raw_sessions` (since
v0.1.0). `reprocess_sessions()` recomputes the stored results from them.

---

## Migration from v0.3.x

1. Upgrade cardiolab, then apply the migrations (V005 adds the `quality`
   column):

   ```python
   with HRVRepository.from_env() as repo:
       repo.run_migrations()
   ```

2. Dry run — see what would change:

   ```python
   from cardiolab.database import HRVRepository, reprocess_sessions

   with HRVRepository.from_env() as repo:
       report = reprocess_sessions(repo, user_id)
   print(report.summary())
   ```

3. Write:

   ```python
   with HRVRepository.from_env() as repo:
       report = reprocess_sessions(repo, user_id, dry_run=False)
   ```

Local pipeline: `python local/main_reprocess.py` (dry run), then `--apply`.
Example: `examples/16_reprocess_history.py`.

---

## What it does

For each session of `hrv_raw_sessions`, in chronological order:

1. The raw RR series is analysed with `analyse_session()` — the same pipeline
   as an import:

   | Protocol | Analysis |
   |----------|----------|
   | resting, orthostatic | `auto_clean=True` (artefact correction), `method="lomb"` |
   | coherence, VO2max | RR series corrected first (`correct_artifacts()`) |
   | HRR, cardiac drift | as recorded (heart-rate based) |

2. The score is recomputed with `session_score()`. The resting readiness
   score uses a baseline made of the **previous** sessions, already
   reprocessed (`poor` sessions excluded); the other protocols use absolute
   thresholds.
3. The result replaces the stored one (upsert on `(user_id, date)`).

VO2max sessions keep the `hr_max` of their stored estimation (Uth model);
`hr_max=` provides one for estimations that have none.

---

## Guarantees

| Point | Behaviour |
|-------|-----------|
| Dry run | Default (`dry_run=True`): report only, nothing written |
| Transaction | Writes happen inside the caller's `with HRVRepository` block — committed together at the end, rolled back on any database error |
| Idempotence | A second run reports every session as `unchanged` and writes nothing |
| Failed analysis | Session reported `failed` (e.g. no orthostatic transition); its stored row is kept |
| No raw RR | Stored sessions without raw intervals (Apple Health import, SDNN only) are listed in `report.skipped`, left untouched — and still used in the resting baseline |
| `since=` | Only sessions on or after the date are reprocessed; earlier ones still feed the baseline |

---

## Report

```python
report.summary()
# Reprocessing (dry run — nothing written, spectral method: lomb)
#   resting       42 sessions — 41 changed, 0 unchanged, 1 new, 0 failed, 2 without raw RR
#   orthostatic   12 sessions — 12 changed, 0 unchanged, 0 new, 0 failed, 0 without raw RR

report.sessions[0].deltas()     # {"rmssd": (78.5, 41.1), "score": (50.0, 61.2), …}
report.to_rows()                # one row per session and metric, with % change
report.count("changed"); report.written; report.skipped
```

Compared metrics per protocol: `KEY_METRICS` (e.g. resting: RMSSD, mean HR,
HF, LF/HF, DFA α1, SampEn, score) plus the quality grade.

---

## Parameters

| Parameter | Default | Effect |
|-----------|---------|--------|
| `protocol` | `None` (all) | One protocol only |
| `since` | `None` | First date reprocessed (ISO) |
| `dry_run` | `True` | `False` to write |
| `method` | `"lomb"` | Spectral method for resting and orthostatic |
| `auto_clean` | `True` | Artefact correction before analysis |
| `hr_max` | `None` | Maximal HR for VO2max estimations without one |
