# cardiolab sample datasets / Jeux de données d'exemple

Real RR-interval recordings shipped with cardiolab so that every protocol can be
tried right after `pip install cardiolab` — no database, no sensor.

Des enregistrements RR réels livrés avec cardiolab pour tester chaque protocole
dès `pip install cardiolab`, sans base de données ni capteur.

```python
from cardiolab.datasets import list_samples, load_sample
from cardiolab.protocols.resting import resting_hrv

rr = load_sample("resting", 0)          # RRSeries, manifest entry in rr.metadata
features = resting_hrv(rr, auto_clean=True)
```

## Content / Contenu

| Protocol | Recordings | Dates | Duration | Position |
|----------|-----------:|-------|----------|----------|
| `resting` | 6 | 2026-04-24 → 2026-04-30 | 5.5 – 11.3 min | supine, morning |
| `orthostatic` | 1 | 2026-05-17 | 10.2 min | supine → standing |

The full list (date, time, beats, duration) is in [`samples.json`](samples.json)
and returned by `list_samples()`.

## Provenance and consent / Provenance et consentement

**EN** — These are the cardiolab author's own recordings (Julien MILON), made
with a Polar H10 chest strap and exported with Elite HRV. They are published
**voluntarily** as example data. They contain no name or identifier, only the
date / time of measurement and the RR intervals.

**FR** — Ce sont les propres mesures de l'auteur de cardiolab (Julien MILON),
réalisées avec une ceinture Polar H10 et exportées via Elite HRV. Elles sont
publiées **volontairement** comme données d'exemple. Elles ne contiennent ni nom
ni identifiant, seulement la date / l'heure de mesure et les intervalles RR.

> Never add someone else's recordings here without their explicit consent:
> everything in this directory is published on PyPI.
> Ne jamais ajouter ici les mesures d'une autre personne sans son consentement
> explicite : tout ce dossier est publié sur PyPI.

## Format

Plain text, one RR interval in milliseconds per line — the format exported by
Polar / Elite HRV, read with `cardiolab.sensors_tools.parse_rr_file()`. The files
are **raw**: artefacts are left in on purpose (e.g. a 1 718 ms interval in
`resting/2026-04-24.txt`), use `auto_clean=True` or `RRSeries.remove_outliers()`.

## Licence

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — free reuse
with attribution: *"cardiolab sample datasets, Julien MILON"*.
The code of cardiolab remains under AGPL-3.0 (see `LICENCE`).

## Your own files / Vos propres fichiers

The `raw/` sub-directory is where the notebooks and examples look for **your**
recordings. It is ignored by git and never packaged.
Le sous-dossier `raw/` accueille **vos** enregistrements pour les notebooks et
les exemples ; il est ignoré par git et jamais packagé.
