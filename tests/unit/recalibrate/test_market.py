"""A match's score from its keepers' rows (mvp-recalibrate design C7; mvp-review's goals against)."""

from __future__ import annotations

from fantadamus.contracts.types import Role
from fantadamus.domains.calibration import match_score
from fantadamus.domains.review import goals_against
from fantadamus.domains.season.silver import PlayerSeasonRow
from tests.cards_data import source


def _row(player_id: int, club: str, role: Role = "P", conceded: int | None = 9) -> PlayerSeasonRow:
    return PlayerSeasonRow(
        **source("https://example.org/statistiche").model_dump(),
        player_id=player_id,
        name=f"Player {player_id}",
        club=club,
        role=role,
        mantra_role=None,
        appearances=9,
        rated_appearances=9,
        average_rating=6.0,
        goals=0,
        assists=0,
        yellow_cards=0,
        penalties_scored=0,
        penalties_taken=0,
        goals_conceded=conceded if role == "P" else None,
    )


def _read(*rows: PlayerSeasonRow) -> dict[int, PlayerSeasonRow]:
    return {row.player_id: row for row in rows}


def test_goals_against_from_each_clubs_keepers() -> None:
    before = _read(
        _row(1, "alfa"),
        _row(2, "alfa", conceded=0),
        _row(3, "beta"),
        _row(4, "gamma"),
        _row(5, "beta", "D"),
        _row(7, "gamma"),
    )
    after = _read(
        _row(1, "alfa", conceded=10),
        _row(2, "alfa", conceded=1),  # two keepers, a goal each: two against
        _row(3, "beta"),
        _row(4, "gamma", conceded=None),  # his figure is gone: not known,
        _row(7, "gamma", conceded=10),  # whatever the club's other keeper conceded
        _row(5, "beta", "D"),
        _row(6, "delta"),  # new since the read before: not known
    )
    assert goals_against(before, after) == {"alfa": 2, "beta": 0, "gamma": None, "delta": None}
    assert goals_against(None, after) == {}


def test_a_score_from_each_sides_goals_against() -> None:
    against = {"alfa": 1, "beta": 2, "gamma": None}
    assert match_score("alfa", "beta", against, played=True) == (2, 1)  # alfa scored beta's two against
    assert match_score("alfa", "gamma", against, played=True) == "its keepers' goals against aren't known"
    assert match_score("alfa", "delta", against, played=True) == "its keepers' goals against aren't known"
    assert match_score("alfa", "beta", against, played=False) == "no official lineup stored"
