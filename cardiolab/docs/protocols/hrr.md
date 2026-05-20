# Protocole de récupération de la fréquence cardiaque (HRR)

## Principe physiologique

La récupération de la fréquence cardiaque (Heart Rate Recovery, HRR) mesure la vitesse à laquelle la FC diminue après un effort maximal ou sous-maximal. Cette décroissance est principalement médiée par la **réactivation parasympathique** (nerf vague) dans les premières secondes–minutes post-effort.

Le HRR à 1 minute (HRR1 = FC_pic − FC_60s) est un **marqueur indépendant de mortalité cardiovasculaire** : une chute < 12 bpm double le risque de décès toutes causes confondues (Cole et al. 1999). Le mécanisme sous-jacent est la réactivation du tonus vagal, qui ralentit le nœud sinusal dès l'arrêt de l'effort.

Deux indicateurs sont calculés :
- **HRR1** : chute de FC à 60 secondes post-pic (marqueur vagal, fort pouvoir pronostique)
- **HRR2** : chute de FC à 120 secondes post-pic (intègre aussi la baisse de catécholamines)

## Comment réaliser le protocole

### Conditions de mesure
- Enregistrement continu des intervalles RR pendant l'effort ET la récupération
- La série RR doit **démarrer au moment du pic d'effort** (dernier battement d'effort)
- Phase de récupération **passive** : le sujet s'asseoit ou reste debout sans marcher
- Durée minimale d'enregistrement post-pic : **2 minutes** (pour HRR1 et HRR2)

### Protocole d'effort recommandé
- Test d'effort maximal (VO2max, Ruffier, test de Cooper) ou
- Effort sous-maximal à intensité contrôlée (85–95 % FCmax)
- L'effort doit être suffisamment intense pour élever la FC à ≥ 150 bpm

### Déroulement
1. Démarrer l'enregistrement RR au moins 2 min avant le pic d'effort
2. Poursuivre l'enregistrement pendant **au moins 2 min** après le pic
3. Identifier le moment de pic d'effort (FC maximale) et tronquer la série à partir de ce point
4. Exporter les intervalles RR de la phase de récupération

### Enregistrement
```python
from cardiolab.signals.rr import RRSeries
from cardiolab.protocols.hrr import heart_rate_recovery

# La série doit commencer au pic d'effort
rr_recovery = RRSeries.from_csv("recovery.csv")
result = heart_rate_recovery(rr_recovery)

print(f"FC pic : {result.hr_peak:.0f} bpm")
print(f"HRR1 : {result.hrr_60:.0f} bpm → {result.hrr_60_category}")
print(f"HRR2 : {result.hrr_120:.0f} bpm → {result.hrr_120_category}")
```

## Métriques calculées

| Métrique | Description | Unité |
|---|---|---|
| `hr_peak` | FC au pic d'effort (premier battement de la série) | bpm |
| `hr_at_60s` | FC à exactement 60 s post-pic | bpm |
| `hr_at_120s` | FC à exactement 120 s post-pic | bpm |
| `hrr_60` | Chute de FC à 60 s (FC_pic − FC_60s) | bpm |
| `hrr_120` | Chute de FC à 120 s (FC_pic − FC_120s) | bpm |
| `hrr_60_category` | Catégorie clinique pour HRR1 | texte |
| `hrr_120_category` | Catégorie clinique pour HRR2 | texte |
| `duration` | Durée totale de l'enregistrement de récupération | s |

## Interprétation des résultats

### HRR1 — Chute à 60 secondes (Cole et al. 1999)

| HRR1 (bpm) | Catégorie | Risque cardiovasculaire |
|---|---|---|
| ≥ 25 | **Excellent** | Très faible — excellente réactivation vagale |
| 20 – 24 | **Bon** | Faible |
| 12 – 19 | **Normal** | Risque moyen |
| < 12 | **Altéré** | Risque élevé — marqueur pronostique péjoratif |

> **Valeur seuil clinique** : HRR1 < 12 bpm est un prédicteur indépendant de mortalité toutes causes (RR = 2,0 ; IC 95 % : 1,5–2,7 ; Cole et al. 1999).

### HRR2 — Chute à 120 secondes

| HRR2 (bpm) | Catégorie |
|---|---|
| ≥ 55 | Excellent |
| 45 – 54 | Bon |
| 35 – 44 | Normal |
| < 35 | Altéré |

### Valeurs typiques par population

| Population | HRR1 moyen | HRR2 moyen |
|---|---|---|
| Sportifs entraînés | 35–50 bpm | 60–80 bpm |
| Adultes actifs | 20–30 bpm | 40–55 bpm |
| Adultes sédentaires | 12–20 bpm | 30–45 bpm |
| Patients cardiaques | < 12 bpm | < 30 bpm |

### Facteurs influençant le HRR
- **Entraînement en endurance** : augmente significativement le HRR (hypertrophie vagale)
- **Âge** : le HRR diminue avec l'âge (-0,5 bpm/an environ)
- **Médicaments** : les bêtabloquants réduisent le HRR ; les anticholinergiques l'augmentent artificiellement
- **Pathologies** : insuffisance cardiaque, diabète autonome, neuropathie vagale → HRR altéré

## Limites et précautions

- La récupération doit être **passive** : toute activité (marche de récupération) accélère artificiellement la baisse de FC et surévalue le HRR.
- Le HRR dépend de l'**intensité de l'effort** : un effort sous-maximal produit un HRR moins informatif.
- Éviter de mesurer le HRR après un effort issu d'une pathologie intercurrente (fièvre, déshydratation sévère).
- Minimum recommandé : **30 intervalles RR** pour un calcul fiable (soit ≈ 30 battements de récupération).

## Références

Cole, C. R., Blackstone, E. H., Pashkow, F. J., Snader, C. E., & Lauer, M. S. (1999). Heart-rate recovery immediately after exercise as a predictor of mortality. *New England Journal of Medicine*, 341(18), 1351–1357. https://doi.org/10.1056/NEJM199910283411804

Imai, K., Sato, H., Hori, M., Kusuoka, H., Ozaki, H., Yokoyama, H., ... & Kamada, T. (1994). Vagally mediated heart rate recovery after exercise is accelerated in athletes but blunted in patients with chronic heart failure. *Journal of the American College of Cardiology*, 24(6), 1529–1535. https://doi.org/10.1016/0735-1097(94)90150-3

Morshedi-Meibodi, A., Larson, M. G., Levy, D., O'Donnell, C. J., & Vasan, R. S. (2002). Heart rate recovery after treadmill exercise testing and risk of cardiovascular disease events (The Framingham Heart Study). *American Journal of Cardiology*, 90(8), 848–852. https://doi.org/10.1016/S0002-9149(02)02801-1

Jouven, X., Empana, J. P., Schwartz, P. J., Desnos, M., Courbon, D., & Ducimetière, P. (2005). Heart-rate profile during exercise as a predictor of sudden death. *New England Journal of Medicine*, 352(19), 1951–1958. https://doi.org/10.1056/NEJMoa043012
