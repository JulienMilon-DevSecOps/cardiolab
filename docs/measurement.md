# 🫀 Mesure des données cardiaques

## 🎯 Objectif

**FR :**
Cette section explique comment mesurer correctement les données cardiaques pour obtenir des analyses fiables dans cardioanalysis.

**EN :**
This section explains how to properly measure cardiac data to obtain reliable analysis in cardioanalysis.

---

## 🧠 Pourquoi la qualité des données est essentielle

**FR :**
Les analyses de variabilité cardiaque (HRV) sont extrêmement sensibles au bruit et aux erreurs de mesure.
Une mauvaise mesure peut conduire à des interprétations totalement erronées.

**EN :**
Heart rate variability (HRV) analysis is highly sensitive to noise and measurement errors.
Poor data quality can lead to completely incorrect interpretations.

---

## 📊 Types de données cardiaques

### 1. Intervalles RR (recommandé)

**FR :**
Temps entre deux battements cardiaques successifs (en millisecondes).

✔️ donnée la plus précise pour HRV
✔️ directement utilisée dans le projet

**EN :**
Time between two consecutive heartbeats (in milliseconds).

✔️ most accurate data for HRV
✔️ directly used in the project

---

### 2. Fréquence cardiaque (HR)

**FR :**
Nombre de battements par minute (bpm).

✔️ facile à mesurer
❌ moins précis pour HRV

**EN :**
Heart rate in beats per minute (bpm).

✔️ easy to measure
❌ less precise for HRV

---

### 3. Signal ECG

**FR :**
Signal électrique du cœur.

✔️ précision maximale
✔️ permet extraction des RR

**EN :**
Electrical signal of the heart.

✔️ highest precision
✔️ allows RR extraction

---

## 📱 Outils de mesure

### 🥇 1. Ceintures cardiaques (ECG) — recommandé

Exemples :

* Polar H10
* Garmin HRM

**FR :**
✔️ très haute précision
✔️ idéal pour HRV
✔️ recommandé pour ce projet

**EN :**
✔️ very high accuracy
✔️ ideal for HRV
✔️ recommended for this project

---

### 🥈 2. Montres connectées (PPG)

Exemples :

* Apple Watch
* Garmin
* Fitbit

**FR :**
✔️ pratique
✔️ accessible
❌ moins précis (surtout HRV)

**EN :**
✔️ convenient
✔️ accessible
❌ less accurate (especially for HRV)

---

### 🥉 3. Capteurs médicaux (ECG clinique)

**FR :**
✔️ précision maximale
❌ peu pratique

**EN :**
✔️ maximum precision
❌ not practical for daily use

---

## ⚙️ Quelle donnée utiliser dans cardioanalysis ?

**FR :**

Ordre de priorité :

1. RR intervals (idéal)
2. ECG → converti en RR
3. HR → converti en RR (moins fiable)

**EN :**

Priority order:

1. RR intervals (ideal)
2. ECG → converted to RR
3. HR → converted to RR (less reliable)

---

## 📏 Bonnes pratiques de mesure

### FR :

* mesurer au repos
* être immobile
* utiliser toujours le même appareil
* mesurer à la même heure (idéalement le matin)
* éviter les perturbations (bruit, mouvement)

---

### EN :

* measure at rest
* stay still
* use the same device
* measure at the same time (ideally morning)
* avoid disturbances (noise, movement)

---

## 🚫 Erreurs fréquentes

### FR :

* mesurer après un effort
* changer de capteur régulièrement
* bouger pendant la mesure
* comparer les données entre personnes

---

### EN :

* measuring after exercise
* switching devices frequently
* moving during measurement
* comparing data between individuals

---

## 🔄 Conversion des données

**FR :**

Le projet permet de convertir :

* ECG → RR
* HR → RR

⚠️ Toute conversion introduit une perte de précision.

---

**EN :**

The project allows conversion:

* ECG → RR
* HR → RR

⚠️ Any conversion introduces loss of precision.

---

## 🧠 Résumé

**FR :**

* la qualité des données est essentielle
* RR est la meilleure donnée
* la régularité est plus importante que la précision absolue

---

**EN :**

* data quality is critical
* RR is the best data type
* consistency is more important than absolute precision
