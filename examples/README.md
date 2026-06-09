# cardiolab — exemples d'utilisation

Ce dossier contient des scripts d'exemple couvrant l'ensemble du pipeline :
signal RR, protocoles HRV, analytics, visualisation, base de données PostgreSQL
et pipelines complets.

```
example/
├── .env.example              ← template à copier en .env (requis pour les scripts DB)
│
│   ── 1. Signal ───────────────────────────────────────────────────────────────
├── 06_rr_validation.py       ← PhysiologicalWarning et validation du signal RR
├── 07_auto_clean.py          ← paramètre auto_clean dans les protocoles
│
│   ── 2. Protocoles ────────────────────────────────────────────────────────────
├── 04_resting_protocol.py    ← resting_hrv() → HRVFeatures + readiness scoring
├── 05_orthostatic_protocol.py ← orthostatic_hrv() → réponse autonome posturale
├── 12_other_protocols.py     ← cohérence, HRR, dérive cardiaque, VO2max
│
│   ── 3. Analytics ─────────────────────────────────────────────────────────────
├── 03_load_and_analyze.py    ← baseline, readiness, anomalie, tendance (depuis DB)
├── 13_training_load.py       ← TRIMP, ATL/CTL/TSB (données synthétiques)
│
│   ── 4. Export ────────────────────────────────────────────────────────────────
├── 08_to_dict_export.py      ← to_dict(), JSON, DataFrame pandas
│
│   ── 5. Visualisation ──────────────────────────────────────────────────────────
├── 09_rr_signal_plots.py     ← 5 figures du signal RR (tachogramme, distribution, …)
├── 10_resting_evolution_plots.py ← évolution RMSSD et score de récupération
├── 11_spectral_plots.py      ← 6 figures spectrales (PSD, LF/HF, radar, heatmap)
│
│   ── 6. Base de données ────────────────────────────────────────────────────────
├── 01_setup_database.py      ← run_migrations() — initialise le schéma complet
├── 02_feed_database.py       ← calcule HRVFeatures et enregistre en base
├── 14_user_profiles.py       ← CRUD table user_profiles
│
│   ── 7. Pipeline complet ───────────────────────────────────────────────────────
└── 15_full_daily_pipeline.py ← pipeline quotidien complet (synthétique, sans DB)
│
└── figures/                  ← figures PNG générées par les scripts de visualisation
```

---

## Configuration (scripts DB uniquement)

Copie le fichier template et remplis tes paramètres PostgreSQL :

```bash
cp example/.env.example .env
```

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cardioanalysis
DB_USER=cardio_user
DB_PASSWORD=ton_mot_de_passe

USER_ID=<ton-uuid>
```

Génère ton `USER_ID` une seule fois :

```bash
python3 -c "import uuid; print(uuid.uuid4())"
```

> **Ne commite jamais `.env`** — il contient tes credentials. Ajoute-le à `.gitignore`.

---

## Par où commencer ?

### Sans base de données (découverte du package)

```bash
# Signal RR : validation, nettoyage
python example/06_rr_validation.py
python example/07_auto_clean.py

# Protocoles : resting, orthostatic, cohérence, HRR, dérive, VO2max
python example/04_resting_protocol.py
python example/05_orthostatic_protocol.py
python example/12_other_protocols.py

# Analytics : charge d'entraînement
python example/13_training_load.py

# Export
python example/08_to_dict_export.py

# Visualisation
python example/09_rr_signal_plots.py
python example/10_resting_evolution_plots.py
python example/11_spectral_plots.py

# Pipeline complet (tout en un)
python example/15_full_daily_pipeline.py
```

### Avec PostgreSQL (persistance)

```bash
# 1. Initialiser le schéma (une seule fois)
python example/01_setup_database.py

# 2. Alimenter la base (après chaque session)
python example/02_feed_database.py

# 3. Charger et analyser
python example/03_load_and_analyze.py

# 4. Gérer les profils utilisateurs
python example/14_user_profiles.py
```

---

## Détail des scripts

### 1. Signal

#### `06_rr_validation.py` — Validation physiologique
- Montre comment `RRSeries` émet un `PhysiologicalWarning` sur des intervalles
  hors de la plage physiologique [300, 2000] ms.
- Comment capturer, filtrer et supprimer l'avertissement après nettoyage.

#### `07_auto_clean.py` — Nettoyage automatique
- Paramètre `auto_clean=True` dans `resting_hrv()` et `orthostatic_hrv()`.
- Quand utiliser `auto_clean` vs `remove_outliers()` manuel.

---

### 2. Protocoles

#### `04_resting_protocol.py` — HRV de repos
- `resting_hrv()` sur données synthétiques 5 min.
- 14 métriques HRV : RMSSD, SDNN, pNN50, LF/HF, HF_nu, …
- Score de readiness multi-facteur et composite.
- Note sur le pipeline d'import depuis fichiers Polar.

#### `05_orthostatic_protocol.py` — Test orthostatic
- `orthostatic_hrv()` sur signal continu supine → debout.
- Inspection des phases (supine, transition, standing) et de la réponse autonome.
- `orthostatic_score()` pour transformer en score 0–100.

#### `12_other_protocols.py` — Autres protocoles
| Protocole | Signal synthétique | Résultat clé | Score |
|---|---|---|---|
| Cohérence cardiaque | RR sinusoïdal 0,1 Hz | `coherence_score` | `coherence_score_100()` |
| Heart rate recovery | Récupération exponentielle | `hrr1`, `hrr2` | `hrr_score()` |
| Dérive cardiaque | Effort continu 20 min | `drift_rate` | `drift_score()` |
| VO2max | HRV de repos | `vo2max_esco`, `vo2max_uth` | `vo2max_score()` |

---

### 3. Analytics

#### `03_load_and_analyze.py` — Pipeline d'analyse (depuis DB)
1. Charge les sessions depuis PostgreSQL.
2. Baseline rolling 7 sessions.
3. Score multi-facteur + composite.
4. Détection d'anomalie (3 méthodes).
5. Tendance RMSSD.

#### `13_training_load.py` — Charge d'entraînement
- `trimp_hrv_based()` et `trimp_banister()` — deux méthodes de calcul du TRIMP.
- Construction d'un historique synthétique de 90 jours.
- `TrainingLoad.from_sessions()` → ATL, CTL, TSB.
- Sauvegarde des 3 figures dans `example/figures/`.

| Figure | Contenu |
|---|---|
| `13_01_atl_ctl_tsb.png` | Courbes ATL / CTL / TSB |
| `13_02_trimp_history.png` | Historique TRIMP par sport |
| `13_03_tsb_zones.png` | TSB avec zones de forme |

---

### 4. Export

#### `08_to_dict_export.py` — Sérialisation
- `HRVFeatures.to_dict()` et `OrthostaticResult.to_dict()`.
- Sérialisation JSON et construction d'un DataFrame pandas.

---

### 5. Visualisation

#### `09_rr_signal_plots.py` — Graphiques du signal RR
| Figure | Contenu |
|---|---|
| `09_01_tachogram.png` | Tachogramme + axe FC |
| `09_02_distribution.png` | Histogramme + KDE |
| `09_03_filtered.png` | Signal brut vs filtré |
| `09_04_comparison.png` | Comparaison multi-sessions |
| `09_05_summary.png` | Figure 2×2 avec tableau |

#### `10_resting_evolution_plots.py` — Évolution temporelle
| Figure | Contenu |
|---|---|
| `10_01_rmssd_evolution.png` | RMSSD + médiane glissante |
| `10_02_readiness_score.png` | Score avec seuils |
| `10_03_evolution_combined.png` | RMSSD + score via `plot_resting_evolution()` |
| `10_04_evolution_rolling.png` | RMSSD + médiane + score rolling |

#### `11_spectral_plots.py` — Visualisation spectrale
| Figure | Contenu |
|---|---|
| `11_01_psd_welch.png` | PSD Welch avec bandes VLF/LF/HF |
| `11_02_psd_ar.png` | PSD AR (Yule-Walker) |
| `11_03_psd_comparison.png` | Welch vs AR superposés |
| `11_04_lf_hf_evolution.png` | LF_nu / HF_nu par session |
| `11_05_hrv_radar.png` | Radar HRV — 5 métriques |
| `11_06_spectral_heatmap.png` | Heatmap sessions × bandes |

Voir [`docs/visualization/`](../docs/visualization/) pour les guides de lecture.

---

### 6. Base de données

#### `01_setup_database.py` — Initialisation du schéma
- `run_migrations()` applique les fichiers SQL versionnés (V001–V004).
- Idempotent : relancer ne réapplique pas les migrations déjà effectuées.
- Crée 9 tables : `hrv_features`, `hrv_orthostatic`, `hrv_coherence`,
  `hrv_hrr`, `hrv_drift`, `hrv_vo2max`, `hrv_raw_sessions`,
  `hrv_training_sessions`, `user_profiles`.

#### `02_feed_database.py` — Import de sessions resting
- Lit les fichiers JSON dans `cardiolab/datasets/resting/`.
- Calcule les `HRVFeatures` via `resting_hrv()`.
- Upsert en base (relancer = mise à jour sans doublon).

#### `14_user_profiles.py` — Profils utilisateurs
- Création, lecture, mise à jour, liste, suppression via `HRVRepository`.
- Illustre le CRUD complet de la table `user_profiles`.

---

### 7. Pipeline complet

#### `15_full_daily_pipeline.py` — Routine matinale quotidienne
Pipeline synthétique end-to-end sans base de données :

| Étape | Fonction |
|---|---|
| 1 | Mesure RR → `resting_hrv()` |
| 2 | Baseline 30 jours → `Baseline.from_features()` |
| 3 | Readiness → `readiness_score_multi()` + `readiness_score_composite()` |
| 4 | Anomalie → `detect_rmssd_anomaly(method="zscore")` |
| 5 | TRIMP → `trimp_hrv_based()` + `trimp_banister()` |
| 6 | ATL/CTL/TSB → `TrainingLoad.from_sessions()` |
| 7 | Résumé décisionnel |

Le bloc DB (étape optionnelle 8) est commenté — décommenter pour persister.
