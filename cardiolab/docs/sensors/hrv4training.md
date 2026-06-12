# HRV4Training — Export CSV

## Matériel requis

- Application **HRV4Training** (iOS ou Android) avec au moins une session enregistrée.
- Un capteur compatible : ceinture thoracique Bluetooth ou capteur optique (résultats moins précis avec la caméra).

---

## Procédure d'export

1. Ouvrir HRV4Training → **Profil** → **Export data**.
2. Sélectionner **Export CSV**.
3. Choisir la plage de dates souhaitée (ou "All time").
4. Envoyer le fichier par e-mail ou AirDrop — le nom par défaut est `hrv4training_export.csv`.

> **Note :** l'export CSV standard contient les métriques résumées (rMSSD, score, HR au repos).
> Les intervalles RR bruts sont inclus **uniquement si** l'option *Export raw RR data* est activée
> dans les réglages de l'app.

---

## Format du fichier

```
date,rMSSD,Readiness,rMSSD Recording,HRV Score,resting HR,RR intervals
2026-01-10,55.2,8.0,55.2,72,56,800;810;795;820;805
2026-01-11,48.3,6.5,,65,58,
2026-01-12,61.0,8.5,61.0,75,54,830;840;825;815;835
```

| Colonne | Type | Description |
|---|---|---|
| `date` | YYYY-MM-DD | Date de la mesure |
| `rMSSD` | float (ms) | RMSSD de la session |
| `resting HR` | int (bpm) | Fréquence cardiaque au repos |
| `RR intervals` | str | Intervalles RR en ms, séparés par `;` (optionnel) |

---

## Import dans cardiolab

### Lire toutes les sessions

```python
from cardiolab.sensors_tools.hrv4training import parse_hrv4training_csv

records = parse_hrv4training_csv("hrv4training_export.csv")

for rec in records:
    print(rec["date"], rec["rmssd"])
```

### Convertir en RRSeries (si RR disponibles)

```python
from cardiolab.sensors_tools.hrv4training import parse_hrv4training_csv, to_rrseries

records = parse_hrv4training_csv("hrv4training_export.csv")

for rec in records:
    if rec["rr_intervals"]:
        rr = to_rrseries(rec)
        print(f"{rec['date']} — {len(rr)} intervalles, HR moyen {rr.mean_hr:.0f} bpm")
    else:
        print(f"{rec['date']} — résumé uniquement (RMSSD = {rec['rmssd']} ms)")
```

### Calculer les features HRV complètes

```python
from cardiolab.features.time_domain import compute_time_domain
from cardiolab.sensors_tools.hrv4training import parse_hrv4training_csv, to_rrseries

records = parse_hrv4training_csv("hrv4training_export.csv")

for rec in records:
    if rec["rr_intervals"]:
        rr = to_rrseries(rec).remove_outliers()
        features = compute_time_domain(rr)
        print(f"{rec['date']} — RMSSD recalculé : {features.rmssd:.1f} ms")
```

---

## Limites connues

- **Export résumé sans RR** : la majorité des exports HRV4Training ne contiennent que les métriques résumées (`rMSSD`, `HRV Score`, etc.), pas les intervalles RR bruts. Dans ce cas, `rec["rr_intervals"]` vaut `None` et `to_rrseries()` lève une `ValueError`. Il n'est alors pas possible de recalculer SDNN, HF, DFA α1 ou les entropies — seul le `rMSSD` fourni par l'app est disponible.
- **RMSSD lossy** : le `rMSSD` exporté par HRV4Training est arrondi à une décimale. Pour une analyse de précision, préférer les intervalles RR bruts.
- **Encodage** : certains exports contiennent un BOM UTF-8 — le parser le gère automatiquement.
