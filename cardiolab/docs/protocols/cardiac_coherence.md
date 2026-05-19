# Protocole de cohérence cardiaque 5-5

## Principe physiologique

La cohérence cardiaque est un état physiologique dans lequel la fréquence cardiaque oscille de manière sinusoïdale et régulière, en résonance avec le système nerveux autonome. Elle est induite par une respiration guidée à **6 cycles/min** (inspiration 5 s / expiration 5 s), ce qui génère une oscillation maximale des intervalles RR à **0,1 Hz** — la fréquence de résonance du baroréflexe.

À 0,1 Hz, le baroréflexe vagal amplifie les oscillations respiratoires de la pression artérielle et de la FC, produisant le plus grand domaine de puissance spectrale possible dans la bande HF. Ce mécanisme, appelé **résonance cardiovasculaire**, est associé à une activation maximale du nerf vague (activité parasympathique).

## Comment réaliser le protocole

### Conditions de mesure
- Position **assise** ou **allongée** dans un environnement calme
- Durée minimale recommandée : **5 minutes** (idéalement 10 min)
- Éviter toute activité physique dans l'heure précédant la mesure
- Utiliser une ceinture cardiaque pour l'enregistrement continu des intervalles RR

### Déroulement
1. S'installer confortablement et noter l'heure de début
2. Utiliser un guide de respiration (visuel ou sonore) à **6 cycles/min** :
   - Inspirer pendant **5 secondes**
   - Expirer pendant **5 secondes**
3. Maintenir ce rythme pendant toute la session
4. Exporter les intervalles RR à la fin de la session

### Enregistrement
```python
from cardiolab.signals.rr import RRSeries
from cardiolab.protocols.cardiac_coherence import cardiac_coherence

rr = RRSeries.from_csv("session_coherence.csv")
result = cardiac_coherence(rr)
print(f"Score de cohérence : {result.coherence_score:.1f} %")
print(f"Fréquence de résonance : {result.resonance_freq:.3f} Hz")
```

## Métriques calculées

| Métrique | Description | Unité |
|---|---|---|
| `coherence_score` | % de puissance concentré au pic de résonance | % (0–100) |
| `resonance_freq` | Fréquence du pic dominant dans la bande 0,04–0,26 Hz | Hz |
| `peak_power` | Densité spectrale au pic de résonance | ms²/Hz |
| `total_power_resonance` | Puissance totale dans la bande de résonance | ms² |
| `rmssd` | RMSSD pendant la session | ms |
| `sdnn` | SDNN pendant la session | ms |
| `mean_hr` | Fréquence cardiaque moyenne | bpm |
| `duration` | Durée effective de l'enregistrement | s |

### Score de cohérence

Le score est calculé comme :

```
coherence_score = (puissance_fenêtre_pic / puissance_totale_résonance) × 100
```

où la fenêtre du pic est centrée sur la fréquence dominante avec une demi-largeur de ±0,015 Hz.

## Interprétation des résultats

### Score de cohérence

| Score (%) | Interprétation | Recommandation |
|---|---|---|
| ≥ 60 | **Bonne cohérence** — résonance vagale forte | Maintenir la pratique |
| 40 – 60 | **Cohérence modérée** — résonance partielle | Améliorer la régularité respiratoire |
| < 40 | **Faible cohérence** — peu de résonance vagale | Vérifier le guidage et la fréquence respiratoire |

### Fréquence de résonance

Pour un protocole 5-5 (6 cycles/min), la fréquence attendue est :

```
f_résonance = 6 / 60 = 0,100 Hz
```

Un pic entre **0,09 et 0,11 Hz** confirme que le sujet suit correctement le guidage respiratoire. Un pic décalé suggère une cadence respiratoire différente de 6 cycles/min.

### RMSSD et SDNN

Un score de cohérence élevé s'accompagne généralement de valeurs RMSSD élevées (activation vagale). Des valeurs RMSSD > 50 ms associées à un score ≥ 60 % indiquent une excellente modulation parasympathique.

## Méthode spectrale

L'analyse utilise la méthode **AR (Yule-Walker)** d'ordre 16, préférable à Welch pour des sessions courtes (2–5 min) car elle offre une meilleure résolution fréquentielle. Le signal RR est rééchantillonné à **4 Hz** avant estimation spectrale.

Bande d'analyse : **0,04 – 0,26 Hz** (couvre la bande HF et s'étend légèrement en dessous pour capturer des cadences respiratoires lentes).

## Limites et précautions

- Le score de cohérence est sensible à la **variabilité inter-respiration** : une respiration irrégulière élargit le pic spectral et réduit le score.
- Une session < 2 minutes (< 120 battements) donne des résultats peu fiables.
- Certains sujets ont une fréquence de résonance personnelle légèrement différente de 0,1 Hz ; adapter le guidage si nécessaire.
- La cohérence cardiaque n'est pas un indicateur de santé globale à elle seule — la combiner avec les mesures HRV de repos.

## Références

Cole, C. R., Blackstone, E. H., Pashkow, F. J., Snader, C. E., & Lauer, M. S. (1999). Heart-rate recovery immediately after exercise as a predictor of mortality. *New England Journal of Medicine*, 341(18), 1351–1357.

Lehrer, P. M., & Gevirtz, R. (2014). Heart rate variability biofeedback: how and why does it work? *Frontiers in Psychology*, 5, 756. https://doi.org/10.3389/fpsyg.2014.00756

McCraty, R., & Shaffer, F. (2015). Heart rate variability: new perspectives on physiological mechanisms, assessment of self-regulatory capacity, and health risk. *Global Advances in Health and Medicine*, 4(1), 46–61. https://doi.org/10.7453/gahmj.2014.073

Shaffer, F., McCraty, R., & Zerr, C. L. (2014). A healthy heart is not a metronome: an integrative review of the heart's anatomy and heart rate variability. *Frontiers in Psychology*, 5, 1040. https://doi.org/10.3389/fpsyg.2014.01040
