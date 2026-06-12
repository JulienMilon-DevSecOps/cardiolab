# Apple Health — Export XML (iPhone / Apple Watch)

## Matériel requis

- **iPhone** avec l'application Santé (iOS 12+).
- **Apple Watch Series 1+** pour les mesures HRV automatiques (Series 4+ recommandé pour la fréquence de mesure).

---

## Procédure d'export

1. Ouvrir l'application **Santé** → icône de profil (en haut à droite).
2. Faire défiler jusqu'à **Exporter les données de santé**.
3. Confirmer l'export — l'iPhone génère une archive `export.zip`.
4. Décompresser l'archive : le fichier `export.xml` se trouve à la racine.

> Le fichier peut être volumineux (plusieurs centaines de Mo pour des années de données).

---

## Format du fichier

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
  <!-- Autres types de données (pas, distance, sommeil…) -->
</HealthData>
```

| Type de Record | Métrique | Unité |
|---|---|---|
| `HKQuantityTypeIdentifierHeartRateVariabilitySDNN` | SDNN | ms |
| `HKQuantityTypeIdentifierRestingHeartRate` | FC au repos | count/min |

---

## Import dans cardiolab

### Lire tous les enregistrements HRV bruts

```python
from cardiolab.sensors_tools.apple_health import parse_apple_health_export

records = parse_apple_health_export("export.xml")

for rec in records:
    if rec["sdnn"] is not None:
        print(f"{rec['date']} — SDNN = {rec['sdnn']:.1f} ms ({rec['source']})")
```

### Extraire un résumé par jour

```python
from cardiolab.sensors_tools.apple_health import extract_hrv_samples

samples = extract_hrv_samples("export.xml")

for s in samples:
    print(f"{s['date']} — SDNN moyen = {s['sdnn']:.1f} ms")
```

---

## ⚠️ Limites connues — export lossy

> **L'export standard Apple Health ne contient pas les intervalles RR bruts.**

Apple Health n'exporte que des métriques pré-calculées :

| Disponible | Non disponible |
|---|---|
| SDNN (ms) | Intervalles RR bruts |
| FC au repos (bpm) | RMSSD |
| | HF / LF power |
| | DFA α1, entropies |

**Conséquences pratiques :**

- `rec["rmssd"]` vaut toujours `None` dans les exports cardiolab.
- Il est **impossible** de recalculer RMSSD, les métriques fréquentielles ou les métriques non-linéaires à partir d'un export Apple Health standard.
- Pour une analyse HRV complète depuis Apple Watch, utiliser une app tierce (HRV4Training, Elite HRV, Polar H10) qui exporte les intervalles RR bruts.

**Pourquoi Apple n'exporte-t-il pas les RR ?**
L'Apple Watch mesure les intervalles RR (`HKHeartbeatSeriesSample`) mais ceux-ci ne sont pas inclus dans l'export XML standard par défaut. Certaines apps tierces (Cardiogram, etc.) peuvent y accéder via HealthKit et les exporter séparément.
