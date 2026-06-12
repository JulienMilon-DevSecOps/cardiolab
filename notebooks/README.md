# cardiolab — Notebooks interactifs

Ce dossier contient 9 notebooks Jupyter qui couvrent l'ensemble du pipeline cardiolab,
de la configuration initiale au pipeline quotidien complet.

Ils complètent les scripts `examples/` (cas d'usage unitaires, prêts à l'emploi) avec
une approche **narrative et interactive** : chaque cellule explique le *pourquoi*
physiologique avant le *comment* technique.

---

## Prérequis

```bash
pip install cardiolab jupyter matplotlib
```

Pour les notebooks qui accèdent à la base de données (00, 02–08) :

```bash
pip install cardiolab[db]   # psycopg2-binary + python-dotenv
```

Créer un fichier `.env` à la racine du dépôt :

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cardiolab
DB_USER=votre_user
DB_PASSWORD=votre_mot_de_passe
```

---

## Notebooks

| # | Notebook | Données | DB requise |
|---|---|---|---|
| [00](00_setup.ipynb) | **Setup & base de données** — init, migrations, reset | — | ✅ |
| [01](01_signal_rr.ipynb) | **Le signal RR** — lecture Polar, nettoyage, visualisation | `datasets/raw/resting/` | ❌ |
| [02](02_import_pipeline.ipynb) | **Pipeline d'import** — dossier → parse → protocole → sauvegarde | `datasets/raw/resting/` | ✅ |
| [03](03_resting_protocol.ipynb) | **Protocole repos** — fichier ou base → features → scoring → reporting | `datasets/raw/resting/` | ✅ |
| [04](04_orthostatic_protocol.ipynb) | **Protocole orthostatique** — fichier ou base → dual score → comparaison | `datasets/raw/orthostatic/` | ✅ |
| [05](05_other_protocols.ipynb) | **Autres protocoles** — cohérence, HRR, drift, VO2max | synthétique | ❌ |
| [06](06_analytics.ipynb) | **Analytics longitudinal** — baseline, readiness, anomalie, tendances | DB ou JSON | ✅ |
| [07](07_training_load.ipynb) | **Charge d'entraînement** — TRIMP, ATL/CTL/TSB, multi-activités | DB | ✅ |
| [08](08_full_pipeline.ipynb) | **Pipeline quotidien complet** — de l'import à la décision | `datasets/raw/resting/` | ✅ |

**Ordre recommandé pour une première utilisation :**
`00 → 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08`

---

## Structure des données

```
cardiolab/datasets/
  raw/
    resting/        ← fichiers Polar .txt — 6 sessions repos (2026-04-24 → 2026-04-30)
    orthostatic/    ← fichiers Polar .txt — 1 session orthostatique (2026-05-17)
  resting/          ← résultats pré-analysés en JSON
  orthostatic/      ← résultat pré-analysé en JSON
  exports/          ← exemples CSV et JSON
```

---

## Évolution future des capteurs

Le notebook `02_import_pipeline` est conçu pour accueillir de nouveaux parseurs sans
modifier le reste du pipeline. Lorsque les intégrations Garmin, Apple Health ou
HRV4Training seront disponibles (v0.3.0), un seul paramètre change :

```python
# Aujourd'hui
from cardiolab.sensors_tools.polar import parse_rr_file as parser

# Demain (v0.3.0)
from cardiolab.sensors_tools.garmin import parse_garmin_fit as parser
```
