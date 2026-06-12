# HRV4Training — Export CSV

## Required Equipment / Matériel requis

**EN:** The **HRV4Training** app (iOS or Android) with at least one recorded session. A compatible sensor: Bluetooth chest strap (most accurate) or the phone's front camera (less accurate — uses camera PPG).  
**FR:** Application **HRV4Training** (iOS ou Android) avec au moins une session enregistrée. Un capteur compatible : ceinture thoracique Bluetooth (plus précis) ou caméra frontale du téléphone (moins précis — utilise la PPG caméra).

## Installation

No extra dependency — the HRV4Training parser is included in the base package.  
Aucune dépendance supplémentaire — le parser HRV4Training est inclus dans le package de base.

```bash
pip install cardiolab
```

---

## Measurement Protocol / Protocole de mesure

### EN

1. **Morning, upon waking**, before any physical activity or caffeine.
2. Open HRV4Training → press the large **HRV** button.
3. Place the **front camera** on your fingertip (or use the chest strap if paired).
4. Remain still for **60 seconds** (app default) — do not breathe differently.
5. The app records the session and computes RMSSD and HRV Score automatically.

**With a chest strap (recommended):**
- Pair a Bluetooth chest strap (Polar H10, Wahoo Tickr) in Settings → Connect Device.
- The app will automatically use the chest strap instead of the camera for more accurate RR intervals.

### FR

1. **Le matin, au réveil**, avant toute activité physique ou caféine.
2. Ouvrir HRV4Training → appuyer sur le grand bouton **HRV**.
3. Placer la **caméra frontale** sur le bout du doigt (ou utiliser la ceinture thoracique si appairée).
4. Rester immobile pendant **60 secondes** (durée par défaut) — ne pas modifier sa respiration.
5. L'app enregistre la session et calcule le RMSSD et le HRV Score automatiquement.

**Avec ceinture thoracique (recommandé) :**
- Appairer une ceinture Bluetooth (Polar H10, Wahoo Tickr) dans Réglages → Connecter un appareil.
- L'app utilisera automatiquement la ceinture plutôt que la caméra pour des intervalles RR plus précis.

---

## Extracting Data from HRV4Training / Export depuis HRV4Training

### EN

1. Open HRV4Training → **Profile** (bottom tab) → **Export data**.
2. Select **Export CSV**.
3. Choose the date range (or "All time").
4. Share the file via email, AirDrop, or Files app.  
   The default filename is `hrv4training_export.csv`.

> **Important:** The standard CSV export contains summary metrics (rMSSD, HRV Score, resting HR).  
> Raw RR intervals are included **only if** the option *Export raw RR data* is enabled in the app settings (Settings → Data → Export raw RR data).

### FR

1. Ouvrir HRV4Training → **Profil** (onglet bas) → **Exporter les données**.
2. Sélectionner **Exporter CSV**.
3. Choisir la plage de dates souhaitée (ou "Toutes les données").
4. Envoyer le fichier par e-mail, AirDrop ou via l'app Fichiers.  
   Le nom par défaut est `hrv4training_export.csv`.

> **Important :** l'export CSV standard contient les métriques résumées (rMSSD, HRV Score, FC au repos).  
> Les intervalles RR bruts sont inclus **uniquement si** l'option *Exporter les données RR brutes* est activée dans les réglages de l'app (Réglages → Données → Exporter les données RR brutes).

---

## File Format / Format du fichier

```
date,rMSSD,Readiness,rMSSD Recording,HRV Score,resting HR,RR intervals
2026-01-10,55.2,8.0,55.2,72,56,800;810;795;820;805
2026-01-11,48.3,6.5,,65,58,
2026-01-12,61.0,8.5,61.0,75,54,830;840;825;815;835
```

| Column / Colonne | Type | Description |
|---|---|---|
| `date` | YYYY-MM-DD | Measurement date / Date de la mesure |
| `rMSSD` | float (ms) | RMSSD from the session / RMSSD de la session |
| `resting HR` | int (bpm) | Resting heart rate / FC au repos |
| `RR intervals` | str | Semicolon-separated RR intervals in ms (optional) / Intervalles RR en ms séparés par `;` (optionnel) |

---

## Import into cardiolab / Import dans cardiolab

### Read all sessions / Lire toutes les sessions

```python
from cardiolab.sensors_tools.hrv4training import parse_hrv4training_csv

records = parse_hrv4training_csv("datasets/raw/hrv4training/hrv4training_export.csv")

for rec in records:
    print(rec["date"], rec["rmssd"])
```

### Convert to RRSeries (if RR available) / Convertir en RRSeries (si RR disponibles)

```python
from cardiolab.sensors_tools.hrv4training import parse_hrv4training_csv, to_rrseries

records = parse_hrv4training_csv("datasets/raw/hrv4training/hrv4training_export.csv")

for rec in records:
    if rec["rr_intervals"]:
        rr = to_rrseries(rec)
        print(f"{rec['date']} — {len(rr)} intervals, mean HR {rr.mean_hr:.0f} bpm")
    else:
        print(f"{rec['date']} — summary only (RMSSD = {rec['rmssd']} ms)")
```

### Compute full HRV features / Calculer les features HRV complètes

```python
from cardiolab.features.time_domain import compute_time_domain
from cardiolab.sensors_tools.hrv4training import parse_hrv4training_csv, to_rrseries

records = parse_hrv4training_csv("datasets/raw/hrv4training/hrv4training_export.csv")

for rec in records:
    if rec["rr_intervals"]:
        rr = to_rrseries(rec).remove_outliers()
        features = compute_time_domain(rr)
        print(f"{rec['date']} — RMSSD recomputed: {features.rmssd:.1f} ms")
```

---

## File Location / Emplacement des fichiers

```
cardiolab/datasets/
└── raw/
    └── hrv4training/
        └── hrv4training_export.csv
```

---

## Known Limitations / Limites connues

**EN**
- **Summary-only export**: most HRV4Training exports contain only summary metrics (`rMSSD`, `HRV Score`, etc.), not raw RR intervals. In that case, `rec["rr_intervals"]` is `None` and `to_rrseries()` raises `ValueError`. SDNN, HF, DFA α1, and entropy metrics cannot be computed — only the app-provided `rMSSD` is available.
- **Lossy RMSSD**: the `rMSSD` exported by HRV4Training is rounded to one decimal. For precision analysis, prefer raw RR intervals.
- **Encoding**: some exports contain a UTF-8 BOM — the parser handles this automatically.

**FR**
- **Export résumé sans RR** : la majorité des exports HRV4Training ne contiennent que les métriques résumées (`rMSSD`, `HRV Score`, etc.), pas les intervalles RR bruts. Dans ce cas, `rec["rr_intervals"]` vaut `None` et `to_rrseries()` lève une `ValueError`. Il n'est alors pas possible de recalculer SDNN, HF, DFA α1 ou les entropies — seul le `rMSSD` fourni par l'app est disponible.
- **RMSSD lossy** : le `rMSSD` exporté par HRV4Training est arrondi à une décimale. Pour une analyse de précision, préférer les intervalles RR bruts.
- **Encodage** : certains exports contiennent un BOM UTF-8 — le parser le gère automatiquement.
