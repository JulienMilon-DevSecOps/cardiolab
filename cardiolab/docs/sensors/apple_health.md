# Apple Health — Export XML (iPhone / Apple Watch)

## Required Equipment / Matériel requis

**EN:** iPhone with the Health app (iOS 12+). Apple Watch Series 1+ for automatic HRV measurements (Series 4+ recommended for better measurement frequency).  
**FR:** **iPhone** avec l'application Santé (iOS 12+). **Apple Watch Series 1+** pour les mesures HRV automatiques (Series 4+ recommandé pour la fréquence de mesure).

---

## ⚠️ Important Warning / Avertissement important

> **EN:** The standard Apple Health XML export does **NOT** contain raw RR intervals — only SDNN (pre-computed by watchOS). The `rmssd` field is always `None`. For a full HRV analysis, use Polar H10, HRV4Training, or Garmin with a chest strap.  
> **FR:** L'export standard Apple Health XML ne contient **pas les intervalles RR bruts** — seulement le SDNN pré-calculé par watchOS. Le champ `rmssd` est toujours `None`. Pour une analyse HRV complète, utiliser Polar H10, HRV4Training ou Garmin avec ceinture.

---

## Measurement Protocol / Protocole de mesure

### EN

Apple Watch measures HRV automatically — no user action required during the night or in the morning:

1. Wear your Apple Watch while sleeping.
2. The watch automatically records HRV (SDNN) during sleep stages and in the morning before you get up.
3. In the Health app → Heart → Heart Rate Variability, you can see the daily SDNN values.

For more consistent morning measurements:
- Stay still for a few minutes after waking before getting out of bed.
- The watch measures HRV during the first minutes after waking.

### FR

L'Apple Watch mesure le VFC automatiquement — aucune action requise pendant la nuit ou le matin :

1. Porter l'Apple Watch pendant le sommeil.
2. La montre enregistre automatiquement le VFC (SDNN) pendant les phases de sommeil et le matin au réveil.
3. Dans l'app Santé → Cœur → Variabilité de la fréquence cardiaque, les valeurs SDNN quotidiennes sont visibles.

Pour des mesures matinales plus consistantes :
- Rester immobile quelques minutes après le réveil avant de se lever.
- La montre mesure le VFC pendant les premières minutes après le réveil.

---

## Extracting Data from iPhone / Export depuis l'iPhone

### EN

1. Open the **Health** app → profile icon (top right).
2. Scroll down to **Export All Health Data**.
3. Confirm the export — iPhone generates an `export.zip` archive.
4. Transfer the archive to your computer (AirDrop, iCloud, email).
5. Unzip the archive: the `export.xml` file is at the root.

> The file can be large (several hundred MB for years of data). Only HRV (`SDNN`) and resting heart rate records are parsed by cardiolab — other data types are ignored.

### FR

1. Ouvrir l'application **Santé** → icône de profil (en haut à droite).
2. Faire défiler jusqu'à **Exporter les données de santé**.
3. Confirmer l'export — l'iPhone génère une archive `export.zip`.
4. Transférer l'archive sur votre ordinateur (AirDrop, iCloud, email).
5. Décompresser l'archive : le fichier `export.xml` se trouve à la racine.

> Le fichier peut être volumineux (plusieurs centaines de Mo pour des années de données). Seuls les enregistrements HRV (SDNN) et FC au repos sont parsés par cardiolab — les autres types de données sont ignorés.

---

## File Format / Format du fichier

```xml
<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="fr_FR">
  <Record type="HKQuantityTypeIdentifierHeartRateVariabilitySDNN"
          sourceName="Apple Watch de Julien"
          unit="ms"
          startDate="2026-01-10 07:30:00 +0100"
          endDate="2026-01-10 07:30:00 +0100"
          value="45.2"/>
  <Record type="HKQuantityTypeIdentifierRestingHeartRate"
          sourceName="Apple Watch de Julien"
          unit="count/min"
          startDate="2026-01-10 07:30:00 +0100"
          endDate="2026-01-10 07:30:00 +0100"
          value="56"/>
  <!-- Other data types (steps, distance, sleep…) — ignored by cardiolab -->
</HealthData>
```

| Record type / Type de Record | Metric / Métrique | Unit / Unité |
|---|---|---|
| `HKQuantityTypeIdentifierHeartRateVariabilitySDNN` | SDNN | ms |
| `HKQuantityTypeIdentifierRestingHeartRate` | Resting HR / FC au repos | count/min |

---

## Import into cardiolab / Import dans cardiolab

### Read all raw HRV records / Lire tous les enregistrements HRV bruts

```python
from cardiolab.sensors_tools.apple_health import parse_apple_health_export

records = parse_apple_health_export("datasets/raw/apple_health/export.xml")

for rec in records:
    if rec["sdnn"] is not None:
        print(f"{rec['date']} — SDNN = {rec['sdnn']:.1f} ms ({rec['source']})")
```

### Extract daily summary / Extraire un résumé par jour

```python
from cardiolab.sensors_tools.apple_health import extract_hrv_samples

samples = extract_hrv_samples("datasets/raw/apple_health/export.xml")

for s in samples:
    print(f"{s['date']} — SDNN moyen = {s['sdnn']:.1f} ms")
```

---

## File Location / Emplacement des fichiers

```
cardiolab/datasets/
└── raw/
    └── apple_health/
        └── export.xml      ← décompresser export.zip depuis l'iPhone
```

---

## Known Limitations / Limites connues — Lossy Export

**EN:** The standard Apple Health XML export contains only pre-computed metrics:

| Available / Disponible | Not available / Non disponible |
|---|---|
| SDNN (ms) | Raw RR intervals / Intervalles RR bruts |
| Resting HR (bpm) | RMSSD |
| | HF / LF power |
| | DFA α1, entropies |

**EN:** Practical consequences:
- `rec["rmssd"]` is always `None` in cardiolab exports.
- It is **impossible** to recompute RMSSD, frequency-domain metrics, or non-linear metrics from a standard Apple Health export.
- For a full HRV analysis from Apple Watch, use a third-party app (HRV4Training, Elite HRV) that exports raw RR intervals.

**FR:** L'export standard Apple Health XML ne contient que des métriques pré-calculées.  
Conséquences pratiques :
- `rec["rmssd"]` vaut toujours `None` dans les exports cardiolab.
- Il est **impossible** de recalculer RMSSD, les métriques fréquentielles ou les métriques non-linéaires à partir d'un export Apple Health standard.
- Pour une analyse HRV complète depuis Apple Watch, utiliser une app tierce (HRV4Training, Elite HRV) qui exporte les intervalles RR bruts.

**EN:** Why doesn't Apple export raw RR?  
The Apple Watch records beat-to-beat intervals (`HKHeartbeatSeriesSample`) but these are not included in the standard XML export by default. Some third-party apps (Cardiogram, etc.) can access them via HealthKit and export them separately.

**FR:** Pourquoi Apple n'exporte-t-il pas les RR ?  
L'Apple Watch mesure les intervalles RR (`HKHeartbeatSeriesSample`) mais ceux-ci ne sont pas inclus dans l'export XML standard par défaut. Certaines apps tierces (Cardiogram, etc.) peuvent y accéder via HealthKit et les exporter séparément.
