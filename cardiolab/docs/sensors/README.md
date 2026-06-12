# Sensor Integrations — cardiolab / Intégrations capteurs — cardiolab

**EN:** This section documents how to collect HRV data from each supported device and import it into cardiolab.  
**FR:** Cette section documente comment collecter des données HRV depuis chaque appareil supporté et les importer dans cardiolab.

---

## Compatibility table / Tableau de compatibilité

| Device / Appareil | Format | Raw RR | RMSSD | SDNN | Resting HR | Parser | Extra dependency |
|---|---|---|---|---|---|---|---|
| **Polar H10** | `.txt` | ✅ | ✅ | ✅ | ❌ | `parse_rr_file` | — |
| **HRV4Training** | `.csv` | ✅ | ✅ | ❌ | ✅ | `parse_hrv4training_csv` | — |
| **Apple Watch** (Health XML) | `.xml` | ❌ | ❌ | ✅ | ✅ | `parse_apple_health_export` | — |
| **Garmin** (FIT) | `.fit` | ✅ | ✅ | ✅ | ❌ | `parse_garmin_fit` | `cardiolab[garmin]` |
| **Garmin** (CSV beat-to-beat) | `.csv` | ✅ | ✅ | ✅ | ❌ | `parse_garmin_csv` | — |

> **Raw RR** = beat-to-beat intervals available (required for RMSSD, pNN50, DFA).  
> **RMSSD / SDNN** = computable from this source.  
> **Extra dependency** = `pip install <value>` if not base install.

---

## Sensor documentation / Documentation par capteur

- [Polar H10](polar.md) — chest strap, best accuracy / ceinture thoracique, meilleure précision
- [HRV4Training](hrv4training.md) — camera-based app, no extra hardware / app caméra, sans matériel
- [Apple Health](apple_health.md) — Apple Watch export, SDNN only / export Apple Watch, SDNN uniquement
- [Garmin](garmin.md) — FIT/CSV, requires chest strap for raw RR / FIT/CSV, ceinture requise pour RR bruts

---

## Quick start / Démarrage rapide

```python
# Polar H10 — full RR access / accès RR complet
from cardiolab.sensors_tools import parse_rr_file
rr = parse_rr_file("datasets/raw/polar/session.txt").remove_outliers()

# HRV4Training — RR + RMSSD from CSV
from cardiolab.sensors_tools import parse_hrv4training_csv, to_rrseries
records = parse_hrv4training_csv("datasets/raw/hrv4training/export.csv")
rr = to_rrseries(records[0])

# Apple Health — SDNN only / SDNN uniquement
from cardiolab.sensors_tools import extract_hrv_samples
samples = extract_hrv_samples("datasets/raw/apple_health/export.xml")
# samples[0] → {"date": ..., "sdnn": float, "rmssd": None}

# Garmin FIT — requires fitparse / nécessite fitparse
# pip install cardiolab[garmin]
from cardiolab.sensors_tools import parse_garmin_fit
rr = parse_garmin_fit("datasets/raw/garmin/activity.fit").remove_outliers()
```

---

## Dataset structure / Structure des datasets

```
cardiolab/datasets/
└── raw/
    ├── polar/          ← Polar H10 .txt files
    ├── hrv4training/   ← HRV4Training .csv exports
    ├── apple_health/   ← Apple Health export.xml
    ├── garmin/         ← Garmin .fit files / CSV beat-to-beat
    ├── resting/        ← processed resting sessions (JSON)
    └── orthostatic/    ← processed orthostatic sessions (JSON)
```
