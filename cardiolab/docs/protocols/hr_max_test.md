# HRmax — field test and HRmax observed in sessions

Added in v0.10.0. Modules: `cardiolab.protocols.hr_max_test` (field test) and
`cardiolab.analytics.hr_max` (held peak, observed HRmax, profile update proposal).

## Why measure it

The maximal heart rate feeds many calculations:

| Uses HRmax | How |
|---|---|
| Training zones without thresholds | 55 / 72 / 82 / 87 / 92 / 100 % of HRmax ([zones](dfa_thresholds.md)) |
| Load « FC de séance » (Banister) | Intensity = (HR − HRrest) / (HRmax − HRrest) |
| VO2max estimate (Uth) | 15.3 × HRmax / HRrest |
| LSCT targets | 60 / 80 / 90 % of HRmax ([lsct](lsct.md)) |

Predicted from the age (Tanaka: `208 − 0.7 × age`), it is off by about **±10 bpm** for one
person — almost a whole zone. Better sources, from the most reliable:

| `hr_max_source` | Where it comes from |
|---|---|
| `field_test` | This test, done all-out with a chest strap |
| `provided` | Entered by the athlete (laboratory test, known value) |
| `observed` | Highest heart rate held 5 s in the imported sessions — a **lower bound** |
| `tanaka` | Predicted from the age |

HRmax depends on the sport: usually **5–10 bpm lower on the bike** than running. The sport
is stored with every value. It does not improve with training and declines slowly with
age: measure again at least every 3 years, in each sport you follow.

---

## Before the test — safety

> **An all-out effort.** Ask a doctor first if you are over 35–40 and do not exercise hard
> regularly, or if you have a heart condition, high blood pressure, diabetes, or symptoms on
> exertion (chest pain, unusual breathlessness, dizziness, fainting) — the ACSM
> pre-participation screening (Riebe et al. 2015). Do it rested, never when ill or after a
> heavy week. **Stop at once** if you feel pain, dizziness or unwell. cardiolab is not a
> medical device.

## Equipment

- A **chest strap** — required. Optical (wrist) sensors lose the beat at high intensity
  (Gillinov et al. 2017): a test recorded with one is `invalid`.
- A hill of a few minutes, or a treadmill at 6–10 % incline (running); the same structure
  on the bike, with the resistance.

## Procedure (Olympiatoppen, intensity scale 2024)

| Phase | Duration | Intensity |
|---|---|---|
| Warm-up | 15 min | Easy to moderate |
| Repetition 1 | 3 min | Hard, uphill |
| Easy jog | 2 min | Recovery |
| Repetition 2 | 3 min | Harder |
| Easy jog | 2 min | Recovery |
| Repetition 3 | 3 min | +0.5 km/h every minute, **to exhaustion** |
| Cool-down | 10 min | Easy |

Keep the recording running until the end of the cool-down.

## Recording

```python
from cardiolab.protocols import hr_max_test
from cardiolab.sensors_tools import parse_fit_records

res = hr_max_test(records=parse_fit_records("2026-09-02_hrmax.fit"), sensor="chest_strap")
res.hr_max              # 189 bpm — highest heart rate held 5 s
res.sport, res.date     # 'running', '2026-09-02' (read from the file)
res.final_effort_sec    # 140 s at ≥ 90 % of the peak before it
res.plateau_reached     # True
res.status              # 'valid' · 'doubtful' · 'invalid'
res.can_update_profile  # True only when valid
```

With other series: `hr_max_test(time_sec, heart_rate, sport="running", sensor=...)`.
Chart: `plot_hr_max_test(time_sec, heart_rate, res, profile_hr_max=185)`; over time:
`plot_hr_max_history(tests, observed=..., profile_hr_max=...)`.

## How it is computed

- **Held 5 s**: values outside 30–230 bpm and jumps of more than 25 bpm in one second
  (sensor drop-outs) removed; the heart rate resampled to 1 s (gaps ≤ 10 s interpolated);
  a 3-sample median removes an isolated
  beat; then the **minimum over each 5-s window** — a value counts only if it was reached for
  the whole 5 seconds. HRmax = the highest of these. A spike of 1 to 4 s never passes; when the
  raw maximum is more than 5 bpm above the held one, a warning reports it (artefact).
- **Final effort**: time held ≥ 90 % of the peak just before it — at least **60 s**.
- **Plateau**: the held heart rate stays within 3 bpm of the peak for at least **20 s**
  around it. A heart rate still climbing steeply when the effort stops has not reached its
  maximum.
- `valid` = chest strap (or not given — a warning recalls it) + final effort + plateau;
  `doubtful` = a criterion is missing: the value is reported, **not proposed** for the
  profile; `invalid` = optical sensor.

---

## HRmax observed in sessions

Many athletes never do a maximal test but sometimes reach a very high heart rate in a race.

```python
from cardiolab.analytics import observed_hr_max

best = observed_hr_max(fit_records_list)          # or dicts: time_sec, heart_rate, sport, date…
best["running"].hr_max, best["running"].date      # 188 bpm, '2026-09-06'
best["cycling"].hr_max                            # sports kept apart
```

Same « held 5 s » rule. Sessions recorded with an optical sensor can be flagged
(`"optical": True`) — the value is marked less reliable — or left out
(`include_optical=False`).

**From the database, without the files** (migration V010): the peak of each session is
computed at import and stored with it (`hrv_training_sessions.hr_peak`, and
`hr_peak_optical`).

```python
from cardiolab.sensors_tools import extract_training_session_garmin

s = extract_training_session_garmin("2026-11-09_lsct.fit")   # s["hr_peak"] → 170.0
repo.save_training_session(user_id, "2026-11-09", s["duration_min"], s["sport"],
                           hr_mean=s["hr_mean"], hr_peak=s["hr_peak"], hr_peak_optical=False)

best = repo.observed_hr_max(user_id)          # {sport: ObservedHRMax}, session_id = activity_id
```

Sessions imported before v0.10.0 have no peak: import their file again, or fill it with
`update_training_session(activity_id, hr_peak=...)`. `observed_from_peaks(rows)` does the
same from any list of stored sessions.

**Smart recording**: many watches store a sample every few seconds. The heart rate is
resampled to 1 s first (gaps up to 10 s interpolated, longer ones left empty), so a plateau
sampled every 5 s still counts as held 5 s.

---

## Updating the profile — proposed, never applied

```python
from cardiolab.analytics import propose_hr_max_update

p = propose_hr_max_update(
    185, res.hr_max, source="field_test", current_source="provided",
    hr_rest=56, load_method="banister",
)
p.propose      # True — higher than the profile HRmax
p.changes      # what it would change:
# zone5_top      {'old': 185, 'new': 189}
# general_zones  old / new bounds of the 5 zones
# lsct_targets   {'old': [111, 148, 167], 'new': [113, 151, 170]}
# lsct_comparable False — the next LSCT becomes the new reference
# vo2max_uth     {'old': 50.5, 'new': 51.6}
# reprocess_load True — « FC de séance » loads to recompute
```

| Profile HRmax | New value | Proposed? |
|---|---|---|
| Empty, or predicted from the age (`tanaka`) | Any | Yes — a measurement beats a prediction |
| Entered, tested or observed | Higher | Yes |
| Entered, tested or observed | Equal or lower | **No** — an observed HRmax is a lower bound; a test below a known value was probably not all-out. The athlete can still lower it by hand |

Only when the athlete accepts:

```python
with HRVRepository.from_env() as repo:
    repo.save_hr_max_test(res, user_id)                       # the test is always stored
    repo.update_user_profile(user_id, hr_max=189, hr_max_source="field_test")
    # then reprocess_sessions(...) if p.changes["reprocess_load"]
```

Storage: table `hrv_hr_max_tests` and column `user_profiles.hr_max_source`, migration
`V009__hr_max.sql`; per-session peaks `hrv_training_sessions.hr_peak` /
`hr_peak_optical`, migration `V010__session_hr_peak.sql`.

## Limitations

- Depends on the motivation of the day: a test that is not quite all-out underestimates
  HRmax.
- Checked on synthetic sessions; not yet on a real test.
- Not wired yet: the peak of a DFA α1 incremental test run to exhaustion is also an HRmax
  measurement.

## References

- Olympiatoppen (2024). *Olympiatoppen's intensity scale*, version 2.
- Tanaka, H., Monahan, K. D., & Seals, D. R. (2001). Age-predicted maximal heart rate
  revisited. *Journal of the American College of Cardiology*, 37(1), 153–156.
- Robergs, R. A., & Landwehr, R. (2002). The surprising history of the "HRmax = 220 − age"
  equation. *Journal of Exercise Physiology Online*, 5(2), 1–10.
- Riebe, D., et al. (2015). Updating ACSM's recommendations for exercise preparticipation
  health screening. *Medicine & Science in Sports & Exercise*, 47(11), 2473–2479.
- Gillinov, S., et al. (2017). Variable accuracy of wearable heart rate monitors during
  aerobic exercise. *Medicine & Science in Sports & Exercise*, 49(8), 1697–1703.
