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

## Phases prévues

| Phase | Contenu | État |
|-------|---------|------|
| 1 | Resting + Orthostatic | ✅ Implémenté |
| 2 | HRR + Drift + Cohérence + VO2max | Planifié |
