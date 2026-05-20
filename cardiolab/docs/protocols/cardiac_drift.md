# Protocole de dérive cardiaque

## Principe physiologique

La dérive cardiaque (cardiac drift) est l'augmentation progressive et continue de la fréquence cardiaque lors d'un exercice prolongé à puissance constante. Ce phénomène survient sans augmentation de la demande métabolique et traduit une inadéquation croissante entre le débit cardiaque et les besoins hémodynamiques.

Les trois mécanismes principaux sont :

1. **Déshydratation** : la réduction du volume plasmatique (−10 à −15 % après 60 min d'effort par temps chaud) diminue le retour veineux et le volume d'éjection systolique. Pour maintenir le débit cardiaque (Q = FC × VES), le cœur compense en augmentant la FC.

2. **Thermorégulation** : la redistribution du flux sanguin vers la peau (refroidissement par sudation) réduit le volume central disponible pour le muscle cardiaque, accentuant la baisse du VES.

3. **Fatigue autonome** : la diminution progressive du tonus parasympathique au cours d'un effort prolongé contribue à l'élévation de la FC basale.

La dérive est quantifiée par la **pente de régression linéaire** de la FC moyenne par fenêtre temporelle sur la durée de l'effort.

## Comment réaliser le protocole

### Conditions de mesure
- Exercice **à puissance constante** : vélo à wattage fixe, course à allure stable, tapis roulant à vitesse et pente constantes
- Durée minimale : **20 minutes** (pour 3 fenêtres de 60 s + marge)
- Durée optimale : **30–60 minutes**
- Conditions environnementales à noter : température, humidité, hydratation

### Déroulement
1. Démarrer l'enregistrement RR dès le début de l'effort à puissance constante (pas d'échauffement dans la série)
2. Maintenir une cadence respiratoire et une posture stables
3. Ne pas consommer de boisson ni s'arrêter pendant la mesure (ou consigner les pauses)
4. Exporter les intervalles RR à la fin de la session

### Enregistrement
```python
from cardiolab.signals.rr import RRSeries
from cardiolab.protocols.cardiac_drift import cardiac_drift

rr = RRSeries.from_csv("effort_constant.csv")
result = cardiac_drift(rr, window_sec=60.0)

print(f"Dérive : {result.drift_rate:.2f} bpm/min")
print(f"FC initiale : {result.initial_hr:.0f} bpm → FC finale : {result.final_hr:.0f} bpm")
print(f"Magnitude totale : {result.drift_magnitude:.1f} bpm")
print(f"R² : {result.r_squared:.3f}")
print(f"Interprétation : {result.interpretation}")
```

## Métriques calculées

| Métrique | Description | Unité |
|---|---|---|
| `drift_rate` | Pente de régression FC ∼ temps | bpm/min |
| `drift_magnitude` | Différence FC_finale − FC_initiale | bpm |
| `r_squared` | Coefficient de détermination R² de la régression | sans unité (0–1) |
| `drift_detected` | Vrai si la dérive ≥ 0,5 bpm/min | booléen |
| `initial_hr` | FC moyenne de la première fenêtre | bpm |
| `final_hr` | FC moyenne de la dernière fenêtre | bpm |
| `n_windows` | Nombre de fenêtres temporelles | entier |
| `interpretation` | Catégorie clinique | texte |
| `duration` | Durée totale de l'enregistrement | s |

## Interprétation des résultats

### Taux de dérive

| Taux (bpm/min) | Catégorie | Signification |
|---|---|---|
| < 0,5 | **Pas de dérive** | Thermorégulation efficace, bonne hydratation |
| 0,5 – 1,5 | **Dérive légère** | Surveiller l'hydratation |
| 1,5 – 3,0 | **Dérive modérée** | S'hydrater, envisager de réduire l'intensité |
| > 3,0 | **Dérive forte** | Arrêter ou réduire significativement |

### Coefficient R²

Le R² de la régression linéaire indique si la dérive est **progressive et régulière** :
- R² > 0,8 : dérive linéaire claire → mécanisme physiologique constant
- R² 0,5–0,8 : dérive modérément linéaire → possible variabilité de l'effort
- R² < 0,5 : pas de tendance claire → pas de dérive cardiaque vraie, ou variabilité importante de la puissance

### Magnitude totale

La magnitude (FC_finale − FC_initiale) est un complément utile :
- Une dérive de +10 bpm sur 30 min (0,33 bpm/min) est légère
- Une dérive de +20 bpm sur 30 min (0,67 bpm/min) nécessite une attention
- Une dérive de +30 bpm sur 30 min (1,0 bpm/min) est cliniquement significative

### Fenêtres temporelles

L'algorithme divise la série RR en fenêtres de `window_sec` secondes (défaut 60 s). Chaque fenêtre produit un point de FC moyenne. Il faut **au minimum 3 fenêtres** pour calculer une régression significative.

## Applications pratiques

### Évaluation de l'hydratation
Un protocole simple consiste à réaliser deux sessions à la même puissance :
- Session 1 : sans hydratation
- Session 2 : avec hydratation ad libitum
La différence de dérive entre les deux sessions quantifie l'effet de l'hydratation.

### Suivi longitudinal
Répéter le test dans des conditions identiques (même puissance, même durée, même heure) permet de suivre l'évolution de la tolérance thermique et de l'efficacité cardiovasculaire.

### Prescription d'effort
Si la dérive est forte (> 3 bpm/min) à une puissance donnée, réduire l'intensité cible de 10–15 % pour limiter la dérive lors des prochaines sessions.

## Limites et précautions

- La puissance d'effort doit être **strictement constante** ; toute variation de cadence ou d'allure introduit un biais dans la régression.
- La dérive est physiologiquement plus importante par **temps chaud et humide** (> 25 °C, > 70 % HR) ; interpréter en fonction des conditions ambiantes.
- La durée minimale est de **3 × window_sec** : pour window_sec = 60 s, il faut ≥ 3 min d'effort.
- Éviter de mesurer pendant des efforts intermittents (HIIT, intervalles) — réservé aux efforts en état stable.

## Références

Coyle, E. F., & González-Alonso, J. (2001). Cardiovascular drift during prolonged exercise: new perspectives. *Exercise and Sport Sciences Reviews*, 29(2), 88–92. https://doi.org/10.1097/00003677-200104000-00009

Wingo, J. E., & Cureton, K. J. (2006). Cardiovascular responses to exercise with and without hydration. *Medicine & Science in Sports & Exercise*, 38(4), 739–748. https://doi.org/10.1249/01.mss.0000191765.30569.03

González-Alonso, J., Calbet, J. A., & Nielsen, B. (1999). Metabolic and thermodynamic responses to dehydration-induced reductions in muscle blood flow in exercising humans. *Journal of Physiology*, 520(2), 577–589. https://doi.org/10.1111/j.1469-7793.1999.00577.x

Cheung, S. S., & McLellan, T. M. (1998). Heat acclimation, aerobic fitness, and hydration effects on tolerance during uncompensable heat stress. *Journal of Applied Physiology*, 84(5), 1731–1739. https://doi.org/10.1152/jappl.1998.84.5.1731
