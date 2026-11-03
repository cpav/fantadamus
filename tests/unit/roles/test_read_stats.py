"""mvp-roles task 2.1: Fantacalcio.it's statistics page read into every player's season so far (design C3;
R1.2, R1.3, R1.6)."""

from __future__ import annotations

from typing import Any

import pytest

from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.fcit_stats import read_stats
from tests.collect_pages import STATS_COLUMNS, stats_page
from tests.roles_data import stats_read, stats_row

NOVE = stats_row(
    "Alfa",
    "A",
    "Pc",
    9001,
    name="Alfa Nove",
    appearances=10,
    average_rating=7.25,
    penalties_scored=1,
    penalties_taken=2,
)


def _as_read(row: dict[str, Any]) -> dict[str, Any]:
    """What the reader gives for a row: the club as its slug, appearances as the rated ones (R1.3)."""
    return row | {"club": row["club"].lower(), "appearances": row["rated_appearances"]}


def test_rows_read() -> None:
    rows = [NOVE, *stats_read()["players"]]
    facts = read_stats(stats_page(rows))
    assert facts.problems == []
    read = [player.model_dump() for player in facts.payload.players]
    assert read == sorted((_as_read(row) for row in rows), key=lambda row: row["player_id"])
    nove = next(player for player in facts.payload.players if player.player_id == 9001)
    assert (nove.mantra_role, nove.appearances, nove.average_rating) == ("Pc", 8, 7.25)  # first Mantra role
    assert (nove.penalties_scored, nove.penalties_taken) == (1, 2)
    unread = {9001: {"mfv": "12,5", "rp": "3", "esp": "2"}}  # fantamedia, penalties saved, red cards
    assert read_stats(stats_page(rows, cells=unread)).payload == facts.payload


def test_no_rating_no_average() -> None:
    unrated = stats_row(
        "Beta",
        "D",
        "Dd",
        9002,
        appearances=0,
        rated_appearances=0,
        average_rating=None,
        goals=0,
        assists=0,
        yellow_cards=0,
    )
    facts = read_stats(stats_page([unrated, NOVE]))
    player = next(player for player in facts.payload.players if player.player_id == 9002)
    assert (player.rated_appearances, player.average_rating) == (0, None)


@pytest.mark.parametrize(
    ("cells", "reason"),
    [
        ({"gol": "x"}, "'x' isn't a number"),
        ({"gs": "3"}, "only a keeper concedes goals"),
        ({"rig": "1-2"}, "'1-2' isn't scored / taken"),
        ({"mv": "6.5"}, "'6.5' isn't a number"),
        ({"ass": None}, "no Assist cell"),
    ],
)
def test_bad_row_left_out(cells: dict[str, str | None], reason: str) -> None:
    rows = [NOVE, *stats_read()["players"]]
    facts = read_stats(stats_page(rows, cells={9001: cells}))
    assert 9001 not in {player.player_id for player in facts.payload.players}
    assert len(facts.payload.players) == len(rows) - 1
    assert len(facts.problems) == 1
    assert facts.problems[0].startswith("Alfa Nove (9001): ")
    assert reason in facts.problems[0]


@pytest.mark.parametrize(
    ("page", "reason"),
    [
        (stats_page([NOVE], title="Calendario Serie A"), "isn't the statistics page"),
        (stats_page([]), "no player rows"),
        (
            stats_page(
                [NOVE], columns=[c if c[0] != "pg" else ("pg", "Presenze", "Pr") for c in STATS_COLUMNS]
            ),
            "the column 'pg' isn't 'Partite a voto'",
        ),
        (stats_page([NOVE], columns=[c for c in STATS_COLUMNS if c[0] != "gs"]), "the column 'gs' isn't"),
        (stats_page([NOVE], cells={9001: {"gol": "x"}}), "no player row could be read"),
        (
            "<html><head><title>Statistiche</title></head><body><p>Nothing</p></body></html>",
            "no statistics table",
        ),
    ],
)
def test_unexpected_layout_unreadable(page: str, reason: str) -> None:
    with pytest.raises(UnreadablePageError, match=reason):
        read_stats(page)
