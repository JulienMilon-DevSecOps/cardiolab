# Garmin — Export FIT et CSV / FIT and CSV Export

## Required Equipment / Matériel requis

**EN:** Any Garmin watch compatible with HRV recording: Fenix, Forerunner 255+, Venu 2+, Epix, or any model with ANT+/Bluetooth chest strap support.  
**FR:** Toute montre Garmin compatible HRV : Fenix, Forerunner 255+, Venu 2+, Epix, ou tout modèle avec ceinture ANT+/Bluetooth.

**EN:** Recommended chest strap: Garmin HRM-Pro, HRM-Dual, or Polar H10 (paired via ANT+) for accurate RR intervals. Without a chest strap, the optical wrist sensor is used — less accurate for high-frequency HRV analysis.  
**FR:** Ceinture thoracique recommandée : Garmin HRM-Pro, HRM-Dual, ou Polar H10 (appairée via ANT+) pour des intervalles RR précis. Sans ceinture, le capteur optique poignet est utilisé — moins précis pour l'analyse HF.

## Installation du support FIT / FIT Support Installation

**EN:** FIT file parsing requires the optional `fitparse` library:  
**FR:** Le parsing des fichiers FIT nécessite la bibliothèque optionnelle `fitparse` :

```bash
pip install cardiolab[garmin]
```

**EN:** CSV parsing (`parse_garmin_csv`) works without any additional dependency.  
**FR:** Le parsing CSV (`parse_garmin_csv`) fonctionne sans dépendance supplémentaire.

---

## Measurement Protocol / Protocole de mesure

### EN

1. **Morning, upon waking**, before any physical activity or caffeine.
2. Remain still for **5 minutes** (minimum 3 minutes).
3. Breathe naturally — do not control your breathing rate.
4. Activate HRV recording on the watch (see below).

### FR

1. **Le matin, au réveil**, avant toute activité physique ou caféine.
2. Rester immobile pendant **5 minutes** (3 minutes minimum).
3. Respiration naturelle — ne pas contrôler le rythme.
4. Activer l'enregistrement HRV sur la montre (voir ci-dessous).

---

## Activating HRV on the Watch / Activer la mesure HRV sur la montre

### EN

- **Fenix 7 / Forerunner 955**: Widgets → HRV Status → Measure Now
- **Via an activity**: create a "Meditation" or "Rest" activity of 5 min — the watch records RR intervals in the FIT file if a chest strap is connected.

### FR

- **Fenix 7 / Forerunner 955** : Widgets → Statut VFC → Mesurer maintenant
- **Via une activité** : créer une activité "Méditation" ou "Repos" de 5 min — la montre enregistre les intervalles RR dans le FIT si une ceinture thoracique est connectée.

> **EN:** Without a chest strap, the optical wrist sensor is used. Wrist optical intervals are less accurate for high-frequency (HF, DFA α1) analysis. Use HRM-Pro or HRM-Dual for complete HRV analysis.  
> **FR:** Sans ceinture thoracique, la montre utilise le capteur optique poignet. Les intervalles RR du capteur optique sont moins précis pour les hautes fréquences (HF, DFA α1). Utiliser une ceinture HRM-Pro ou HRM-Dual pour une analyse HRV complète.

---

## Extracting Data from Garmin Connect / Export depuis Garmin Connect

### FIT export (raw RR intervals) / Export FIT (intervalles RR bruts)

**EN**
1. Open **Garmin Connect** (web or app) → Activities.
2. Select the activity or rest session.
3. Click **⚙️ → Export to FIT** (web) or **Share → Export File** (app).
4. The downloaded file has the `.fit` extension.

**FR**
1. Ouvrir **Garmin Connect** (web ou app) → Activités.
2. Sélectionner l'activité ou la session de repos.
3. Cliquer sur **⚙️ → Exporter vers FIT** (web) ou **Partager → Exporter le fichier** (app).
4. Le fichier téléchargé porte l'extension `.fit`.

### CSV export (activity summary) / Export CSV (résumé d'activité)

**EN**
1. Garmin Connect (web) → Activities → select a time period.
2. Click **Export CSV**.
3. The CSV contains one row per activity with summary metrics (average HR, max HR).

> **EN:** For beat-to-beat RR intervals in CSV format, use a third-party tool (Kubios HRV, HRVanalysis) to export from the FIT file.  
> **FR:** Pour les intervalles RR en CSV beat-to-beat, utiliser un outil tiers (Kubios, HRVanalysis) pour exporter depuis le fichier FIT.

**FR**
1. Garmin Connect (web) → Activités → sélectionner une période.
2. Cliquer sur **Exporter CSV**.
3. Le CSV contient une ligne par activité avec les métriques résumées (FC moy, FC max).

---

## File Formats / Format des fichiers

### FIT — RR intervals / intervalles RR

**EN:** The `.fit` file is binary. RR intervals are stored in `hrv` messages:  
**FR:** Le fichier `.fit` est binaire. Les intervalles RR sont stockés dans les messages `hrv` :

| Field / Champ | Type | Description |
|---|---|---|
| `time` | `tuple[float]` | **EN:** RR intervals in **seconds** (multiply × 1000 for ms) / **FR:** Intervalles RR en **secondes** (× 1000 pour ms) |

### CSV — beat-to-beat RR (third-party / tiers)

**EN:** Third-party CSV format with a column containing "RR" in the name (auto-detected):  
**FR:** Format CSV tiers avec une colonne contenant "RR" dans le nom (détection automatique) :

```
Timestamp,RR Interval (ms),HR (bpm)
2026-01-10T07:30:00,800,75
2026-01-10T07:30:01,810,74
```

---

## Import into cardiolab / Import dans cardiolab

### Read RR intervals from FIT / Lire les intervalles RR depuis un FIT

```python
from cardiolab.sensors_tools.garmin import parse_garmin_fit
from cardiolab.features.time_domain import compute_time_domain

rr = parse_garmin_fit("datasets/raw/garmin/activity.fit").remove_outliers()
features = compute_time_domain(rr)
print(f"RMSSD : {features.rmssd:.1f} ms | SDNN : {features.sdnn:.1f} ms")
```

### Read RR intervals from CSV / Lire les intervalles RR depuis un CSV

```python
from cardiolab.sensors_tools.garmin import parse_garmin_csv

rr = parse_garmin_csv("datasets/raw/garmin/rr_export.csv").remove_outliers()
print(f"{len(rr)} intervalles | HR moyen : {rr.mean_hr:.0f} bpm")
```

### Extract training session summary / Extraire le résumé d'une session d'entraînement

```python
from cardiolab.sensors_tools.garmin import extract_training_session_garmin

session = extract_training_session_garmin("datasets/raw/garmin/activity.fit")
print(f"Durée : {session['duration_min']:.1f} min")
print(f"FC moy : {session['hr_mean']:.0f} bpm | FC max : {session['hr_max']:.0f} bpm")
```

---

## File Location / Emplacement des fichiers

```
cardiolab/datasets/
└── raw/
    └── garmin/
        ├── activity.fit          ← session FIT (HRV ou entraînement)
        └── rr_export.csv         ← CSV beat-to-beat (export tiers)
```

---

## Known Limitations / Limites connues

**EN**
- **Optical sensor**: wrist optical RR intervals are noisy above 0.15 Hz. Always call `remove_outliers()`.
- **FIT without HRV**: if the watch has no paired chest strap, the FIT may contain no `hrv` messages — `parse_garmin_fit()` raises `ValueError`.
- **Summary CSV**: CSVs exported from Garmin Connect contain only summary metrics (average HR, max HR), not beat-to-beat RR intervals. Only beat-to-beat CSVs (exported via Kubios or third-party tools) are compatible with `parse_garmin_csv()`.

**FR**
- **Capteur optique** : les intervalles RR du capteur optique poignet sont bruités pour les fréquences > 0.15 Hz. Le filtre `remove_outliers()` est indispensable.
- **FIT sans HRV** : si la montre n'a pas de ceinture thoracique associée, le FIT peut ne pas contenir de messages `hrv` — `parse_garmin_fit()` lèvera alors une `ValueError`.
- **CSV résumé** : les CSV exportés depuis Garmin Connect ne contiennent que des métriques résumées (FC moy, FC max), pas les intervalles RR. Seuls les CSV beat-to-beat (exportés via Kubios ou outils tiers) sont compatibles avec `parse_garmin_csv()`.
