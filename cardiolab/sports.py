"""Reference list of the sports known to cardiolab.

Each sport is defined once, with a stable code (stored in the ``sport_type``
column of training sessions), English / French labels, a chart colour and a
family::

    from cardiolab.sports import get_sport, list_sports, normalize_sport

    normalize_sport("Course à pied")          # → "running"
    normalize_sport("running", "trail")       # Garmin FIT sport + sub-sport → "trail"
    get_sport("cycling").label_fr             # → "Vélo"
    [s.code for s in list_sports("endurance")]

:func:`normalize_sport` maps free text (French or English labels, common
synonyms) and Garmin FIT ``sport`` / ``sub_sport`` values to a code; anything
it does not recognise becomes ``"other"`` (tolerant: imports, charts).
:func:`validate_sport` is the strict variant used when saving a training
session: an unknown name is rejected with a suggestion, so typos never reach
the ``sport_type`` column.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass

FAMILIES: dict[str, tuple[str, str]] = {
    "endurance": ("Endurance", "Endurance"),
    "strength": ("Strength & fitness", "Force et fitness"),
    "team_racket": ("Team & racket sports", "Sports collectifs et de raquette"),
    "other": ("Other", "Autre"),
}
"""Sport families: ``code → (English label, French label)``."""


@dataclass(frozen=True)
class Sport:
    """One sport of the reference list.

    Attributes:
        code: Stable identifier, stored in ``sport_type`` (e.g. ``"running"``).
        label_en: English display label.
        label_fr: French display label.
        color: Hex colour used in charts.
        family: One of the :data:`FAMILIES` codes.

    """

    code: str
    label_en: str
    label_fr: str
    color: str
    family: str


_SPORT_LIST: tuple[Sport, ...] = (
    # ── Endurance ─────────────────────────────────────────────────────────
    # The six colours used before v0.3.4 (running, trail, cycling, swimming,
    # rowing, strength) are kept unchanged.
    Sport("running", "Running", "Course à pied", "#e74c3c", "endurance"),
    Sport("trail", "Trail running", "Trail", "#d35400", "endurance"),
    Sport("cycling", "Cycling", "Vélo", "#2980b9", "endurance"),
    Sport("mountain_bike", "Mountain biking", "VTT", "#1f618d", "endurance"),
    Sport("swimming", "Swimming", "Natation", "#1abc9c", "endurance"),
    Sport("rowing", "Rowing", "Aviron", "#16a085", "endurance"),
    Sport("hiking", "Hiking", "Randonnée", "#7d6608", "endurance"),
    Sport("walking", "Walking", "Marche", "#b7950b", "endurance"),
    Sport(
        "cross_country_skiing",
        "Cross-country skiing",
        "Ski de fond",
        "#5dade2",
        "endurance",
    ),
    # ── Strength & fitness ────────────────────────────────────────────────
    Sport("strength", "Strength training", "Renforcement", "#8e44ad", "strength"),
    Sport("hiit", "HIIT", "HIIT", "#c0392b", "strength"),
    Sport("yoga", "Yoga", "Yoga", "#af7ac5", "strength"),
    # ── Team & racket sports ──────────────────────────────────────────────
    Sport("football", "Football", "Football", "#27ae60", "team_racket"),
    Sport("basketball", "Basketball", "Basketball", "#e67e22", "team_racket"),
    Sport("tennis", "Tennis", "Tennis", "#f1c40f", "team_racket"),
    # ── Other ─────────────────────────────────────────────────────────────
    Sport("alpine_skiing", "Alpine skiing", "Ski alpin", "#85c1e9", "other"),
    Sport("other", "Other", "Autre", "#95a5a6", "other"),
)

SPORTS: dict[str, Sport] = {s.code: s for s in _SPORT_LIST}
"""Reference list of sports, keyed by code, in display order."""


# Synonyms and import names → code (keys are normalised with _slug()).
# Garmin FIT ``sport`` values that are not codes themselves are listed here too.
_SYNONYMS: dict[str, str] = {
    # running
    "run": "running",
    "course": "running",
    "jogging": "running",
    "footing": "running",
    "treadmill": "running",
    "street": "running",
    "track": "running",
    # trail
    "trail_running": "trail",
    # cycling
    "bike": "cycling",
    "biking": "cycling",
    "velo": "cycling",
    "road": "cycling",
    "road_cycling": "cycling",
    "indoor_cycling": "cycling",
    "home_trainer": "cycling",
    "e_biking": "cycling",
    "gravel_cycling": "cycling",
    # mountain bike
    "vtt": "mountain_bike",
    "mtb": "mountain_bike",
    "mountain": "mountain_bike",
    "mountain_biking": "mountain_bike",
    # swimming
    "swim": "swimming",
    "nage": "swimming",
    "lap_swimming": "swimming",
    "open_water": "swimming",
    # rowing
    "row": "rowing",
    "indoor_rowing": "rowing",
    # hiking / walking
    "hike": "hiking",
    "rando": "hiking",
    "walk": "walking",
    # skiing
    "ski_de_fond": "cross_country_skiing",
    "xc_skiing": "cross_country_skiing",
    "nordic_skiing": "cross_country_skiing",
    "ski": "alpine_skiing",
    "downhill_skiing": "alpine_skiing",
    # strength / fitness
    "renfo": "strength",
    "musculation": "strength",
    "strength_training": "strength",
    "weights": "strength",
    "gym": "strength",
    "crossfit": "hiit",
    "circuit": "hiit",
    # team & racket
    "soccer": "football",
    "foot": "football",
    "basket": "basketball",
    # Garmin FIT generic values
    "generic": "other",
    "training": "other",
    "fitness_equipment": "other",
    "autre": "other",
}

# Garmin FIT (sport, sub_sport) pairs whose sub-sport is more precise.
_FIT_SUB_SPORTS: dict[tuple[str, str], str] = {
    ("running", "trail"): "trail",
    ("running", "treadmill"): "running",
    ("cycling", "mountain"): "mountain_bike",
    ("cycling", "indoor_cycling"): "cycling",
    ("training", "strength_training"): "strength",
    ("training", "cardio_training"): "hiit",
    ("training", "hiit"): "hiit",
    ("training", "yoga"): "yoga",
    ("fitness_equipment", "indoor_rowing"): "rowing",
    ("fitness_equipment", "treadmill"): "running",
    ("fitness_equipment", "indoor_cycling"): "cycling",
    ("swimming", "lap_swimming"): "swimming",
    ("swimming", "open_water"): "swimming",
}


def _slug(value: str) -> str:
    """Lower-case, strip accents and turn separators into underscores."""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# Every code, English label and French label is also a valid input.
_LOOKUP: dict[str, str] = {
    **{_slug(k): v for k, v in _SYNONYMS.items()},
    **{_slug(s.label_en): s.code for s in _SPORT_LIST},
    **{_slug(s.label_fr): s.code for s in _SPORT_LIST},
    **{s.code: s.code for s in _SPORT_LIST},
}


def normalize_sport(value: str | None, sub_sport: str | None = None) -> str:
    """Map a free-text sport name or a Garmin FIT sport to a reference code.

    Matching ignores case, accents and separators, and accepts the codes, the
    English and French labels and common synonyms (« Course à pied », ``"run"``,
    ``"VTT"``…). With a Garmin FIT ``sub_sport``, a more precise sport is used
    when the pair is known (``running`` + ``trail`` → ``"trail"``).

    Args:
        value: Sport name, code, or FIT ``sport`` value. ``None`` or empty
            gives ``"other"``.
        sub_sport: Optional FIT ``sub_sport`` value.

    Returns:
        A code of :data:`SPORTS`; ``"other"`` when not recognised.

    """
    main = _slug(value) if value else ""
    if sub_sport:
        refined = _FIT_SUB_SPORTS.get((main, _slug(sub_sport)))
        if refined:
            return refined
    return _LOOKUP.get(main, "other")


def validate_sport(value: str | None) -> str | None:
    """Return the reference code of a sport to store, or raise if it is unknown.

    Unlike :func:`normalize_sport`, an unrecognised name is **rejected** instead
    of becoming ``"other"``, so that typos (``"runing"``) never reach the
    database. Accepts everything :func:`normalize_sport` recognises (codes,
    English / French labels, synonyms, FIT values).

    Args:
        value: Sport name entered by the user or the application. ``None`` or
            empty means « no sport » and is allowed.

    Returns:
        The reference code, or ``None`` for no sport.

    Raises:
        ValueError: If ``value`` is not recognised; the message suggests the
            closest known sport.

    """
    if value is None or not _slug(value):
        return None
    slug = _slug(value)
    if slug in _LOOKUP:
        return _LOOKUP[slug]
    close = difflib.get_close_matches(slug, list(_LOOKUP), n=1, cutoff=0.75)
    hint = f" Did you mean {_LOOKUP[close[0]]!r}?" if close else ""
    raise ValueError(
        f"Unknown sport {value!r}.{hint} Use a code of cardiolab.sports.SPORTS "
        f"({', '.join(SPORTS)}), a label or a known synonym."
    )


def get_sport(value: str | None) -> Sport:
    """Return the :class:`Sport` for a code or any name :func:`normalize_sport` accepts.

    Args:
        value: Code, label or synonym. Unknown values give the ``"other"`` sport.

    Returns:
        The matching :class:`Sport`.

    """
    return SPORTS[normalize_sport(value)]


def list_sports(family: str | None = None) -> list[Sport]:
    """List the reference sports, in display order.

    Args:
        family: Keep only this family (see :data:`FAMILIES`). ``None`` returns
            every sport.

    Returns:
        The sports, ``"other"`` last.

    Raises:
        ValueError: If ``family`` is not a known family.

    """
    if family is not None and family not in FAMILIES:
        raise ValueError(f"Unknown family {family!r}. Known: {', '.join(FAMILIES)}.")
    return [s for s in _SPORT_LIST if family is None or s.family == family]


__all__ = [
    "FAMILIES",
    "SPORTS",
    "Sport",
    "get_sport",
    "list_sports",
    "normalize_sport",
    "validate_sport",
]
