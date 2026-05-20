# cardiolab — exemples d'utilisation

Ce dossier contient des scripts d'exemple couvrant l'ensemble du pipeline :
base de données PostgreSQL, analyse HRV, validation du signal, export et visualisation.

```
example/
├── .env.example              ← template à copier en .env (requis pour 01–03)
│
│   ── Base de données ──────────────────────────────────────────────────────
├── 01_setup_database.py      ← créer les tables (une seule fois)
├── 02_feed_database.py       ← alimenter la base après chaque nouvelle session
├── 03_load_and_analyze.py    ← analyse complète depuis la DB
│
│   ── Import & pipeline ────────────────────────────────────────────────────
├── 04_import_resting.py      ← importer des sessions de repos depuis des fichiers bruts
├── 05_import_orthostatic.py  ← importer des sessions orthostatiques
│
│   ── Validation & export ──────────────────────────────────────────────────
├── 06_rr_validation.py       ← PhysiologicalWarning et nettoyage du signal RR
├── 07_auto_clean.py          ← suppression automatique des artefacts
├── 08_to_dict_export.py      ← sérialisation to_dict(), JSON et DataFrame pandas
│
│   ── Visualisation ────────────────────────────────────────────────────────
├── 09_rr_signal_plots.py     ← 5 graphiques du signal RR brut (tachogramme, distribution, …)
├── 10_resting_evolution_plots.py ← évolution RMSSD et score de récupération dans le temps
│
└── figures/                  ← figures PNG générées par les scripts de visualisation
```

---

## Étape 0 — Configuration (une seule fois)

Copie le fichier template et remplis tes paramètres PostgreSQL :

```bash
cp example/.env.example .env
```

Contenu de `.env` à compléter :

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cardioanalysis
DB_USER=cardio_user
DB_PASSWORD=ton_mot_de_passe

USER_ID=<ton-uuid>
```

Génère ton `USER_ID` avec Python :

```bash
python3 -c "import uuid; print(uuid.uuid4())"
```

Copie le résultat dans `.env` sous `USER_ID=`. Ne le change plus — c'est ton identifiant stable dans la base de données.

> **Ne commite jamais `.env`** — il contient ton mot de passe. Ajoute-le à `.gitignore`.

---

## Étape 1 — Créer la table (une seule fois)

```bash
python example/01_setup_database.py
```

Crée la table `hrv_features` avec le schéma complet :

| Colonne    | Type               | Rôle                              |
|------------|--------------------|-----------------------------------|
| `id`       | SERIAL PRIMARY KEY | Clé technique auto-incrémentée    |
| `user_id`  | TEXT NOT NULL      | UUID de l'utilisateur             |
| `date`     | DATE NOT NULL      | Date de la session                |
| `rmssd`    | FLOAT              | Variabilité court terme (ms)      |
| `ln_rmssd` | FLOAT              | RMSSD normalisé (log)             |
| `sdnn`     | FLOAT              | Variabilité globale (ms)          |
| `pnn50`    | FLOAT              | % de paires > 50 ms               |
| `mean_hr`  | FLOAT              | FC moyenne (bpm)                  |
| `vlf`      | FLOAT              | Puissance très basse fréquence    |
| `lf`       | FLOAT              | Puissance basse fréquence         |
| `hf`       | FLOAT              | Puissance haute fréquence         |
| `lf_hf`    | FLOAT              | Ratio LF/HF (équilibre autonome)  |
| `hf_pct`   | FLOAT              | HF en % de la puissance totale    |
| `lf_nu`    | FLOAT              | LF en unités normalisées          |
| `hf_nu`    | FLOAT              | HF en unités normalisées          |
| `duration` | FLOAT              | Durée de la session (secondes)    |
| `score`    | FLOAT              | Score de récupération (0–100)     |

Une contrainte `UNIQUE(user_id, date)` garantit qu'il n'y a qu'une ligne par utilisateur par jour.

Relancer ce script est sans danger — `CREATE TABLE IF NOT EXISTS` est idempotent.

---

## Étape 2 — Alimenter la base (après chaque nouvelle session)

```bash
python example/02_feed_database.py
```

Le script :

1. Lit tous les fichiers `.json` dans `cardiolab/datasets/resting/`.
2. Calcule les 14 indicateurs HRV via `resting_hrv()`.
3. Insère chaque session dans PostgreSQL sous ton `USER_ID`.

L'upsert (`ON CONFLICT … DO UPDATE`) rend le script **idempotent** : relancer sur les mêmes fichiers met à jour les lignes existantes sans créer de doublons. C'est utile si tu recalcules tes features après une correction.

Sortie attendue :

```
=== cardiolab — feed database ===

User ID : 550e8400-e29b-41d4-a716-446655440000
Sessions found : 2
Saved to table  : 'hrv_features' (upsert — duplicates are updated)

Date                      RMSSD    SDNN     HR   HF_nu   LF/HF
-----------------------------------------------------------------
2026-04-24 07-52-36        78.5    95.9   57.9    0.24    3.12
2026-04-25 07-58-25        51.8   108.3   52.2    0.25    2.95
```

---

## Étape 3 — Charger et analyser

```bash
python example/03_load_and_analyze.py
```

Le script charge toutes les sessions depuis la base de données puis exécute la pipeline d'analyse complète :

1. **Baseline rolling 7 sessions** — RMSSD moyen, médiane, FC moyenne.
2. **Score de la dernière session** — algorithme Oura-inspired (RMSSD 70 % + FC 30 %) et multi-facteur (RMSSD + FC + HF_nu + tendance).
3. **Détection d'anomalie** — trois méthodes : `simple` (% d'écart), `zscore` (distance standardisée), `rolling` (médiane glissante).
4. **Tendance RMSSD** — régression linéaire sur l'historique complet (`increasing`, `stable`, `decreasing`).

Interprétation du score :

| Score   | Interprétation         |
|---------|------------------------|
| 80–100  | Très bien récupéré     |
| 60–80   | Récupération normale   |
| 40–60   | Fatigue modérée        |
| 20–40   | Fatigué                |
| < 20    | Surcharge — repos conseillé |

---

## Pourquoi un UUID pour `user_id` ?

La colonne `user_id` est de type `TEXT` dans PostgreSQL. Elle pourrait contenir n'importe quelle chaîne (`"julien"`, `"user_1"`…), mais un UUID présente plusieurs avantages :

- **Unicité garantie** — la probabilité de collision d'un UUID v4 est astronomiquement faible, même sans coordination entre systèmes.
- **Pas d'information personnelle exposée** — un UUID ne révèle ni nom ni email dans les logs ou les exports.
- **Préparation multi-utilisateurs** — si la plateforme évolue vers plusieurs utilisateurs ou une API, les UUID sont le standard pour identifier des ressources sans conflit.
- **Stable dans le temps** — contrairement à un identifiant dérivé d'un nom ou d'une adresse, un UUID ne change pas si tu modifies tes informations.

Le format normalisé est `8-4-4-4-12` (exemple : `550e8400-e29b-41d4-a716-446655440000`). Le script `02_feed_database.py` normalise automatiquement la valeur lue depuis `.env` via `uuid.UUID(raw_value)`, donc peu importe si tu l'as copié avec ou sans tirets.

---

## Scripts de visualisation (sans base de données)

Les scripts 09 et 10 ne nécessitent pas de PostgreSQL et fonctionnent directement
depuis les fichiers de session JSON présents dans `cardiolab/datasets/resting/`.
Si aucun fichier n'est trouvé, des données synthétiques sont générées automatiquement.

```bash
# Graphiques du signal RR brut (5 types de figures)
python example/09_rr_signal_plots.py

# Évolution du RMSSD et du score de récupération dans le temps
python example/10_resting_evolution_plots.py
```

Les figures sont sauvegardées dans `example/figures/` au format PNG (150 dpi).

### Script 09 — Graphiques RR

| Figure générée | Contenu |
|---|---|
| `09_01_tachogram.png` | Tachogramme RR avec axe FC |
| `09_02_distribution.png` | Histogramme + KDE de la distribution |
| `09_03_filtered.png` | Signal brut vs filtré, artefacts en rouge |
| `09_04_comparison.png` | Comparaison multi-sessions |
| `09_05_summary.png` | Figure 2×2 avec tableau de statistiques |

### Script 10 — Évolution temporelle

| Figure générée | Contenu |
|---|---|
| `10_01_rmssd_evolution.png` | RMSSD et médiane glissante sur la période |
| `10_02_readiness_score.png` | Score de récupération avec seuils d'interprétation |

Voir [`cardiolab/docs/visualization/reading_charts.md`](../cardiolab/docs/visualization/reading_charts.md)
pour le guide de lecture de chaque type de graphique.
