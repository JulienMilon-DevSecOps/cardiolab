# Sports — reference list

`cardiolab.sports` defines once the sports known to cardiolab: a stable **code**
(stored in the `sport_type` column of training sessions), English and French
**labels**, a chart **colour** and a **family**. Added in v0.3.4.

```python
from cardiolab.sports import get_sport, list_sports, normalize_sport

normalize_sport("Course à pied")        # "running"
normalize_sport("VTT")                  # "mountain_bike"
normalize_sport("running", "trail")     # Garmin FIT sport + sub-sport → "trail"
normalize_sport("pétanque")             # "other"

get_sport("cycling").label_fr           # "Vélo"
[s.code for s in list_sports("endurance")]
```

---

## The list

| Code | English | French | Family | Colour |
|------|---------|--------|--------|--------|
| `running` | Running | Course à pied | Endurance | `#e74c3c` |
| `trail` | Trail running | Trail | Endurance | `#d35400` |
| `cycling` | Cycling | Vélo | Endurance | `#2980b9` |
| `mountain_bike` | Mountain biking | VTT | Endurance | `#1f618d` |
| `swimming` | Swimming | Natation | Endurance | `#1abc9c` |
| `rowing` | Rowing | Aviron | Endurance | `#16a085` |
| `hiking` | Hiking | Randonnée | Endurance | `#7d6608` |
| `walking` | Walking | Marche | Endurance | `#b7950b` |
| `cross_country_skiing` | Cross-country skiing | Ski de fond | Endurance | `#5dade2` |
| `strength` | Strength training | Renforcement | Strength & fitness | `#8e44ad` |
| `hiit` | HIIT | HIIT | Strength & fitness | `#c0392b` |
| `yoga` | Yoga | Yoga | Strength & fitness | `#af7ac5` |
| `football` | Football | Football | Team & racket sports | `#27ae60` |
| `basketball` | Basketball | Basketball | Team & racket sports | `#e67e22` |
| `tennis` | Tennis | Tennis | Team & racket sports | `#f1c40f` |
| `alpine_skiing` | Alpine skiing | Ski alpin | Other | `#85c1e9` |
| `other` | Other | Autre | Other | `#95a5a6` |

The six colours used by the charts before v0.3.4 (running, trail, cycling,
swimming, rowing, strength) are unchanged.

---

## Normalising names — `normalize_sport(value, sub_sport=None)`

Matching ignores case, accents and separators. It accepts:

* the **codes** (`"running"`), the **English** and **French labels**
  (`"Mountain biking"`, `"Course à pied"`);
* common **synonyms** (`"run"`, `"vélo"`, `"VTT"`, `"musculation"`, `"soccer"`…);
* **Garmin FIT** `sport` values, refined by `sub_sport` when the pair is known
  (`running` + `trail` → `trail`, `cycling` + `mountain` → `mountain_bike`,
  `training` + `strength_training` → `strength`).

Anything else gives `"other"`. Empty or `None` gives `"other"`.

---

## Saving a session — `validate_sport(value)`

`HRVRepository.save_training_session()` validates the sport **before writing**:

* a code, a label or a known synonym is stored **as its code**
  (`"Course à pied"` → `"running"`);
* `None` (or empty) is allowed: no sport;
* anything else is **rejected** with a `ValueError` that suggests the closest
  sport — a typo never reaches the database:

```python
repo.save_training_session(user_id, "2026-08-25", 52, sport_type="runing")
# ValueError: Unknown sport 'runing'. Did you mean 'running'? Use a code of …
```

`find_training_sessions(sport_type=...)` accepts the same names.

Interfaces should offer the reference list itself (`list_sports()`, grouped by
family) rather than a free text field.

**Sessions saved before v0.3.4** keep their original text (cardiolab never
rewrites stored values). Charts still colour them correctly through
`normalize_sport()`; to clean them once, read each row, apply
`normalize_sport()` and update `sport_type`.

---

## Where it is used

| Place | Use |
|-------|-----|
| `extract_training_session_garmin()` | Returns `"sport"` (normalised code) and `"sport_raw"` (FIT value) |
| `plot_trimp_history()` | Bar colours by sport; a stored name that is not a code (`"Course à pied"`) gets its sport colour, an unknown sport gets the `other` colour, a session without sport keeps the default colour; `sport_colors` still overrides |
| `labels.py` | Keys `sport_<code>` and `sport_family_<code>` in `LABELS_EN` / `LABELS_FR` — e.g. French legend with `labels=LABELS_FR` |

Sport has **no effect on the load calculation**: the TRIMP methods
(`trimp_hrv_based`, `trimp_banister`) are the same for every sport. An
effort-based load valid for all sports (session RPE) is planned for v0.5.0.

---

## Families

| Code | English | French |
|------|---------|--------|
| `endurance` | Endurance | Endurance |
| `strength` | Strength & fitness | Force et fitness |
| `team_racket` | Team & racket sports | Sports collectifs et de raquette |
| `other` | Other | Autre |
