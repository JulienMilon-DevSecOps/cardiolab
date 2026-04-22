# ❤️ cardiolab

**cardiolab** est un moteur d’analyse physiologique dédié à l’étude du rythme cardiaque et de la variabilité cardiaque (HRV).

Ce projet constitue le cœur scientifique du produit **cardioanalysis**.

---

## 🎯 Objectif

Transformer des signaux physiologiques bruts (ECG, PPG, HR) en :

* métriques fiables (HR, HRV)
* analyses physiologiques (fatigue, récupération)
* scores interprétables

---

## 🧠 Pipeline global

```
Signal brut (ECG / PPG)
        ↓
Préprocessing
        ↓
RR intervals
        ↓
Features (HRV)
        ↓
Protocoles
        ↓
Scoring
        ↓
Analytics
```

---

## 🧱 Structure du projet

```
cardiolab/
│
├── signals/          → données brutes (ECG, PPG, RR)
├── preprocessing/    → nettoyage des signaux
├── transformations/  → conversion (ECG → RR)
├── features/         → calcul HRV
├── protocols/        → tests physiologiques
├── scoring/          → scores (fatigue, readiness)
├── analytics/        → analyse long terme
├── models/           → objets métier
└── validation/       → validation scientifique
```

---

## 🫀 Concepts clés

### RR intervals

Les intervalles RR constituent la base de toutes les analyses.

### HRV (Heart Rate Variability)

Variabilité du rythme cardiaque utilisée pour évaluer :

* fatigue
* stress
* récupération

---

## 🚧 État du projet

Projet en cours de développement.

Modules actuellement implémentés :

* ECGSignal
* RRSeries

---

## 🔬 Philosophie

* approche scientifique
* modularité
* reproductibilité
* extensibilité

---

## 📚 Références

* Task Force HRV (1996)
* Shaffer & Ginsberg (2017)

---

## 👨‍💻 Projet associé

**cardioanalysis** → plateforme web d’analyse cardiaque

---

## 🚀 Roadmap

* [ ] HRV complet
* [ ] protocoles physiologiques
* [ ] API FastAPI
* [ ] interface utilisateur

---

## 📌 Note

Ce package est en phase de conception et n’est pas encore distribué.
