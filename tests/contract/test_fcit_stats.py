"""mvp-review task 1.1: the statistics page's fantasy average, penalties saved and red cards, read as the
other columns are (design C1; R2.1, R5.3)."""

from __future__ import annotations

import pytest

from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.fcit_stats import read_stats
from tests.collect_pages import STATS_COLUMNS, stats_page
from tests.roles_data import stats_row

KEEPER = stats_row("Alfa", "P", "Por", 9101, fantasy_average=4.5, penalties_saved=2, red_cards=1)
STRIKER = stats_row("Alfa", "A", "Pc", 9102, average_rating=7.25, fantasy_average=11.75)
UNRATED = stats_row(
    "Beta",
    "D",
    "Dd",
    9103,
    appearances=0,
    rated_appearances=0,
    average_rating=None,
    fantasy_average=None,
    goals=0,
    assists=0,
    yellow_cards=0,
)


def test_the_three_new_columns() -> None:
    facts = read_stats(stats_page([KEEPER, STRIKER, UNRATED]))
    assert facts.problems == []
    read = {player.player_id: player for player in facts.payload.players}
    assert (read[9101].fantasy_average, read[9101].penalties_saved, read[9101].red_cards) == (4.5, 2, 1)
    assert (read[9102].fantasy_average, read[9102].penalties_saved, read[9102].red_cards) == (11.75, 0, 0)
    assert read[9103].fantasy_average is None  # no rating, no fantasy average


def test_a_fantasy_average_below_zero_reads() -> None:
    """A keeper who concedes a lot can average below zero."""
    facts = read_stats(stats_page([KEEPER], cells={9101: {"mfv": "-1,5"}}))
    assert facts.payload.players[0].fantasy_average == -1.5


@pytest.mark.parametrize("key", ["mfv", "rp", "esp"])
def test_a_column_that_changes_meaning_makes_the_page_unreadable(key: str) -> None:
    columns = [
        (column, f"{name}?" if column == key else name, short) for column, name, short in STATS_COLUMNS
    ]
    with pytest.raises(UnreadablePageError, match=key):
        read_stats(stats_page([KEEPER, STRIKER], columns=columns))
