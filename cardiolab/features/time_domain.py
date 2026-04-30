

from __future__ import annotations

import numpy as np

# ======================
# Fonction du domaine temporel, calculées directement sur les intervalles RR.
# ======================

def rmssd(rr) -> float:
    """
    RMSSD
    
    FR :
    RMSSD mesure la variabilité à court terme entre battements consécutifs.
    RMSSD = sqrt(mean((RR[i+1] - RR[i])²))
    
    Interprétation physiologique
        reflète principalement l'activité parasympathique (vagale)
    
    Lecture 
        * RMSSD élevé → bonne récupération / relaxation
        * RMSSD faible → stress / fatigue / charge élevée
        
    C’est LA métrique la plus utilisée en sport

    Valeurs typiques (adulte)
    | RMSSD (ms) | Interprétation |
    | ---------- | -------------- |
    | < 20       | très faible    |
    | 20 – 40    | faible         |
    | 40 – 70    | normal         |
    | 70 – 100   | bon            |
    | > 100      | très élevé     |

    * < 30 → fatigue, stress, surcharge
    * > 70 → bonne récupération
    * > 100 → très bon état parasympathique (souvent athlètes)

    Dépendant de la personne, âge, niveau sportif, ...

    EN :
    RMSSD measures short-term variability between consecutive heartbeats.
    RMSSD = sqrt(mean((RR[i+1] - RR[i])²))

    Physiological Interpretation
        Primarily reflects parasympathetic (vagal) activity.

    Reading
        * High RMSSD → good recovery/relaxation
        * Low RMSSD → stress/fatigue/high workload

    This is THE most widely used metric in sports.
    
    Typical Values (Adult)
    | RMSSD (ms) | Interprétation |
    | ---------- | -------------- |
    | < 20       | very low       |
    | 20 – 40    | low            |
    | 40 – 70    | normal         |
    | 70 – 100   | high           |
    | > 100      | very high      |

    * < 30 → fatigue, stress, overload
    * > 70 → good recovery
    * > 100 → very good parasympathetic function (often found in athletes)

    Depends on the individual, age, fitness level, etc.
    """
    diff = np.diff(rr.intervals)
    return float(np.sqrt(np.mean(diff ** 2)))

def ln_rmssd(rr) -> float:
    """
    FR :
    Calcule le logarithme naturel du RMSSD.

    Très utilisé car RMSSD est fortement asymétrique.

    EN :
    Computes natural logarithm of RMSSD.

    Widely used because RMSSD is highly skewed.
    """

    value = rmssd(rr)

    if value <= 0:
        return 0.0

    return float(np.log(value))


def sdnn(rr) -> float:
    """
    SDNN
    
    FR :
    SDNN est l’écart-type des intervalles RR (ou NN) sur une période donnée.

    Interprétation physiologique :
        * mesure la variabilité globale du rythme cardiaque
        * reflète :
            activité sympathique + parasympathique

    Lecture (valeurs variable suivant la durée d'analyse)
        * SDNN élevé → bonne variabilité → système adaptable
        * SDNN faible → fatigue / stress / faible adaptabilité

    Valeurs typiques (cour terme ~5 min)
    | SDNN (ms) | Interprétation |
    | --------- | -------------- |
    | < 20      | très faible    |
    | 20 – 50   | faible         |
    | 50 – 80   | normal         |
    | > 80      | élevé          |

    EN :
    SDNN is the standard deviation of the RR (or NN) intervals over a given period.

    Physiological interpretation:
        * measures the overall variability of heart rate
        * reflects:
            sympathetic + parasympathetic activity

    Reading (values vary depending on the duration of analysis)

        * High SDNN → good variability → adaptable system
        * Low SDNN → fatigue / stress / poor adaptability

    Typical values (short term ~5 min)
    | SDNN (ms) | Interpretation |
    | --------- | -------------- |
    | < 20      | very low       |
    | 20 – 50   | low            |
    | 50 – 80   | normal         |
    | > 80      | high           |
    """
    return float(np.std(rr.intervals, ddof=1))


def pnn50(rr) -> float:
    """
    pNN50 (%)
    
    FR : 
    pNN50 est le pourcentage de paires d’intervalles RR successifs qui diffèrent de plus de 50 ms.
    pNN50 = (nombre de |RR[i+1] - RR[i]| > 50 ms) / total x 100

    Interprétation physiologique
        reflète principalement l'activité parasympathique
    
    Lecture
        * pNN50 élevé → forte variabilité (relaxation)
        * pNN50 faible → stress / fatigue
            
    Valeurs typique
        | pNN50 (%) | Interprétation |
        | --------- | -------------- |
        | < 5%      | très faible    |
        | 5 – 15%   | faible         |
        | 15 – 30%  | normal         |
        | > 30%     | élevé          |

        Indicateur tout de même peux fiable, sensible au bruit.

        EN :
        pNN50 is the percentage of successive RR interval pairs that differ by more than 50 ms.
        pNN50 = (number of |RR[i+1] - RR[i]| > 50 ms) / total x 100

        Physiological interpretation
            primarily reflects parasympathetic activity

        Reading
            * High pNN50 → high variability (relaxation)
            * Low pNN50 → stress / fatigue

        Typical values
        | pNN50 (%) | Interprétation |
        | --------- | -------------- |
        | < 5%      | very low       |
        | 5 – 15%   | low            |
        | 15 – 30%  | normal         |
        | > 30%     | high           |

        However, this indicator is not very reliable and is sensitive to noise.
        """
    
    diff = np.abs(np.diff(rr.intervals))
    return float(np.sum(diff > 50) / len(diff) * 100)