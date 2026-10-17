"""Tests for the sports reference list (cardiolab.sports) and its use in plots."""

from __future__ import annotations

import re

import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from matplotlib.colors import to_hex  # noqa: E402

from cardiolab.analytics.training_load import (  # noqa: E402
    TrainingLoad,
    compute_atl,
    compute_ctl,
    compute_tsb,
)
from cardiolab.labels import LABELS_EN, LABELS_FR  # noqa: E402
from cardiolab.sports import (  # noqa: E402
    FAMILIES,
    SPORTS,
    get_sport,
    list_sports,
    normalize_sport,
    validate_sport,
)
from cardiolab.visualization.training_load_plots import (  # noqa: E402
    _TRIMP_COLOR,
    plot_trimp_history,
)

# Colours used by the TRIMP history chart before v0.3.4 — must not change.
_LEGACY_COLORS = {
    "running": "#e74c3c",
    "cycling": "#2980b9",
    "swimming": "#1abc9c",
    "strength": "#8e44ad",
    "trail": "#d35400",
    "rowing": "#16a085",
}


@pytest.mark.unit
class TestReferenceList:
    """The reference list is complete and consistent."""

    def test_codes_are_keys(self):
        """Each sport is stored under its own code."""
        assert all(code == s.code for code, s in SPORTS.items())

    def test_fields_are_valid(self):
        """Labels are set, colours are hex, families are known."""
        for s in SPORTS.values():
            assert s.label_en and s.label_fr
            assert re.fullmatch(r"#[0-9a-f]{6}", s.color), s.code
            assert s.family in FAMILIES, s.code

    def test_colors_are_unique(self):
        """Two sports never share a colour (stacked bars stay readable)."""
        colors = [s.color for s in SPORTS.values()]
        assert len(colors) == len(set(colors))

    def test_legacy_colors_unchanged(self):
        """The six colours used before v0.3.4 are kept."""
        for code, color in _LEGACY_COLORS.items():
            assert SPORTS[code].color == color

    def test_other_exists(self):
        """The fallback sport exists."""
        assert "other" in SPORTS


@pytest.mark.unit
class TestNormalizeSport:
    """normalize_sport() maps free text and FIT values to codes."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("running", "running"),
            ("RUNNING", "running"),
            ("Course à pied", "running"),
            ("course a pied", "running"),
            ("run", "running"),
            ("Vélo", "cycling"),
            ("velo", "cycling"),
            ("indoor_cycling", "cycling"),
            ("VTT", "mountain_bike"),
            ("Natation", "swimming"),
            ("open water", "swimming"),
            ("Ski de fond", "cross_country_skiing"),
            ("Randonnée", "hiking"),
            ("musculation", "strength"),
            ("Renforcement", "strength"),
            ("soccer", "football"),
            ("Trail running", "trail"),
            ("Mountain biking", "mountain_bike"),
        ],
    )
    def test_names_labels_and_synonyms(self, value, expected):
        """Codes, English / French labels and synonyms are recognised."""
        assert normalize_sport(value) == expected

    @pytest.mark.parametrize(
        ("sport", "sub_sport", "expected"),
        [
            ("running", "trail", "trail"),
            ("running", "treadmill", "running"),
            ("running", "generic", "running"),
            ("cycling", "mountain", "mountain_bike"),
            ("training", "strength_training", "strength"),
            ("training", "yoga", "yoga"),
            ("fitness_equipment", "indoor_rowing", "rowing"),
        ],
    )
    def test_fit_sub_sports(self, sport, sub_sport, expected):
        """A known FIT (sport, sub_sport) pair refines the sport."""
        assert normalize_sport(sport, sub_sport) == expected

    @pytest.mark.parametrize(
        "value", [None, "", "   ", "pétanque", "generic", "training"]
    )
    def test_unknown_gives_other(self, value):
        """Empty, unknown or generic values give "other"."""
        assert normalize_sport(value) == "other"

    def test_every_code_and_label_round_trips(self):
        """Every code and both labels of every sport normalise to that sport."""
        for code, s in SPORTS.items():
            assert normalize_sport(code) == code
            assert normalize_sport(s.label_en) == code
            assert normalize_sport(s.label_fr) == code


@pytest.mark.unit
class TestValidateSport:
    """validate_sport() — strict variant used when saving a session."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("running", "running"),
            ("Course à pied", "running"),
            ("course", "running"),
            ("VÉLO", "cycling"),
            ("generic", "other"),
            ("Autre", "other"),
        ],
    )
    def test_known_names_give_codes(self, value, expected):
        """Known names are converted to their code."""
        assert validate_sport(value) == expected

    @pytest.mark.parametrize("value", [None, "", "  "])
    def test_no_sport(self, value):
        """No sport is allowed and gives None."""
        assert validate_sport(value) is None

    @pytest.mark.parametrize(
        ("typo", "suggestion"),
        [("runing", "running"), ("cyclng", "cycling"), ("natatoin", "swimming")],
    )
    def test_typo_rejected_with_suggestion(self, typo, suggestion):
        """A typo is rejected and the closest sport is suggested."""
        with pytest.raises(ValueError, match=f"Did you mean '{suggestion}'"):
            validate_sport(typo)

    def test_unknown_rejected_without_suggestion(self):
        """A name far from every sport is rejected, with the list of codes."""
        with pytest.raises(ValueError, match="Unknown sport 'pétanque'.*running"):
            validate_sport("pétanque")


@pytest.mark.unit
class TestGetAndList:
    """get_sport() and list_sports()."""

    def test_get_sport_accepts_any_name(self):
        """get_sport() accepts a label or synonym."""
        assert get_sport("Course à pied").code == "running"

    def test_get_sport_unknown(self):
        """Unknown → the "other" sport."""
        assert get_sport("pétanque").code == "other"

    def test_list_all_other_last(self):
        """All sports, "other" last."""
        sports = list_sports()
        assert len(sports) == len(SPORTS)
        assert sports[-1].code == "other"

    def test_list_by_family(self):
        """Filtering keeps one family."""
        endurance = list_sports("endurance")
        assert endurance
        assert all(s.family == "endurance" for s in endurance)

    def test_unknown_family_raises(self):
        """Unknown family → ValueError."""
        with pytest.raises(ValueError, match="Unknown family"):
            list_sports("aquatic")


@pytest.mark.unit
class TestLabels:
    """Sport labels are available in LABELS_EN / LABELS_FR."""

    def test_sport_keys(self):
        """One sport_<code> key per sport, in both languages."""
        for code, s in SPORTS.items():
            assert LABELS_EN[f"sport_{code}"] == s.label_en
            assert LABELS_FR[f"sport_{code}"] == s.label_fr

    def test_family_keys(self):
        """One sport_family_<code> key per family, in both languages."""
        for code, (en, fr) in FAMILIES.items():
            assert LABELS_EN[f"sport_family_{code}"] == en
            assert LABELS_FR[f"sport_family_{code}"] == fr


def _training_load() -> TrainingLoad:
    trimp = np.array([30.0, 40.0, 20.0])
    atl, ctl = compute_atl(trimp), compute_ctl(trimp)
    return TrainingLoad(
        dates=["2026-01-01", "2026-01-02", "2026-01-03"],
        trimp=trimp,
        atl=atl,
        ctl=ctl,
        tsb=compute_tsb(ctl, atl),
    )


def _sessions(*sports: str) -> list[dict]:
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    trimps = [30.0, 40.0, 20.0]
    return [
        {"date": d, "trimp": t, "duration_min": 45.0, "sport_type": s}
        for d, t, s in zip(dates, trimps, sports, strict=False)
    ]


def _bar_colors(fig) -> list[str]:
    return [to_hex(p.get_facecolor()) for p in fig.axes[0].patches]


@pytest.mark.unit
class TestPlotUsesReferenceList:
    """plot_trimp_history() takes colours and labels from the reference list."""

    def test_non_normalised_name_gets_sport_color(self):
        """A French label stored as-is gets the colour of its sport."""
        fig = plot_trimp_history(_training_load(), sessions=_sessions("Course à pied"))
        assert to_hex(SPORTS["running"].color) in _bar_colors(fig)

    def test_new_sport_has_its_color(self):
        """A sport added in v0.3.4 has its own colour."""
        fig = plot_trimp_history(_training_load(), sessions=_sessions("tennis"))
        assert to_hex(SPORTS["tennis"].color) in _bar_colors(fig)

    def test_unknown_sport_gets_other_color(self):
        """An unknown sport is drawn with the "other" colour."""
        fig = plot_trimp_history(_training_load(), sessions=_sessions("pétanque"))
        assert to_hex(SPORTS["other"].color) in _bar_colors(fig)

    def test_missing_sport_keeps_default_color(self):
        """A session without sport keeps the default TRIMP colour."""
        fig = plot_trimp_history(_training_load(), sessions=_sessions(""))
        assert to_hex(_TRIMP_COLOR) in _bar_colors(fig)

    def test_custom_color_overrides(self):
        """sport_colors still overrides the reference colour."""
        fig = plot_trimp_history(
            _training_load(),
            sessions=_sessions("running"),
            sport_colors={"running": "#000000"},
        )
        assert "#000000" in _bar_colors(fig)

    def test_french_legend(self):
        """With LABELS_FR, the legend shows French sport names."""
        fig = plot_trimp_history(
            _training_load(), sessions=_sessions("running", "cycling"), labels=LABELS_FR
        )
        texts = {t.get_text() for t in fig.axes[0].get_legend().get_texts()}
        assert {"Course à pied", "Vélo"} <= texts

    def test_legend_without_labels_keeps_raw_values(self):
        """Without labels, the legend keeps the stored values (unchanged behaviour)."""
        fig = plot_trimp_history(_training_load(), sessions=_sessions("running"))
        texts = {t.get_text() for t in fig.axes[0].get_legend().get_texts()}
        assert "running" in texts
