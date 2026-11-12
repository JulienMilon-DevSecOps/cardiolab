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
3. Turn on **HRV logging**. On recent Garmin watches: *Settings → System → Data Recording →
   Log HRV*; set the *Recording Interval* to *Every Second* in the same menu if it is offered
   (the default "smart" recording writes a sample only every 1–15 s, sometimes more). Menu
   names vary with the model and firmware.
4. Check after a first session: the watch file must contain `hrv` messages
   (`parse_garmin_fit()` raises `ValueError` otherwise). Pairing the strap alone is not
   enough — a file recorded with the strap but without HRV logging has the heart rate only
   (observed, November 2026).

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
3. Activer l'**enregistrement de la VFC**. Sur les montres Garmin récentes : *Paramètres →
   Système → Enregistrement des données → Enregistrer la VFC* ; dans le même menu, régler
   l'*intervalle d'enregistrement* sur *Chaque seconde* s'il est proposé (l'enregistrement
   « intelligent » par défaut n'écrit un point que toutes les 1 à 15 s, parfois plus). Les noms
   des menus varient selon le modèle et la version du logiciel.
4. Vérifier après une première séance : le fichier de la montre doit contenir des messages
   `hrv` (sinon `parse_garmin_fit()` lève `ValueError`). Associer la ceinture ne suffit pas :
   un fichier enregistré avec la ceinture mais sans la VFC n'a que la FC (constaté en novembre
   2026).

**FR — à chaque test :**
1. Mettre la ceinture.
2. Lancer une activité **vélo d'intérieur** sur la montre, puis la séance dans l'application.
3. Arrêter les deux à la fin ; importer le `.fit` **de la montre** (Garmin Connect : exporter le
   fichier original).
- L'application garde sa FC : beaucoup de ceintures acceptent plusieurs connexions (ANT+ vers
  la montre, Bluetooth vers l'application), ou la montre la diffuse pendant l'activité.
- **Doublons** : la séance est enregistrée deux fois — désactivez l'envoi de l'une vers Strava.

---

## Set-up C — merge two files / Fusionner deux fichiers

```
Indoor trainer ──(control + power)──► training app ──► .fit (power, cadence)
Chest strap ──(heart rate)──► watch (indoor cycling activity) ──► .fit (heart rate [+ RR])
                                   └──── merge_fit_records() ────┘
```

**EN**
- Two recordings of the same session: the app records the power, the watch records the heart
  rate from the strap (and the beat intervals if HRV logging is on). Nothing to pair between
  the trainer and the watch.
- `merge_fit_records(watch, app)` aligns them on their **timestamps** and resamples every
  second over the period both cover. Each series comes from the first file that has it (heart
  rate from the watch, power and cadence from the app). Gaps up to 30 s are interpolated
  (smart recording), longer ones stay missing.
- Clocks: **do not trust them blindly**. On the author's test of 2026-11-12, the start time
  written by MyWhoosh was 40 s late, and its time drifted from the watch's: about 35 s lost
  over 15 min, irregularly. Check the alignment on the plot: the heart rate must rise a few
  seconds *after* each power increase and start falling as soon as you stop pedalling.
- Correction: locate two **landmarks** in both files (seconds since the start of each): the
  first pedal stroke (power rises in the app; heart rate rises on the watch a few seconds
  later), and stopping pedalling (heart rate starts to fall). `align_from_anchors(watch, app,
  [(watch_s, app_s), (watch_s, app_s)])` returns the offset and the time scale for
  `merge_fit_records(..., second_offset_sec=, second_time_scale=)`. The correction is linear:
  an irregular drift is only averaged between the landmarks.
- For the LSCT, add `clock="second"` (the stages were timed on the app's screen) and
  `span="all"` (keeps the seated recovery the watch recorded after the app stopped or
  paused). By default (`span="overlap"`), only the seconds both files cover are kept.
- Enough for training sessions and the LSCT. For DFA thresholds, the beats still come from the
  watch file (HRV logging on).

**FR**
- Deux enregistrements de la même séance : l'application enregistre la puissance, la montre
  la FC de la ceinture (et les battements si la VFC est activée). Rien à associer entre le
  home-trainer et la montre.
- `merge_fit_records(montre, application)` les cale sur leur **horodatage** et les rééchantillonne
  chaque seconde sur la période couverte par les deux. Chaque série vient du premier fichier
  qui la contient (FC de la montre, puissance et cadence de l'application). Les trous jusqu'à
  30 s sont interpolés (enregistrement intelligent), les plus longs restent vides.
- Horloges : **ne pas s'y fier les yeux fermés**. Au test de l'auteur du 12/11/2026, l'heure de
  début écrite par MyWhoosh avait 40 s de retard, et son temps dérivait par rapport à celui de
  la montre : environ 35 s perdues en 15 min, de façon irrégulière. Vérifiez le recalage sur
  le graphique : la FC doit monter quelques secondes *après* chaque hausse de puissance, et
  commencer à baisser dès l'arrêt du pédalage.
- Correction : repérez deux **repères** dans les deux fichiers (secondes depuis le début de
  chacun) : le premier coup de pédale (la puissance monte dans l'application, la FC monte sur
  la montre quelques secondes après) et l'arrêt du pédalage (la FC commence à baisser).
  `align_from_anchors(montre, application, [(s_montre, s_appli), (s_montre, s_appli)])` donne
  le décalage et l'échelle de temps pour `merge_fit_records(..., second_offset_sec=,
  second_time_scale=)`. La correction est linéaire : une dérive irrégulière est seulement
  moyennée entre les repères.
- Pour le LSCT, ajoutez `clock="second"` (les paliers ont été chronométrés sur l'écran de
  l'application) et `span="all"` (garde la récupération assise enregistrée par la montre
  après l'arrêt ou la pause de l'application). Par défaut (`span="overlap"`), seules les
  secondes couvertes par les deux fichiers sont gardées.
- Suffit pour les séances et le LSCT. Pour les seuils DFA, les battements viennent toujours du
  fichier de la montre (VFC activée).

---

## Import into cardiolab / Import dans cardiolab

```python
from cardiolab.protocols import dfa_thresholds, lsct_from_records
from cardiolab.sensors_tools import (
    extract_training_session_garmin,
    align_from_anchors,
    merge_fit_records,
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

# Set-up C — heart rate from the watch, power from the app
watch = parse_fit_records("2026-11-12_hometrainer_garmin_lsct.fit")
app = parse_fit_records("2026-11-12_hometrainer_mywhoosh_lsct.fit")
# Landmarks: first pedal stroke (watch 40 s / app 2 s), stop at 15:00 (watch 905 s / app 902 s)
offset, scale = align_from_anchors(watch, app, [(40, 2), (905, 902)])  # → -1.9 s, 0.961
merged = merge_fit_records(
    watch, app, second_offset_sec=offset, second_time_scale=scale,
    clock="second", span="all",
)
# The merged time counts app seconds from the watch start: stage 1 (app second 0)
# is 39 merged seconds in (the watch started about 38 real seconds before the app)
app_zero = (app.start - merged.start).total_seconds() + offset  # real seconds
lsct_result = lsct_from_records(merged, hr_max=180, start_sec=round(app_zero / scale))
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
