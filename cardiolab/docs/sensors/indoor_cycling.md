# Indoor cycling — recording set-ups / Home-trainer : les branchements

**EN:** How to record power, heart rate and beat-to-beat intervals together on an indoor
trainer driven by a training app (MyWhoosh, Zwift, Wahoo SYSTM…).  
**FR :** Comment enregistrer ensemble la puissance, la fréquence cardiaque et les
battements sur un home-trainer piloté par une application d'entraînement (MyWhoosh,
Zwift, Wahoo SYSTM…).

---

## What each use needs / Ce dont chaque usage a besoin

| Use / Usage | Power / Puissance | Heart rate / FC | Beat intervals (RR) / Battements |
|---|---|---|---|
| Training session — load, time in zones / Séance : charge, temps par zone | optional / facultative | ✅ | — |
| Submaximal test (LSCT) / Test sous-maximal | ✅ | ✅ | — |
| **DFA α1 thresholds** / **Seuils DFA α1** | useful (power at the thresholds) / utile | ✅ | ✅ **chest strap required / ceinture obligatoire** |

> **EN:** Beat intervals only come from a **chest strap**. A watch's optical wrist sensor gives
> a usable heart rate, but not beat-accurate intervals: DFA α1 needs a strap (Rogers et al.
> 2021, see [`protocols/dfa_thresholds.md`](../protocols/dfa_thresholds.md)).  
> **FR :** Les battements ne viennent que d'une **ceinture cardio**. Le capteur optique d'une
> montre donne une FC correcte, mais pas des battements assez précis : le DFA α1 exige une
> ceinture.

---

## Set-up A — everything through the app / Tout passe par l'application

```
Indoor trainer ──(control + power)──► training app ──► .fit (power + heart rate)
Watch or strap ──(heart rate)─────────┘
```

**EN**
- Usual set-up: the app drives the trainer; the watch broadcasts its heart rate (or the strap
  is paired) to the app.
- Gives **power + heart rate**, never beat intervals: training apps do not record them.
- Enough for training sessions and the LSCT, **not for DFA thresholds**.
- **Download the file from the app itself.** With MyWhoosh (mywhoosh.com → profile →
  activities), the file exported by the app had the heart rate, while the copy exported from
  Strava for the same session did not (observed on one session, November 2026). Check that
  the heart rate is in the file you import.

**FR**
- Installation habituelle : l'application pilote le home-trainer ; la montre diffuse sa FC (ou
  la ceinture est connectée) vers l'application.
- Donne **puissance + FC**, jamais les battements : les applications d'entraînement ne les
  enregistrent pas.
- Suffit pour les séances et le LSCT, **pas pour les seuils DFA**.
- **Téléchargez le fichier depuis l'application elle-même.** Avec MyWhoosh (mywhoosh.com →
  profil → activités), le fichier exporté par l'application contenait la FC, alors que la copie
  exportée depuis Strava pour la même séance ne la contenait pas (constaté sur une séance,
  novembre 2026). Vérifiez que la FC est dans le fichier importé.

---

## Set-up B — the watch records too (threshold tests) / La montre enregistre aussi (tests de seuils)

```
Indoor trainer ──(control)───────────────► training app   (route, workouts — unchanged)
      └──(power, read only, ANT+)──► watch ──► .fit (heart rate + RR + power + cadence)
Chest strap ─────────────────────────► watch
```

**EN — once, on the watch:**
1. Pair the **chest strap**.
2. Pair the trainer **as a power sensor**, **not as a smart trainer**: otherwise the watch may
   try to control the resistance against the app. The simplest is the watch reading the
   trainer over **ANT+** while the app controls it over Bluetooth — ANT+ accepts several
   listeners, many trainers accept a single Bluetooth connection.
3. Turn on **HRV logging** (on Garmin devices, a « log HRV » option in the heart rate sensor or
   data recording settings — the exact name depends on the model).

**EN — for each test:**
1. Put the strap on.
2. Start an **indoor cycling** activity on the watch, then the session in the app.
3. Stop both at the end; import the **watch's** `.fit` (Garmin Connect: export original).
- The app keeps its heart rate: many straps accept several connections at once (ANT+ to the
  watch, Bluetooth to the app), or the watch broadcasts it during the activity.
- **Duplicates**: the session is recorded twice — turn off the upload of one of them to Strava.

**FR — une fois, sur la montre :**
1. Associer la **ceinture cardio**.
2. Associer le home-trainer **comme capteur de puissance**, **pas comme home-trainer
   connecté** : sinon la montre peut essayer de piloter la résistance contre l'application. Le
   plus simple : la montre lit le home-trainer en **ANT+** pendant que l'application le pilote
   en Bluetooth — l'ANT+ accepte plusieurs récepteurs, beaucoup de home-trainers une seule
   connexion Bluetooth.
3. Activer l'**enregistrement de la VFC** (sur Garmin, une option « enregistrer la VFC » dans
   les réglages du capteur cardio ou de l'enregistrement des données — le nom dépend du modèle).

**FR — à chaque test :**
1. Mettre la ceinture.
2. Lancer une activité **vélo d'intérieur** sur la montre, puis la séance dans l'application.
3. Arrêter les deux à la fin ; importer le `.fit` **de la montre** (Garmin Connect : exporter le
   fichier original).
- L'application garde sa FC : beaucoup de ceintures acceptent plusieurs connexions (ANT+ vers
  la montre, Bluetooth vers l'application), ou la montre la diffuse pendant l'activité.
- **Doublons** : la séance est enregistrée deux fois — désactivez l'envoi de l'une vers Strava.

---

## Set-up C — merge two files / Fusionner deux fichiers *(planned / prévu)*

**EN:** power from the app's file, heart rate and beat intervals from the watch's file,
aligned on their timestamps — for sessions already recorded when the watch recorded an
activity with the strap. Not implemented yet (cardiolab v0.6.0, in progress).  
**FR :** la puissance du fichier de l'application, la FC et les battements du fichier de la
montre, calés sur leur horodatage — pour les séances déjà faites, si la montre avait
enregistré une activité avec la ceinture. Pas encore disponible (cardiolab v0.6.0, en cours).

---

## Import into cardiolab / Import dans cardiolab

```python
from cardiolab.protocols import dfa_thresholds
from cardiolab.sensors_tools import (
    extract_training_session_garmin,
    parse_fit_records,
    parse_garmin_fit,
)

# Session summary — set-up A or B (heart rate optional since 0.6.0)
session = extract_training_session_garmin("2026-11-05_ride.fit")
# {'duration_min': 83.6, 'hr_mean': 128.1, 'hr_max': 161.0,
#  'power_mean': 145.3, 'power_max': 484.0, 'sport': 'cycling', ...}

# Per-second samples: power, heart rate, cadence, speed
records = parse_fit_records("2026-11-05_ride.fit")
records.has("heart_rate"), records.has("power")

# DFA thresholds — set-up B: beats and power from the same watch file
rr = parse_garmin_fit("2026-11-12_ramp.fit")
result = dfa_thresholds(rr, intensity=records.intensity("power"), intensity_unit="W")
```

**EN**
- `parse_fit_records()` reads any FIT activity (Garmin, MyWhoosh…). Missing fields are `nan`; a
  heart rate of 0 is a sensor drop-out (`nan`), a power or cadence of 0 is kept
  (freewheeling).
- The beat intervals of a FIT file carry no timestamps: cardiolab takes them as starting with
  the activity's first record — true when both come from the same file (set-up B).
- Only the per-second timestamps are used: the summary dates of some apps are inconsistent
  (MyWhoosh: session end equal to its start, local time in 2046).

**FR**
- `parse_fit_records()` lit toute activité FIT (Garmin, MyWhoosh…). Les champs absents valent
  `nan` ; une FC à 0 est une coupure du capteur (`nan`), une puissance ou une cadence à 0 est
  conservée (roue libre).
- Les battements d'un FIT n'ont pas d'horodatage : cardiolab les fait commencer au premier
  enregistrement de l'activité — exact quand les deux viennent du même fichier (montage B).
- Seuls les horodatages seconde par seconde sont utilisés : les dates de résumé de certaines
  applications sont incohérentes (MyWhoosh : fin de séance égale au début, heure locale en
  2046).
