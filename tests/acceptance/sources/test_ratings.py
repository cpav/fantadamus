"""AT-4 of mvp-sources: a round's base rating from the league's rater, recovered from two statistics reads by
hand, or from the ratings page where the reads don't give it; kept in the round's calibration set and counted
as evidence for the rating constants (design C6; R4.1, R4.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fantadamus.domains.calibration import Outcome, SetRow, league_rating
from fantadamus.domains.recalibration import waiting
from fantadamus.domains.season.silver import PlayerSeasonRow
from fantadamus.engine.constants import MINIMUM_SAMPLE
from tests.acceptance.recalibrate.test_sets import _kept, _scored
from tests.cards_data import source
from tests.lineup_harness import a_round, player_id, stats_after_rated
from tests.sources_pages import Rated, ratings_page

pytestmark = pytest.mark.anyio


def _season(rated: int, average: float, **figures: Any) -> PlayerSeasonRow:
    values = {
        "player_id": 1,
        "name": "Alfa Nove",
        "club": "alfa",
        "role": "A",
        "mantra_role": None,
        "appearances": rated,
        "rated_appearances": rated,
        "average_rating": average,
        "fantasy_average": None,
        "goals": 2,
        "assists": 1,
        "yellow_cards": 1,
        "red_cards": 0,
        "penalties_scored": 0,
        "penalties_taken": 0,
        "penalties_saved": None,
        "goals_conceded": None,
    }
    return PlayerSeasonRow(**source("https://example.org/statistiche").model_dump(), **(values | figures))


def test_at4_from_two_reads_by_hand() -> None:
    """Before the round he had 8 rated games at 6.25, 50 points; after it, 9 at 6.28, about 56.5: his rating
    was 6.5, the only half point within the page's rounding. The page's rating isn't needed."""
    assert league_rating(_season(8, 6.25), _season(9, 6.28), page=6.0) == (6.5, "reads")


def test_at4_from_the_page() -> None:
    """Where the reads don't bracket the round, or could give two ratings, the Fantacalcio.it desk's rating on
    the ratings page; with neither, none."""
    assert league_rating(None, _season(9, 6.28), page=6.0) == (6.0, "page")
    assert league_rating(_season(8, 6.25), None, page=6.0) == (6.0, "page")
    assert league_rating(_season(8, 6.25), _season(10, 6.3), page=5.5) == (5.5, "page")  # two games between
    assert league_rating(None, None, page=None) == (None, None)


async def test_at4_kept_in_the_set(tmp_path: Path) -> None:
    """Round 10 played and scored: a starter whose reads give his rating keeps it from them; a bench player
    the statistics page doesn't move, rated 6.0 by the page's Fantacalcio.it desk, keeps the page's."""
    page = ratings_page(
        10, [("Alfa", "Beta", [Rated("DODICI", "A", "C", ("6,00", "6,50", "5,50"), came_on=20)], [])]
    )
    async with a_round(tmp_path, ratings=page) as here:
        await _scored(here, stats=stats_after_rated({"Alfa_Nove": 7.5}))
        rows = {row.player_id: row for row in _kept(here).rows}
    assert (rows[player_id("Alfa", "Nove")].rating, rows[player_id("Alfa", "Nove")].rating_from) == (
        7.5,
        "reads",
    )
    dodici = rows[player_id("Alfa", "Dodici")]
    assert (dodici.rating, dodici.rating_from) == (6.0, "page")


def _row(rating: float | None) -> SetRow:
    outcome = Outcome(started=True, rated=True, scored=False, clean_sheet="an outfield player")
    return SetRow(
        round=10,
        home="alfa",
        away="beta",
        club="alfa",
        player_id=1,
        role="A",
        consensus=0.9,
        p_start=0.9,
        p_rating=0.9,
        p_scores=0.3,
        p_scores_cameo=None,
        p_clean_sheet=None,
        outcome=outcome,
        rating=rating,
        rating_from="reads" if rating is not None else None,
    )


def test_at4_counted_as_evidence() -> None:
    """The rating constants wait for players with the league's rating, counted against their minimum; a set
    stored before ratings were kept counts none."""
    rows = [_row(6.5), _row(7.0), _row(None)]
    ratings = next(wait for wait in waiting(rows) if "VOTE_NOISE" in wait.names)
    assert (ratings.have, ratings.minimum) == (2, MINIMUM_SAMPLE["ratings"])
    assert MINIMUM_SAMPLE["ratings"] == 1500
    assert ratings.needs == "rated players with the league's rating, and cards in each match"
    old = SetRow.model_validate(_row(None).model_dump(exclude={"rating", "rating_from"}))
    assert (old.rating, old.rating_from) == (None, None)
