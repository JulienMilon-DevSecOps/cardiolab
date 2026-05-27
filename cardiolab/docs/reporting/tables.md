# Reporting — tableaux tabulaires HRV

Le module `cardiolab.reporting` produit des tableaux pandas **prêts à afficher** dans Jupyter Notebook.  
Chaque fonction retourne un `pd.Styler` : colorisation des cellules incluse, exportable en HTML ou Excel.

---

## Import rapide

```python
from cardiolab.reporting import (
    table_resting_history,       # historique multi-session repos
    table_resting_session,       # détail d'une session repos
    table_orthostatic_comparison,# comparaison allongé vs debout
    table_orthostatic_history,   # historique orthostatique condensé
)
```

---

## Protocole repos (`resting`)

### `table_resting_history`

Historique multi-session : une ligne par session, colonnes clés avec gradients de couleur.

```python
from cardiolab.reporting import table_resting_history

# features_list : list[HRVFeatures], dans l'ordre chronologique
styler = table_resting_history(features_list)
display(styler)
```

**Signature**

```python
table_resting_history(
    features_list: list[HRVFeatures],
    cols: list[str] | None = None,
    caption_text: str = "Historique repos — rouge = bas · vert = élevé",
) -> pd.Styler
```

**Colonnes par défaut**

| Colonne | Description | Gradient |
|---------|-------------|---------|
| `date` | Date de session | — |
| `rmssd` | RMSSD (ms) | 🟢 vert = élevé |
| `sdnn` | SDNN (ms) | — |
| `mean_hr` | FC moyenne (bpm) | 🔴 rouge = élevé |
| `sd1` | SD1 — court terme (ms) | 🟢 vert = élevé |
| `sd2` | SD2 — long terme (ms) | 🟢 vert = élevé |
| `sd_ratio` | SD1/SD2 | — |
| `dfa_alpha1` | DFA α1 (n/a si NaN) | 🟢 vert entre 0.75–1.25 |
| `apen` | ApEn (n/a si NaN) | 🟢 vert entre 1.2–1.8 |
| `sampen` | SampEn (n/a si NaN) | 🟢 vert entre 1.2–2.0 |
| `score` | Score de récupération (0–100) | 🟢 vert = élevé |

**Personnaliser les colonnes**

```python
# Seulement date + RMSSD + score
styler = table_resting_history(features_list, cols=["date", "rmssd", "score"])

# Les colonnes inconnues sont silencieusement ignorées
```

---

### `table_resting_session`

Détail complet d'une session : une ligne par métrique, groupée par domaine.

```python
from cardiolab.reporting import table_resting_session

styler = table_resting_session(features)
display(styler)
```

**Signature**

```python
table_resting_session(
    features: HRVFeatures,
    caption_text: str | None = None,  # défaut : "Session YYYY-MM-DD"
) -> pd.Styler
```

**Structure du tableau**

| Métrique | Valeur | Domaine |
|----------|--------|---------|
| RMSSD (ms) | 42.00 | Temporal |
| ln(RMSSD) | 3.738 | Temporal |
| SDNN (ms) | 55.00 | Temporal |
| pNN50 (%) | 28.0 | Temporal |
| Mean HR (bpm) | 60.0 | Temporal |
| Method | welch | Frequency |
| VLF (ms²) | 200.00 | Frequency |
| LF (ms²) | 500.00 | Frequency |
| HF (ms²) | 800.00 | Frequency |
| LF/HF | 0.625 | Frequency |
| HF% (%) | 53.0 | Frequency |
| LF_nu | 0.380 | Frequency |
| HF_nu | 0.610 | Frequency |
| SD1 (ms) | 29.70 | Non-linear |
| SD2 (ms) | 70.30 | Non-linear |
| SD1/SD2 | 0.422 | Non-linear |
| DFA α1 | 1.050 | Non-linear |
| ApEn | 1.200 | Non-linear |
| SampEn | 1.350 | Non-linear |
| HRV Score | 72.0 / 100 | Score |

> Les valeurs DFA α1, ApEn et SampEn s'affichent `n/a` quand elles sont `NaN`.

---

## Protocole orthostatique (`orthostatic`)

### `table_orthostatic_comparison`

Comparaison côte à côte allongé / debout, une ligne par session.

```python
from cardiolab.reporting import table_orthostatic_comparison

results = [r1, r2, r3]          # list[OrthostaticResult]
dates   = ["2024-01-01", ...]   # optionnel — défaut : "Session N"

styler = table_orthostatic_comparison(results, dates=dates)
display(styler)
```

**Signature**

```python
table_orthostatic_comparison(
    results: list[OrthostaticResult],
    dates: list[str] | None = None,
    caption_text: str = "Comparaison allongé / debout — rouge = bas · vert = élevé",
) -> pd.Styler
```

**Colonnes produites**

*Pour chaque métrique de phase, deux colonnes `supine_*` et `standing_*` :*

| Groupe | Métriques incluses |
|--------|--------------------|
| Phases | `rmssd`, `mean_hr`, `sd1`, `sd2`, `sd_ratio`, `dfa_alpha1`, `hf_nu`, `apen`, `sampen` |
| Réponse | `hr_response`, `lf_hf_change`, `hf_response_pct`, `hf_hr_pct_change` |
| Interprétation | `interpretation` (cellule colorée) |

**Gradients et couleurs**

| Colonne | Signal | Gradient |
|---------|--------|---------|
| `supine_rmssd`, `standing_rmssd`, `supine_sd1`, … | Variabilité | 🟢 vert = élevé |
| `hr_response` | Tachycardie orthostatique | 🔴 rouge = élevé (0–30 bpm) |
| `interpretation` | Catégorie clinique | Vert = `normal`, rouge = `impaired`, orange = `elevated` |

**Valeurs de référence — réponse orthostatique normale**

| Indicateur | Valeur attendue au lever |
|------------|--------------------------|
| `hr_response` | +5 à +30 bpm |
| `lf_hf_change` | > 1 (activation sympathique) |
| `hf_response_pct` | −30 % à −50 % (retrait vagal) |
| `hf_hr_pct_change` | Négatif (retrait vagal) |

---

### `table_orthostatic_history`

Vue condensée multi-session : indicateurs clés de réponse autonome, une ligne par session.

```python
from cardiolab.reporting import table_orthostatic_history

styler = table_orthostatic_history(results, dates=dates)
display(styler)
```

**Signature**

```python
table_orthostatic_history(
    results: list[OrthostaticResult],
    dates: list[str] | None = None,
    caption_text: str = "Historique orthostatique — réponse autonome par session",
) -> pd.Styler
```

**Colonnes**

| Colonne | Description | Gradient |
|---------|-------------|---------|
| `date` | Date de session | — |
| `supine_rmssd` | RMSSD allongé (ms) | 🟢 vert = élevé |
| `standing_rmssd` | RMSSD debout (ms) | 🟢 vert = élevé |
| `supine_hr` | FC allongé (bpm) | 🔴 rouge = élevé |
| `standing_hr` | FC debout (bpm) | 🔴 rouge = élevé |
| `hr_response` | Hausse FC au lever (bpm) | 🔴 rouge > 30 bpm |
| `lf_hf_change` | Ratio LF/HF debout / allongé | — |
| `hf_response_pct` | Variation HF% (%) | — |
| `hf_hr_pct_change` | Variation HF/FC (%) | — |
| `interpretation` | Catégorie clinique | Colorée |

---

## Gestion des erreurs

Toutes les fonctions valident leurs entrées et lèvent des exceptions claires :

```python
# TypeError — mauvais type
table_resting_history("pas une liste")
# → TypeError: features_list must be a list, got str

# ValueError — liste vide
table_resting_history([])
# → ValueError: features_list must contain at least one element.

# ValueError — longueur dates ≠ longueur résultats
table_orthostatic_comparison(results, dates=["une seule date"])
# → ValueError: dates length (1) must match results length (3)

# TypeError — mauvais type d'élément
table_resting_history([features, "pas un HRVFeatures"])
# → TypeError: features_list[1] must be a HRVFeatures, got str
```

---

## Export HTML / Excel

Le `Styler` retourné par chaque fonction peut être exporté :

```python
# Export HTML (inclut les couleurs)
html = styler.to_html()
with open("rapport.html", "w") as f:
    f.write(html)

# Export Excel (inclut les couleurs si openpyxl installé)
styler.to_excel("rapport.xlsx", engine="openpyxl")

# Export LaTeX (sans couleurs)
latex = styler.to_latex()
```

---

---

## Protocole HRR (`hrr`)

### `table_hrr_history`

Historique multi-session de récupération cardiaque post-effort.

```python
from cardiolab.reporting import table_hrr_history

styler = table_hrr_history(results, dates=dates)
display(styler)
```

**Signature**

```python
table_hrr_history(
    results: list[HRRResult],
    dates: list[str] | None = None,
    caption_text: str = "Historique HRR — récupération cardiaque post-effort",
) -> pd.Styler
```

**Colonnes**

| Colonne | Description | Gradient |
|---------|-------------|---------|
| `date` | Date de session | — |
| `hr_peak` | FC au pic d'effort (bpm) | 🔴 rouge = élevé |
| `hr_at_60s` | FC à 60 s (bpm) | — |
| `hrr_60` | Chute FC à 60 s (bpm) | 🟢 vert = élevé |
| `hrr_60_category` | Catégorie clinique HRR1 | Colorée |
| `hr_at_120s` | FC à 120 s (bpm, n/a si absent) | — |
| `hrr_120` | Chute FC à 120 s (bpm, n/a si absent) | 🟢 vert = élevé |
| `hrr_120_category` | Catégorie clinique HRR2 | Colorée |
| `duration` | Durée de l'enregistrement (s) | — |

**Catégories cliniques (Cole et al. 1999)**

| HRR1 (bpm) | Catégorie | Couleur |
|------------|-----------|---------|
| ≥ 25 | `excellent` | 🟢 Vert |
| 20 – 24 | `good` | 🟡 Jaune clair |
| 12 – 19 | `normal` | 🟠 Orange clair |
| < 12 | `impaired` | 🔴 Rouge |

> **Note :** `result.date` est utilisé en priorité sur le label `dates[i]` s'il est renseigné.

---

## Protocole dérive cardiaque (`drift`)

### `table_drift_history`

Historique multi-session de dérive cardiaque à charge constante.

```python
from cardiolab.reporting import table_drift_history

styler = table_drift_history(results, dates=dates)
display(styler)
```

**Signature**

```python
table_drift_history(
    results: list[DriftResult],
    dates: list[str] | None = None,
    caption_text: str = "Historique dérive cardiaque — vert = stable · rouge = forte dérive",
) -> pd.Styler
```

**Colonnes**

| Colonne | Description | Gradient |
|---------|-------------|---------|
| `date` | Date de session | — |
| `drift_rate` | Pente HR–temps (bpm/min) | 🔴 rouge = élevé (0–3) |
| `drift_magnitude` | Δ HR premier/dernier fenêtre (bpm) | 🔴 rouge = élevé (0–15) |
| `r_squared` | R² de la régression linéaire | 🟢 vert = élevé |
| `initial_hr` | FC moyenne première fenêtre (bpm) | — |
| `final_hr` | FC moyenne dernière fenêtre (bpm) | — |
| `n_windows` | Nombre de fenêtres glissantes | — |
| `duration` | Durée de l'enregistrement (s) | — |
| `interpretation` | Catégorie clinique | Colorée |

**Catégories**

| Taux (bpm/min) | Catégorie | Couleur |
|----------------|-----------|---------|
| < 0.5 | `no_drift` | 🟢 Vert |
| 0.5 – 1.5 | `mild` | 🟡 Jaune clair |
| 1.5 – 3.0 | `moderate` | 🟠 Orange clair |
| > 3.0 | `strong` | 🔴 Rouge |

---

## Protocole cohérence cardiaque (`coherence`)

### `table_coherence_history`

Historique multi-session de cohérence cardiaque.

```python
from cardiolab.reporting import table_coherence_history

styler = table_coherence_history(results, dates=dates)
display(styler)
```

**Signature**

```python
table_coherence_history(
    results: list[CoherenceResult],
    dates: list[str] | None = None,
    caption_text: str = "Historique cohérence cardiaque — vert ≥ 60 % · rouge < 40 %",
) -> pd.Styler
```

**Colonnes**

| Colonne | Description | Gradient |
|---------|-------------|---------|
| `date` | Date de session | — |
| `coherence_score` | Score de cohérence (%, 0–100) | 🟢 vert entre 40–60 |
| `category` | Catégorie dérivée (low/moderate/high) | Colorée |
| `resonance_freq` | Fréquence dominante (Hz) | — |
| `peak_power` | Puissance au pic spectral (ms²/Hz) | — |
| `total_power_resonance` | Puissance totale de la bande (ms²) | — |
| `rmssd` | RMSSD de session (ms) | 🟢 vert = élevé |
| `sdnn` | SDNN (ms) | — |
| `mean_hr` | FC moyenne (bpm) | 🔴 rouge = élevé |
| `duration` | Durée (s) | — |

**Catégories (McCraty / HeartMath)**

| Score (%) | Catégorie | Couleur |
|-----------|-----------|---------|
| ≥ 60 | `high` | 🟢 Vert |
| 40 – 60 | `moderate` | 🟡 Jaune clair |
| < 40 | `low` | 🔴 Rouge |

> La catégorie n'est pas stockée dans `CoherenceResult` — elle est calculée à la volée à partir du score.

---

## Protocole VO2max (`vo2max`)

### `table_vo2max_history`

Historique multi-session des estimations VO2max.

```python
from cardiolab.reporting import table_vo2max_history

styler = table_vo2max_history(results, dates=dates)
display(styler)
```

**Signature**

```python
table_vo2max_history(
    results: list[VO2maxResult],
    dates: list[str] | None = None,
    caption_text: str = "Historique VO2max — vert = élevé · ACSM 2022",
) -> pd.Styler
```

**Colonnes**

| Colonne | Description | Gradient |
|---------|-------------|---------|
| `date` | Date de session | — |
| `vo2max_uth` | Modèle Uth et al. 2004 (n/a sans HR_max) | 🟢 vert (20–65) |
| `vo2max_esco_flatt` | Modèle Esco & Flatt 2014 (mL/kg/min) | 🟢 vert (20–65) |
| `vo2max_ln_rmssd` | Modèle ln-RMSSD (mL/kg/min) | 🟢 vert (20–65) |
| `hr_rest` | FC repos (bpm) | — |
| `hr_max` | FC max fournie (bpm, n/a si absente) | — |
| `rmssd_used` | RMSSD utilisé (ms) | — |
| `ln_rmssd_used` | ln(RMSSD) utilisé | — |
| `fitness_category` | Catégorie ACSM | Colorée |

> Le gradient sur `vo2max_uth` n'est appliqué que si au moins une session fournit une valeur non-NaN.

---

### `table_vo2max_session`

Détail d'une session VO2max : une ligne par indicateur.

```python
from cardiolab.reporting import table_vo2max_session

styler = table_vo2max_session(result)
display(styler)
```

**Signature**

```python
table_vo2max_session(
    result: VO2maxResult,
    caption_text: str | None = None,
) -> pd.Styler
```

**Structure**

| Indicateur | Groupe |
|------------|--------|
| VO2max Uth (mL/kg/min) | Model |
| VO2max Esco-Flatt (mL/kg/min) | Model |
| VO2max ln-RMSSD (mL/kg/min) | Model |
| HR repos (bpm) | Inputs |
| HR max (bpm) | Inputs |
| RMSSD utilisé (ms) | Inputs |
| ln(RMSSD) utilisé | Inputs |
| Catégorie fitness | Result |

La cellule **Catégorie fitness** est colorée selon la zone ACSM (pauvre → excellent).

**Catégories ACSM 2022**

| VO2max (mL/kg/min) | Catégorie | Couleur |
|--------------------|-----------|---------|
| ≥ 58 | `excellent` | 🟢 Vert |
| 48 – 57 | `very_good` | 🔵 Bleu clair |
| 38 – 47 | `good` | 🟡 Jaune clair |
| 28 – 37 | `fair` | 🟠 Orange clair |
| < 28 | `poor` | 🔴 Rouge |

---

## Gestion des erreurs

Toutes les fonctions valident leurs entrées et lèvent des exceptions claires :

```python
# TypeError — mauvais type
table_resting_history("pas une liste")
# → TypeError: features_list must be a list, got str

# ValueError — liste vide
table_resting_history([])
# → ValueError: features_list must contain at least one element.

# ValueError — longueur dates ≠ longueur résultats
table_orthostatic_comparison(results, dates=["une seule date"])
# → ValueError: dates length (1) must match results length (3)

# TypeError — mauvais type d'élément
table_resting_history([features, "pas un HRVFeatures"])
# → TypeError: features_list[1] must be a HRVFeatures, got str
```

---

## Export HTML / Excel

Le `Styler` retourné par chaque fonction peut être exporté :

```python
# Export HTML (inclut les couleurs)
html = styler.to_html()
with open("rapport.html", "w") as f:
    f.write(html)

# Export Excel (inclut les couleurs si openpyxl installé)
styler.to_excel("rapport.xlsx", engine="openpyxl")

# Export LaTeX (sans couleurs)
latex = styler.to_latex()
```
