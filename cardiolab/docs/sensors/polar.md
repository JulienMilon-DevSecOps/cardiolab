# Polar — Export RR Intervals (.txt) / Export intervalles RR (.txt)

## Required Equipment / Matériel requis

**EN:** Polar H10 (recommended) or H9 chest strap — ECG-grade sensor.  
**FR:** Ceinture thoracique **Polar H10** (recommandé) ou H9 — capteur de qualité ECG.

**EN:** Recording app: **Polar Sensor Logger** (Android/iOS, free), **Elite HRV**, **HRV4Training**, or **Kubios HRV**.  
**FR:** Application d'enregistrement : **Polar Sensor Logger** (Android/iOS, gratuit), **Elite HRV**, **HRV4Training** ou **Kubios HRV**.

## Installation

No extra dependency — the Polar parser is included in the base package.  
Aucune dépendance supplémentaire — le parser Polar est inclus dans le package de base.

```bash
pip install cardiolab
```

---

## Measurement Protocol / Protocole de mesure

### EN

1. **Morning, upon waking**, before any physical activity or caffeine.
2. Lie down and remain still for **5 minutes**.
3. Start the recording **within the first 30 seconds** of lying down.
4. Breathe naturally — do not consciously control your breathing rate.
5. Stop the recording after 5 minutes.

### FR

1. **Le matin, au réveil**, avant toute activité physique ou caféine.
2. S'allonger et rester immobile pendant **5 minutes**.
3. Lancer l'enregistrement **dans les 30 premières secondes** après s'être allongé.
4. Respiration naturelle — ne pas contrôler consciemment le rythme.
5. Arrêter l'enregistrement après 5 minutes.

---

## Recording with Polar Sensor Logger / Enregistrement avec Polar Sensor Logger

### EN

1. Install **Polar Sensor Logger** on your phone.
2. Open the app → **Scan** → select your Polar H10.
3. Enable **RR Interval** in the capture options.
4. Press **Start** → record 5 minutes → **Stop**.
5. Export via **Share** → `.txt` file with RR intervals in milliseconds.

### FR

1. Installer **Polar Sensor Logger** sur votre téléphone.
2. Ouvrir l'app → **Scan** → sélectionner le Polar H10.
3. Activer **RR Interval** dans les options de capture.
4. Appuyer sur **Start** → enregistrer 5 minutes → **Stop**.
5. Exporter via **Share** → fichier `.txt` avec les intervalles RR en millisecondes.

### Exported file format / Format du fichier exporté

```
Phone Timestamp,RR-interval [ms]
2026-01-10 07:30:00.123,812
2026-01-10 07:30:00.935,810
2026-01-10 07:30:01.745,795
...
```

The cardiolab parser auto-detects the RR column (case-insensitive search).  
Le parser cardiolab détecte automatiquement la colonne RR (recherche insensible à la casse).

---

## Import into cardiolab / Import dans cardiolab

### Read a Polar RR file / Lire un fichier RR Polar

```python
from cardiolab.sensors_tools import parse_rr_file
from cardiolab.features.time_domain import compute_time_domain

rr = parse_rr_file("datasets/raw/polar/2026-01-10_repos.txt")
rr_clean = rr.remove_outliers()

features = compute_time_domain(rr_clean)
print(f"RMSSD : {features.rmssd:.1f} ms | SDNN : {features.sdnn:.1f} ms")
```

### Full pipeline via import_rr / Pipeline complet via import_rr

```bash
# Drop the .txt file in datasets/raw/resting/ then run:
# Déposer le fichier .txt dans datasets/raw/resting/ puis lancer :
python cardiolab/scripts/import_rr.py
```

---

## File location / Emplacement des fichiers

```
cardiolab/datasets/
└── raw/
    └── polar/
        ├── 2026-01-10_repos.txt
        └── 2026-01-11_repos.txt
```

---

## Known limitations / Limites connues

**EN**
- **Motion artefacts**: the H10 is very accurate, but abrupt movements at session start generate outliers. Always call `remove_outliers()`.
- **Unstable connection**: Bluetooth dropout creates gaps. Intervals > 2000 ms are automatically flagged by `PhysiologicalWarning`.
- **Third-party apps**: files exported by Elite HRV or HRV4Training may differ slightly in format. Use the dedicated parsers (`parse_hrv4training_csv`) when applicable.

**FR**
- **Artefacts de mouvement** : le H10 est très précis, mais les mouvements brusques en début de session génèrent des artefacts. Toujours appeler `remove_outliers()`.
- **Connexion instable** : une coupure Bluetooth crée des gaps dans les données. Les intervalles > 2000 ms sont automatiquement signalés par `PhysiologicalWarning`.
- **Applications tierces** : les fichiers exportés par Elite HRV ou HRV4Training peuvent avoir un format légèrement différent. Utiliser les parsers dédiés (`parse_hrv4training_csv`) si nécessaire.
