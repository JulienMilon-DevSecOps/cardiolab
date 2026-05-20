# Estimation du VO2max depuis la VRC

## Principe physiologique

La consommation maximale d'oxygène (VO2max) est le gold standard de la capacité cardiorespiratoire. Sa mesure directe nécessite un laboratoire équipé (analyseur de gaz, épreuve d'effort maximale). Deux modèles indirects permettent de l'estimer depuis des données cardiaques simples.

### Modèle 1 — Ratio FC (Uth et al. 2004)

La méthode Heart Rate Ratio (HRR) repose sur la relation entre FC maximale, FC de repos et VO2max :

```
VO2max ≈ 15,3 × (FCmax / FCrepos)
```

**Justification** : FCmax est déterminée par le volume systolique maximal et la consommation d'O₂ maximale ; FCrepos reflète le tonus vagal et la réserve cardiaque. Le rapport FCmax/FCrepos corrèle linéairement avec le VO2max (r = 0,87 dans l'étude originale).

**Précision** : ±10–15 % (erreur standard ≈ 3,5 mL/kg/min).

### Modèle 2 — RMSSD (Esco & Flatt 2014)

La RMSSD reflète l'activité parasympathique, elle-même fortement corrélée au VO2max dans les populations actives :

```
VO2max ≈ 18,37 + 0,054 × RMSSD
```

Avec le logarithme naturel de la RMSSD (variant logarithmique, Nunan / Esco-Flatt étendu) :

```
VO2max ≈ 24,89 + 5,97 × ln(RMSSD)
```

**Justification** : un entraînement en endurance augmente simultanément le VO2max et la RMSSD via les adaptations autonomes cardiaques (hypertrophie vagale). Le ln(RMSSD) stabilise la variance et offre une meilleure relation linéaire.

**Précision** : ±7–12 % (erreur standard ≈ 5,5 mL/kg/min pour le modèle RMSSD simple).

## Comment réaliser le protocole

### Conditions de mesure
- Enregistrement **au repos**, à jeun ou ≥ 2 h après un repas léger
- Position **allongée** ou **assise** pendant au moins 5 minutes avant l'enregistrement
- Durée recommandée : **5 minutes** (minimum 30 intervalles RR)
- Même heure chaque jour (le matin au réveil est idéal pour la FCrepos)

### Obtention de la FCmax (pour le modèle Uth)
- Mesure directe lors d'un test d'effort maximal (ergomètre, test de Cooper, etc.)
- Estimation : **220 − âge** (précision ±10–15 bpm — peu fiable individuellement)
- Estimation améliorée : **207 − 0,7 × âge** (Tanaka et al. 2001 — adultes sains)

### Enregistrement
```python
from cardiolab.signals.rr import RRSeries
from cardiolab.protocols.vo2max import vo2max_from_hrv

rr = RRSeries.from_csv("repos_matin.csv")

# Avec FC maximale connue
result = vo2max_from_hrv(rr, hr_max=185.0)
print(f"VO2max (Uth)       : {result.vo2max_uth:.1f} mL/kg/min")
print(f"VO2max (Esco-Flatt) : {result.vo2max_esco_flatt:.1f} mL/kg/min")
print(f"VO2max (ln-RMSSD)  : {result.vo2max_ln_rmssd:.1f} mL/kg/min")
print(f"Catégorie fitness   : {result.fitness_category}")

# Sans FC maximale — modèles RMSSD seulement
result = vo2max_from_hrv(rr)
print(f"VO2max (Esco-Flatt) : {result.vo2max_esco_flatt:.1f} mL/kg/min")
```

## Métriques calculées

| Métrique | Description | Unité |
|---|---|---|
| `vo2max_uth` | VO2max (Uth et al. 2004) : 15,3 × FCmax/FCrepos | mL/kg/min |
| `vo2max_esco_flatt` | VO2max (Esco & Flatt 2014) : 18,37 + 0,054 × RMSSD | mL/kg/min |
| `vo2max_ln_rmssd` | VO2max (ln-RMSSD) : 24,89 + 5,97 × ln(RMSSD) | mL/kg/min |
| `hr_rest` | FC de repos dérivée de la série RR | bpm |
| `hr_max` | FC maximale fournie par l'utilisateur | bpm |
| `rmssd_used` | RMSSD calculée depuis la série RR | ms |
| `ln_rmssd_used` | ln(RMSSD) | sans unité |
| `fitness_category` | Catégorie ACSM de forme aérobique | texte |

## Interprétation des résultats

### Catégories de forme aérobique (ACSM 2022 — adultes mixtes)

| VO2max (mL/kg/min) | Catégorie | Interprétation |
|---|---|---|
| ≥ 58 | **Excellent** | Niveau sportif élite |
| 48 – 57 | **Très bon** | Athlète amateur entraîné |
| 38 – 47 | **Bon** | Adulte actif |
| 28 – 37 | **Passable** | Actif mais non entraîné |
| < 28 | **Faible** | Sédentaire — risque cardiométabolique accru |

### Valeurs de référence par âge et sexe (hommes, ACSM)

| Âge | Faible | Passable | Bon | Très bon | Excellent |
|---|---|---|---|---|---|
| 20–29 | < 38 | 38–43 | 44–50 | 51–56 | > 56 |
| 30–39 | < 34 | 34–38 | 39–45 | 46–51 | > 51 |
| 40–49 | < 30 | 30–34 | 35–41 | 42–46 | > 46 |
| 50–59 | < 25 | 25–30 | 31–37 | 38–42 | > 42 |
| 60–69 | < 21 | 21–25 | 26–32 | 33–37 | > 37 |

### Comparaison des modèles

| Modèle | Données requises | Précision | Recommandation |
|---|---|---|---|
| Uth (FCmax/FCrepos) | FCmax + enregistrement repos | ±10–15 % | Utiliser si FCmax mesurée en test |
| Esco-Flatt (RMSSD) | Enregistrement repos seul | ±7–12 % | Suivi longitudinal sans test d'effort |
| ln-RMSSD | Enregistrement repos seul | ±7–12 % | Complémentaire à Esco-Flatt |

**Priorité de la catégorie fitness** : le modèle Uth est utilisé quand FCmax est disponible (mesure plus précise) ; sinon le modèle Esco-Flatt.

### Suivi longitudinal

Répéter la mesure dans des conditions identiques (même heure, même durée, même position) permet de tracker l'évolution du VO2max estimé sans test d'effort. Une augmentation de la RMSSD de +10 ms correspond à une augmentation de VO2max estimé de ≈ 0,5 mL/kg/min.

## Limites et précautions

- Ces estimations sont des **prédictions populationnelles** avec une imprécision individuelle de ±10–15 %. Ne pas les utiliser pour des décisions médicales sans confirmation par un test direct.
- Le modèle Uth est sensible à la **qualité de la FCmax** : une valeur estimée (220 − âge) introduit une erreur supplémentaire de ±10 bpm.
- Le modèle Esco-Flatt a été validé sur des adultes **récréativement actifs** (20–50 ans) ; l'extrapolation à des populations extrêmes (très sédentaires, élites) peut sous-estimer ou surestimer.
- La RMSSD mesurée en ultracourt (< 1 min) donne des résultats moins précis ; privilégier **≥ 5 min** d'enregistrement.

## Références

Uth, N., Sørensen, H., Overgaard, K., & Pedersen, P. K. (2004). Estimation of VO2max from the ratio between HRmax and HRrest — the Heart Rate Ratio Method. *European Journal of Applied Physiology*, 91(1), 111–115. https://doi.org/10.1007/s00421-003-0988-y

Esco, M. R., & Flatt, A. A. (2014). Ultra-short-term heart rate variability indices for gender identification and automatic prediction of cardiorespiratory fitness. *Sensors*, 14(3), 3934–3952. https://doi.org/10.3390/s140303934

Nunan, D., Donovan, G., Jakovljevic, D. G., Hodges, L. D., Sandercock, G. R., & Brodie, D. A. (2010). Validity and reliability of short-term heart-rate variability from the Polar S810. *Medicine & Science in Sports & Exercise*, 42(2), 243–250. https://doi.org/10.1249/MSS.0b013e3181b6dd7a

Tanaka, H., Monahan, K. D., & Seals, D. R. (2001). Age-predicted maximal heart rate revisited. *Journal of the American College of Cardiology*, 37(1), 153–156. https://doi.org/10.1016/S0735-1097(00)01054-8

American College of Sports Medicine. (2022). *ACSM's Guidelines for Exercise Testing and Prescription* (11th ed.). Lippincott Williams & Wilkins.
